"""
Currency Service - 실시간 환율 조회 서비스
FastAPI 기반 웹 서버

주요 기능:
- Redis에서 최신 환율 데이터 조회
- 프론트엔드에 실시간 환율 정보 제공
- 다중 통화 동시 조회 지원

API 엔드포인트:
- GET /health: 헬스 체크
- GET /api/v1/currencies/latest: 최신 환율 조회
- GET /api/v1/currencies/multiple: 여러 통화 환율 일괄 조회
- GET /api/v1/currencies/{currency_code}: 통화별 상세 정보
- GET /api/v1/currencies/search: 나라명으로 통화 검색
- DELETE /api/v1/currencies/cache: 환율 캐시 클리어
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

# Prometheus monitoring
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time

from shared.config import init_config, get_config
from shared.database import init_database, get_db_manager
import logging
from shared.logging import set_correlation_id, set_request_id
from shared.models import (
    LatestRatesResponse, CurrencyInfo, 
    CurrencyCode, CountryCode, SuccessResponse, ErrorResponse
)
from shared.exceptions import (
    BaseServiceException, InvalidCurrencyCodeError, 
    InvalidCountryCodeError, get_http_status_code
)
from shared.utils import SecurityUtils

from app.services.currency_provider import CurrencyProvider
from shared.messaging import MessageConsumer

# 로거 초기화
logger = logging.getLogger(__name__)

# 전역 변수
currency_provider: Optional[CurrencyProvider] = None
kafka_consumer = None

# Prometheus 메트릭 정의 (중복 방지를 위한 새 레지스트리 사용)
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, generate_latest

# 새로운 레지스트리 생성 (기본 레지스트리와 분리)
currency_registry = CollectorRegistry()

# 서비스별 메트릭 생성 (독립 레지스트리 사용)
http_requests_total = Counter(
    'currency_http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=currency_registry
)

http_request_duration_seconds = Histogram(
    'currency_http_request_duration_seconds',
    'Time spent processing HTTP requests',
    ['method', 'endpoint'],
    registry=currency_registry
)

currency_requests_total = Counter(
    'currency_requests_total',
    'Total number of currency API requests',
    ['currency_code', 'endpoint'],
    registry=currency_registry
)

active_connections = Gauge(
    'currency_active_database_connections',
    'Number of active database connections',
    ['database_type'],
    registry=currency_registry
)

cache_operations_total = Counter(
    'currency_cache_operations_total',
    'Total cache operations',
    ['operation', 'cache_type'],
    registry=currency_registry
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global currency_provider
    
    try:
        # 설정 가져오기 (이미 초기화됨)
        config = get_config()
        logger.info(f"Currency Service starting, version: {config.service_version}")
        
        # 데이터베이스 초기화
        await init_database()
        logger.info("Database connections initialized")
        
        # 서비스 프로바이더 초기화
        currency_provider = CurrencyProvider()
        
        # Kafka 이벤트 구독 시작
        await start_kafka_consumer()
        
        logger.info("Currency Service started successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start Currency Service: {e}")
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
        logger.info("Currency Service stopped")


# 설정을 미리 초기화하여 CORS 미들웨어에서 사용 가능하게 함
config = init_config("service-currency")
_config_initialized = True

# FastAPI 앱 생성
app = FastAPI(
    title="Currency Service",
    description="실시간 환율 조회 서비스",
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
def get_currency_provider() -> CurrencyProvider:
    """Currency Provider 의존성"""
    if currency_provider is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return currency_provider




# 미들웨어
@app.middleware("http")
async def logging_middleware(request, call_next):
    """로깅 및 메트릭 미들웨어"""
    # 상관관계 ID 설정
    correlation_id = request.headers.get("X-Correlation-ID") or SecurityUtils.generate_correlation_id()
    set_correlation_id(correlation_id)

    # 요청 ID 설정 (Lambda에서는 AWS Request ID 사용)
    request_id = request.headers.get("X-Request-ID") or SecurityUtils.generate_uuid()
    set_request_id(request_id)

    # 메트릭을 위한 시작 시간 기록
    start_time = time.time()
    endpoint = request.url.path
    method = request.method

    logger.info(f"Request started: {method} {request.url}")

    try:
        response = await call_next(request)

        # HTTP 요청 메트릭 업데이트
        status = str(response.status_code)
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()

        # 응답 시간 메트릭 업데이트
        duration = time.time() - start_time
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

        logger.info(f"Request completed: {method} {request.url} - {response.status_code}")

        # 응답 헤더에 상관관계 ID 추가
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    except Exception as e:
        # 에러 상태도 메트릭에 기록
        http_requests_total.labels(method=method, endpoint=endpoint, status="500").inc()
        duration = time.time() - start_time
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

        logger.error(f"Request failed: {method} {request.url} - {e}")
        raise


# 예외 처리기
@app.exception_handler(BaseServiceException)
async def service_exception_handler(request, exc: BaseServiceException):
    """서비스 예외 처리기"""
    logger.error(f"Service exception: {exc.error_code} - {exc.message}")
    
    from datetime import datetime
    return JSONResponse(
        status_code=get_http_status_code(exc),
        content={
            "success": False,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "version": "v1",
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


# Prometheus 메트릭 엔드포인트
@app.get("/metrics")
async def get_metrics():
    """Prometheus 메트릭 엔드포인트"""
    return Response(generate_latest(currency_registry), media_type=CONTENT_TYPE_LATEST)

# API 엔드포인트들
@app.get("/health")
async def health_check():
    """헬스 체크 - 데이터베이스 연결 상태 포함"""
    try:
        health_status = {
            "status": "healthy",
            "service": "service-currency",
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
            if currency_provider:
                # MySQL 연결 테스트
                test_query = "SELECT 1 as test"
                await currency_provider.mysql_helper.execute_query(test_query)
                health_status["checks"]["database"] = "healthy"
                
                # Redis 연결 테스트
                await currency_provider.redis_helper.ping()
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
                "service": "service-currency",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )


@app.get("/api/v1/currencies/latest", response_model=SuccessResponse)
async def get_latest_rates(
    symbols: Optional[str] = Query(None, description="쉼표로 구분된 통화 코드"),
    base: str = Query("KRW", description="기준 통화 코드"),
    provider: CurrencyProvider = Depends(get_currency_provider)
):
    """
    최신 환율 정보 조회
    
    - **symbols**: 조회할 통화 코드들 (예: USD,JPY,EUR,GBP,CNY,AUD,CAD,CHF,SGD,HKD)
    - **base**: 기준 통화 코드 (기본값: KRW)
    """
    try:
        # 파라미터 파싱
        currency_codes = []
        if symbols:
            currency_codes = [code.strip().upper() for code in symbols.split(",")]
            # 통화 코드 검증
            for code in currency_codes:
                if code not in [c.value for c in CurrencyCode]:
                    raise InvalidCurrencyCodeError(code)
        
        # 기준 통화 검증
        if base.upper() not in [c.value for c in CurrencyCode]:
            raise InvalidCurrencyCodeError(base)
        
        # 환율 데이터 조회
        rates_data = await provider.get_latest_rates(currency_codes, base.upper())

        # 비즈니스 메트릭 업데이트
        for code in currency_codes:
            currency_requests_total.labels(currency_code=code, endpoint="/latest").inc()

        # 프론트엔드 호환성을 위해 기존 형태로 응답
        return SuccessResponse(data=rates_data)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest rates: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve exchange rates")




@app.get("/api/v1/currencies/search", response_model=SuccessResponse)
async def search_currencies_by_country(
    country: str = Query(..., description="나라명 (예: 미국, 일본, 유럽)"),
    provider: CurrencyProvider = Depends(get_currency_provider)
):
    """
    나라명으로 통화 검색
    
    - **country**: 나라명 (예: 미국, 일본, 유럽, 중국)
    """
    try:
        # 나라명 매핑
        country_mapping = {
            "미국": "USD",
            "일본": "JPY", 
            "유럽": "EUR",
            "중국": "CNY",
            "영국": "GBP",
            "호주": "AUD",
            "캐나다": "CAD",
            "스위스": "CHF",
            "싱가포르": "SGD",
            "홍콩": "HKD",
            "태국": "THB",
            "베트남": "VND",
            "인도": "INR",
            "브라질": "BRL",
            "러시아": "RUB",
            "멕시코": "MXN",
            "남아프리카": "ZAR",
            "터키": "TRY",
            "폴란드": "PLN",
            "체코": "CZK",
            "헝가리": "HUF",
            "노르웨이": "NOK",
            "스웨덴": "SEK",
            "덴마크": "DKK"
        }
        
        # 나라명을 통화 코드로 변환
        currency_code = country_mapping.get(country)
        if not currency_code:
            raise HTTPException(status_code=404, detail=f"Country '{country}' not found")
        
        # 환율 데이터 조회
        rates_data = await provider.get_latest_rates([currency_code], "KRW")
        
        if not rates_data:
            raise HTTPException(status_code=404, detail=f"Exchange rate for {country} not found")
        
        return SuccessResponse(data={
            "country": country,
            "currency_code": currency_code,
            "rate": rates_data[0]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search currency for {country}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search currency")


@app.get("/api/v1/currencies/{currency_code}", response_model=SuccessResponse)
async def get_currency_info(
    currency_code: str,
    currency_provider: CurrencyProvider = Depends(get_currency_provider)
):
    """
    통화별 상세 정보 조회

    - **currency_code**: 3자리 통화 코드 (예: USD)
    """
    try:
        # 통화 코드 검증
        currency_code = currency_code.upper()

        # 일반 통화 정보 조회
        if currency_code not in [c.value for c in CurrencyCode]:
            raise InvalidCurrencyCodeError(currency_code)

        # 통화 정보 조회
        currency_info = await currency_provider.get_currency_info(currency_code)

        return SuccessResponse(data=currency_info)

    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get info for {currency_code}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve information")


@app.get("/api/v1/currencies/multiple", response_model=SuccessResponse)
async def get_multiple_currencies(
    symbols: str = Query(..., description="쉼표로 구분된 통화 코드들"),
    provider: CurrencyProvider = Depends(get_currency_provider)
):
    """
    여러 통화의 환율을 한 번에 조회 (성능 최적화)
    
    - **symbols**: 조회할 통화 코드들 (예: USD,JPY,EUR,GBP,CNY,AUD,CAD,CHF,SGD,HKD)
    """
    try:
        # 파라미터 파싱
        currency_codes = [code.strip().upper() for code in symbols.split(",")]
        
        # 통화 코드 검증
        for code in currency_codes:
            if code not in [c.value for c in CurrencyCode]:
                raise InvalidCurrencyCodeError(code)
        
        # 환율 데이터 조회
        rates_data = await provider.get_multiple_rates(currency_codes)
        
        return SuccessResponse(data=rates_data)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get multiple currencies: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve exchange rates")


@app.delete("/api/v1/currencies/cache")
async def clear_currency_cache(
    currency_code: Optional[str] = Query(None, description="특정 통화 코드 (없으면 전체 캐시 클리어)"),
    provider: CurrencyProvider = Depends(get_currency_provider)
):
    """
    환율 캐시 클리어
    
    - **currency_code**: 특정 통화 코드 (선택사항)
    """
    try:
        await provider.clear_cache(currency_code)
        
        message = f"Cache cleared for {currency_code}" if currency_code else "All currency cache cleared"
        return SuccessResponse(data={"message": message})
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


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
        
        kafka_consumer = MessageConsumer(topics, "service-currency")
        await kafka_consumer.initialize()
        
        # 백그라운드에서 메시지 소비 시작
        import asyncio
        asyncio.create_task(kafka_consumer.consume_messages(handle_kafka_message))
        
        logger.info("Kafka consumer started for Currency Service")
        
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
        elif topic == "exchange_rate_updated":
            await handle_exchange_rate_updated(message)
        elif topic == "data_processing_completed":
            await handle_data_processing_completed(message)
        elif topic == "cache_invalidation":
            await handle_cache_invalidation(message)
        else:
            logger.warning(f"Unknown topic: {topic}")
            
    except Exception as e:
        logger.error(f"Failed to handle Kafka message from {topic}: {e}")


async def handle_new_data_received(message: dict):
    """새로운 데이터 수신 이벤트 처리"""
    source = message.get("source")
    data_count = message.get("data_count")
    logger.info("New data received event processed", 
                source=source,
                data_count=data_count)
    
    # 새로운 환율 데이터가 수신되었을 때 Currency Service 준비
    try:
        if currency_provider:
            # 전체 환율 캐시 새로고침 준비
            logger.info("Preparing for new exchange rate data refresh")
    except Exception as e:
        logger.warning(f"Failed to prepare for new data: {e}")


async def handle_exchange_rate_updated(message: dict):
    """환율 업데이트 이벤트 처리"""
    currency_code = message.get("currency_code")
    rate = message.get("deal_base_rate")
    logger.info("Exchange rate updated event processed", 
                currency=currency_code,
                rate=rate)
    
    # 특정 통화의 환율이 업데이트되었을 때 해당 통화의 캐시 무효화
    try:
        if currency_provider:
            # 해당 통화의 캐시 무효화
            await currency_provider.clear_cache(currency_code)
            logger.info(f"Cache cleared for updated currency: {currency_code}")
            
            # 새로운 환율 데이터로 캐시 갱신
            await currency_provider.refresh_currency_cache(currency_code)
            logger.info(f"Cache refreshed for currency: {currency_code}")
    except Exception as e:
        logger.warning(f"Failed to refresh cache for {currency_code}: {e}")


async def handle_data_processing_completed(message: dict):
    """데이터 처리 완료 이벤트 처리"""
    source = message.get("source")
    total_processed = message.get("total_processed")
    logger.info("Data processing completed event processed",
                source=source,
                total_processed=total_processed)
    
    # 데이터 처리 완료 후 전체 환율 캐시 갱신
    try:
        if currency_provider:
            # 모든 환율 캐시 새로고침
            await currency_provider.refresh_all_currency_cache()
            logger.info("All currency cache refreshed due to data processing completion")
    except Exception as e:
        logger.warning(f"Failed to refresh all currency cache: {e}")


async def handle_cache_invalidation(message: dict):
    """캐시 무효화 이벤트 처리"""
    cache_keys = message.get("cache_keys", [])
    invalidation_type = message.get("invalidation_type")
    logger.info("Cache invalidation event processed",
                keys=cache_keys,
                type=invalidation_type)
    
    # Currency Service의 캐시 무효화 처리
    if currency_provider and cache_keys:
        try:
            for key in cache_keys:
                if key.startswith("exchange_rate:"):
                    currency_code = key.split(":")[1]
                    # 해당 통화의 캐시 무효화
                    await currency_provider.clear_cache(currency_code)
                    logger.info(f"Cache cleared for currency: {currency_code}")
            
            # 전체 캐시 무효화인 경우
            if invalidation_type == "exchange_rate_update":
                await currency_provider.clear_all_cache()
                logger.info("All currency cache cleared")
                
        except Exception as e:
            logger.warning(f"Failed to handle cache invalidation: {e}")


# AWS Lambda 핸들러 (배포 시 사용)
def lambda_handler(event, context):
    """
    AWS Lambda 핸들러
    
    AWS 배포 시 수정 필요사항:
    1. Mangum 설치: pip install mangum
    2. 아래 코드 주석 해제 및 수정
    3. Lambda 환경변수 설정
    4. VPC 설정 (Aurora, ElastiCache 접근용)
    5. IAM 역할 권한 설정
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
    port = int(os.getenv("PORT", "8000"))  # Currency Service는 8000 포트
    
    logger.info(f"Starting Currency Service on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,  # 개발 모드에서만 사용
        log_level="info"
    )