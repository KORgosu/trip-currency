"""
Data Processor - 수집된 데이터 처리 및 저장
데이터 정제, 변환, 저장 및 메시징 처리
"""
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
shared_dir = os.path.join(parent_dir, 'shared')

sys.path.insert(0, parent_dir)
sys.path.insert(0, shared_dir)

from shared.database import MySQLHelper, RedisHelper, get_db_manager
from shared.logging import get_logger
from shared.models import CollectionResult, RawExchangeRateData, ExchangeRate
from shared.exceptions import DatabaseError, DataProcessingError
from shared.utils import DateTimeUtils, DataUtils, PerformanceUtils, SecurityUtils
from shared.messaging import send_exchange_rate_update

logger = get_logger(__name__)


class DataProcessor:
    """데이터 처리자"""
    
    def __init__(self):
        # __init__에서는 helper 객체를 미리 생성하지 않습니다.
        self._mysql_helper: Optional[MySQLHelper] = None
        self._redis_helper: Optional[RedisHelper] = None
        self.batch_size = 100
        self.duplicate_check_enabled = True

    # --- [핵심 수정: @property 추가] ---
    # 각 helper를 처음 사용할 때 생성하는 프로퍼티(property)를 추가합니다.
    @property
    def mysql_helper(self) -> MySQLHelper:
        if self._mysql_helper is None:
            # self.mysql_helper가 처음 호출되는 순간 객체를 생성합니다.
            self._mysql_helper = MySQLHelper()
        return self._mysql_helper

    @property
    def redis_helper(self) -> RedisHelper:
        if self._redis_helper is None:
            # self.redis_helper가 처음 호출되는 순간 객체를 생성합니다.
            self._redis_helper = RedisHelper()
        return self._redis_helper
    
    async def initialize(self):
        """처리자 초기화"""
        try:
            logger.info("Data processor initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize data processor", error=e)
            raise
    
    @PerformanceUtils.measure_time
    async def process_exchange_rate_data(self, collection_result: CollectionResult):
        """환율 데이터 처리"""
        if not collection_result.success or not collection_result.raw_data:
            logger.warning("No data to process", source=collection_result.source)
            return
        
        logger.info(
            "Processing exchange rate data",
            source=collection_result.source,
            data_count=len(collection_result.raw_data)
        )
        
        try:
            # 데이터 정제 및 변환
            processed_data = await self._clean_and_transform_data(
                collection_result.raw_data, 
                collection_result.source
            )
            
            if not processed_data:
                logger.warning("No valid data after cleaning", source=collection_result.source)
                return
            
            # 중복 데이터 체크 및 필터링
            if self.duplicate_check_enabled:
                processed_data = await self._filter_duplicates(processed_data)
            
            # 데이터베이스에 저장
            saved_count = await self._save_to_database(processed_data)
            
            # Redis 캐시 업데이트
            await self._update_cache(processed_data)
            
            # 메시징 시스템으로 이벤트 전송
            await self._send_update_events(processed_data, collection_result)
            
            logger.info(
                "Data processing completed",
                source=collection_result.source,
                processed_count=len(processed_data),
                saved_count=saved_count
            )
            
        except Exception as e:
            logger.error("Failed to process exchange rate data", error=e, source=collection_result.source)
            raise DataProcessingError(
                f"Failed to process data from {collection_result.source}",
                data_type="exchange_rate",
                processing_step="processing"
            )
    
    async def _clean_and_transform_data(
        self, 
        raw_data: List[RawExchangeRateData], 
        source: str
    ) -> List[ExchangeRate]:
        """데이터 정제 및 변환"""
        processed_data = []
        
        for raw_item in raw_data:
            try:
                # 환율 값 정규화
                base_rate = DataUtils.safe_decimal(raw_item.rate, 4)
                
                # TTS/TTB 계산 (송금 시 수수료 적용)
                tts = base_rate * Decimal('1.02')  # 송금 보낼 때 2% 수수료
                ttb = base_rate * Decimal('0.98')  # 받을 때 2% 할인
                
                # 통화명 매핑
                currency_name = self._get_currency_name(raw_item.currency_code)
                
                # ExchangeRate 객체 생성
                exchange_rate = ExchangeRate(
                    currency_code=raw_item.currency_code,
                    currency_name=currency_name,
                    deal_base_rate=base_rate,
                    tts=tts,
                    ttb=ttb,
                    source=source,
                    recorded_at=raw_item.timestamp,
                    updated_at=raw_item.timestamp  # updated_at 필드 추가
                )
                
                processed_data.append(exchange_rate)
                
            except Exception as e:
                logger.warning(
                    "Failed to process raw data item",
                    currency=raw_item.currency_code,
                    error=str(e),
                    source=source
                )
                continue
        
        logger.debug(
            "Data cleaning completed",
            source=source,
            original_count=len(raw_data),
            processed_count=len(processed_data)
        )
        
        return processed_data
    
    def _get_currency_name(self, currency_code: str) -> str:
        """통화 코드에서 통화명 반환"""
        currency_names = {
            "USD": "미국 달러",
            "JPY": "일본 엔",
            "EUR": "유럽연합 유로",
            "GBP": "영국 파운드",
            "CNY": "중국 위안",
            "AUD": "호주 달러",
            "CAD": "캐나다 달러",
            "CHF": "스위스 프랑",
            "HKD": "홍콩 달러",
            "SGD": "싱가포르 달러"
        }
        return currency_names.get(currency_code, currency_code)
    
    async def _filter_duplicates(self, processed_data: List[ExchangeRate]) -> List[ExchangeRate]:
        """
        중복 데이터 필터링

        개선된 로직:
        - 최근 10분 내 동일 소스의 동일 통화 데이터만 중복으로 처리
        - 환율 변동을 고려하여 0.1% 이내 차이는 동일 값으로 처리
        - 타임스탬프가 최신인 데이터는 항상 저장
        """
        if not processed_data:
            return []

        try:
            # 최근 10분 내 데이터만 중복 체크 (환율 변동 고려)
            ten_minutes_ago = DateTimeUtils.utc_now() - timedelta(minutes=10)

            filtered_data = []

            for item in processed_data:
                # 중복 체크 쿼리 (개선됨)
                query = """
                    SELECT COUNT(*) as count, MAX(recorded_at) as latest_timestamp
                    FROM exchange_rate_history
                    WHERE currency_code = %s
                        AND source = %s
                        AND recorded_at > %s
                        AND ABS(deal_base_rate - %s) < (%s * 0.001)  -- 0.1%% 이내 차이
                """

                deal_rate = float(item.deal_base_rate)
                result = await self.mysql_helper.execute_query(
                    query,
                    (item.currency_code, item.source, ten_minutes_ago,
                     deal_rate, deal_rate)
                )

                if result and result[0]['count'] == 0:
                    # 중복이 아닌 경우만 추가
                    filtered_data.append(item)
                    logger.debug(
                        "New data accepted",
                        currency=item.currency_code,
                        source=item.source,
                        rate=float(item.deal_base_rate)
                    )
                else:
                    # 중복 데이터이지만 타임스탬프가 더 최신인 경우 업데이트
                    latest_timestamp = result[0]['latest_timestamp'] if result else None
                    if latest_timestamp and item.recorded_at > latest_timestamp:
                        filtered_data.append(item)
                        logger.debug(
                            "Updated data accepted (newer timestamp)",
                            currency=item.currency_code,
                            source=item.source,
                            old_timestamp=latest_timestamp.isoformat(),
                            new_timestamp=item.recorded_at.isoformat()
                        )
                    else:
                        logger.debug(
                            "Duplicate data filtered",
                            currency=item.currency_code,
                            source=item.source,
                            rate=float(item.deal_base_rate),
                            existing_count=result[0]['count'] if result else 0
                        )

            logger.info(
                "Duplicate filtering completed",
                original_count=len(processed_data),
                filtered_count=len(filtered_data),
                duplicates_filtered=len(processed_data) - len(filtered_data)
            )

            return filtered_data

        except Exception as e:
            logger.warning("Duplicate filtering failed, proceeding with all data", error=e)
            return processed_data
    
    async def _save_to_database(self, processed_data: List[ExchangeRate]) -> int:
        """데이터베이스에 저장"""
        if not processed_data:
            return 0
        
        try:
            saved_count = 0
            
            # 배치 단위로 저장
            for i in range(0, len(processed_data), self.batch_size):
                batch = processed_data[i:i + self.batch_size]
                
                for item in batch:
                    try:
                        # INSERT 쿼리 실행
                        query = """
                            INSERT INTO exchange_rate_history 
                            (currency_code, currency_name, deal_base_rate, tts, ttb, source, recorded_at, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        
                        await self.mysql_helper.execute_insert(
                            query,
                            (
                                item.currency_code,
                                item.currency_name,
                                float(item.deal_base_rate),
                                float(item.tts) if item.tts else None,
                                float(item.ttb) if item.ttb else None,
                                item.source,
                                item.recorded_at,
                                DateTimeUtils.utc_now()
                            )
                        )
                        
                        saved_count += 1
                        
                    except Exception as e:
                        logger.warning(
                            "Failed to save individual record",
                            currency=item.currency_code,
                            error=str(e)
                        )
                        continue
                
                # 배치 간 짧은 대기
                if i + self.batch_size < len(processed_data):
                    await asyncio.sleep(0.1)
            
            logger.info(
                "Database save completed",
                total_records=len(processed_data),
                saved_records=saved_count
            )
            
            return saved_count
            
        except Exception as e:
            logger.error("Failed to save to database", error=e)
            raise DatabaseError(
                "Failed to save exchange rate data",
                operation="batch_insert",
                table="exchange_rate_history"
            )
    
    async def _update_cache(self, processed_data: List[ExchangeRate]):
        """Redis 캐시 업데이트"""
        try:
            cache_updates = 0
            
            for item in processed_data:
                try:
                    # 캐시 키 생성
                    cache_key = f"rate:{item.currency_code}"
                    
                    # 캐시 데이터 구성
                    cache_data = {
                        'currency_name': item.currency_name,
                        'deal_base_rate': str(item.deal_base_rate),
                        'tts': str(item.tts) if item.tts else '',
                        'ttb': str(item.ttb) if item.ttb else '',
                        'source': item.source,
                        'last_updated_at': DateTimeUtils.to_iso_string(item.recorded_at)
                    }
                    
                    # Redis에 저장 (TTL: 1시간)
                    await self.redis_helper.set_hash(cache_key, cache_data, 3600)
                    cache_updates += 1
                    
                except Exception as e:
                    logger.warning(
                        "Failed to update cache for currency",
                        currency=item.currency_code,
                        error=str(e)
                    )
                    continue
            
            logger.debug(
                "Cache update completed",
                total_items=len(processed_data),
                cache_updates=cache_updates
            )
            
        except Exception as e:
            # 캐시 업데이트 실패는 로그만 남기고 계속 진행
            logger.warning("Cache update failed", error=e)
    
    async def _send_update_events(self, processed_data: List[ExchangeRate], collection_result: CollectionResult):
        """업데이트 이벤트 전송"""
        try:
            from shared.messaging import (
                send_new_data_received, 
                send_exchange_rate_updated, 
                send_data_processing_completed,
                send_cache_invalidation
            )
            
            events_sent = 0
            
            # 1. 새로운 데이터 수신 이벤트 발행
            new_data_event = {
                "source": collection_result.source,
                "data_count": len(processed_data),
                "collection_time": DateTimeUtils.to_iso_string(collection_result.collection_time),
                "processing_time_ms": collection_result.processing_time_ms,
                "correlation_id": SecurityUtils.generate_correlation_id()
            }
            
            success = await send_new_data_received(new_data_event)
            if success:
                events_sent += 1
                logger.info("New data received event sent", source=collection_result.source)
            
            # 2. 각 환율 데이터 업데이트 이벤트 발행
            for item in processed_data:
                try:
                    # 이벤트 데이터 구성
                    event_data = {
                        "currency_code": item.currency_code,
                        "currency_name": item.currency_name,
                        "deal_base_rate": float(item.deal_base_rate),
                        "tts": float(item.tts) if item.tts else None,
                        "ttb": float(item.ttb) if item.ttb else None,
                        "source": item.source,
                        "recorded_at": DateTimeUtils.to_iso_string(item.recorded_at),
                        "updated_at": DateTimeUtils.to_iso_string(DateTimeUtils.utc_now())
                    }
                    
                    # 환율 업데이트 이벤트 전송
                    success = await send_exchange_rate_updated(event_data)
                    
                    if success:
                        events_sent += 1
                    
                except Exception as e:
                    logger.warning(
                        "Failed to send exchange rate update event",
                        currency=item.currency_code,
                        error=str(e)
                    )
                    continue
            
            # 3. 데이터 처리 완료 이벤트 발행
            processing_completed_event = {
                "source": collection_result.source,
                "total_processed": len(processed_data),
                "processing_time_ms": collection_result.processing_time_ms,
                "completed_at": DateTimeUtils.to_iso_string(DateTimeUtils.utc_now()),
                "correlation_id": SecurityUtils.generate_correlation_id()
            }
            
            success = await send_data_processing_completed(processing_completed_event)
            if success:
                events_sent += 1
                logger.info("Data processing completed event sent", source=collection_result.source)
            
            # 4. 캐시 무효화 이벤트 발행
            cache_invalidation_event = {
                "cache_keys": [f"exchange_rate:{item.currency_code}" for item in processed_data],
                "invalidation_type": "exchange_rate_update",
                "invalidated_at": DateTimeUtils.to_iso_string(DateTimeUtils.utc_now())
            }
            
            success = await send_cache_invalidation(cache_invalidation_event)
            if success:
                events_sent += 1
                logger.info("Cache invalidation event sent")
            
            logger.info(
                "Update events sent successfully",
                total_items=len(processed_data),
                events_sent=events_sent,
                source=collection_result.source
            )
            
        except Exception as e:
            # 이벤트 전송 실패는 로그만 남기고 계속 진행
            logger.warning("Failed to send update events", error=e)
    
    
    async def cleanup_old_data(self, retention_days: int = 365):
        """오래된 데이터 정리"""
        logger.info("Starting data cleanup", retention_days=retention_days)
        
        try:
            cutoff_date = DateTimeUtils.utc_now() - timedelta(days=retention_days)
            
            # 오래된 이력 데이터 삭제
            delete_query = """
                DELETE FROM exchange_rate_history
                WHERE recorded_at < %s
            """
            
            deleted_count = await self.mysql_helper.execute_update(delete_query, (cutoff_date,))
            
            logger.info(
                "Data cleanup completed",
                cutoff_date=DateTimeUtils.to_iso_string(cutoff_date),
                deleted_records=deleted_count
            )
            
        except Exception as e:
            logger.error("Failed to cleanup old data", error=e)
            raise DatabaseError(
                "Failed to cleanup old exchange rate data",
                operation="delete",
                table="exchange_rate_history"
            )
    
    async def generate_daily_aggregates(self, target_date: datetime = None):
        if target_date is None:
            target_date = DateTimeUtils.utc_now() - timedelta(days=1)
        
        logger.info("Generating daily aggregates", target_date=DateTimeUtils.get_date_string(target_date))
        
        try:
            aggregate_query = """
                INSERT INTO daily_exchange_rates 
                (currency_code, trade_date, open_rate, close_rate, high_rate, low_rate, avg_rate, volume, volatility, updated_at)
                SELECT 
                    currency_code,
                    DATE(recorded_at) as trade_date,
                    (SELECT deal_base_rate FROM exchange_rate_history h2 
                        WHERE h2.currency_code = h1.currency_code 
                        AND DATE(h2.recorded_at) = %s
                        ORDER BY h2.recorded_at ASC LIMIT 1) as open_rate,
                    (SELECT deal_base_rate FROM exchange_rate_history h2 
                        WHERE h2.currency_code = h1.currency_code 
                        AND DATE(h2.recorded_at) = %s
                        ORDER BY h2.recorded_at DESC LIMIT 1) as close_rate,
                    MAX(deal_base_rate) as high_rate,
                    MIN(deal_base_rate) as low_rate,
                    AVG(deal_base_rate) as avg_rate,
                    COUNT(*) as volume,
                    STDDEV(deal_base_rate) as volatility,
                    CURRENT_TIMESTAMP as updated_at
                FROM exchange_rate_history h1
                WHERE DATE(recorded_at) = %s
                GROUP BY currency_code, DATE(recorded_at)
                ON DUPLICATE KEY UPDATE
                    open_rate = VALUES(open_rate),
                    close_rate = VALUES(close_rate),
                    high_rate = VALUES(high_rate),
                    low_rate = VALUES(low_rate),
                    avg_rate = VALUES(avg_rate),
                    volume = VALUES(volume),
                    volatility = VALUES(volatility),
                    updated_at = VALUES(updated_at)
            """
            
            target_date_str = target_date.date().isoformat()
            
            affected_rows = await self.mysql_helper.execute_update(
                aggregate_query, 
                # 쿼리 안의 %s 3개에 각각 값을 전달
                (target_date_str, target_date_str, target_date_str)
            )
            
            logger.info(
                "Daily aggregates generated",
                target_date=DateTimeUtils.get_date_string(target_date),
                affected_rows=affected_rows
            )
            
        except Exception as e:
            logger.error("Failed to generate daily aggregates", error=e, exc_info=True)
            raise DatabaseError(
                "Failed to generate daily aggregates",
                operation="aggregate",
                table="daily_exchange_rates"
            )
    
    async def close(self):
        """리소스 정리"""
        logger.info("Data processor closed")