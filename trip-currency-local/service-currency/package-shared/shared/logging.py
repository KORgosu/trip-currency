"""
Logging Configuration
구조화된 로깅 설정
"""
import logging
import sys
import structlog
from typing import Optional
from .config import get_config, Environment


def get_logger(name: str) -> structlog.BoundLogger:
    """로거 반환"""
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: str):
    """상관관계 ID 설정"""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def set_request_id(request_id: str):
    """요청 ID 설정"""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def configure_logging():
    """로깅 설정"""
    try:
        config = get_config()
        level = getattr(logging, config.log_level.upper(), logging.INFO)
        env = config.environment
    except Exception:
        config = None
        level = logging.INFO
        env = Environment.LOCAL

    # 기존 핸들러 제거
    root_logger = logging.getLogger()
    if hasattr(root_logger, 'handlers'):
        root_logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    
    try:
        from .config import Environment as _Env
        is_local = (env == _Env.LOCAL)
    except Exception:
        is_local = True  # 설정 알 수 없을 때는 간단 포맷 사용
    
    if config is None or is_local and getattr(config, 'log_format', 'text') != "json":
        # 로컬 환경: 간단한 포맷
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
    else:
        # 프로덕션 환경: JSON 포맷
        handler.setFormatter(logging.Formatter('%(message)s'))
    
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    
    # structlog 설정
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
    ]
    
    if config is None or is_local and getattr(config, 'log_format', 'text') != "json":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# 로깅 설정 초기화
configure_logging()