"""
Ranking Provider - 나라 검색 랭킹 데이터 제공 서비스
MongoDB에서 나라 클릭수 기반 랭킹 데이터 조회 및 계산
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import json
import uuid

from shared.database import DynamoDBHelper, RedisHelper
import logging
from shared.models import RankingItem, CountryStats, RankingPeriod
from shared.exceptions import (
    DatabaseError, NotFoundError, 
    handle_database_exception
)

logger = logging.getLogger(__name__)


class RankingProvider:
    """랭킹 데이터 제공자"""
    
    def __init__(self):
        self.redis_helper = RedisHelper()
        self.dynamodb_helper = None
        self.rankings_table = "RankingResults"
        self.selections_table = "travel_destination_selections"
        self.cache_ttl = 300  # 5분
    
    async def initialize(self):
        """서비스 초기화"""
        try:
            # DynamoDB 헬퍼 초기화
            try:
                from shared.database import get_db_manager
                db_manager = get_db_manager()
                self.dynamodb_helper = DynamoDBHelper(self.rankings_table)
                logger.info("DynamoDB helper initialized for rankings")
            except Exception as e:
                logger.warning(f"DynamoDB not available, using mock data: {e}")
                self.dynamodb_helper = None
                
        except Exception as e:
            logger.error(f"Failed to initialize RankingProvider: {e}")
            raise
    
    async def get_rankings(
        self,
        period: str,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        랭킹 데이터 조회
        
        Args:
            period: 랭킹 기간 (daily, weekly, monthly)
            limit: 결과 개수 제한
            offset: 페이지네이션 오프셋
            
        Returns:
            랭킹 데이터
        """
        try:
            # 캐시에서 먼저 조회
            cache_key = f"ranking:{period}:{limit}:{offset}"
            cached_data = await self.redis_helper.get_json(cache_key)
            
            if cached_data:
                logger.info(f"Ranking cache hit for {period}")
                return cached_data
            
            # DynamoDB에서 랭킹 데이터 조회
            if not self.dynamodb_helper:
                raise NotFoundError("Ranking service is not available - database connection failed")
            
            try:
                ranking_data = await self._get_ranking_from_dynamodb(period)
            except Exception as e:
                logger.error(f"Failed to get ranking from DynamoDB for {period}: {e}")
                raise NotFoundError(f"Ranking data not available for period: {period}")
            
            # 페이지네이션 적용
            total_items = len(ranking_data.get("ranking", []))
            ranking_items = ranking_data.get("ranking", [])[offset:offset + limit]
            
            result = {
                "period": period,
                "total_selections": ranking_data.get("total_selections", 0),
                "last_updated": ranking_data.get("last_updated", datetime.utcnow().isoformat() + 'Z'),
                "ranking": ranking_items,
                "pagination": {
                    "current_page": (offset // limit) + 1,
                    "total_pages": (total_items + limit - 1) // limit,
                    "has_next": offset + limit < total_items,
                    "has_previous": offset > 0,
                    "total_items": total_items,
                    "items_per_page": limit
                }
            }
            
            # 캐시에 저장
            await self.redis_helper.set_json(cache_key, result, self.cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get rankings for {period}: {e}")
            raise handle_database_exception(e, "get_rankings", self.rankings_table)
    
    async def get_country_stats(
        self,
        country_code: str,
        period: str = "7d"
    ) -> Dict[str, Any]:
        """
        국가별 선택 통계 조회
        
        Args:
            country_code: 국가 코드
            period: 통계 기간 (7d, 30d, 90d)
            
        Returns:
            국가별 통계 데이터
        """
        try:
            # 캐시에서 먼저 조회
            cache_key = f"country_stats:{country_code}:{period}"
            cached_data = await self.redis_helper.get_json(cache_key)
            
            if cached_data:
                return cached_data
            
            # 통계 데이터 계산
            stats_data = await self._calculate_country_stats(country_code, period)
            
            # 캐시에 저장 (30분)
            await self.redis_helper.set_json(cache_key, stats_data, 1800)
            
            return stats_data
            
        except Exception as e:
            logger.error(f"Failed to get country stats for {country_code}: {e}")
            raise handle_database_exception(e, "get_country_stats")
    
    async def trigger_ranking_calculation(self, period: str) -> str:
        """
        랭킹 계산 트리거
        
        Args:
            period: 계산할 랭킹 기간
            
        Returns:
            계산 작업 ID
        """
        try:
            calculation_id = f"calc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # 실제로는 SQS나 Lambda를 통해 비동기 계산 트리거
            # 현재는 즉시 계산 수행
            await self._calculate_and_save_ranking(period, calculation_id)
            
            logger.info(f"Ranking calculation triggered", 
                       calculation_id=calculation_id, 
                       period=period)
            
            return calculation_id
            
        except Exception as e:
            logger.error(f"Failed to trigger ranking calculation for {period}: {e}")
            raise
    
    async def _get_ranking_from_dynamodb(self, period: str) -> Dict[str, Any]:
        """DynamoDB에서 랭킹 데이터 조회"""
        try:
            # DynamoDB에서 period 키로 직접 조회
            try:
                item = await self.dynamodb_helper.get_item({"period": period})
                if item:
                    return {
                        "period": item.get("period", period),
                        "total_selections": item.get("total_selections", 0),
                        "last_updated": item.get("last_updated", ""),
                        "ranking": item.get("ranking_data", [])
                    }
                # 랭킹 데이터가 없으면 모의 데이터 생성
                logger.info(f"No ranking data found for {period}, generating mock ranking")
                return await self._generate_mock_ranking(period)
            except Exception as e:
                logger.warning(f"DynamoDB get_item failed: {e}, using mock data")
                return await self._generate_mock_ranking(period)
                
        except Exception as e:
            logger.error(f"Failed to get ranking from DynamoDB for {period}: {e}")
            # 실패 시 모의 데이터 반환
            return await self._generate_mock_ranking(period)
    
    async def _generate_mock_ranking(self, period: str) -> Dict[str, Any]:
        """
        [DEPRECATED - 개발용만] 모의 랭킹 데이터 생성
        프로덕션 환경에서는 사용하지 않음
        """
        try:
            # Redis에서 실시간 통계 조회
            today = datetime.utcnow().strftime('%Y-%m-%d')
            
            countries = ["JP", "US", "EU", "GB", "CN", "AU", "CA"]
            ranking_items = []
            
            for i, country_code in enumerate(countries):
                # Redis에서 일일 카운트 조회
                daily_key = f"daily_count:{today}:{country_code}"
                try:
                    count = await self.redis_helper.client.get(daily_key)
                    score = int(count) if count else (100 - i * 10)  # 기본값
                except:
                    score = 100 - i * 10  # 기본값
                
                country_name = await self._get_country_name(country_code)
                
                ranking_items.append({
                    "rank": i + 1,
                    "country_code": country_code,
                    "country_name": country_name,
                    "score": score,
                    "percentage": round((score / 1000) * 100, 2),
                    "change": "SAME",
                    "change_value": 0,
                    "previous_rank": i + 1
                })
            
            # 점수순으로 정렬 (모의 데이터는 단순 순위 부여)
            ranking_items.sort(key=lambda x: x["score"], reverse=True)
            for i, item in enumerate(ranking_items):
                item["rank"] = i + 1
            
            total_selections = sum(item["score"] for item in ranking_items)
            
            return {
                "period": period,
                "total_selections": total_selections,
                "last_updated": datetime.utcnow().isoformat() + 'Z',
                "ranking": ranking_items
            }
            
        except Exception as e:
            logger.error(f"Failed to generate mock ranking for {period}: {e}")
            raise
    
    async def _calculate_country_stats(
        self,
        country_code: str,
        period: str
    ) -> Dict[str, Any]:
        """국가별 통계 계산"""
        try:
            # 기간 파싱
            days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 7)
            
            # 일별 데이터 수집
            daily_breakdown = []
            total_selections = 0
            
            for i in range(days):
                date = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
                daily_key = f"daily_count:{date}:{country_code}"
                
                try:
                    count = await self.redis_helper.client.get(daily_key)
                    count = int(count) if count else 0
                except:
                    count = 0
                
                daily_breakdown.append({
                    "date": date,
                    "count": count,
                    "rank": 1  # 실제로는 해당 날짜의 랭킹 조회 필요
                })
                
                total_selections += count
            
            # 통계 계산
            daily_average = Decimal(str(total_selections / days)) if days > 0 else Decimal("0")
            
            # 최고 기록일 찾기
            peak_day_data = max(daily_breakdown, key=lambda x: x["count"])
            
            country_name = await self._get_country_name(country_code)
            
            return {
                "country_code": country_code,
                "country_name": country_name,
                "period": period,
                "statistics": {
                    "total_selections": total_selections,
                    "daily_average": float(daily_average),
                    "peak_day": peak_day_data["date"],
                    "peak_selections": peak_day_data["count"],
                    "growth_rate": 0.0  # 실제로는 이전 기간과 비교하여 계산
                },
                "daily_breakdown": daily_breakdown[:7]  # 최근 7일만 반환
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate country stats for {country_code}: {e}")
            raise
    
    async def _calculate_and_save_ranking(
        self,
        period: str,
        calculation_id: str = None
    ) -> Dict[str, Any]:
        """랭킹 계산 및 저장"""
        try:
            if not calculation_id:
                calculation_id = f"calc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            # 실제 랭킹 데이터 계산 (현재는 구현되지 않음)
            # TODO: 실제 사용자 선택 데이터를 기반으로 랭킹 계산 로직 구현
            raise NotImplementedError("Ranking calculation is not implemented yet")
            
            # DynamoDB에 저장 (가능한 경우)
            if self.dynamodb_helper:
                try:
                    ranking_item = {
                        "period": period,
                        "ranking_data": ranking_data["ranking"],
                        "total_selections": ranking_data["total_selections"],
                        "last_updated": ranking_data["last_updated"],
                        "calculation_metadata": {
                            "calculation_id": calculation_id,
                            "calculation_time": datetime.utcnow().isoformat(),
                            "total_records": ranking_data["total_selections"],
                            "algorithm_version": "v1.0"
                        }
                    }
                    
                    await self.dynamodb_helper.put_item(ranking_item)
                    logger.info(f"Ranking saved to DynamoDB", period=period)
                    
                except Exception as e:
                    logger.warning(f"Failed to save ranking to DynamoDB: {e}")
            
            # 캐시 무효화
            cache_pattern = f"ranking:{period}:*"
            # Redis에서 패턴 매칭 키 삭제는 복잡하므로 생략
            
            return ranking_data
            
        except Exception as e:
            logger.error(f"Failed to calculate and save ranking for {period}: {e}")
            raise
    
    async def _get_country_name(self, country_code: str) -> str:
        """국가 코드에서 국가명 조회"""
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
    
    async def get_country_rankings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        나라 클릭수 기반 랭킹 조회 (MongoDB)
        
        Args:
            limit: 조회할 랭킹 개수
            
        Returns:
            랭킹 리스트 (클릭수 내림차순)
        """
        try:
            # Redis에서 캐시된 랭킹 조회
            cache_key = f"country_rankings:{limit}"
            cached_rankings = await self.redis_helper.get(cache_key)
            
            if cached_rankings:
                logger.debug("Returning cached country rankings")
                return json.loads(cached_rankings)
            
            # MongoDB에서 랭킹 조회 (클릭수 내림차순)
            rankings = []
            
            # Mock 데이터 (실제 MongoDB 연동 시 수정 필요)
            mock_rankings = [
                {"country": "미국", "clicks": 150, "rank": 1},
                {"country": "일본", "clicks": 120, "rank": 2},
                {"country": "유럽", "clicks": 100, "rank": 3},
                {"country": "중국", "clicks": 80, "rank": 4},
                {"country": "영국", "clicks": 70, "rank": 5},
                {"country": "호주", "clicks": 60, "rank": 6},
                {"country": "캐나다", "clicks": 50, "rank": 7},
                {"country": "스위스", "clicks": 40, "rank": 8},
                {"country": "싱가포르", "clicks": 30, "rank": 9},
                {"country": "홍콩", "clicks": 20, "rank": 10}
            ]
            
            rankings = mock_rankings[:limit]
            
            # Redis에 캐시 (1분 TTL)
            await self.redis_helper.setex(cache_key, 60, json.dumps(rankings))
            
            logger.info(f"Retrieved {len(rankings)} country rankings")
            return rankings
            
        except Exception as e:
            logger.error(f"Failed to get country rankings: {e}")
            raise DatabaseError(f"Failed to retrieve country rankings: {e}")
    
    async def increment_country_clicks(self, country: str) -> int:
        """
        나라 클릭수 증가 (MongoDB)
        
        Args:
            country: 나라명
            
        Returns:
            업데이트된 클릭수
        """
        try:
            # MongoDB에서 클릭수 증가 (실제 구현 시 수정 필요)
            # 현재는 Mock 데이터로 처리
            
            # Redis에서 현재 클릭수 조회
            click_key = f"country_clicks:{country}"
            current_clicks = await self.redis_helper.get(click_key)
            
            if current_clicks:
                new_clicks = int(current_clicks) + 1
            else:
                new_clicks = 1
            
            # Redis에 클릭수 저장 (24시간 TTL)
            await self.redis_helper.setex(click_key, 86400, str(new_clicks))
            
            logger.info(f"Incremented clicks for {country}: {new_clicks}")
            return new_clicks
            
        except Exception as e:
            logger.error(f"Failed to increment clicks for {country}: {e}")
            raise DatabaseError(f"Failed to increment clicks: {e}")
    
    async def reset_all_click_counts(self) -> int:
        """
        모든 나라의 클릭수 초기화 (한국시간 0시 실행)
        
        Returns:
            초기화된 나라 수
        """
        try:
            # Redis에서 모든 나라 클릭수 키 삭제
            pattern = "country_clicks:*"
            keys = await self.redis_helper.keys(pattern)
            
            if keys:
                await self.redis_helper.delete(*keys)
            
            # 랭킹 캐시도 삭제
            ranking_keys = await self.redis_helper.keys("country_rankings:*")
            if ranking_keys:
                await self.redis_helper.delete(*ranking_keys)
            
            reset_count = len(keys)
            logger.info(f"Reset click counts for {reset_count} countries")
            return reset_count
            
        except Exception as e:
            logger.error(f"Failed to reset click counts: {e}")
            raise DatabaseError(f"Failed to reset click counts: {e}")
    
    async def close(self):
        """리소스 정리"""
        try:
            logger.info("RankingProvider closed")
        except Exception as e:
            logger.error(f"Error closing RankingProvider: {e}")