"""
Database Management
데이터베이스 연결 및 헬퍼 클래스
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
import aiomysql
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
from .config import get_config

logger = logging.getLogger(__name__)

# 전역 데이터베이스 매니저
_db_manager: Optional['DatabaseManager'] = None


class MySQLHelper:
    """MySQL 헬퍼 클래스"""
    
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
    
    async def connect(self):
        """MySQL 연결"""
        config = get_config()
        try:
            self.pool = await aiomysql.create_pool(
                host=config.database.host,
                port=config.database.port,
                user=config.database.user,
                password=config.database.password,
                db=config.database.name,
                minsize=1,
                maxsize=10,
                autocommit=True
            )
            logger.info("MySQL connection pool created")
        except Exception as e:
            logger.error(f"Failed to create MySQL connection pool: {e}")
            raise
    
    async def execute_query(self, query: str, params: tuple = None) -> list:
        """쿼리 실행"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                result = await cursor.fetchall()
                return result
    
    async def execute_insert(self, query: str, params: tuple = None) -> int:
        """INSERT 쿼리 실행"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.lastrowid
    
    async def execute_update(self, query: str, params: tuple = None) -> int:
        """UPDATE/DELETE 쿼리 실행"""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.rowcount
    
    async def close(self):
        """연결 종료"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()


class RedisHelper:
    """Redis 헬퍼 클래스"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Redis 연결"""
        config = get_config()
        try:
            self.client = redis.Redis(
                host=config.redis.host,
                port=config.redis.port,
                decode_responses=True
            )
            await self.client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def get(self, key: str) -> Optional[str]:
        """값 조회"""
        if not self.client:
            await self.connect()
        return await self.client.get(key)
    
    async def set(self, key: str, value: str, ex: int = None) -> bool:
        """값 저장"""
        if not self.client:
            await self.connect()
        return await self.client.set(key, value, ex=ex)
    
    async def setex(self, key: str, time: int, value: str) -> bool:
        """값 저장 (TTL 포함)"""
        if not self.client:
            await self.connect()
        return await self.client.setex(key, time, value)
    
    async def delete(self, *keys: str) -> int:
        """키 삭제"""
        if not self.client:
            await self.connect()
        return await self.client.delete(*keys)
    
    async def keys(self, pattern: str) -> list:
        """키 패턴 검색"""
        if not self.client:
            await self.connect()
        return await self.client.keys(pattern)
    
    async def set_hash(self, key: str, data: Dict[str, Any], ex: int = None) -> bool:
        """해시 데이터 저장"""
        if not self.client:
            await self.connect()
        return await self.client.hset(key, mapping=data) and (await self.client.expire(key, ex) if ex else True)
    
    async def get_hash(self, key: str) -> Optional[Dict[str, Any]]:
        """해시 데이터 조회"""
        if not self.client:
            await self.connect()
        return await self.client.hgetall(key)
    
    async def get_multiple_hashes(self, keys: List[str]) -> List[Optional[Dict[str, Any]]]:
        """여러 해시 데이터 일괄 조회"""
        if not self.client:
            await self.connect()
        
        # 파이프라인을 사용하여 일괄 조회
        pipe = self.client.pipeline()
        for key in keys:
            pipe.hgetall(key)
        
        results = await pipe.execute()
        return results
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """JSON 데이터 조회"""
        if not self.client:
            await self.connect()
        
        data = await self.client.get(key)
        if data:
            import json
            return json.loads(data)
        return None
    
    async def set_json(self, key: str, data: Dict[str, Any], ex: int = None) -> bool:
        """JSON 데이터 저장"""
        if not self.client:
            await self.connect()
        
        import json
        json_data = json.dumps(data, ensure_ascii=False)
        return await self.client.set(key, json_data, ex=ex)
    
    async def delete_pattern(self, pattern: str) -> int:
        """패턴으로 키 삭제"""
        if not self.client:
            await self.connect()
        keys = await self.client.keys(pattern)
        if keys:
            return await self.client.delete(*keys)
        return 0
    
    async def ping(self) -> bool:
        """Redis 연결 상태 확인"""
        if not self.client:
            await self.connect()
        try:
            result = await self.client.ping()
            return result
        except Exception:
            return False
    
    async def close(self):
        """연결 종료"""
        if self.client:
            await self.client.close()


class MongoDBHelper:
    """MongoDB 헬퍼 클래스"""
    
    def __init__(self, database_name: str = None):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database_name = database_name or "currency_db"
        self.db = None
    
    async def connect(self):
        """MongoDB 연결"""
        config = get_config()
        try:
            connection_string = f"mongodb://{config.mongodb.user}:{config.mongodb.password}@{config.mongodb.host}:{config.mongodb.port}/?authSource=admin"
            self.client = AsyncIOMotorClient(connection_string)
            self.db = self.client[self.database_name]
            
            # 연결 테스트
            await self.client.admin.command('ping')
            logger.info("MongoDB connection established")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def get_collection(self, collection_name: str):
        """컬렉션 반환"""
        if not self.db:
            await self.connect()
        return self.db[collection_name]
    
    async def close(self):
        """연결 종료"""
        if self.client:
            self.client.close()


class DynamoDBHelper:
    """DynamoDB 헬퍼 클래스 (로컬에서는 Mock)"""
    
    def __init__(self):
        self.client = None
    
    async def initialize(self):
        """DynamoDB 초기화 (로컬에서는 Mock)"""
        logger.info("DynamoDB helper initialized (Mock mode for local development)")
    
    async def put_item(self, item: Dict[str, Any]) -> bool:
        """아이템 저장 (Mock)"""
        logger.debug(f"Mock DynamoDB put_item: {item}")
        return True
    
    async def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """아이템 조회 (Mock)"""
        logger.debug(f"Mock DynamoDB get_item: {key}")
        return None
    
    async def query(self, **kwargs) -> List[Dict[str, Any]]:
        """쿼리 실행 (Mock)"""
        logger.debug(f"Mock DynamoDB query: {kwargs}")
        return []
    
    async def scan(self, **kwargs):
        """스캔 실행 (Mock)"""
        logger.debug(f"Mock DynamoDB scan: {kwargs}")
        return []
    
    async def delete_pattern(self, pattern: str):
        """패턴으로 키 삭제 (Mock)"""
        logger.debug(f"Mock DynamoDB delete_pattern: {pattern}")
        return 0
    
    async def close(self):
        """연결 종료"""
        pass


class DatabaseManager:
    """데이터베이스 매니저"""
    
    def __init__(self):
        self.mysql: Optional[MySQLHelper] = None
        self.redis: Optional[RedisHelper] = None
        self.mongodb: Optional[MongoDBHelper] = None
        self.dynamodb: Optional[DynamoDBHelper] = None
    
    async def initialize(self):
        """모든 데이터베이스 초기화"""
        import os

        try:
            # MySQL 초기화 (SKIP_MYSQL_INIT 환경 변수가 true가 아닌 경우에만)
            if os.getenv("SKIP_MYSQL_INIT", "false").lower() != "true":
                self.mysql = MySQLHelper()
                await self.mysql.connect()
                logger.info("MySQL initialized")
            else:
                logger.info("MySQL initialization skipped")

            # Redis 초기화
            self.redis = RedisHelper()
            await self.redis.connect()

            # MongoDB 초기화 (SKIP_MONGODB_INIT 환경 변수가 true가 아닌 경우에만)
            if os.getenv("SKIP_MONGODB_INIT", "false").lower() != "true":
                self.mongodb = MongoDBHelper()
                await self.mongodb.connect()
                logger.info("MongoDB initialized")
            else:
                logger.info("MongoDB initialization skipped")

            # DynamoDB 초기화 (Mock)
            self.dynamodb = DynamoDBHelper()
            await self.dynamodb.initialize()

            logger.info("Database initialization completed")
        except Exception as e:
            logger.error(f"Failed to initialize databases: {e}")
            raise
    
    async def close(self):
        """모든 데이터베이스 연결 종료"""
        if self.mysql:
            await self.mysql.close()
        if self.redis:
            await self.redis.close()
        if self.mongodb:
            await self.mongodb.close()
        if self.dynamodb:
            await self.dynamodb.close()


async def init_database():
    """데이터베이스 초기화"""
    global _db_manager
    
    _db_manager = DatabaseManager()
    await _db_manager.initialize()


def get_db_manager() -> DatabaseManager:
    """데이터베이스 매니저 반환"""
    global _db_manager
    
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    return _db_manager
