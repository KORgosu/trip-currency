"""
Currency Provider - 환율 데이터 제공 서비스
Redis 캐시 우선 조회, Aurora DB 폴백
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import json

from shared.database import RedisHelper, MySQLHelper
import logging
from shared.models import ExchangeRate, CurrencyInfo
from shared.exceptions import (
    DatabaseError, CacheError, NotFoundError, 
    handle_database_exception, handle_cache_exception
)

logger = logging.getLogger(__name__)


class CurrencyProvider:
    """환율 데이터 제공자"""
    
    # TODO: 실시간 서비스 변경 - mock DB 데이터 대신 data-ingestor의 실제 환율 수집 데이터 사용
    # - _get_rate_from_db: Aurora DB의 exchange_rate_history 테이블에서 실제 최신 환율 조회
    # - data-ingestor에서 BOK API 호출로 실시간 업데이트
    # AWS 연결: ElastiCache Redis 캐싱 (TTL 10분), Aurora MySQL 폴백
    
    def __init__(self):
        self.redis_helper = RedisHelper()
        self.mysql_helper = MySQLHelper()
        self.cache_ttl = 600  # 10분
    
    async def get_latest_rates(
        self, 
        currency_codes: List[str] = None, 
        base_currency: str = "KRW"
    ) -> Dict[str, Any]:
        """
        최신 환율 조회
        
        Args:
            currency_codes: 조회할 통화 코드 리스트
            base_currency: 기준 통화
            
        Returns:
            환율 데이터 딕셔너리
        """
        try:
            # 기본 통화 목록 설정 (주요 통화 10개)
            if not currency_codes:
                currency_codes = ["USD", "JPY", "EUR", "GBP", "CNY", "AUD", "CAD", "CHF", "SGD", "HKD"]
            
            rates = {}
            cache_hits = 0
            db_hits = 0
            
            # Redis에서 캐시된 환율 조회
            for currency_code in currency_codes:
                try:
                    cached_rate = await self._get_cached_rate(currency_code)
                    if cached_rate:
                        rates[currency_code] = float(cached_rate["deal_base_rate"])
                        cache_hits += 1
                        logger.debug(f"Cache hit for {currency_code}")
                    else:
                        # 캐시 미스 시 DB에서 조회
                        db_rate = await self._get_rate_from_db(currency_code)
                        if db_rate:
                            rates[currency_code] = float(db_rate["deal_base_rate"])
                            db_hits += 1
                            # 캐시에 저장
                            await self._cache_rate(currency_code, db_rate)
                            logger.debug(f"DB hit for {currency_code}")
                        else:
                            logger.warning(f"No rate found for {currency_code}")
                
                except Exception as e:
                    logger.error(f"Failed to get rate for {currency_code}: {e}")
                    continue
            
            # 응답 데이터 구성
            response_data = {
                "base": base_currency,
                "timestamp": int(datetime.utcnow().timestamp()),
                "rates": rates,
                "source": "redis_cache" if cache_hits > 0 else "database",
                "cache_hit": cache_hits > 0,
                "cache_hit_ratio": cache_hits / len(currency_codes) if currency_codes else 0,
                "total_currencies": len(currency_codes),
                "cached_currencies": cache_hits,
                "db_currencies": db_hits
            }
            
            logger.info(f"Latest rates retrieved: {cache_hits} cache hits, {db_hits} DB hits")
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get latest rates: {e}")
            raise handle_database_exception(e, "get_latest_rates")
    
    async def get_currency_info(self, currency_code: str) -> Dict[str, Any]:
        """
        통화 상세 정보 조회
        
        Args:
            currency_code: 통화 코드
            
        Returns:
            통화 정보 딕셔너리
        """
        try:
            # 캐시에서 먼저 조회
            cache_key = f"currency_info:{currency_code}"
            cached_info = await self.redis_helper.get_json(cache_key)
            
            if cached_info:
                logger.debug(f"Currency info cache hit for {currency_code}")
                return cached_info
            
            # DB에서 통화 정보 조회 (latest_exchange_rates 뷰 사용)
            query = """
                SELECT 
                    currency_code,
                    currency_name,
                    symbol,
                    deal_base_rate as current_rate,
                    tts,
                    ttb,
                    recorded_at as last_updated,
                    source
                FROM latest_exchange_rates
                WHERE currency_code = %s
            """
            
            result = await self.mysql_helper.execute_query(query, (currency_code,))
            
            if not result:
                raise NotFoundError("currency", currency_code)
            
            currency_info = result[0]
            
            # 응답 데이터 구성
            response_data = {
                "currency_code": currency_info["currency_code"],
                "currency_name": currency_info["currency_name"],
                "symbol": currency_info["symbol"],
                "current_rate": float(currency_info["current_rate"]) if currency_info["current_rate"] else None,
                "tts": float(currency_info["tts"]) if currency_info["tts"] else None,
                "ttb": float(currency_info["ttb"]) if currency_info["ttb"] else None,
                "last_updated": currency_info["last_updated"].isoformat() + 'Z' if currency_info["last_updated"] else None,
                "source": currency_info["source"]
            }
            
            # 캐시에 저장 (1시간)
            await self.redis_helper.set_json(cache_key, response_data, 3600)
            logger.debug(f"Currency info cached for {currency_code}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to get currency info for {currency_code}: {e}")
            if isinstance(e, NotFoundError):
                raise
            raise handle_database_exception(e, "get_currency_info", "latest_exchange_rates")
    
    async def _get_cached_rate(self, currency_code: str) -> Optional[Dict[str, Any]]:
        """Redis에서 캐시된 환율 조회"""
        try:
            cache_key = f"rate:CurrencyCode.{currency_code}"
            cached_data = await self.redis_helper.get_hash(cache_key)
            
            if cached_data and "deal_base_rate" in cached_data:
                return {
                    "currency_code": currency_code,
                    "currency_name": cached_data.get("currency_name", ""),
                    "deal_base_rate": cached_data["deal_base_rate"],
                    "tts": cached_data.get("tts"),
                    "ttb": cached_data.get("ttb"),
                    "source": cached_data.get("source", "cache"),
                    "last_updated_at": cached_data.get("last_updated_at")
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Cache lookup failed for {currency_code}", error=e)
            return None
    
    async def _get_rate_from_db(self, currency_code: str) -> Optional[Dict[str, Any]]:
        """데이터베이스에서 최신 환율 조회 (latest_exchange_rates 뷰 사용)"""
        try:
            query = """
                SELECT
                    currency_code,
                    currency_name,
                    symbol,
                    deal_base_rate,
                    tts,
                    ttb,
                    source,
                    recorded_at,
                    created_at
                FROM latest_exchange_rates
                WHERE currency_code = %s
            """
            
            result = await self.mysql_helper.execute_query(query, (currency_code,))
            
            if result:
                rate_data = result[0]
                return {
                    "currency_code": rate_data["currency_code"],
                    "currency_name": rate_data["currency_name"],
                    "deal_base_rate": str(rate_data["deal_base_rate"]),
                    "tts": str(rate_data["tts"]) if rate_data["tts"] else None,
                    "ttb": str(rate_data["ttb"]) if rate_data["ttb"] else None,
                    "source": rate_data["source"],
                    "last_updated_at": rate_data["recorded_at"].isoformat() + 'Z'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Database lookup failed for {currency_code}: {e}")
            raise handle_database_exception(e, "get_rate_from_db", "latest_exchange_rates")
    
    async def _cache_rate(self, currency_code: str, rate_data: Dict[str, Any]):
        """환율 데이터를 Redis에 캐시"""
        # TODO: AWS 연결 - ElastiCache Redis 클러스터 사용
        # - set_hash: 실제 클러스터 엔드포인트로 캐싱
        # - TTL 10분으로 실시간성 유지
        try:
            cache_key = f"rate:CurrencyCode.{currency_code}"
            
            cache_data = {
                "currency_name": rate_data["currency_name"],
                "deal_base_rate": rate_data["deal_base_rate"],
                "tts": rate_data.get("tts", ""),
                "ttb": rate_data.get("ttb", ""),
                "source": rate_data["source"],
                "last_updated_at": rate_data["last_updated_at"]
            }
            
            await self.redis_helper.set_hash(cache_key, cache_data, self.cache_ttl)
            logger.debug(f"Rate cached for {currency_code}")
            
        except Exception as e:
            logger.warning(f"Failed to cache rate for {currency_code}: {e}")
            # 캐시 실패는 치명적이지 않으므로 예외를 발생시키지 않음
    
    async def get_multiple_rates(self, currency_codes: List[str]) -> Dict[str, Any]:
        """
        여러 통화의 환율을 한 번에 조회 (성능 최적화)
        
        Args:
            currency_codes: 조회할 통화 코드 리스트
            
        Returns:
            환율 데이터 딕셔너리
        """
        try:
            if not currency_codes:
                return {"rates": {}, "source": "empty", "cache_hit": False}
            
            rates = {}
            cache_hits = 0
            db_hits = 0
            
            # Redis에서 일괄 조회
            cache_keys = [f"rate:CurrencyCode.{code}" for code in currency_codes]
            cached_data = await self.redis_helper.get_multiple_hashes(cache_keys)
            
            # 캐시된 데이터 처리
            for i, currency_code in enumerate(currency_codes):
                if cached_data[i] and "deal_base_rate" in cached_data[i]:
                    rates[currency_code] = float(cached_data[i]["deal_base_rate"])
                    cache_hits += 1
                else:
                    # 캐시 미스 시 DB에서 조회
                    db_rate = await self._get_rate_from_db(currency_code)
                    if db_rate:
                        rates[currency_code] = float(db_rate["deal_base_rate"])
                        db_hits += 1
                        # 캐시에 저장
                        await self._cache_rate(currency_code, db_rate)
            
            return {
                "rates": rates,
                "source": "redis_cache" if cache_hits > 0 else "database",
                "cache_hit": cache_hits > 0,
                "cache_hit_ratio": cache_hits / len(currency_codes) if currency_codes else 0,
                "total_currencies": len(currency_codes),
                "cached_currencies": cache_hits,
                "db_currencies": db_hits
            }
            
        except Exception as e:
            logger.error(f"Failed to get multiple rates: {e}")
            raise handle_database_exception(e, "get_multiple_rates")
    
    async def clear_cache(self, currency_code: str = None):
        """
        캐시 클리어
        
        Args:
            currency_code: 특정 통화 코드 (None이면 전체 캐시 클리어)
        """
        try:
            if currency_code:
                cache_key = f"rate:CurrencyCode.{currency_code}"
                await self.redis_helper.delete(cache_key)
                logger.info(f"Cache cleared for {currency_code}")
            else:
                # 전체 환율 캐시 클리어
                pattern = "rate:CurrencyCode.*"
                await self.redis_helper.delete_pattern(pattern)
                logger.info("All rate cache cleared")
                
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise handle_cache_exception(e, "clear_cache")
    
    async def refresh_currency_cache(self, currency_code: str):
        """
        특정 통화의 캐시 새로고침
        
        Args:
            currency_code: 새로고침할 통화 코드
        """
        try:
            # 캐시 클리어
            await self.clear_cache(currency_code)
            
            # 데이터베이스에서 최신 데이터 조회
            rate_data = await self._get_rate_from_db(currency_code)
            
            if rate_data:
                # 새로운 데이터로 캐시 갱신
                await self._cache_rate(currency_code, rate_data)
                logger.info(f"Cache refreshed for {currency_code}")
            else:
                logger.warning(f"No data found for {currency_code} to refresh cache")
                
        except Exception as e:
            logger.error(f"Failed to refresh cache for {currency_code}: {e}")
            raise handle_cache_exception(e, "refresh_currency_cache")
    
    async def refresh_all_currency_cache(self):
        """
        모든 통화의 캐시 새로고침
        """
        try:
            # 전체 캐시 클리어
            await self.clear_cache()
            
            # 주요 통화들의 캐시 새로고침
            major_currencies = ["USD", "JPY", "EUR", "GBP", "CNY", "AUD", "CAD", "CHF", "SGD", "HKD"]
            
            for currency_code in major_currencies:
                try:
                    rate_data = await self._get_rate_from_db(currency_code)
                    if rate_data:
                        await self._cache_rate(currency_code, rate_data)
                except Exception as e:
                    logger.warning(f"Failed to refresh cache for {currency_code}: {e}")
                    continue
            
            logger.info("All currency cache refreshed")
                
        except Exception as e:
            logger.error(f"Failed to refresh all currency cache: {e}")
            raise handle_cache_exception(e, "refresh_all_currency_cache")
    
    async def clear_all_cache(self):
        """
        모든 캐시 클리어 (clear_cache의 별칭)
        """
        await self.clear_cache()