"""
Messaging System
Kafka 및 SQS 메시징 시스템
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from .config import get_config, Environment
from .exceptions import MessagingError

logger = logging.getLogger(__name__)

# Kafka 관련 import (선택적)
try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# SQS 관련 import (선택적)
try:
    import boto3
    SQS_AVAILABLE = True
except ImportError:
    SQS_AVAILABLE = False


class MessageProducer:
    """메시지 프로듀서"""
    
    def __init__(self):
        self.kafka_producer: Optional[AIOKafkaProducer] = None
        self.sqs_client = None
        self.config = get_config()
    
    async def initialize(self):
        """프로듀서 초기화"""
        try:
            # Kafka 프로듀서 초기화 (로컬 환경에서도 사용)
            if KAFKA_AVAILABLE:
                self.kafka_producer = AIOKafkaProducer(
                    bootstrap_servers=self.config.messaging.kafka_bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                await self.kafka_producer.start()
                logger.info("Kafka producer initialized")
            
            # SQS 클라이언트 초기화 (백업용)
            if SQS_AVAILABLE and self.config.messaging.sqs_queue_url:
                self.sqs_client = boto3.client('sqs')
                logger.info("SQS client initialized")
                
        except Exception as e:
            logger.warning(f"Failed to initialize message producer: {e}")
    
    async def send_message(self, topic: str, message: Dict[str, Any]) -> bool:
        """메시지 전송"""
        try:
            # Kafka로 전송 시도
            if self.kafka_producer:
                await self.kafka_producer.send(topic, message)
                logger.debug(f"Message sent to Kafka topic {topic}")
                return True
            
            # SQS로 백업 전송
            if self.sqs_client and self.config.messaging.sqs_queue_url:
                response = self.sqs_client.send_message(
                    QueueUrl=self.config.messaging.sqs_queue_url,
                    MessageBody=json.dumps({
                        "topic": topic,
                        "message": message
                    })
                )
                logger.debug(f"Message sent to SQS: {response['MessageId']}")
                return True
            
            logger.warning("No messaging system available")
            return False
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise MessagingError(f"Failed to send message: {e}")
    
    async def close(self):
        """프로듀서 종료"""
        if self.kafka_producer:
            await self.kafka_producer.stop()


class MessageConsumer:
    """메시지 컨슈머"""
    
    def __init__(self, topics: List[str], group_id: str):
        self.topics = topics
        self.group_id = group_id
        self.kafka_consumer: Optional[AIOKafkaConsumer] = None
        self.config = get_config()
    
    async def initialize(self):
        """컨슈머 초기화"""
        try:
            if KAFKA_AVAILABLE:
                self.kafka_consumer = AIOKafkaConsumer(
                    *self.topics,
                    bootstrap_servers=self.config.messaging.kafka_bootstrap_servers,
                    group_id=self.group_id,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',
                    enable_auto_commit=True
                )
                await self.kafka_consumer.start()
                logger.info(f"Kafka consumer initialized for topics: {self.topics}")
                
        except Exception as e:
            logger.warning(f"Failed to initialize message consumer: {e}")
    
    async def consume_messages(self, callback):
        """메시지 소비"""
        if not self.kafka_consumer:
            logger.warning("Kafka consumer not available")
            return
        
        try:
            async for message in self.kafka_consumer:
                try:
                    await callback(message.topic, message.value)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except Exception as e:
            logger.error(f"Error consuming messages: {e}")
            raise MessagingError(f"Failed to consume messages: {e}")
    
    async def close(self):
        """컨슈머 종료"""
        if self.kafka_consumer:
            await self.kafka_consumer.stop()


# 전역 프로듀서 인스턴스
_producer: Optional[MessageProducer] = None


async def get_producer() -> MessageProducer:
    """프로듀서 인스턴스 반환"""
    global _producer
    
    if _producer is None:
        _producer = MessageProducer()
        await _producer.initialize()
    
    return _producer


async def send_exchange_rate_update(data: Dict[str, Any]) -> bool:
    """환율 업데이트 이벤트 전송"""
    try:
        producer = await get_producer()
        return await producer.send_message("exchange_rate_updates", data)
    except Exception as e:
        logger.error(f"Failed to send exchange rate update: {e}")
        return False


async def send_ranking_update(data: Dict[str, Any]) -> bool:
    """랭킹 업데이트 이벤트 전송"""
    try:
        producer = await get_producer()
        return await producer.send_message("ranking_updates", data)
    except Exception as e:
        logger.error(f"Failed to send ranking update: {e}")
        return False


async def send_new_data_received(data: Dict[str, Any]) -> bool:
    """새로운 데이터 수신 이벤트 전송"""
    try:
        producer = await get_producer()
        return await producer.send_message("new_data_received", data)
    except Exception as e:
        logger.error(f"Failed to send new data received event: {e}")
        return False


async def send_exchange_rate_updated(data: Dict[str, Any]) -> bool:
    """환율 데이터 업데이트 이벤트 전송"""
    try:
        producer = await get_producer()
        return await producer.send_message("exchange_rate_updated", data)
    except Exception as e:
        logger.error(f"Failed to send exchange rate updated event: {e}")
        return False


async def send_data_processing_completed(data: Dict[str, Any]) -> bool:
    """데이터 처리 완료 이벤트 전송"""
    try:
        producer = await get_producer()
        return await producer.send_message("data_processing_completed", data)
    except Exception as e:
        logger.error(f"Failed to send data processing completed event: {e}")
        return False


async def send_cache_invalidation(data: Dict[str, Any]) -> bool:
    """캐시 무효화 이벤트 전송"""
    try:
        producer = await get_producer()
        return await producer.send_message("cache_invalidation", data)
    except Exception as e:
        logger.error(f"Failed to send cache invalidation event: {e}")
        return False