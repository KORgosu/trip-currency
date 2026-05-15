"""
Ranking Service - 나라 검색 랭킹 서비스
FastAPI 기반 웹 서버

주요 기능:
- 사용자의 나라 검색 클릭수 기반 랭킹 관리
- 1분마다 랭킹 갱신
- 한국시간 0시 기준으로 모든 클릭수 초기화
- MongoDB 사용 (나라이름 : 클릭수)
- 클릭수가 많은 나라부터 순서대로 출력

API 엔드포인트:
- GET /health: 헬스 체크
- GET /api/v1/rankings: 랭킹 조회
- POST /api/v1/rankings/click: 나라 클릭 기록
- GET /api/v1/rankings/reset: 클릭수 초기화 (관리자용)
"""
import os
import sys
import time
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

# 상위 디렉토리의 shared 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn
from typing import List, Optional, Dict, Any

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from shared.config import init_config, get_config
from shared.database import init_database, get_db_manager
import logging
from shared.logging import set_correlation_id, set_request_id
from shared.models import (
    UserSelection, RankingResponse, CountryStats, 
    RankingPeriod, CountryCode, SuccessResponse, ErrorResponse
)
from shared.exceptions import (
    BaseServiceException, InvalidCountryCodeError, 
    InvalidPeriodError, RateLimitExceededError, get_http_status_code
)
from shared.utils import SecurityUtils, ValidationUtils

from app.services.selection_recorder import SelectionRecorder
from app.services.ranking_provider import RankingProvider
from app.services.mongodb_service import MongoDBService, get_mongodb_service
from app.services.scheduler_service import RankingScheduler, get_ranking_scheduler
from shared.database import DynamoDBHelper, RedisHelper
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

# 로거 초기화
logger = logging.getLogger(__name__)

# Prometheus 메트릭 정의 (중복 방지를 위한 새 레지스트리 사용)
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, generate_latest

# 새로운 레지스트리 생성 (기본 레지스트리와 분리)
ranking_registry = CollectorRegistry()

# 서비스별 메트릭 생성 (독립 레지스트리 사용)
http_requests_total = Counter('ranking_http_requests_total', 'Total number of HTTP requests', ['method', 'endpoint', 'status'], registry=ranking_registry)
http_request_duration_seconds = Histogram('ranking_http_request_duration_seconds', 'Time spent processing HTTP requests', ['method', 'endpoint'], registry=ranking_registry)
ranking_requests_total = Counter('ranking_requests_total', 'Total number of ranking API requests', ['country_code', 'endpoint'], registry=ranking_registry)
country_clicks_total = Counter('ranking_country_clicks_total', 'Total number of country clicks recorded', ['country_code'], registry=ranking_registry)
daily_reset_operations_total = Counter('ranking_daily_reset_operations_total', 'Total number of daily reset operations', registry=ranking_registry)
scheduler_operations_total = Counter('ranking_scheduler_operations_total', 'Total number of scheduler operations', ['operation', 'status'], registry=ranking_registry)
mongodb_connections_active = Gauge('ranking_mongodb_connections_active', 'Number of active MongoDB connections', registry=ranking_registry)

# 전역 변수
selection_recorder: Optional[SelectionRecorder] = None
ranking_provider: Optional[RankingProvider] = None
mongodb_service: Optional[MongoDBService] = None
ranking_scheduler: Optional[RankingScheduler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global selection_recorder, ranking_provider, mongodb_service, ranking_scheduler
    
    try:
        # 설정 가져오기 (이미 초기화됨)
        config = get_config()
        logger.info(f"Ranking Service starting - version: {config.service_version}")
        
        # 데이터베이스 초기화
        await init_database()
        logger.info("Database connections initialized")
        
        # 서비스 프로바이더 초기화
        selection_recorder = SelectionRecorder()
        ranking_provider = RankingProvider()
        mongodb_service = MongoDBService()
        ranking_scheduler = RankingScheduler()
        
        # 서비스 초기화
        await selection_recorder.initialize()
        await ranking_provider.initialize()
        await mongodb_service.connect()
        
        # 스케줄러 시작 (한국시간 00시 초기화)
        asyncio.create_task(ranking_scheduler.start_daily_reset_scheduler())
        logger.info("Daily reset scheduler started")
        
        logger.info("Ranking Service started successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start Ranking Service: {e}")
        raise
    finally:
        # 정리 작업
        if ranking_scheduler:
            await ranking_scheduler.stop_scheduler()
        if mongodb_service:
            await mongodb_service.close()
        if selection_recorder:
            await selection_recorder.close()
        if ranking_provider:
            await ranking_provider.close()
        
        try:
            db_manager = get_db_manager()
            await db_manager.close()
        except RuntimeError:
            # 데이터베이스가 초기화되지 않은 경우 무시
            pass
        logger.info("Ranking Service stopped")


# 설정을 미리 초기화하여 CORS 미들웨어에서 사용 가능하게 함
config = init_config("service-ranking")
_config_initialized = True

# FastAPI 앱 생성
app = FastAPI(
    title="Ranking Service",
    description="사용자 활동 기록 및 랭킹 서비스",
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
def get_selection_recorder() -> SelectionRecorder:
    """Selection Recorder 의존성"""
    if selection_recorder is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return selection_recorder


def get_ranking_provider() -> RankingProvider:
    """Ranking Provider 의존성"""
    if ranking_provider is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return ranking_provider


# Rate Limiting 체크 (간단한 구현)
rate_limit_store = {}

async def check_rate_limit(request: Request):
    """Rate Limiting 체크"""
    client_ip = request.client.host
    current_time = int(time.time())
    window = 60  # 1분
    limit = 100  # 분당 100회
    
    # 윈도우 초기화
    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []
    
    # 오래된 요청 제거
    rate_limit_store[client_ip] = [
        timestamp for timestamp in rate_limit_store[client_ip]
        if current_time - timestamp < window
    ]
    
    # 현재 요청 추가
    rate_limit_store[client_ip].append(current_time)
    
    # 제한 확인
    if len(rate_limit_store[client_ip]) > limit:
        raise RateLimitExceededError(limit, window, 60)


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
    return Response(generate_latest(ranking_registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    """헬스 체크 - 데이터베이스 연결 상태 포함"""
    try:
        health_status = {
            "status": "healthy",
            "service": "service-ranking",
            "version": get_config().service_version,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "checks": {
                "mongodb": "unknown",
                "scheduler": "unknown"
            }
        }
        
        # MongoDB 연결 상태 확인
        try:
            mongodb_service = await get_mongodb_service()
            if mongodb_service and mongodb_service.connected:
                health_status["checks"]["mongodb"] = "healthy"
            else:
                health_status["checks"]["mongodb"] = "unavailable"
        except Exception as e:
            logger.warning(f"MongoDB health check failed: {e}")
            health_status["checks"]["mongodb"] = "unhealthy"
            health_status["status"] = "degraded"
        
        # 스케줄러 상태 확인
        try:
            scheduler = await get_ranking_scheduler()
            if scheduler and scheduler.running:
                health_status["checks"]["scheduler"] = "healthy"
            else:
                health_status["checks"]["scheduler"] = "unavailable"
        except Exception as e:
            logger.warning(f"Scheduler health check failed: {e}")
            health_status["checks"]["scheduler"] = "unhealthy"
        
        # 전체 상태 결정
        if health_status["checks"]["mongodb"] == "unhealthy":
            health_status["status"] = "unhealthy"
        
        return SuccessResponse(data=health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "status": "unhealthy",
                "service": "service-ranking",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )


@app.post("/api/v1/rankings/click", response_model=SuccessResponse, status_code=201)
async def record_country_click(
    request: Request,
    country: str = Query(..., description="나라명 또는 국가 코드 (예: 미국, US, 일본, JP)"),
    mongodb_service: MongoDBService = Depends(get_mongodb_service)
):
    """
    나라 클릭 기록 및 카운팅
    
    - **country**: 나라명 또는 국가 코드 (예: 미국, US, 일본, JP)
    """
    try:
        # Rate Limiting 체크
        await check_rate_limit(request)
        
        # 클라이언트 정보 수집
        client_ip = request.client.host
        user_agent = request.headers.get("User-Agent", "")
        
        # 국가 코드 정규화
        country_code = await _normalize_country_code(country)
        country_name = await _get_country_name(country_code)
        
        # MongoDB에서 클릭수 증가 (원자적 연산)
        click_data = await mongodb_service.increment_country_clicks(
            country_code=country_code,
            country_name=country_name
        )

        # 메트릭 업데이트
        country_clicks_total.labels(country_code=country_code).inc()
        ranking_requests_total.labels(country_code=country_code, endpoint="click").inc()

        logger.info(f"Country click recorded: {country} -> {country_code} (clicks: {click_data['daily_clicks']}, rank: {click_data['current_rank']})")
        
        return SuccessResponse(
            data={
                "country_code": country_code,
                "country_name": country_name,
                "daily_clicks": click_data['daily_clicks'],
                "total_clicks": click_data['total_clicks'],
                "current_rank": click_data['current_rank'],
                "date": click_data['date'],
                "message": "Country click recorded and counted successfully"
            }
        )
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to record country click: {e}")
        raise HTTPException(status_code=500, detail="Failed to record country click")


async def _normalize_country_code(country_input: str) -> str:
    """나라 입력을 국가 코드로 정규화"""
    country_mapping = {
        # 한국어 -> 국가 코드
        "미국": "US", "일본": "JP", "한국": "KR", "유럽": "EU", "유럽연합": "EU",
        "영국": "GB", "중국": "CN", "호주": "AU", "캐나다": "CA", "스위스": "CH",
        "홍콩": "HK", "싱가포르": "SG", "태국": "TH", "베트남": "VN",
        "독일": "DE", "프랑스": "FR", "이탈리아": "IT", "스페인": "ES",
        "네덜란드": "NL", "벨기에": "BE", "오스트리아": "AT", "스웨덴": "SE",
        "노르웨이": "NO", "덴마크": "DK", "핀란드": "FI", "폴란드": "PL",
        "체코": "CZ", "헝가리": "HU", "그리스": "GR", "터키": "TR",
        "러시아": "RU", "인도": "IN", "브라질": "BR", "멕시코": "MX",
        "아르헨티나": "AR", "칠레": "CL", "남아프리카": "ZA", "이집트": "EG",
        "모로코": "MA", "케냐": "KE", "나이지리아": "NG", "이스라엘": "IL",
        "아랍에미리트": "AE", "사우디아라비아": "SA", "카타르": "QA",
        "쿠웨이트": "KW", "바레인": "BH", "오만": "OM", "요르단": "JO",
        "레바논": "LB", "이라크": "IQ", "이란": "IR", "파키스탄": "PK",
        "방글라데시": "BD", "스리랑카": "LK", "네팔": "NP", "부탄": "BT",
        "몰디브": "MV", "인도네시아": "ID", "말레이시아": "MY", "필리핀": "PH",
        "브루나이": "BN", "라오스": "LA", "캄보디아": "KH", "미얀마": "MM",
        "뉴질랜드": "NZ", "피지": "FJ", "파푸아뉴기니": "PG", "솔로몬제도": "SB",
        "바누아투": "VU", "통가": "TO", "사모아": "WS", "키리바시": "KI",
        "투발루": "TV", "나우루": "NR", "팔라우": "PW", "마셜제도": "MH",
        "미크로네시아": "FM", "북마리아나제도": "MP", "괌": "GU", "아메리칸사모아": "AS",
        "쿡제도": "CK", "니우에": "NU", "토켈라우": "TK", "피트케언제도": "PN"
    }
    
    # 입력 정리
    country_clean = country_input.strip()
    
    # 이미 국가 코드인 경우 (2-3자리 대문자)
    if len(country_clean) <= 3 and country_clean.isupper():
        return country_clean
    
    # 한국어 매핑에서 찾기
    if country_clean in country_mapping:
        return country_mapping[country_clean]
    
    # 첫 글자만 대문자로 변환해서 찾기
    country_title = country_clean.title()
    if country_title in country_mapping:
        return country_mapping[country_title]
    
    # 찾지 못한 경우 원본을 대문자로 변환해서 반환
    return country_clean.upper()


async def _get_country_name(country_code: str) -> str:
    """국가 코드에서 국가명 조회"""
    country_mapping = {
        "US": "미국", "JP": "일본", "KR": "한국", "EU": "유럽연합",
        "GB": "영국", "CN": "중국", "AU": "호주", "CA": "캐나다",
        "CH": "스위스", "HK": "홍콩", "SG": "싱가포르", "TH": "태국",
        "VN": "베트남", "DE": "독일", "FR": "프랑스", "IT": "이탈리아",
        "ES": "스페인", "NL": "네덜란드", "BE": "벨기에", "AT": "오스트리아",
        "SE": "스웨덴", "NO": "노르웨이", "DK": "덴마크", "FI": "핀란드",
        "PL": "폴란드", "CZ": "체코", "HU": "헝가리", "GR": "그리스",
        "TR": "터키", "RU": "러시아", "IN": "인도", "BR": "브라질",
        "MX": "멕시코", "AR": "아르헨티나", "CL": "칠레", "ZA": "남아프리카",
        "EG": "이집트", "MA": "모로코", "KE": "케냐", "NG": "나이지리아",
        "IL": "이스라엘", "AE": "아랍에미리트", "SA": "사우디아라비아",
        "QA": "카타르", "KW": "쿠웨이트", "BH": "바레인", "OM": "오만",
        "JO": "요르단", "LB": "레바논", "IQ": "이라크", "IR": "이란",
        "PK": "파키스탄", "BD": "방글라데시", "LK": "스리랑카",
        "NP": "네팔", "BT": "부탄", "MV": "몰디브", "ID": "인도네시아",
        "MY": "말레이시아", "PH": "필리핀", "BN": "브루나이", "LA": "라오스",
        "KH": "캄보디아", "MM": "미얀마", "NZ": "뉴질랜드", "FJ": "피지",
        "PG": "파푸아뉴기니", "SB": "솔로몬제도", "VU": "바누아투",
        "TO": "통가", "WS": "사모아", "KI": "키리바시", "TV": "투발루",
        "NR": "나우루", "PW": "팔라우", "MH": "마셜제도", "FM": "미크로네시아",
        "MP": "북마리아나제도", "GU": "괌", "AS": "아메리칸사모아",
        "CK": "쿡제도", "NU": "니우에", "TK": "토켈라우", "PN": "피트케언제도"
    }
    
    return country_mapping.get(country_code.upper(), country_code.upper())


@app.get("/api/v1/rankings", response_model=SuccessResponse)
async def get_daily_rankings(
    limit: int = Query(10, ge=1, le=50, description="결과 개수 제한"),
    date: Optional[str] = Query(None, description="조회할 날짜 (YYYY-MM-DD), None이면 오늘"),
    mongodb_service: MongoDBService = Depends(get_mongodb_service)
):
    """
    일일 랭킹 조회 (클릭수 기준, 1위부터 순서대로)
    
    - **limit**: 결과 개수 제한 (1-50)
    - **date**: 조회할 날짜 (YYYY-MM-DD), None이면 오늘
    """
    try:
        # MongoDB에서 일일 랭킹 조회 (클릭수 내림차순)
        rankings = await mongodb_service.get_daily_rankings(limit=limit, date=date)
        
        return SuccessResponse(
            data={
                "rankings": rankings,
                "total_count": len(rankings),
                "limit": limit,
                "date": date or datetime.now().strftime('%Y-%m-%d'),
                "updated_at": datetime.utcnow().isoformat() + 'Z'
            }
        )
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get daily rankings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve rankings")


@app.post("/api/v1/rankings/reset", response_model=SuccessResponse)
async def reset_daily_clicks(
    date: Optional[str] = Query(None, description="초기화할 날짜 (YYYY-MM-DD), None이면 오늘"),
    mongodb_service: MongoDBService = Depends(get_mongodb_service),
    scheduler: RankingScheduler = Depends(get_ranking_scheduler)
):
    """
    일일 클릭수 초기화 (관리자용)
    한국시간 00시에 자동으로 실행되지만, 수동으로도 실행 가능
    
    - **date**: 초기화할 날짜 (YYYY-MM-DD), None이면 오늘
    """
    try:
        # MongoDB에서 일일 클릭수 초기화
        reset_count = await mongodb_service.reset_daily_clicks(date=date)

        # 메트릭 업데이트
        daily_reset_operations_total.inc()

        return SuccessResponse(
            data={
                "message": "Daily click counts have been reset",
                "reset_count": reset_count,
                "date": date or datetime.now().strftime('%Y-%m-%d'),
                "reset_at": datetime.utcnow().isoformat() + 'Z'
            }
        )
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset daily clicks: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset daily clicks")


@app.get("/api/v1/rankings/scheduler/status", response_model=SuccessResponse)
async def get_scheduler_status(
    scheduler: RankingScheduler = Depends(get_ranking_scheduler)
):
    """
    스케줄러 상태 조회
    
    - **running**: 스케줄러 실행 상태
    - **next_reset_time**: 다음 초기화 예정 시간
    - **stats**: 스케줄러 통계
    """
    try:
        status = scheduler.get_scheduler_status()
        
        return SuccessResponse(data=status)
        
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheduler status")


@app.post("/api/v1/rankings/scheduler/reset", response_model=SuccessResponse)
async def manual_scheduler_reset(
    scheduler: RankingScheduler = Depends(get_ranking_scheduler)
):
    """
    수동 스케줄러 초기화 실행
    
    한국시간 00시가 아닌 시점에서 수동으로 초기화를 실행할 때 사용
    """
    try:
        result = await scheduler.run_manual_reset()
        
        if result["success"]:
            return SuccessResponse(data=result)
        else:
            raise HTTPException(status_code=500, detail=result["message"])
        
    except Exception as e:
        logger.error(f"Failed to run manual scheduler reset: {e}")
        raise HTTPException(status_code=500, detail="Failed to run manual scheduler reset")


@app.get("/api/v1/rankings/stats/{country_code}", response_model=SuccessResponse)
async def get_country_stats(
    country_code: str,
    days: int = Query(7, ge=1, le=30, description="통계 기간 (일수)"),
    mongodb_service: MongoDBService = Depends(get_mongodb_service)
):
    """
    국가별 클릭 통계 조회
    
    - **country_code**: 국가 코드
    - **days**: 통계 기간 (1-30일)
    """
    try:
        # 국가 코드 검증
        country_code = country_code.upper()
        
        # 통계 데이터 조회
        stats_data = await mongodb_service.get_country_stats(country_code, days)
        
        return SuccessResponse(data=stats_data)
        
    except Exception as e:
        logger.error(f"Failed to get country stats for {country_code}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve country statistics")




@app.post("/api/v1/rankings/calculate", response_model=SuccessResponse)
async def trigger_ranking_calculation(
    period: str = Query(..., description="계산할 랭킹 기간"),
    provider: RankingProvider = Depends(get_ranking_provider)
):
    """
    랭킹 계산 트리거 (관리자용)
    
    - **period**: 계산할 랭킹 기간
    """
    try:
        # 기간 검증
        valid_periods = [p.value for p in RankingPeriod]
        period = ValidationUtils.validate_period(period, valid_periods)
        
        # 랭킹 계산 트리거
        calculation_id = await provider.trigger_ranking_calculation(period)
        
        return SuccessResponse(
            data={
                "calculation_id": calculation_id,
                "period": period,
                "message": "Ranking calculation triggered successfully"
            }
        )
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger ranking calculation: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger ranking calculation")


# ----- Ranking store read/write APIs (DynamoDB: RankingResults) -----

class RankingStoreItem(BaseModel):
    period: str = Field(..., description="랭킹 기간 키 (daily|weekly|monthly)")
    ranking: List[Dict[str, Any]] = Field(default_factory=list)
    total_selections: int = 0
    last_updated: Optional[str] = None
    calculation_metadata: Optional[Dict[str, Any]] = None
    ttl: Optional[int] = Field(None, description="TTL epoch seconds (optional)")


def get_rankings_table_helper() -> DynamoDBHelper:
    try:
        return DynamoDBHelper("RankingResults")
    except Exception as e:
        logger.error(f"DynamoDB not initialized: {e}")
        raise HTTPException(status_code=503, detail="DynamoDB not initialized")


@app.post("/api/v1/rankings/store", response_model=SuccessResponse)
async def upsert_ranking_item(payload: RankingStoreItem):
    """랭킹 결과 저장/업데이트 (DynamoDB)"""
    try:
        # 기본 last_updated
        if not payload.last_updated:
            from datetime import datetime
            payload.last_updated = datetime.utcnow().isoformat() + 'Z'

        item = {
            "period": payload.period,
            "ranking_data": payload.ranking,
            "total_selections": payload.total_selections,
            "last_updated": payload.last_updated,
        }
        if payload.calculation_metadata is not None:
            item["calculation_metadata"] = payload.calculation_metadata
        if payload.ttl is not None:
            item["ttl"] = payload.ttl

        helper = get_rankings_table_helper()
        await helper.put_item(item)

        # 캐시 무효화: 저장된 period의 랭킹 캐시 제거
        try:
            redis = RedisHelper()
            await redis.delete_pattern(f"ranking:{payload.period}:*")
        except Exception:
            pass

        return SuccessResponse(data={"message": "Ranking item upserted", "period": payload.period})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert ranking item: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert ranking item")


@app.get("/api/v1/rankings/store/{period}", response_model=SuccessResponse)
async def get_ranking_item(period: str):
    """특정 기간의 랭킹 결과 조회 (DynamoDB)"""
    try:
        helper = get_rankings_table_helper()
        item = await helper.get_item({"period": period})
        if not item:
            raise HTTPException(status_code=404, detail="Ranking item not found")

        # 호환되는 응답 구조로 반환
        raw_items = item.get("ranking_data", [])
        normalized = []
        for idx, it in enumerate(raw_items):
            if isinstance(it, dict):
                obj = dict(it)
                if "selection_count" not in obj and "score" in obj:
                    obj["selection_count"] = obj["score"]
                if "rank" not in obj:
                    obj["rank"] = idx + 1
                normalized.append(obj)
            else:
                normalized.append(it)

        data = {
            "period": item.get("period", period),
            "total_selections": item.get("total_selections", 0),
            "last_updated": item.get("last_updated"),
            "ranking": normalized,
            "calculation_metadata": item.get("calculation_metadata")
        }
        return SuccessResponse(data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ranking item: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ranking item")


@app.get("/api/v1/rankings/store", response_model=SuccessResponse)
async def list_ranking_items():
    """저장된 랭킹 키 목록 조회 (DynamoDB)"""
    try:
        helper = get_rankings_table_helper()
        items = await helper.scan(ProjectionExpression="#p, last_updated",
                                  ExpressionAttributeNames={"#p": "period"})
        periods = [
            {"period": it.get("period"), "last_updated": it.get("last_updated")}
            for it in items
        ]
        return SuccessResponse(data={"items": periods, "count": len(periods)})
    except Exception as e:
        logger.error(f"Failed to list ranking items: {e}")
        raise HTTPException(status_code=500, detail="Failed to list ranking items")


# ----- Increment scores for selected countries (page entry) -----
class UpdateRankingRequest(BaseModel):
    countries: List[str] = Field(..., description="선택된 국가 코드 리스트 (예: ['US','JP'])")
    period: Optional[str] = Field('daily', description="업데이트할 랭킹 기간 (기본: daily)")


@app.post("/api/v1/rankings/update", response_model=SuccessResponse)
async def update_ranking_counts(payload: UpdateRankingRequest):
    """선택된 나라들의 점수를 1씩 증가

    동작:
    - 우선 DynamoDB의 RankingResults[{period}]가 있으면 해당 문서의 ranking_data를 수정 후 저장
    - 문서가 없거나 DynamoDB 사용 불가하면 Redis 카운터를 증가 (기존 fallback)
    """
    try:
        period = (payload.period or 'daily').lower()

        # 1) 시도: DynamoDB 문서 업데이트
        try:
            helper = get_rankings_table_helper()
            item = await helper.get_item({"period": period})
            if item:
                now_iso = datetime.utcnow().isoformat() + 'Z'
                ranking_list = list(item.get("ranking_data", []))

                # 인덱스 맵 구성
                index_by_code = {}
                for idx, entry in enumerate(ranking_list):
                    if isinstance(entry, dict) and 'country_code' in entry:
                        index_by_code[str(entry['country_code']).upper()] = idx

                # 스코어 증가 또는 신규 추가
                for code in payload.countries:
                    cc = str(code).upper().strip()
                    if not cc:
                        continue
                    if cc in index_by_code:
                        entry = dict(ranking_list[index_by_code[cc]])
                        entry['score'] = int(entry.get('score', 0)) + 1
                        # selection_count 필드가 있으면 함께 증가
                        if 'selection_count' in entry:
                            entry['selection_count'] = int(entry['selection_count']) + 1
                        ranking_list[index_by_code[cc]] = entry
                    else:
                        # 간단 기본값으로 신규 엔트리 생성
                        ranking_list.append({
                            'rank': None,
                            'country_code': cc,
                            'country_name': cc,
                            'score': 1,
                            'percentage': 0,
                            'change': 'SAME',
                            'change_value': 0,
                            'previous_rank': None
                        })

                # 정렬 및 순위 재계산 (동점은 동일 순위)
                ranking_list.sort(key=lambda x: int(x.get('score', 0)), reverse=True)
                total = sum(int(x.get('score', 0)) for x in ranking_list) or 0
                last_score = None
                last_rank = 0
                for idx, entry in enumerate(ranking_list, start=1):
                    score = int(entry.get('score', 0))
                    if last_score is None or score != last_score:
                        entry['rank'] = idx
                        last_rank = idx
                        last_score = score
                    else:
                        entry['rank'] = last_rank
                    if total > 0:
                        try:
                            entry['percentage'] = round((score / total) * 100, 2)
                        except Exception:
                            entry['percentage'] = 0

                # 문서 업데이트
                item['ranking_data'] = ranking_list
                item['total_selections'] = total
                item['last_updated'] = now_iso
                await helper.put_item(item)

                # 캐시 무효화: 해당 period의 랭킹 캐시 제거
                try:
                    redis = RedisHelper()
                    await redis.delete_pattern(f"ranking:{period}:*")
                except Exception as _:
                    pass

                return SuccessResponse(data={
                    "updated_countries": [str(c).upper().strip() for c in payload.countries if str(c).strip()],
                    "count": len([c for c in payload.countries if str(c).strip()]),
                    "period": period,
                    "source": "dynamodb"
                })
            else:
                # 문서가 없으면 자동 생성하여 DynamoDB를 소스로 사용
                now_iso = datetime.utcnow().isoformat() + 'Z'
                ranking_list = []

                # 신규 엔트리 생성 (각 국가 score=1)
                for code in payload.countries:
                    cc = str(code).upper().strip()
                    if not cc:
                        continue
                    ranking_list.append({
                        'rank': None,
                        'country_code': cc,
                        'country_name': cc,
                        'score': 1,
                        'percentage': 0,
                        'change': 'SAME',
                        'change_value': 0,
                        'previous_rank': None
                    })

                # 정렬 및 순위/퍼센트 계산 (동점은 동일 순위)
                ranking_list.sort(key=lambda x: int(x.get('score', 0)), reverse=True)
                total = sum(int(x.get('score', 0)) for x in ranking_list) or 0
                last_score = None
                last_rank = 0
                for idx, entry in enumerate(ranking_list, start=1):
                    score = int(entry.get('score', 0))
                    if last_score is None or score != last_score:
                        entry['rank'] = idx
                        last_rank = idx
                        last_score = score
                    else:
                        entry['rank'] = last_rank
                    if total > 0:
                        try:
                            entry['percentage'] = round((score / total) * 100, 2)
                        except Exception:
                            entry['percentage'] = 0

                new_item = {
                    'period': period,
                    'ranking_data': ranking_list,
                    'total_selections': total,
                    'last_updated': now_iso
                }

                await helper.put_item(new_item)

                return SuccessResponse(data={
                    "updated_countries": [str(c).upper().strip() for c in payload.countries if str(c).strip()],
                    "count": len([c for c in payload.countries if str(c).strip()]),
                    "period": period,
                    "source": "dynamodb-created"
                })
        except HTTPException:
            # get_rankings_table_helper가 실패한 경우 등은 Redis 폴백으로 진행
            pass
        except Exception as e:
            logger.warning(f"DynamoDB update path failed, falling back to Redis: {e}")

        # 2) 폴백: Redis 카운터 증가
        redis = RedisHelper()
        if not redis.client:
            # Redis도 없으면 서비스 불가
            raise HTTPException(status_code=503, detail="Datastore not available (DynamoDB/Redis)")

        today = datetime.utcnow().strftime('%Y-%m-%d')
        hour = datetime.utcnow().strftime('%Y-%m-%d-%H')

        updated = []
        for code in payload.countries:
            country_code = str(code).upper().strip()
            if not country_code:
                continue
            try:
                daily_key = f"daily_count:{today}:{country_code}"
                await redis.client.incr(daily_key)
                await redis.client.expire(daily_key, 86400 * 7)

                total_daily_key = f"daily_total:{today}"
                await redis.client.incr(total_daily_key)
                await redis.client.expire(total_daily_key, 86400 * 7)

                hourly_key = f"hourly_count:{hour}:{country_code}"
                await redis.client.incr(hourly_key)
                await redis.client.expire(hourly_key, 86400)

                updated.append(country_code)
            except Exception as inner:
                logger.warning(f"Failed to update counter for {country_code}: {inner}")

        return SuccessResponse(data={
            "updated_countries": updated,
            "count": len(updated),
            "period": period,
            "source": "redis"
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ranking counts: {e}")
        raise HTTPException(status_code=500, detail="Failed to update ranking counts")


# 로컬 개발 서버 실행
if __name__ == "__main__":
    # 환경 변수에서 설정 로드
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))  # 모든 서비스 표준 8000 포트
    
    logger.info(f"Starting Ranking Service on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,  # 개발 모드에서만 사용
        log_level="info"
    )