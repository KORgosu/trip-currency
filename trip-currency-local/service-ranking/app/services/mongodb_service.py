"""
MongoDB Service - 클릭수 기반 랭킹 데이터 관리
MongoDB를 사용한 나라별 클릭수 저장 및 랭킹 조회
"""
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
except ImportError:
    # motor가 설치되지 않은 경우를 위한 대체 구현
    AsyncIOMotorClient = None
    AsyncIOMotorDatabase = None
    AsyncIOMotorCollection = None

from shared.config import get_config
from shared.exceptions import DatabaseError
from shared.utils import DateTimeUtils

logger = logging.getLogger(__name__)


class MongoDBService:
    """MongoDB 연동 서비스"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.country_clicks_collection: Optional[AsyncIOMotorCollection] = None
        self.click_history_collection: Optional[AsyncIOMotorCollection] = None
        self.connected = False
        
        # 컬렉션명
        self.COUNTRY_CLICKS_COLLECTION = "country_clicks"
        self.CLICK_HISTORY_COLLECTION = "click_history"
    
    async def connect(self):
        """MongoDB 연결"""
        try:
            if not AsyncIOMotorClient:
                logger.warning("Motor not installed, using mock MongoDB service")
                self.connected = False
                return
            
            config = get_config()
            
            # MongoDB 연결 정보
            host = os.getenv("MONGODB_HOST", "localhost")
            port = int(os.getenv("MONGODB_PORT", "27017"))
            username = os.getenv("MONGODB_USER", "")
            password = os.getenv("MONGODB_PASSWORD", "")
            database = os.getenv("MONGODB_DATABASE", "currency_db")
            
            # 연결 문자열 구성
            if username and password:
                connection_string = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource=admin"
            else:
                connection_string = f"mongodb://{host}:{port}/{database}"
            
            # MongoDB 클라이언트 생성
            self.client = AsyncIOMotorClient(
                connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # 연결 테스트
            await self.client.admin.command('ping')
            
            # 데이터베이스 및 컬렉션 설정
            self.db = self.client[database]
            self.country_clicks_collection = self.db[self.COUNTRY_CLICKS_COLLECTION]
            self.click_history_collection = self.db[self.CLICK_HISTORY_COLLECTION]
            
            # 인덱스 생성
            await self._create_indexes()
            
            self.connected = True
            logger.info(f"MongoDB connected successfully: {host}:{port}/{database}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.connected = False
            # 연결 실패 시에도 서비스는 계속 동작 (Redis 폴백 사용)
    
    async def _create_indexes(self):
        """MongoDB 인덱스 생성"""
        try:
            if not self.connected:
                return
            
            # country_clicks 컬렉션 인덱스
            await self.country_clicks_collection.create_index([
                ("country_code", 1),
                ("date", 1)
            ], unique=True)
            
            await self.country_clicks_collection.create_index([
                ("daily_clicks", -1),
                ("date", 1)
            ])
            
            # click_history 컬렉션 인덱스
            await self.click_history_collection.create_index([
                ("country_code", 1),
                ("date", 1)
            ], unique=True)
            
            logger.info("MongoDB indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Failed to create MongoDB indexes: {e}")
    
    async def increment_country_clicks(self, country_code: str, country_name: str = None) -> Dict:
        """
        나라 클릭수 증가 (원자적 연산)
        
        Args:
            country_code: 국가 코드
            country_name: 국가명 (선택사항)
            
        Returns:
            업데이트된 클릭수 정보
        """
        try:
            if not self.connected:
                # MongoDB 연결 실패 시 Mock 데이터 반환
                return await self._mock_increment_clicks(country_code, country_name)
            
            today = DateTimeUtils.kst_now().strftime('%Y-%m-%d')
            now = DateTimeUtils.kst_now()
            
            # 국가명이 없으면 기본값 사용
            if not country_name:
                country_name = await self._get_country_name(country_code)
            
            # upsert 연산으로 클릭수 증가
            result = await self.country_clicks_collection.find_one_and_update(
                {
                    "country_code": country_code.upper(),
                    "date": today
                },
                {
                    "$inc": {
                        "daily_clicks": 1,
                        "total_clicks": 1
                    },
                    "$set": {
                        "country_name": country_name,
                        "last_updated": now,
                        "updated_at": now
                    },
                    "$setOnInsert": {
                        "created_at": now
                    }
                },
                upsert=True,
                return_document=True
            )
            
            # 현재 랭킹 조회
            current_ranking = await self.get_country_ranking(country_code, today)
            
            logger.info(f"Incremented clicks for {country_code}: {result['daily_clicks']} (rank: {current_ranking})")
            
            return {
                "country_code": country_code.upper(),
                "country_name": country_name,
                "daily_clicks": result['daily_clicks'],
                "total_clicks": result['total_clicks'],
                "current_rank": current_ranking,
                "date": today,
                "last_updated": result['last_updated'].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to increment clicks for {country_code}: {e}")
            raise DatabaseError(f"Failed to increment clicks: {e}")
    
    async def get_daily_rankings(self, limit: int = 10, date: str = None) -> List[Dict]:
        """
        일일 랭킹 조회 (클릭수 내림차순)
        
        Args:
            limit: 조회할 랭킹 개수
            date: 조회할 날짜 (YYYY-MM-DD), None이면 오늘
            
        Returns:
            랭킹 리스트
        """
        try:
            if not self.connected:
                return await self._mock_get_rankings(limit)
            
            if not date:
                date = DateTimeUtils.kst_now().strftime('%Y-%m-%d')
            
            # 클릭수 내림차순으로 조회
            cursor = self.country_clicks_collection.find(
                {"date": date}
            ).sort("daily_clicks", -1).limit(limit)
            
            rankings = []
            rank = 1
            async for doc in cursor:
                rankings.append({
                    "rank": rank,
                    "country_code": doc["country_code"],
                    "country_name": doc["country_name"],
                    "daily_clicks": doc["daily_clicks"],
                    "total_clicks": doc["total_clicks"],
                    "date": doc["date"],
                    "last_updated": doc["last_updated"].isoformat()
                })
                rank += 1
            
            logger.info(f"Retrieved {len(rankings)} daily rankings for {date}")
            return rankings
            
        except Exception as e:
            logger.error(f"Failed to get daily rankings: {e}")
            raise DatabaseError(f"Failed to retrieve rankings: {e}")
    
    async def get_country_ranking(self, country_code: str, date: str = None) -> Optional[int]:
        """특정 국가의 현재 랭킹 조회"""
        try:
            if not self.connected:
                return None
            
            if not date:
                date = DateTimeUtils.kst_now().strftime('%Y-%m-%d')
            
            # 해당 국가의 클릭수 조회
            country_doc = await self.country_clicks_collection.find_one({
                "country_code": country_code.upper(),
                "date": date
            })
            
            if not country_doc:
                return None
            
            # 해당 클릭수보다 높은 클릭수를 가진 국가 수 계산
            higher_count = await self.country_clicks_collection.count_documents({
                "date": date,
                "daily_clicks": {"$gt": country_doc["daily_clicks"]}
            })
            
            return higher_count + 1
            
        except Exception as e:
            logger.error(f"Failed to get country ranking for {country_code}: {e}")
            return None
    
    async def reset_daily_clicks(self, date: str = None) -> int:
        """
        일일 클릭수 초기화
        
        Args:
            date: 초기화할 날짜 (YYYY-MM-DD), None이면 오늘
            
        Returns:
            초기화된 국가 수
        """
        try:
            if not self.connected:
                logger.warning("MongoDB not connected, skipping daily reset")
                return 0
            
            if not date:
                date = DateTimeUtils.kst_now().strftime('%Y-%m-%d')
            
            # 해당 날짜의 모든 문서의 daily_clicks을 0으로 초기화
            result = await self.country_clicks_collection.update_many(
                {"date": date},
                {
                    "$set": {
                        "daily_clicks": 0,
                        "last_updated": DateTimeUtils.kst_now()
                    }
                }
            )
            
            logger.info(f"Reset daily clicks for {result.modified_count} countries on {date}")
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Failed to reset daily clicks: {e}")
            raise DatabaseError(f"Failed to reset daily clicks: {e}")
    
    async def get_country_stats(self, country_code: str, days: int = 7) -> Dict:
        """국가별 통계 조회 (최근 N일)"""
        try:
            if not self.connected:
                return await self._mock_get_country_stats(country_code, days)
            
            # 최근 N일 데이터 조회
            end_date = DateTimeUtils.kst_now()
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            stats = []
            total_clicks = 0
            
            for i in range(days):
                date = (start_date - DateTimeUtils.timedelta(days=i)).strftime('%Y-%m-%d')
                doc = await self.country_clicks_collection.find_one({
                    "country_code": country_code.upper(),
                    "date": date
                })
                
                daily_clicks = doc["daily_clicks"] if doc else 0
                total_clicks += daily_clicks
                
                stats.append({
                    "date": date,
                    "clicks": daily_clicks
                })
            
            country_name = await self._get_country_name(country_code)
            
            return {
                "country_code": country_code.upper(),
                "country_name": country_name,
                "period_days": days,
                "total_clicks": total_clicks,
                "average_daily_clicks": round(total_clicks / days, 2),
                "daily_breakdown": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get country stats for {country_code}: {e}")
            raise DatabaseError(f"Failed to retrieve country stats: {e}")
    
    async def _get_country_name(self, country_code: str) -> str:
        """국가 코드에서 국가명 조회"""
        country_mapping = {
            "US": "미국", "JP": "일본", "KR": "한국", "EU": "유럽연합",
            "GB": "영국", "CN": "중국", "AU": "호주", "CA": "캐나다",
            "CH": "스위스", "HK": "홍콩", "SG": "싱가포르", "TH": "태국",
            "VN": "베트남", "DE": "독일", "FR": "프랑스", "IT": "이탈리아"
        }
        return country_mapping.get(country_code.upper(), country_code.upper())
    
    # Mock 데이터 메서드들 (MongoDB 연결 실패 시 사용)
    async def _mock_increment_clicks(self, country_code: str, country_name: str = None) -> Dict:
        """Mock 클릭수 증가"""
        country_name = country_name or await self._get_country_name(country_code)
        return {
            "country_code": country_code.upper(),
            "country_name": country_name,
            "daily_clicks": 1,
            "total_clicks": 1,
            "current_rank": 1,
            "date": DateTimeUtils.kst_now().strftime('%Y-%m-%d'),
            "last_updated": DateTimeUtils.kst_now().isoformat()
        }
    
    async def _mock_get_rankings(self, limit: int) -> List[Dict]:
        """Mock 랭킹 데이터"""
        mock_countries = [
            ("JP", "일본"), ("US", "미국"), ("TH", "태국"), ("VN", "베트남"),
            ("SG", "싱가포르"), ("CN", "중국"), ("GB", "영국"), ("AU", "호주"),
            ("CA", "캐나다"), ("DE", "독일")
        ]
        
        rankings = []
        for i, (code, name) in enumerate(mock_countries[:limit]):
            rankings.append({
                "rank": i + 1,
                "country_code": code,
                "country_name": name,
                "daily_clicks": max(100 - i * 10, 1),
                "total_clicks": max(1000 - i * 100, 10),
                "date": DateTimeUtils.kst_now().strftime('%Y-%m-%d'),
                "last_updated": DateTimeUtils.kst_now().isoformat()
            })
        
        return rankings
    
    async def _mock_get_country_stats(self, country_code: str, days: int) -> Dict:
        """Mock 국가 통계"""
        country_name = await self._get_country_name(country_code)
        return {
            "country_code": country_code.upper(),
            "country_name": country_name,
            "period_days": days,
            "total_clicks": 150,
            "average_daily_clicks": 21.43,
            "daily_breakdown": [
                {"date": "2024-01-15", "clicks": 25},
                {"date": "2024-01-14", "clicks": 20},
                {"date": "2024-01-13", "clicks": 18},
                {"date": "2024-01-12", "clicks": 22},
                {"date": "2024-01-11", "clicks": 19},
                {"date": "2024-01-10", "clicks": 24},
                {"date": "2024-01-09", "clicks": 22}
            ]
        }
    
    async def close(self):
        """MongoDB 연결 종료"""
        try:
            if self.client:
                self.client.close()
                self.connected = False
                logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")


# 전역 MongoDB 서비스 인스턴스
mongodb_service = None


async def get_mongodb_service() -> MongoDBService:
    """MongoDB 서비스 의존성"""
    global mongodb_service
    if mongodb_service is None:
        mongodb_service = MongoDBService()
        await mongodb_service.connect()
    return mongodb_service
