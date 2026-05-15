"""
Custom Exceptions
커스텀 예외 클래스
"""
from typing import Dict, Any, Optional
from fastapi import HTTPException


class BaseServiceException(Exception):
    """기본 서비스 예외"""
    
    def __init__(self, message: str, error_code: str = "SERVICE_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class InvalidCurrencyCodeError(BaseServiceException):
    """잘못된 통화 코드 에러"""
    
    def __init__(self, currency_code: str):
        super().__init__(
            message=f"Invalid currency code: {currency_code}",
            error_code="INVALID_CURRENCY_CODE",
            details={"currency_code": currency_code}
        )


class InvalidCountryCodeError(BaseServiceException):
    """잘못된 국가 코드 에러"""
    
    def __init__(self, country_code: str):
        super().__init__(
            message=f"Invalid country code: {country_code}",
            error_code="INVALID_COUNTRY_CODE",
            details={"country_code": country_code}
        )


class InvalidPeriodError(BaseServiceException):
    """잘못된 기간 에러"""
    
    def __init__(self, period: str):
        super().__init__(
            message=f"Invalid period: {period}",
            error_code="INVALID_PERIOD",
            details={"period": period}
        )


class RateLimitExceededError(BaseServiceException):
    """요청 제한 초과 에러"""
    
    def __init__(self, limit: int, window: int, retry_after: int):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window} seconds",
            error_code="RATE_LIMIT_EXCEEDED",
            details={
                "limit": limit,
                "window": window,
                "retry_after": retry_after
            }
        )


class DatabaseError(BaseServiceException):
    """데이터베이스 에러"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=details or {}
        )


class CacheError(BaseServiceException):
    """캐시 에러"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            details=details or {}
        )


class NotFoundError(BaseServiceException):
    """데이터 없음 에러"""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier}
        )


class ExternalAPIError(BaseServiceException):
    """외부 API 에러"""
    
    def __init__(self, api_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"External API error ({api_name}): {message}",
            error_code="EXTERNAL_API_ERROR",
            details={"api_name": api_name, **(details or {})}
        )


class DataValidationError(BaseServiceException):
    """데이터 검증 에러"""
    
    def __init__(self, message: str, field: str, value: Any):
        super().__init__(
            message=f"Data validation error: {message}",
            error_code="DATA_VALIDATION_ERROR",
            details={"field": field, "value": str(value)}
        )


class DataProcessingError(BaseServiceException):
    """데이터 처리 에러"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="DATA_PROCESSING_ERROR",
            details=details or {}
        )


class CalculationError(BaseServiceException):
    """계산 에러"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CALCULATION_ERROR",
            details=details or {}
        )


class MessagingError(BaseServiceException):
    """메시징 에러"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="MESSAGING_ERROR",
            details=details or {}
        )


def get_http_status_code(exception: BaseServiceException) -> int:
    """예외에 따른 HTTP 상태 코드 반환"""
    status_code_map = {
        "INVALID_CURRENCY_CODE": 400,
        "INVALID_COUNTRY_CODE": 400,
        "INVALID_PERIOD": 400,
        "RATE_LIMIT_EXCEEDED": 429,
        "DATABASE_ERROR": 500,
        "CACHE_ERROR": 500,
        "NOT_FOUND": 404,
        "EXTERNAL_API_ERROR": 502,
        "DATA_VALIDATION_ERROR": 400,
        "DATA_PROCESSING_ERROR": 500,
        "MESSAGING_ERROR": 500,
        "SERVICE_ERROR": 500
    }
    
    return status_code_map.get(exception.error_code, 500)


def handle_database_exception(func):
    """데이터베이스 예외 처리 데코레이터"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise DatabaseError(f"Database operation failed: {str(e)}")
    return wrapper


class SchedulerError(BaseServiceException):
    """스케줄러 에러"""
    
    def __init__(self, message: str, scheduler_name: str = None):
        super().__init__(
            message=f"Scheduler error: {message}",
            error_code="SCHEDULER_ERROR",
            details={"scheduler_name": scheduler_name} if scheduler_name else {}
        )


def handle_cache_exception(func):
    """캐시 예외 처리 데코레이터"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise CacheError(f"Cache operation failed: {str(e)}")
    return wrapper
