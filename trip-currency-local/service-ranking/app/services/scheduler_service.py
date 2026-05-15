"""
Scheduler Service - 한국시간 기준 일일 초기화 스케줄러
매일 한국시간 00:00에 나라별 클릭수를 초기화하는 스케줄러
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import pytz

from shared.utils import DateTimeUtils
from shared.exceptions import SchedulerError
from .mongodb_service import get_mongodb_service

logger = logging.getLogger(__name__)


class RankingScheduler:
    """랭킹 초기화 스케줄러"""
    
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.korea_tz = pytz.timezone('Asia/Seoul')
        
        # 스케줄러 통계
        self.stats = {
            "total_resets": 0,
            "successful_resets": 0,
            "failed_resets": 0,
            "last_reset_time": None,
            "last_success_time": None,
            "last_error": None,
            "next_reset_time": None
        }
    
    async def start_daily_reset_scheduler(self):
        """한국시간 00시 초기화 스케줄러 시작"""
        if self.running:
            logger.warning("Daily reset scheduler is already running")
            return
        
        self.running = True
        logger.info("Starting daily reset scheduler for Korea timezone")
        
        # 다음 초기화 시간 계산
        next_reset = self.get_next_reset_time()
        self.stats["next_reset_time"] = next_reset.isoformat()
        
        logger.info(f"Next daily reset scheduled for: {next_reset}")
        
        # 백그라운드 태스크 시작
        self.task = asyncio.create_task(self._scheduler_loop())
        
        try:
            await self.task
        except Exception as e:
            logger.error(f"Scheduler execution failed: {e}")
            raise
        finally:
            self.running = False
    
    async def stop_scheduler(self):
        """스케줄러 중지"""
        logger.info("Stopping daily reset scheduler")
        self.running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Daily reset scheduler stopped")
    
    async def _scheduler_loop(self):
        """스케줄러 메인 루프"""
        logger.info("Daily reset scheduler loop started")
        
        while self.running:
            try:
                # 다음 초기화 시간까지 대기
                await self._wait_for_next_reset()
                
                if not self.running:
                    break
                
                # 일일 초기화 실행
                await self._execute_daily_reset()
                
            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                self.stats["failed_resets"] += 1
                self.stats["last_error"] = str(e)
                
                # 에러 발생 시 1시간 대기 후 재시도
                await asyncio.sleep(3600)
        
        logger.info("Daily reset scheduler loop stopped")
    
    async def _wait_for_next_reset(self):
        """다음 초기화 시간까지 대기"""
        next_reset = self.get_next_reset_time()
        current_time = DateTimeUtils.kst_now()
        
        wait_seconds = (next_reset - current_time).total_seconds()
        
        logger.info(
            f"Waiting for next daily reset - Current: {current_time.isoformat()}, "
            f"Next reset: {next_reset.isoformat()}, Wait: {wait_seconds}s"
        )
        
        # 대기 중에도 종료 신호 체크
        while wait_seconds > 0 and self.running:
            sleep_time = min(wait_seconds, 60)  # 최대 1분씩 대기
            await asyncio.sleep(sleep_time)
            wait_seconds -= sleep_time
    
    def get_next_reset_time(self) -> datetime:
        """다음 초기화 시간 계산 (한국시간 기준)"""
        # 현재 한국시간
        korea_now = DateTimeUtils.kst_now()
        
        # 오늘 00:00:00
        today_midnight = korea_now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 이미 00:00이 지났다면 내일 00:00
        if korea_now >= today_midnight:
            next_reset = today_midnight + timedelta(days=1)
        else:
            next_reset = today_midnight
        
        return next_reset
    
    async def _execute_daily_reset(self):
        """일일 초기화 실행"""
        reset_time = DateTimeUtils.kst_now()
        correlation_id = f"reset_{reset_time.strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(
            f"Starting daily reset",
            correlation_id=correlation_id,
            reset_time=reset_time.isoformat()
        )
        
        try:
            self.stats["total_resets"] += 1
            self.stats["last_reset_time"] = reset_time
            
            # MongoDB 서비스 가져오기
            mongodb_service = await get_mongodb_service()
            
            # 일일 클릭수 초기화
            reset_count = await mongodb_service.reset_daily_clicks()
            
            # 통계 업데이트
            self.stats["successful_resets"] += 1
            self.stats["last_success_time"] = reset_time
            self.stats["last_error"] = None
            
            # 다음 초기화 시간 업데이트
            self.stats["next_reset_time"] = self.get_next_reset_time().isoformat()
            
            logger.info(
                f"Daily reset completed successfully",
                correlation_id=correlation_id,
                reset_count=reset_count,
                reset_time=reset_time.isoformat()
            )
            
        except Exception as e:
            self.stats["failed_resets"] += 1
            self.stats["last_error"] = str(e)
            
            logger.error(
                f"Daily reset failed",
                correlation_id=correlation_id,
                error=e,
                reset_time=reset_time.isoformat()
            )
            
            raise SchedulerError(f"Daily reset failed: {e}")
    
    async def run_manual_reset(self) -> Dict:
        """수동 초기화 실행"""
        logger.info("Starting manual daily reset")
        
        try:
            await self._execute_daily_reset()
            return {
                "success": True,
                "message": "Manual reset completed successfully",
                "reset_time": DateTimeUtils.kst_now().isoformat()
            }
        except Exception as e:
            logger.error(f"Manual reset failed: {e}")
            return {
                "success": False,
                "message": f"Manual reset failed: {e}",
                "error": str(e)
            }
    
    def get_scheduler_status(self) -> Dict:
        """스케줄러 상태 반환"""
        current_time = DateTimeUtils.kst_now()
        
        return {
            "running": self.running,
            "stats": self.stats,
            "current_korea_time": current_time.isoformat(),
            "next_reset_time": self.stats.get("next_reset_time"),
            "time_until_next_reset": (
                (datetime.fromisoformat(self.stats["next_reset_time"]) - current_time).total_seconds()
                if self.stats.get("next_reset_time") else None
            )
        }
    
    def get_health_status(self) -> Dict:
        """스케줄러 건강 상태 반환"""
        current_time = DateTimeUtils.kst_now()
        
        # 건강 상태 체크
        is_healthy = True
        health_issues = []
        
        # 최근 실행 시간 체크 (24시간 이상 지연 시 문제)
        if self.stats["last_reset_time"]:
            last_reset = self.stats["last_reset_time"]
            time_since_last_reset = (current_time - last_reset).total_seconds()
            
            if time_since_last_reset > 25 * 3600:  # 25시간 이상
                is_healthy = False
                health_issues.append(f"No reset for {time_since_last_reset / 3600:.1f} hours")
        
        # 성공률 체크
        if self.stats["total_resets"] > 0:
            success_rate = self.stats["successful_resets"] / self.stats["total_resets"]
            if success_rate < 0.8:  # 80% 미만
                is_healthy = False
                health_issues.append(f"Low success rate: {success_rate:.2%}")
        
        return {
            "healthy": is_healthy,
            "running": self.running,
            "issues": health_issues,
            "status": self.get_scheduler_status()
        }


# 전역 스케줄러 인스턴스
ranking_scheduler = None


async def get_ranking_scheduler() -> RankingScheduler:
    """랭킹 스케줄러 의존성"""
    global ranking_scheduler
    if ranking_scheduler is None:
        ranking_scheduler = RankingScheduler()
    return ranking_scheduler
