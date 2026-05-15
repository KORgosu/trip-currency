"""
Trip Currency Shared Package v1.0.0

환율 서비스의 공통 모듈 라이브러리
마이크로서비스 아키텍처를 위한 공통 기능 제공

주요 모듈:
- config: 환경 설정 관리
- database: 데이터베이스 연결 (MySQL, Redis, MongoDB, DynamoDB)
- models: Pydantic 모델 정의
- exceptions: 커스텀 예외 클래스
- logging: 구조화된 로깅
- messaging: Kafka/SQS 메시징
- utils: 유틸리티 함수들

사용법:
    from shared.config import init_config, get_config
    from shared.database import init_database, get_db_manager
    from shared.models import ExchangeRate, CurrencyInfo
    from shared.exceptions import BaseServiceException
    from shared.logging import get_logger
    from shared.utils import SecurityUtils, DateTimeUtils

버전: 1.0.0
작성자: KORgosu
라이선스: MIT
"""

__version__ = "1.0.0"
__author__ = "KORgosu"
__email__ = "korgosu@example.com"
__license__ = "MIT"
__description__ = "Trip Currency Service의 공통 모듈 라이브러리"

# 주요 모듈들을 패키지 레벨에서 import 가능하도록 설정
from .config import init_config, get_config, Environment
from .database import init_database, get_db_manager
from .models import *
from .exceptions import *
from .logging import get_logger, set_correlation_id, set_request_id
from .messaging import MessageProducer, MessageConsumer, send_exchange_rate_update
from .utils import *

__all__ = [
    # Config
    "init_config",
    "get_config", 
    "Environment",
    
    # Database
    "init_database",
    "get_db_manager",
    "MySQLHelper",
    "RedisHelper",
    "MongoDBHelper",
    "DynamoDBHelper",
    
    # Logging
    "get_logger",
    "set_correlation_id",
    "set_request_id",
    
    # Messaging
    "MessageProducer",
    "MessageConsumer", 
    "send_exchange_rate_update",
    
    # Models (모든 모델들)
    "ExchangeRate",
    "CurrencyInfo",
    "LatestRatesResponse",
    "UserSelection",
    "RankingResponse",
    "HistoryResponse",
    "CountryStats",
    "RankingPeriod",
    "SuccessResponse",
    "ErrorResponse",
    
    # Exceptions (모든 예외들)
    "BaseServiceException",
    "InvalidCurrencyCodeError",
    "InvalidCountryCodeError",
    "InvalidPeriodError",
    "RateLimitExceededError",
    "DatabaseError",
    "CacheError",
    "NotFoundError",
    "ExternalAPIError",
    "DataValidationError",
    "DataProcessingError",
    "CalculationError",
    "MessagingError",
    "SchedulerError",
    "get_http_status_code",
    
    # Utils (모든 유틸리티들)
    "DateTimeUtils",
    "DataUtils",
    "PerformanceUtils",
    "SecurityUtils",
    "ValidationUtils",
    "HTTPUtils",
]
