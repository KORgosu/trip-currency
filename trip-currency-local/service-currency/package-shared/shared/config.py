"""
Configuration Management
환경별 설정 관리 모듈
"""
import os
from enum import Enum
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """환경 타입"""
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class DatabaseConfig(BaseSettings):
    """데이터베이스 설정"""
    host: str = Field(default="localhost")
    port: int = Field(default=3306)
    name: str = Field(default="currency_db")
    user: str = Field(default="trip_user")
    password: str = Field(default="trip-service-user")

    def __init__(self, **kwargs):
        import os
        super().__init__(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            name=os.getenv("MYSQL_DATABASE", "currency_db"),
            user=os.getenv("MYSQL_USER", "trip_user"),
            password=os.getenv("MYSQL_PASSWORD", "trip-service-user"),
            **kwargs
        )

    class Config:
        env_prefix = "DB_"
        env_file = ".env"


class RedisConfig(BaseSettings):
    """Redis 설정"""
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    
    def __init__(self, **kwargs):
        import os
        super().__init__(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            **kwargs
        )
    
    class Config:
        env_file = ".env"


class MongoDBConfig(BaseSettings):
    """MongoDB 설정"""
    host: str = Field(default="localhost")
    port: int = Field(default=27017)
    user: str = Field(default="trip_user")
    password: str = Field(default="trip-service-mongo")
    database: str = Field(default="currency_db")
    
    def __init__(self, **kwargs):
        import os
        super().__init__(
            host=os.getenv("MONGODB_HOST", "localhost"),
            port=int(os.getenv("MONGODB_PORT", "27017")),
            user=os.getenv("MONGODB_USER", "trip_user"),
            password=os.getenv("MONGODB_PASSWORD", "trip-service-mongo"),
            database=os.getenv("MONGODB_DATABASE", "currency_db"),
            **kwargs
        )
    
    class Config:
        env_file = ".env"


class MessagingConfig(BaseSettings):
    """메시징 설정"""
    kafka_bootstrap_servers: str = Field(default="localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    sqs_queue_url: Optional[str] = Field(default=None, env="SQS_QUEUE_URL")


class ExternalAPIsConfig(BaseSettings):
    """외부 API 설정"""
    # ExchangeRate-API는 API 키가 필요하지 않음
    pass


class ServiceConfig(BaseSettings):
    """서비스 설정"""
    name: str = Field(default="trip-service-currency", env="SERVICE_NAME")
    version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    port: int = Field(default=8000, env="PORT")
    environment: Environment = Field(default=Environment.LOCAL, env="ENVIRONMENT")
    
    # 로깅 설정
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="text", env="LOG_FORMAT")
    
    # CORS 설정
    cors_origins: List[str] = Field(default=["http://localhost:3000"])

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # 콤마로 구분된 문자열을 리스트로 변환
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # 데이터베이스 설정
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    mongodb: MongoDBConfig = Field(default_factory=MongoDBConfig)
    
    # 메시징 설정
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    
    # 외부 API 설정
    external_apis: ExternalAPIsConfig = Field(default_factory=ExternalAPIsConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 전역 설정 인스턴스
_config: Optional[ServiceConfig] = None


def init_config(service_name: str) -> ServiceConfig:
    """설정 초기화"""
    global _config
    
    # 환경 변수에서 서비스명 설정
    os.environ["SERVICE_NAME"] = service_name
    
    _config = ServiceConfig()
    return _config


def get_config() -> ServiceConfig:
    """설정 인스턴스 반환"""
    global _config
    
    if _config is None:
        _config = ServiceConfig()
    
    return _config
