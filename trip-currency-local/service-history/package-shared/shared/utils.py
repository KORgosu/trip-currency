"""
Utility Functions
유틸리티 함수들
"""
import uuid
import hashlib
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from decimal import Decimal, InvalidOperation
import aiohttp
import pandas as pd
import numpy as np


class SecurityUtils:
    """보안 유틸리티"""
    
    @staticmethod
    def generate_uuid() -> str:
        """UUID 생성"""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_correlation_id() -> str:
        """상관관계 ID 생성"""
        return f"corr_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def hash_data(data: str) -> str:
        """데이터 해시화"""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()


class DateTimeUtils:
    """날짜/시간 유틸리티"""
    
    @staticmethod
    def utc_now() -> datetime:
        """현재 UTC 시간"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def kst_now() -> datetime:
        """현재 한국 시간"""
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst)
    
    @staticmethod
    def to_iso_string(dt: datetime) -> str:
        """ISO 문자열로 변환"""
        return dt.isoformat() + 'Z'
    
    @staticmethod
    def parse_iso_string(iso_str: str) -> datetime:
        """ISO 문자열 파싱"""
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + '+00:00'
        return datetime.fromisoformat(iso_str)
    
    @staticmethod
    def get_date_string(dt: datetime) -> str:
        """날짜 문자열 반환 (YYYY-MM-DD 형식)"""
        return dt.strftime('%Y-%m-%d')


class DataUtils:
    """데이터 유틸리티"""
    
    @staticmethod
    def clean_numeric(value: Any) -> Optional[float]:
        """숫자 데이터 정리"""
        if value is None:
            return None
        
        try:
            # 문자열인 경우 쉼표 제거
            if isinstance(value, str):
                value = value.replace(',', '')
            
            return float(value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
        """안전한 나눗셈"""
        if denominator == 0:
            return default
        return numerator / denominator
    
    @staticmethod
    def safe_decimal(value: Any, precision: int = 4) -> Decimal:
        """안전한 Decimal 변환"""
        if value is None:
            return Decimal('0')
        
        try:
            if isinstance(value, str):
                value = value.replace(',', '')
            return Decimal(str(value)).quantize(Decimal('0.' + '0' * precision))
        except (ValueError, TypeError, InvalidOperation):
            return Decimal('0')
    
    @staticmethod
    def calculate_percentage_change(old_value: float, new_value: float) -> float:
        """백분율 변화 계산"""
        if old_value == 0:
            return 0.0
        return ((new_value - old_value) / old_value) * 100


class PerformanceUtils:
    """성능 유틸리티"""
    
    @staticmethod
    def measure_time(func):
        """함수 실행 시간 측정 데코레이터"""
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            end_time = time.time()
            
            # 실행 시간을 로그로 출력 (선택사항)
            execution_time = end_time - start_time
            if hasattr(func, '__name__'):
                print(f"Function {func.__name__} executed in {execution_time:.4f} seconds")
            
            return result
        return wrapper
    
    @staticmethod
    def batch_process(items: List[Any], batch_size: int = 100):
        """배치 처리"""
        for i in range(0, len(items), batch_size):
            yield items[i:i + batch_size]


class ValidationUtils:
    """검증 유틸리티"""
    
    @staticmethod
    def validate_currency_code(code: str) -> str:
        """통화 코드 검증 및 정규화"""
        valid_codes = [
            # 주요 통화
            'USD', 'JPY', 'EUR', 'CNY', 'GBP', 'AUD', 'CAD', 'CHF', 'SGD', 'HKD', 'THB', 'VND', 'INR', 'BRL', 'RUB', 'MXN', 'ZAR', 'TRY', 'PLN', 'CZK', 'HUF', 'NOK', 'SEK', 'DKK', 'KRW',
            # 추가 아시아 통화
            'TWD', 'MYR', 'PHP', 'IDR', 'NZD', 'ILS', 'AED', 'QAR', 'KWD', 'BHD', 'OMR', 'JOD', 'LBP', 'PKR', 'BDT', 'LKR', 'NPR', 'AFN', 'KZT', 'UZS', 'KGS', 'TJS', 'TMT',
            # 추가 유럽 통화
            'ISK', 'RON', 'BGN', 'HRK', 'RSD', 'UAH', 'BYN',
            # 추가 아메리카 통화
            'ARS', 'CLP', 'COP', 'PEN', 'UYU', 'BOB', 'PYG', 'VES',
            # 추가 아프리카/중동 통화
            'EGP', 'MAD', 'TND', 'NGN', 'KES', 'UGX', 'TZS'
        ]
        
        if not code:
            raise ValueError("통화 코드가 제공되지 않았습니다")
        
        normalized_code = code.upper()
        if normalized_code not in valid_codes:
            raise ValueError(f"유효하지 않은 통화 코드: {code}")
        
        return normalized_code
    
    @staticmethod
    def validate_country_code(code: str) -> bool:
        """국가 코드 검증"""
        valid_codes = [
            # 주요 국가
            'US', 'JP', 'EU', 'CN', 'GB', 'AU', 'CA', 'CH', 'SG', 'HK', 'TH', 'VN', 'IN', 'BR', 'RU', 'MX', 'ZA', 'TR', 'PL', 'CZ', 'HU', 'NO', 'SE', 'DK', 'KR',
            # 추가 아시아 국가
            'TW', 'MY', 'PH', 'ID', 'NZ', 'IL', 'AE', 'QA', 'KW', 'BH', 'OM', 'JO', 'LB', 'PK', 'BD', 'LK', 'NP', 'AF', 'KZ', 'UZ', 'KG', 'TJ', 'TM',
            # 추가 유럽 국가
            'IS', 'RO', 'BG', 'HR', 'RS', 'UA', 'BY',
            # 추가 아메리카 국가
            'AR', 'CL', 'CO', 'PE', 'UY', 'BO', 'PY', 'VE',
            # 추가 아프리카/중동 국가
            'EG', 'MA', 'TN', 'NG', 'KE', 'UG', 'TZ'
        ]
        return code.upper() in valid_codes
    
    @staticmethod
    def validate_period(period: str, valid_periods: List[str]) -> str:
        """기간 검증"""
        if period.lower() not in [p.lower() for p in valid_periods]:
            raise ValueError(f"Invalid period: {period}. Valid periods: {valid_periods}")
        return period.lower()


class HTTPUtils:
    """HTTP 유틸리티"""
    
    @staticmethod
    async def make_request(url: str, method: str = 'GET', headers: Dict[str, str] = None, data: Dict[str, Any] = None, timeout: int = 30) -> Dict[str, Any]:
        """HTTP 요청"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.request(method, url, headers=headers, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")
    
    @staticmethod
    async def make_get_request(url: str, headers: Dict[str, str] = None, timeout: int = 30) -> Dict[str, Any]:
        """GET 요청"""
        return await HTTPUtils.make_request(url, 'GET', headers=headers, timeout=timeout)
    
    @staticmethod
    async def make_post_request(url: str, data: Dict[str, Any], headers: Dict[str, str] = None, timeout: int = 30) -> Dict[str, Any]:
        """POST 요청"""
        return await HTTPUtils.make_request(url, 'POST', headers=headers, data=data, timeout=timeout)
