"""
Data Collector - 외부 API에서 환율 데이터 수집
다중 소스에서 데이터를 수집하고 검증
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
shared_dir = os.path.join(parent_dir, 'shared')

sys.path.insert(0, parent_dir)
sys.path.insert(0, shared_dir)

from shared.models import CollectionResult, RawExchangeRateData
from shared.exceptions import ExternalAPIError, DataValidationError
from shared.utils import HTTPUtils, DateTimeUtils, ValidationUtils, PerformanceUtils

def get_logger_safe():
    """안전한 로거 가져오기"""
    try:
        from shared.logging import get_logger
        return get_logger(__name__)
    except:
        import logging
        return logging.getLogger(__name__)

# 전역 로거 초기화 (지연 로딩)
logger = get_logger_safe()


class DataCollector:
    """외부 데이터 수집자"""
    
    # ExchangeRate-API를 사용한 환율 데이터 수집
    # - API 키 불필요 (무료)
    # - 매시각 정시 실행 (00:00, 01:00, 02:00...)
    # - 실패 시 재시도 로직 포함
    
    def __init__(self):
        self.config = None  # 초기화 시점에서 로드
        self.session = None
        self.api_sources = {}  # 초기화 시점에서 로드
    
    async def initialize(self):
        """수집자 초기화"""
        try:
            # 설정 로드
            from shared.config import get_config
            self.config = get_config()
            
            # API 소스 초기화
            self.api_sources = self._initialize_api_sources()
            
            # HTTP 세션 생성
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            logger.info("Data collector initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize data collector", error=e)
            raise
    
    def _initialize_api_sources(self) -> Dict[str, Dict[str, Any]]:
        """API 소스 설정 초기화"""
        return {
            "exchangerate_api": {  # 메인 API
                "name": "ExchangeRate-API",
                "base_url": "https://api.exchangerate-api.com/v4/latest/KRW",
                "api_key": None,  # API 키 불필요
                "currencies": [
                    # 주요 통화 (24개)
                    "USD", "JPY", "EUR", "GBP", "CNY", "AUD", "CAD", "CHF", 
                    "SGD", "HKD", "THB", "VND", "INR", "BRL", "RUB", "MXN", 
                    "ZAR", "TRY", "PLN", "CZK", "HUF", "NOK", "SEK", "DKK",
                    # 추가 아시아 통화
                    "TWD", "MYR", "PHP", "IDR", "KRW", "NZD", "ILS", "AED",
                    # 추가 유럽 통화  
                    "CHF", "ISK", "RON", "BGN", "HRK", "RSD", "UAH", "BYN",
                    # 추가 아메리카 통화
                    "ARS", "CLP", "COP", "PEN", "UYU", "BOB", "PYG", "VES",
                    # 추가 아프리카/중동 통화
                    "EGP", "MAD", "TND", "ZAR", "NGN", "KES", "UGX", "TZS",
                    # 기타 주요 통화
                    "QAR", "KWD", "BHD", "OMR", "JOD", "LBP", "PKR", "BDT",
                    "LKR", "NPR", "AFN", "KZT", "UZS", "KGS", "TJS", "TMT"
                ],  # 총 60개 주요 통화
                "timeout": 10,
                "priority": 1,
                "active": True
            }
        }
    
    @PerformanceUtils.measure_time
    async def collect_all_data(self) -> List[CollectionResult]:
        """ExchangeRate-API에서 데이터 수집"""
        logger.info("Starting data collection from ExchangeRate-API")
        
        # ExchangeRate-API만 사용
        source_id = "exchangerate_api"
        source_config = self.api_sources[source_id]
        
        try:
            # 단일 소스에서 데이터 수집
            result = await self._collect_from_source(source_id, source_config)
            
            logger.info(
                "Data collection completed",
                source=source_id,
                success=result.success,
                currency_count=len(result.raw_data) if result.raw_data else 0
            )
            
            return [result]
            
        except Exception as e:
            logger.error(f"Data collection failed: {str(e)}")
            
            # 실패한 경우에도 CollectionResult 반환
            failed_result = CollectionResult(
                source=source_id,
                success=False,
                error_message=str(e),
                collection_time=DateTimeUtils.utc_now(),
                processing_time_ms=0
            )
            
            return [failed_result]
    
    async def _collect_from_source(
        self, 
        source_id: str, 
        source_config: Dict[str, Any]
    ) -> CollectionResult:
        """특정 소스에서 데이터 수집"""
        start_time = datetime.utcnow()
        
        logger.info(
            "Collecting data from source",
            source=source_id,
            source_name=source_config["name"]
        )
        
        try:
            # ExchangeRate-API에서 데이터 수집
            if source_id == "exchangerate_api":
                raw_data = await self._collect_from_exchangerate_api(source_config)
            else:
                raise ValueError(f"Unknown source: {source_id}")
            
            # 데이터 검증
            validated_data = self._validate_collected_data(raw_data, source_id)
            
            end_time = datetime.utcnow()
            processing_time = int((end_time - start_time).total_seconds() * 1000)
            
            logger.info(
                "Data collection successful",
                source=source_id,
                currency_count=len(validated_data),
                processing_time_ms=processing_time
            )
            
            return CollectionResult(
                source=source_id,
                success=True,
                currency_count=len(validated_data),
                collection_time=end_time,
                processing_time_ms=processing_time,
                raw_data=validated_data
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            processing_time = int((end_time - start_time).total_seconds() * 1000)
            
            logger.error(
                "Data collection failed",
                source=source_id,
                error=e,
                processing_time_ms=processing_time
            )
            
            return CollectionResult(
                source=source_id,
                success=False,
                error_message=str(e),
                collection_time=end_time,
                processing_time_ms=processing_time
            )
    
    
    async def _collect_from_exchangerate_api(self, config: Dict[str, Any]) -> List[RawExchangeRateData]:
        """ExchangeRate-API에서 데이터 수집"""
        try:
            logger.info("Collecting data from ExchangeRate-API", url=config["base_url"])
            
            async with self.session.get(config["base_url"]) as response:
                response.raise_for_status()
                data = await response.json()
                
                raw_data = []
                
                if "rates" in data:
                    logger.info(f"Received rates for {len(data['rates'])} currencies")
                    
                    # 모든 통화 수집 (currencies 리스트가 비어있으면 모든 통화)
                    target_currencies = config["currencies"] if config["currencies"] else data["rates"].keys()
                    
                    for currency_code, rate in data["rates"].items():
                        if not config["currencies"] or currency_code in target_currencies:
                            # KRW 기준이므로 역수 계산 (1 USD = 1300 KRW -> 1 KRW = 1/1300 USD)
                            krw_rate = 1 / rate if rate > 0 else 0
                            
                            raw_data.append(RawExchangeRateData(
                                currency_code=currency_code,
                                rate=krw_rate,
                                timestamp=DateTimeUtils.utc_now(),
                                metadata={
                                    "base_currency": data.get("base", "KRW"),
                                    "date": data.get("date"),
                                    "original_rate": rate
                                }
                            ))
                    
                    logger.info(f"Successfully collected {len(raw_data)} exchange rates")
                else:
                    logger.warning("No rates found in ExchangeRate-API response")
                
                return raw_data
                
        except Exception as e:
            logger.error(f"ExchangeRate-API request failed: {str(e)}")
            raise ExternalAPIError(f"ExchangeRate-API request failed: {str(e)}", "exchangerate_api")
    
    
    
    def _validate_collected_data(
        self, 
        raw_data: List[RawExchangeRateData], 
        source: str
    ) -> List[RawExchangeRateData]:
        """수집된 데이터 검증"""
        validated_data = []
        
        for item in raw_data:
            try:
                # 통화 코드 검증
                ValidationUtils.validate_currency_code(item.currency_code)
                
                # 환율 값 검증
                rate_value = float(item.rate)
                if rate_value <= 0 or rate_value > 10000:
                    logger.warning(
                        "Invalid exchange rate value",
                        currency=item.currency_code,
                        rate=rate_value,
                        source=source
                    )
                    continue
                
                # 타임스탬프 검증
                if not item.timestamp:
                    item.timestamp = DateTimeUtils.utc_now()
                
                validated_data.append(item)
                
            except Exception as e:
                logger.warning(
                    "Data validation failed",
                    currency=item.currency_code,
                    error=str(e),
                    source=source
                )
                continue
        
        logger.debug(
            "Data validation completed",
            source=source,
            original_count=len(raw_data),
            validated_count=len(validated_data)
        )
        
        return validated_data
    
    async def test_api_connectivity(self) -> Dict[str, bool]:
        """API 연결성 테스트"""
        logger.info("Testing API connectivity")
        
        connectivity_results = {}
        
        for source_id, config in self.api_sources.items():
            if not config.get("active", False):
                connectivity_results[source_id] = False
                continue
            
            try:
                # 간단한 연결 테스트
                if source_id == "exchangerate_api":
                    async with self.session.get(config["base_url"]) as response:
                        connectivity_results[source_id] = response.status == 200
                else:
                    # 다른 API들은 기본 URL 테스트
                    async with self.session.get(config["base_url"].split('?')[0]) as response:
                        connectivity_results[source_id] = response.status in [200, 400]  # 400도 연결은 됨
                        
            except Exception as e:
                logger.warning(f"Connectivity test failed for {source_id}", error=e)
                connectivity_results[source_id] = False
        
        logger.info("API connectivity test completed", results=connectivity_results)
        return connectivity_results
    
    async def close(self):
        """리소스 정리"""
        if self.session:
            await self.session.close()
        
        logger.info("Data collector closed")