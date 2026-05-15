"""
Data Ingestion Scheduler - 데이터 수집 스케줄러
주기적으로 데이터 수집 및 처리 작업 실행
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import signal

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.logging import get_logger, set_correlation_id
from shared.utils import SecurityUtils, DateTimeUtils
from shared.exceptions import DataProcessingError

logger = get_logger(__name__)


class DataIngestionScheduler:
    """데이터 수집 스케줄러"""
    
    def __init__(self, data_collector, data_processor):
        self.data_collector = data_collector
        self.data_processor = data_processor
        self.running = False
        self.collection_interval = 300   # 5분 (300초) - 5분 간격
        self.cleanup_interval = 86400   # 24시간 (86400초)
        self.aggregate_interval = 3600  # 1시간 (3600초)
        self.last_cleanup = None
        self.last_aggregate = None
        
        # 작업 통계
        self.stats = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_run_time": None,
            "last_success_time": None,
            "last_error": None
        }
    
    async def start(self):
        """스케줄러 시작"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        logger.info(
            "Data ingestion scheduler started",
            collection_schedule="5분 간격 (00:05, 00:10, 00:15...)",
            cleanup_interval=self.cleanup_interval,
            aggregate_interval=self.aggregate_interval
        )
        
        # 백그라운드 작업들 시작
        tasks = [
            asyncio.create_task(self._collection_loop()),
            asyncio.create_task(self._maintenance_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error("Scheduler execution failed", error=e)
            raise
        finally:
            self.running = False
    
    async def stop(self):
        """스케줄러 중지"""
        logger.info("Stopping data ingestion scheduler")
        self.running = False
        
        # 진행 중인 작업이 완료될 때까지 잠시 대기
        await asyncio.sleep(2)
        
        logger.info("Data ingestion scheduler stopped")
    
    async def _collection_loop(self):
        """데이터 수집 루프"""
        logger.info("Starting data collection loop")
        
        while self.running:
            try:
                # 다음 실행 시간까지 대기
                await self._wait_for_next_collection()
                
                if not self.running:
                    break
                
                # 데이터 수집 실행
                await self._run_data_collection()
                
            except Exception as e:
                logger.error("Collection loop error", error=e)
                self.stats["failed_runs"] += 1
                self.stats["last_error"] = str(e)
                
                # 에러 발생 시 짧은 대기 후 재시도
                await asyncio.sleep(60)
        
        logger.info("Data collection loop stopped")
    
    async def _maintenance_loop(self):
        """유지보수 작업 루프"""
        logger.info("Starting maintenance loop")
        
        while self.running:
            try:
                current_time = DateTimeUtils.utc_now()
                
                # 데이터 정리 작업 (일 1회)
                if (self.last_cleanup is None or 
                    (current_time - self.last_cleanup).total_seconds() >= self.cleanup_interval):
                    
                    await self._run_data_cleanup()
                    self.last_cleanup = current_time
                
                # 일별 집계 작업 (시간마다 체크)
                if (self.last_aggregate is None or 
                    (current_time - self.last_aggregate).total_seconds() >= self.aggregate_interval):
                    
                    await self._run_daily_aggregation()
                    self.last_aggregate = current_time
                
                # 1분마다 체크
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error("Maintenance loop error", error=e)
                await asyncio.sleep(300)  # 에러 시 5분 대기
        
        logger.info("Maintenance loop stopped")
    
    async def _wait_for_next_collection(self):
        """다음 수집 시간까지 대기 (5분 간격)"""
        current_time = DateTimeUtils.utc_now()
        
        # 다음 5분 단위 시간 계산 (00:05, 00:10, 00:15, ...)
        current_minute = current_time.minute
        next_minute = ((current_minute // 5) + 1) * 5  # 다음 5분 단위
        
        if next_minute >= 60:
            # 다음 시간으로 넘어가는 경우
            next_time = current_time.replace(minute=0, second=0, microsecond=0)
            next_time = next_time.replace(hour=current_time.hour + 1)
        else:
            # 같은 시간 내에서 다음 5분 단위
            next_time = current_time.replace(minute=next_minute, second=0, microsecond=0)
        
        # 자정을 넘어가는 경우 처리
        if next_time.hour >= 24:
            next_time = next_time.replace(hour=0, day=next_time.day + 1)
        
        wait_seconds = (next_time - current_time).total_seconds()
        
        logger.debug(
            "Waiting for next collection (5-minute interval)",
            current_time=DateTimeUtils.to_iso_string(current_time),
            next_time=DateTimeUtils.to_iso_string(next_time),
            wait_seconds=wait_seconds
        )
        
        # 대기 중에도 종료 신호 체크
        while wait_seconds > 0 and self.running:
            sleep_time = min(wait_seconds, 10)  # 최대 10초씩 대기
            await asyncio.sleep(sleep_time)
            wait_seconds -= sleep_time
    
    async def _run_data_collection(self):
        """데이터 수집 실행"""
        correlation_id = SecurityUtils.generate_correlation_id()
        set_correlation_id(correlation_id)
        
        start_time = DateTimeUtils.utc_now()
        
        logger.info(
            "Starting scheduled data collection at 5-minute interval",
            correlation_id=correlation_id,
            run_number=self.stats["total_runs"] + 1,
            collection_time=DateTimeUtils.to_iso_string(start_time)
        )
        
        try:
            self.stats["total_runs"] += 1
            self.stats["last_run_time"] = start_time
            
            # 데이터 수집
            collection_results = await self.data_collector.collect_all_data()
            
            # 수집 결과 처리
            successful_collections = 0
            failed_collections = 0
            
            for result in collection_results:
                if result.success:
                    try:
                        await self.data_processor.process_exchange_rate_data(result)
                        successful_collections += 1
                    except Exception as e:
                        logger.error(
                            "Failed to process collected data",
                            source=result.source,
                            error=e
                        )
                        failed_collections += 1
                else:
                    failed_collections += 1
            
            end_time = DateTimeUtils.utc_now()
            duration = (end_time - start_time).total_seconds()
            
            if successful_collections > 0:
                self.stats["successful_runs"] += 1
                self.stats["last_success_time"] = end_time
                
                logger.info(
                    "Scheduled data collection completed successfully",
                    correlation_id=correlation_id,
                    duration_seconds=duration,
                    successful_collections=successful_collections,
                    failed_collections=failed_collections
                )
            else:
                self.stats["failed_runs"] += 1
                logger.warning(
                    "Scheduled data collection completed with no successful collections",
                    correlation_id=correlation_id,
                    failed_collections=failed_collections
                )
            
        except Exception as e:
            self.stats["failed_runs"] += 1
            self.stats["last_error"] = str(e)
            
            logger.error(
                "Scheduled data collection failed",
                correlation_id=correlation_id,
                error=e
            )
            raise
    
    async def _run_data_cleanup(self):
        """데이터 정리 작업 실행"""
        logger.info("Starting scheduled data cleanup")
        
        try:
            # 1년 이상 된 데이터 정리
            await self.data_processor.cleanup_old_data(retention_days=365)
            
            logger.info("Scheduled data cleanup completed")
            
        except Exception as e:
            logger.error("Scheduled data cleanup failed", error=e)
            # 정리 작업 실패는 전체 스케줄러를 중단시키지 않음
    
    async def _run_daily_aggregation(self):
        """일별 집계 작업 실행"""
        logger.info("Starting scheduled daily aggregation")
        
        try:
            # 어제 데이터에 대한 집계 생성
            yesterday = DateTimeUtils.utc_now() - timedelta(days=1)
            await self.data_processor.generate_daily_aggregates(yesterday)
            
            logger.info("Scheduled daily aggregation completed")
            
        except Exception as e:
            logger.error("Scheduled daily aggregation failed", error=e)
            # 집계 작업 실패는 전체 스케줄러를 중단시키지 않음
    
    async def run_manual_collection(self):
        """수동 데이터 수집 실행"""
        logger.info("Starting manual data collection")
        
        try:
            await self._run_data_collection()
            return True
        except Exception as e:
            logger.error("Manual data collection failed", error=e)
            return False
    
    async def run_manual_cleanup(self, retention_days: int = 365):
        """수동 데이터 정리 실행"""
        logger.info("Starting manual data cleanup", retention_days=retention_days)
        
        try:
            await self.data_processor.cleanup_old_data(retention_days)
            return True
        except Exception as e:
            logger.error("Manual data cleanup failed", error=e)
            return False
    
    async def run_manual_aggregation(self, target_date: datetime = None):
        """수동 일별 집계 실행"""
        logger.info("Starting manual daily aggregation", target_date=target_date)
        
        try:
            await self.data_processor.generate_daily_aggregates(target_date)
            return True
        except Exception as e:
            logger.error("Manual daily aggregation failed", error=e)
            return False
    
    def get_stats(self) -> dict:
        """스케줄러 통계 반환"""
        return {
            **self.stats,
            "running": self.running,
            "collection_interval": self.collection_interval,
            "last_cleanup": DateTimeUtils.to_iso_string(self.last_cleanup) if self.last_cleanup else None,
            "last_aggregate": DateTimeUtils.to_iso_string(self.last_aggregate) if self.last_aggregate else None,
            "uptime_seconds": (
                (DateTimeUtils.utc_now() - self.stats["last_run_time"]).total_seconds()
                if self.stats["last_run_time"] else 0
            )
        }
    
    def get_health_status(self) -> dict:
        """스케줄러 건강 상태 반환"""
        current_time = DateTimeUtils.utc_now()
        
        # 최근 실행 시간 체크
        is_healthy = True
        health_issues = []
        
        if self.stats["last_run_time"]:
            time_since_last_run = (current_time - self.stats["last_run_time"]).total_seconds()
            if time_since_last_run > self.collection_interval * 2:  # 2배 이상 지연
                is_healthy = False
                health_issues.append(f"No collection for {time_since_last_run} seconds")
        
        # 성공률 체크
        if self.stats["total_runs"] > 0:
            success_rate = self.stats["successful_runs"] / self.stats["total_runs"]
            if success_rate < 0.8:  # 80% 미만
                is_healthy = False
                health_issues.append(f"Low success rate: {success_rate:.2%}")
        
        return {
            "healthy": is_healthy,
            "running": self.running,
            "issues": health_issues,
            "stats": self.get_stats()
        }