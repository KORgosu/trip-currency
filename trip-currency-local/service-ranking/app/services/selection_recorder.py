"""
Selection Recorder - 사용자 선택 기록 서비스
DynamoDB에 사용자 여행지 선택 기록 저장
"""
import hashlib
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import uuid

from shared.database import DynamoDBHelper, RedisHelper
import logging
from shared.models import UserSelection, SelectionRecord
from shared.exceptions import DatabaseError, handle_database_exception
from shared.utils import SecurityUtils

logger = logging.getLogger(__name__)


class SelectionRecorder:
    """사용자 선택 기록자"""
    
    def __init__(self):
        self.redis_helper = RedisHelper()
        self.dynamodb_helper = None  # 초기화에서 설정
        self.table_name = "travel_destination_selections"
    
    async def initialize(self):
        """서비스 초기화"""
        try:
            # DynamoDB 헬퍼 초기화 (테이블이 존재하지 않을 수 있음)
            try:
                from shared.database import get_db_manager
                db_manager = get_db_manager()
                self.dynamodb_helper = DynamoDBHelper(self.table_name)
                logger.info("DynamoDB helper initialized for selections")
            except Exception as e:
                logger.warning(f"DynamoDB not available, using Redis fallback: {e}")
                self.dynamodb_helper = None
                
        except Exception as e:
            logger.error(f"Failed to initialize SelectionRecorder: {e}")
            raise
    
    async def record_selection(
        self,
        selection: UserSelection,
        client_ip: str,
        user_agent: str
    ) -> str:
        """
        사용자 선택 기록
        
        Args:
            selection: 사용자 선택 데이터
            client_ip: 클라이언트 IP
            user_agent: User Agent
            
        Returns:
            생성된 선택 기록 ID
        """
        try:
            # 선택 기록 ID 생성
            timestamp = datetime.utcnow()
            selection_id = f"sel_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # 개인정보 해시화
            ip_hash = self._hash_sensitive_data(client_ip)
            user_agent_hash = self._hash_sensitive_data(user_agent)
            
            # 국가명 조회
            country_name = await self._get_country_name(selection.country_code)
            
            # 선택 기록 생성
            selection_record = SelectionRecord(
                selection_date=timestamp.strftime('%Y-%m-%d'),
                selection_timestamp_userid=f"{timestamp.strftime('%Y%m%d%H%M%S')}_{selection.user_id}",
                country_code=selection.country_code,
                country_name=country_name,
                user_id=selection.user_id,
                session_id=selection.session_id,
                ip_address_hash=ip_hash,
                user_agent_hash=user_agent_hash,
                referrer=selection.referrer,
                created_at=timestamp,
                ttl=int((timestamp + timedelta(days=365)).timestamp())  # 1년 후 만료
            )
            
            # DynamoDB에 저장 시도
            if self.dynamodb_helper:
                try:
                    await self._save_to_dynamodb(selection_record)
                    logger.info("Selection recorded to DynamoDB", selection_id=selection_id)
                except Exception as e:
                    logger.warning(f"DynamoDB save failed, using Redis fallback: {e}")
                    await self._save_to_redis_fallback(selection_record)
            else:
                # DynamoDB 사용 불가 시 Redis에 저장
                await self._save_to_redis_fallback(selection_record)
            
            # 실시간 통계 업데이트
            await self._update_realtime_stats(selection.country_code)
            
            return selection_id
            
        except Exception as e:
            logger.error(f"Failed to record selection: {e}")
            raise handle_database_exception(e, "record_selection", self.table_name)
    
    async def _save_to_dynamodb(self, record: SelectionRecord):
        """DynamoDB에 선택 기록 저장"""
        try:
            item = {
                "selection_date": record.selection_date,
                "selection_timestamp_userid": record.selection_timestamp_userid,
                "country_code": record.country_code,
                "country_name": record.country_name,
                "user_id": record.user_id,
                "session_id": record.session_id,
                "ip_address_hash": record.ip_address_hash,
                "user_agent_hash": record.user_agent_hash,
                "referrer": record.referrer,
                "created_at": record.created_at.isoformat(),
                "ttl": record.ttl
            }
            
            # None 값 제거
            item = {k: v for k, v in item.items() if v is not None}
            
            await self.dynamodb_helper.put_item(item)
            
        except Exception as e:
            logger.error(f"Failed to save to DynamoDB: {e}")
            raise
    
    async def _save_to_redis_fallback(self, record: SelectionRecord):
        """Redis에 폴백 저장"""
        try:
            # Redis에 선택 기록 저장 (JSON 형태)
            redis_key = f"selection:{record.selection_date}:{record.selection_timestamp_userid}"
            
            record_data = {
                "selection_date": record.selection_date,
                "selection_timestamp_userid": record.selection_timestamp_userid,
                "country_code": record.country_code,
                "country_name": record.country_name,
                "user_id": record.user_id,
                "session_id": record.session_id,
                "created_at": record.created_at.isoformat(),
                "ttl": record.ttl
            }
            
            # 24시간 TTL로 저장
            await self.redis_helper.set_json(redis_key, record_data, 86400)
            
            logger.info("Selection saved to Redis fallback")
            
        except Exception as e:
            logger.error(f"Failed to save to Redis fallback: {e}")
            # Redis 저장도 실패하면 로그만 남기고 계속 진행
    
    async def _update_realtime_stats(self, country_code: str):
        """실시간 통계 업데이트"""
        try:
            today = datetime.utcnow().strftime('%Y-%m-%d')
            
            # 일일 카운터 증가
            daily_key = f"daily_count:{today}:{country_code}"
            await self.redis_helper.client.incr(daily_key)
            await self.redis_helper.client.expire(daily_key, 86400 * 7)  # 7일 보관
            
            # 전체 일일 카운터
            total_daily_key = f"daily_total:{today}"
            await self.redis_helper.client.incr(total_daily_key)
            await self.redis_helper.client.expire(total_daily_key, 86400 * 7)
            
            # 시간별 카운터 (실시간 모니터링용)
            hour = datetime.utcnow().strftime('%Y-%m-%d-%H')
            hourly_key = f"hourly_count:{hour}:{country_code}"
            await self.redis_helper.client.incr(hourly_key)
            await self.redis_helper.client.expire(hourly_key, 86400)  # 24시간 보관
            
        except Exception as e:
            logger.warning(f"Failed to update realtime stats: {e}")
            # 통계 업데이트 실패는 치명적이지 않음
    
    async def _get_country_name(self, country_code: str) -> str:
        """국가 코드에서 국가명 조회"""
        try:
            # 간단한 매핑 (실제로는 DB에서 조회)
            country_mapping = {
                "US": "미국",
                "JP": "일본", 
                "KR": "한국",
                "EU": "유럽연합",
                "GB": "영국",
                "CN": "중국",
                "AU": "호주",
                "CA": "캐나다",
                "CH": "스위스",
                "HK": "홍콩",
                "SG": "싱가포르"
            }
            
            return country_mapping.get(country_code, country_code)
            
        except Exception as e:
            logger.warning(f"Failed to get country name for {country_code}: {e}")
            return country_code
    
    def _hash_sensitive_data(self, data: str) -> str:
        """민감한 데이터 해시화"""
        if not data:
            return ""
        
        # SHA-256 해시 사용
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    async def close(self):
        """리소스 정리"""
        try:
            # 현재는 특별한 정리 작업 없음
            logger.info("SelectionRecorder closed")
        except Exception as e:
            logger.error(f"Error closing SelectionRecorder: {e}")
    
    async def record_country_click(
        self,
        country: str,
        client_ip: str,
        user_agent: str
    ) -> str:
        """
        나라 클릭 기록
        
        Args:
            country: 나라명
            client_ip: 클라이언트 IP
            user_agent: 사용자 에이전트
            
        Returns:
            클릭 기록 ID
        """
        try:
            # 클릭 기록 ID 생성
            click_id = SecurityUtils.generate_uuid()
            
            # 클릭 기록 데이터
            click_record = {
                "click_id": click_id,
                "country": country,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "date": datetime.utcnow().strftime("%Y-%m-%d")
            }
            
            # Redis에 클릭 기록 저장 (24시간 TTL)
            click_key = f"country_click:{click_id}"
            await self.redis_helper.setex(click_key, 86400, json.dumps(click_record))
            
            # 나라별 클릭수 증가
            from app.services.ranking_provider import RankingProvider
            ranking_provider = RankingProvider()
            await ranking_provider.initialize()
            await ranking_provider.increment_country_clicks(country)
            
            logger.info(f"Recorded country click: {country} (ID: {click_id})")
            return click_id
            
        except Exception as e:
            logger.error(f"Failed to record country click: {e}")
            raise DatabaseError(f"Failed to record country click: {e}")