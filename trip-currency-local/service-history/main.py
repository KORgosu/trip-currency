"""
History Service - 환율 이력 분석 및 차트 데이터 서비스
FastAPI 기반 웹 서버

주요 기능:
- MySQL에 저장된 환율 데이터 분석
- 하루동안의 환율 변동을 1시간 단위로 그래프화
- 1시간마다 분석 작업 실행
- 프론트엔드에 차트 데이터 제공

API 엔드포인트:
- GET /health: 헬스 체크
- GET /api/v1/history/{currency_code}: 통화별 환율 이력 조회
- GET /api/v1/history/{currency_code}/chart: 차트 데이터 조회
- GET /api/v1/history/{currency_code}/analysis: 환율 분석 데이터 조회
"""
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

# 상위 디렉토리의 shared 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn
from typing import List, Optional
import time

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from shared.config import init_config, get_config
from shared.database import init_database, get_db_manager
import logging
from shared.logging import set_correlation_id, set_request_id
from shared.models import (
    HistoryResponse, CurrencyCode, HistoryPeriod, 
    SuccessResponse, ErrorResponse
)
from shared.exceptions import (
    BaseServiceException, InvalidCurrencyCodeError, 
    InvalidPeriodError, get_http_status_code
)
from shared.utils import SecurityUtils, ValidationUtils

from app.services.history_provider import HistoryProvider
from app.services.analysis_provider import AnalysisProvider
from shared.messaging import MessageConsumer

# 로거 초기화
logger = logging.getLogger(__name__)

# Prometheus 메트릭 정의 (중복 방지를 위한 새 레지스트리 사용)
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, generate_latest

# 새로운 레지스트리 생성 (기본 레지스트리와 분리)
history_registry = CollectorRegistry()

# 서비스별 메트릭 생성 (독립 레지스트리 사용)
http_requests_total = Counter('history_http_requests_total', 'Total number of HTTP requests', ['method', 'endpoint', 'status'], registry=history_registry)
http_request_duration_seconds = Histogram('history_http_request_duration_seconds', 'Time spent processing HTTP requests', ['method', 'endpoint'], registry=history_registry)
history_requests_total = Counter('history_requests_total', 'Total number of history API requests', ['currency_code', 'endpoint'], registry=history_registry)
exchange_rate_queries_total = Counter('history_exchange_rate_queries_total', 'Total number of exchange rate queries', ['target', 'base', 'period'], registry=history_registry)
analysis_operations_total = Counter('history_analysis_operations_total', 'Total number of analysis operations', ['operation', 'currency'], registry=history_registry)
kafka_messages_processed_total = Counter('history_kafka_messages_processed_total', 'Total number of Kafka messages processed', ['topic', 'status'], registry=history_registry)
mysql_connections_active = Gauge('history_mysql_connections_active', 'Number of active MySQL connections', registry=history_registry)

# 전역 변수
history_provider: Optional[HistoryProvider] = None
analysis_provider: Optional[AnalysisProvider] = None
kafka_consumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global history_provider, analysis_provider
    
    try:
        # 설정 초기화
        config = init_config("service-history")
        logger.info(f"History Service starting, version: {config.service_version}")
        
        # 데이터베이스 초기화 (선택적)
        try:
            await init_database()
            logger.info("Database connections initialized")
        except Exception as db_error:
            logger.warning(f"Database initialization failed, using mock data: {db_error}")
            # Mock 모드로 계속 진행
        
        # 서비스 프로바이더 초기화
        history_provider = HistoryProvider()
        analysis_provider = AnalysisProvider()
        
        # Kafka 이벤트 구독 시작
        await start_kafka_consumer()
        
        logger.info("History Service started successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start History Service: {e}")
        raise
    finally:
        # 정리 작업
        await stop_kafka_consumer()
        try:
            db_manager = get_db_manager()
            await db_manager.close()
        except RuntimeError:
            # 데이터베이스가 초기화되지 않은 경우 무시
            pass
        logger.info("History Service stopped")


# 설정을 미리 초기화하여 CORS 미들웨어에서 사용 가능하게 함
config = init_config("service-history")

# FastAPI 앱 생성
app = FastAPI(
    title="History Service",
    description="환율 이력 분석 및 차트 데이터 서비스",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
if config and config.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# 의존성 함수들
def get_history_provider() -> HistoryProvider:
    """History Provider 의존성"""
    if history_provider is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return history_provider


def get_analysis_provider() -> AnalysisProvider:
    """Analysis Provider 의존성"""
    if analysis_provider is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return analysis_provider


# 미들웨어
@app.middleware("http")
async def logging_middleware(request, call_next):
    """로깅 및 메트릭 미들웨어"""
    # 상관관계 ID 설정
    correlation_id = request.headers.get("X-Correlation-ID") or SecurityUtils.generate_correlation_id()
    set_correlation_id(correlation_id)

    # 요청 ID 설정
    request_id = request.headers.get("X-Request-ID") or SecurityUtils.generate_uuid()
    set_request_id(request_id)

    logger.info(f"Request started: {request.method} {request.url}")

    # 메트릭 수집 시작
    start_time = time.time()
    endpoint = str(request.url.path)
    method = request.method

    try:
        response = await call_next(request)

        # 응답 시간 측정 및 메트릭 업데이트
        duration = time.time() - start_time
        status_code = str(response.status_code)

        http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

        logger.info(f"Request completed: {request.method} {request.url} - {response.status_code}")

        # 응답 헤더에 상관관계 ID 추가
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    except Exception as e:
        # 오류 메트릭 업데이트
        duration = time.time() - start_time
        http_requests_total.labels(method=method, endpoint=endpoint, status="500").inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

        logger.error(f"Request failed: {request.method} {request.url} - {e}")
        raise


# 예외 처리기
@app.exception_handler(BaseServiceException)
async def service_exception_handler(request, exc: BaseServiceException):
    """서비스 예외 처리기"""
    logger.error(f"Service exception: {exc.error_code} - {exc.message}")
    
    error_response = ErrorResponse(error=exc.to_dict())
    return JSONResponse(
        status_code=get_http_status_code(exc),
        content={
            "success": False,
            "timestamp": error_response.timestamp.isoformat() + 'Z',
            "version": error_response.version,
            "error": exc.to_dict()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """일반 예외 처리기"""
    logger.error(f"Unexpected error occurred: {exc}")
    
    from datetime import datetime
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "version": "v1",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )


# API 엔드포인트들
@app.get("/metrics")
async def get_metrics():
    """Prometheus 메트릭 엔드포인트"""
    return Response(generate_latest(history_registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    """헬스 체크 - 데이터베이스 연결 상태 포함"""
    try:
        health_status = {
            "status": "healthy",
            "service": "service-history",
            "version": get_config().service_version,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "checks": {
                "database": "unknown",
                "redis": "unknown",
                "kafka": "unknown"
            }
        }
        
        # 데이터베이스 연결 상태 확인
        try:
            if history_provider:
                # MySQL 연결 테스트
                test_query = "SELECT 1 as test"
                await history_provider.mysql_helper.execute_query(test_query)
                health_status["checks"]["database"] = "healthy"
                
                # Redis 연결 테스트
                await history_provider.redis_helper.ping()
                health_status["checks"]["redis"] = "healthy"
            else:
                health_status["checks"]["database"] = "unavailable"
                health_status["checks"]["redis"] = "unavailable"
        except Exception as e:
            logger.warning(f"Database/Redis health check failed: {e}")
            health_status["checks"]["database"] = "unhealthy"
            health_status["checks"]["redis"] = "unhealthy"
            health_status["status"] = "degraded"
        
        # Kafka 연결 상태 확인
        try:
            if kafka_consumer:
                health_status["checks"]["kafka"] = "healthy"
            else:
                health_status["checks"]["kafka"] = "unavailable"
        except Exception as e:
            logger.warning(f"Kafka health check failed: {e}")
            health_status["checks"]["kafka"] = "unhealthy"
        
        # 전체 상태 결정
        if health_status["checks"]["database"] == "unhealthy" or health_status["checks"]["redis"] == "unhealthy":
            health_status["status"] = "unhealthy"
        
        return SuccessResponse(data=health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "status": "unhealthy",
                "service": "service-history",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )


@app.get("/api/v1/history", response_model=SuccessResponse)
async def get_exchange_rate_history(
    period: str = Query("1d", description="조회 기간 (1d, 1w, 1m, 6m)"),
    target: str = Query(..., description="대상 통화 코드"),
    base: str = Query("KRW", description="기준 통화 코드"),
    interval: str = Query("hourly", description="데이터 간격 (daily, hourly)"),
    provider: HistoryProvider = Depends(get_history_provider)
):
    """
    환율 이력 조회
    
    - **period**: 조회 기간 (1d, 1w, 1m, 6m)
    - **target**: 대상 통화 코드 (USD, JPY 등)
    - **base**: 기준 통화 코드 (기본값: KRW)
    - **interval**: 데이터 간격 (daily, hourly)
    """
    try:
        # 파라미터 검증
        valid_periods = ["1d"] + [p.value for p in HistoryPeriod]
        if period not in valid_periods:
            raise InvalidPeriodError(period, valid_periods)
        
        # 통화 코드 검증 및 정규화
        if not target:
            raise HTTPException(status_code=400, detail="대상 통화 코드가 제공되지 않았습니다")
        if not base:
            raise HTTPException(status_code=400, detail="기준 통화 코드가 제공되지 않았습니다")
        
        target = target.upper()
        base = base.upper()
        
        # 유효한 통화 코드인지 확인
        valid_codes = ['USD', 'JPY', 'EUR', 'CNY', 'GBP', 'AUD', 'CAD', 'CHF', 'SGD', 'HKD', 'THB', 'VND', 'INR', 'BRL', 'RUB', 'MXN', 'ZAR', 'TRY', 'PLN', 'CZK', 'HUF', 'NOK', 'SEK', 'DKK', 'KRW']
        if target not in valid_codes:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 대상 통화 코드: {target}")
        if base not in valid_codes:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 기준 통화 코드: {base}")
        
        if interval not in ["daily", "hourly"]:
            raise InvalidPeriodError(interval, ["daily", "hourly"])
        
        # 환율 이력 데이터 조회
        history_data = await provider.get_exchange_rate_history(
            period=period,
            target_currency=target,
            base_currency=base,
            interval=interval
        )

        # 메트릭 업데이트
        history_requests_total.labels(currency_code=target, endpoint="history").inc()
        exchange_rate_queries_total.labels(target=target, base=base, period=period).inc()

        return SuccessResponse(data=history_data)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get exchange rate history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve exchange rate history")


@app.get("/api/v1/history/stats", response_model=SuccessResponse)
async def get_exchange_rate_stats(
    target: str = Query(..., description="대상 통화 코드"),
    period: str = Query("6m", description="분석 기간"),
    base: str = Query("KRW", description="기준 통화 코드"),
    provider: AnalysisProvider = Depends(get_analysis_provider)
):
    """
    환율 통계 분석
    
    - **target**: 대상 통화 코드
    - **period**: 분석 기간
    - **base**: 기준 통화 코드
    """
    try:
        # 파라미터 검증
        target = ValidationUtils.validate_currency_code(target)
        base = ValidationUtils.validate_currency_code(base)
        
        # 통계 분석 데이터 조회
        stats_data = await provider.get_exchange_rate_statistics(
            target_currency=target,
            base_currency=base,
            period=period
        )

        # 메트릭 업데이트
        history_requests_total.labels(currency_code=target, endpoint="stats").inc()
        analysis_operations_total.labels(operation="statistics", currency=target).inc()

        return SuccessResponse(data=stats_data)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get exchange rate stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve exchange rate statistics")


@app.get("/api/v1/history/compare", response_model=SuccessResponse)
async def compare_currencies(
    targets: str = Query(..., description="쉼표로 구분된 통화 코드들"),
    period: str = Query("1m", description="비교 기간"),
    base: str = Query("KRW", description="기준 통화 코드"),
    provider: AnalysisProvider = Depends(get_analysis_provider)
):
    """
    환율 비교 분석
    
    - **targets**: 쉼표로 구분된 통화 코드들 (예: USD,JPY,EUR,GBP,CNY,AUD,CAD,CHF,SGD,HKD)
    - **period**: 비교 기간
    - **base**: 기준 통화 코드
    """
    try:
        # 파라미터 파싱 및 검증
        currency_codes = [code.strip().upper() for code in targets.split(",")]
        
        for code in currency_codes:
            ValidationUtils.validate_currency_code(code)
        
        base = ValidationUtils.validate_currency_code(base)
        
        if len(currency_codes) > 10:  # 최대 10개 통화까지 비교
            raise InvalidPeriodError("Too many currencies", "Maximum 10 currencies allowed")
        
        # 통화 비교 분석
        comparison_data = await provider.compare_currencies(
            currency_codes=currency_codes,
            base_currency=base,
            period=period
        )
        
        return SuccessResponse(data=comparison_data)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare currencies: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare currencies")


@app.get("/api/v1/history/forecast/{currency_code}", response_model=SuccessResponse)
async def get_exchange_rate_forecast(
    currency_code: str,
    days: int = Query(7, ge=1, le=30, description="예측 일수"),
    base: str = Query("KRW", description="기준 통화 코드"),
    provider: AnalysisProvider = Depends(get_analysis_provider)
):
    """
    환율 예측 (간단한 트렌드 기반)
    
    - **currency_code**: 대상 통화 코드
    - **days**: 예측 일수 (1-30일)
    - **base**: 기준 통화 코드
    """
    try:
        # 파라미터 검증
        currency_code = ValidationUtils.validate_currency_code(currency_code)
        base = ValidationUtils.validate_currency_code(base)
        
        # 환율 예측
        forecast_data = await provider.get_exchange_rate_forecast(
            target_currency=currency_code,
            base_currency=base,
            forecast_days=days
        )
        
        return SuccessResponse(data=forecast_data)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get exchange rate forecast: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate exchange rate forecast")


# Kafka 이벤트 처리 함수들
async def start_kafka_consumer():
    """Kafka 컨슈머 시작"""
    global kafka_consumer
    
    try:
        # 구독할 토픽들
        topics = [
            "new_data_received",
            "exchange_rate_updated", 
            "data_processing_completed",
            "cache_invalidation"
        ]
        
        kafka_consumer = MessageConsumer(topics, "service-history")
        await kafka_consumer.initialize()
        
        # 백그라운드에서 메시지 소비 시작
        import asyncio
        asyncio.create_task(kafka_consumer.consume_messages(handle_kafka_message))
        
        logger.info("Kafka consumer started for History Service")
        
    except Exception as e:
        logger.warning(f"Failed to start Kafka consumer: {e}")


async def stop_kafka_consumer():
    """Kafka 컨슈머 중지"""
    global kafka_consumer
    
    if kafka_consumer:
        try:
            await kafka_consumer.close()
            logger.info("Kafka consumer stopped")
        except Exception as e:
            logger.warning(f"Failed to stop Kafka consumer: {e}")


async def handle_kafka_message(topic: str, message: dict):
    """Kafka 메시지 처리"""
    try:
        logger.info(f"Received Kafka message from topic: {topic}")

        if topic == "new_data_received":
            await handle_new_data_received(message)
            kafka_messages_processed_total.labels(topic=topic, status="success").inc()
        elif topic == "exchange_rate_updated":
            await handle_exchange_rate_updated(message)
            kafka_messages_processed_total.labels(topic=topic, status="success").inc()
        elif topic == "data_processing_completed":
            await handle_data_processing_completed(message)
            kafka_messages_processed_total.labels(topic=topic, status="success").inc()
        elif topic == "cache_invalidation":
            await handle_cache_invalidation(message)
            kafka_messages_processed_total.labels(topic=topic, status="success").inc()
        else:
            logger.warning(f"Unknown topic: {topic}")
            kafka_messages_processed_total.labels(topic=topic, status="unknown").inc()

    except Exception as e:
        logger.error(f"Failed to handle Kafka message from {topic}: {e}")
        kafka_messages_processed_total.labels(topic=topic, status="error").inc()


async def handle_new_data_received(message: dict):
    """새로운 데이터 수신 이벤트 처리"""
    source = message.get("source")
    data_count = message.get("data_count")
    logger.info("New data received event processed", 
                source=source,
                data_count=data_count)
    
    # 새로운 환율 데이터가 수신되었을 때 이력 분석 갱신
    try:
        if analysis_provider:
            # 분석 캐시 무효화
            await analysis_provider.clear_analysis_cache()
            logger.info("Analysis cache cleared due to new data")
    except Exception as e:
        logger.warning(f"Failed to clear analysis cache: {e}")


async def handle_exchange_rate_updated(message: dict):
    """환율 업데이트 이벤트 처리"""
    currency_code = message.get("currency_code")
    rate = message.get("deal_base_rate")
    logger.info("Exchange rate updated event processed", 
                currency=currency_code,
                rate=rate)
    
    # 특정 통화의 환율이 업데이트되었을 때 해당 통화의 이력 데이터 갱신
    try:
        if history_provider:
            # 해당 통화의 이력 캐시 무효화
            await history_provider.clear_currency_history_cache(currency_code)
            logger.info(f"History cache cleared for currency: {currency_code}")
    except Exception as e:
        logger.warning(f"Failed to clear history cache for {currency_code}: {e}")


async def handle_data_processing_completed(message: dict):
    """데이터 처리 완료 이벤트 처리"""
    source = message.get("source")
    total_processed = message.get("total_processed")
    logger.info("Data processing completed event processed",
                source=source,
                total_processed=total_processed)
    
    # 데이터 처리 완료 후 통계 분석 갱신
    try:
        if analysis_provider:
            # 전체 통계 캐시 무효화
            await analysis_provider.clear_all_statistics_cache()
            logger.info("All statistics cache cleared due to data processing completion")
    except Exception as e:
        logger.warning(f"Failed to clear statistics cache: {e}")


async def handle_cache_invalidation(message: dict):
    """캐시 무효화 이벤트 처리"""
    cache_keys = message.get("cache_keys", [])
    invalidation_type = message.get("invalidation_type")
    logger.info("Cache invalidation event processed",
                keys=cache_keys,
                type=invalidation_type)
    
    # 캐시 무효화 이벤트에 따른 이력 서비스 캐시 처리
    try:
        if history_provider and analysis_provider:
            for key in cache_keys:
                if key.startswith("exchange_rate:"):
                    currency_code = key.split(":")[1]
                    # 해당 통화의 이력 및 분석 캐시 무효화
                    await history_provider.clear_currency_history_cache(currency_code)
                    await analysis_provider.clear_currency_statistics_cache(currency_code)
                    logger.info(f"Cleared history and statistics cache for currency: {currency_code}")
            
            # 전체 캐시 무효화인 경우
            if invalidation_type == "exchange_rate_update":
                await history_provider.clear_all_history_cache()
                await analysis_provider.clear_all_statistics_cache()
                logger.info("Cleared all history and statistics cache")
                
    except Exception as e:
        logger.warning(f"Failed to handle cache invalidation: {e}")


# AWS Lambda 핸들러 (배포 시 사용)
def lambda_handler(event, context):
    """
    AWS Lambda 핸들러
    
    AWS 배포 시 수정 필요사항:
    1. Mangum 설치: pip install mangum
    2. Aurora 클러스터 접근 권한 설정
    3. VPC 설정 (Aurora, Redis 접근용)
    4. Parameter Store에서 DB 비밀번호 조회 로직 추가
    """
    # TODO: AWS 배포 시 아래 코드 활성화
    # from mangum import Mangum
    # handler = Mangum(app, lifespan="off")
    # return handler(event, context)
    pass


# 로컬 개발 서버 실행
if __name__ == "__main__":
    # 환경 변수에서 설정 로드
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))  # History Service는 8000 포트
    
    logger.info(f"Starting History Service on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,  # 개발 모드에서만 사용
        log_level="info"
    )