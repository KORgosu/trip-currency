"""
Data Ingestor Service - 외부 데이터 수집 및 처리 서비스
CronJob으로 실행되는 배치 작업 (로컬에서는 스케줄러로 실행)

주요 기능:
- 외부 API에서 환율 데이터 수집 (5분마다)
- 데이터 검증 및 정제
- MySQL에 데이터 저장
- Redis에 최신 데이터 캐싱
- Kafka로 실시간 스트리밍

실행 모드:
- single: 단일 실행 (테스트용)
- scheduler: 지속적 스케줄러 실행 (로컬 개발용)
- cronjob: Kubernetes CronJob 실행 (운영용)

수집 주기:
- 기본: 5분마다 실행 (00:05, 00:10, 00:15...)
- ExchangeRate-API: 실시간 환율 데이터
"""
import asyncio
import os
import signal
import platform
import sys
from typing import Optional

# Windows 운영체제일 경우, asyncio 정책을 변경하여 SelectorEventLoop를 사용하도록 설정
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# -------------------- [핵심 수정 부분 시작] --------------------
# Docker 환경(PYTHONPATH)이 모든 경로 관리를 책임지므로,
# 복잡한 sys.path 조작 코드를 모두 제거합니다.

# 1) config를 먼저 초기화해서 import 시점 로깅에도 안전하게 만듭니다.
try:
    from shared.config import init_config
except ImportError as e:
    print("FATAL: Cannot import shared.config.init_config", file=sys.stderr)
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

config = init_config("data-ingestor")

# 2) 이후 의존 모듈들을 import합니다 (일부 모듈은 import 시 로깅이 발생할 수 있음).
try:
    from shared.logging import get_logger, set_correlation_id
    from shared.database import init_database, get_db_manager
    from shared.utils import SecurityUtils
    from app.services.data_collector import DataCollector
    from app.services.data_processor import DataProcessor
    from app.scheduler import DataIngestionScheduler
except ImportError as e:
    print(f"FATAL: Module import failed. Check Dockerfile's PYTHONPATH and COPY instructions.", file=sys.stderr)
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

# 3) logger 초기화
logger = get_logger(__name__)
# -------------------- [핵심 수정 부분 끝] --------------------


# 전역 변수
data_collector: Optional[DataCollector] = None
data_processor: Optional[DataProcessor] = None
scheduler: Optional[DataIngestionScheduler] = None
running = True


async def initialize_services():
    """서비스 초기화"""
    global data_collector, data_processor, scheduler
    
    try:
        logger.info("Data Ingestor Service starting", version=config.service_version)
        
        await init_database()
        logger.info("Database connections initialized")
        
        data_collector = DataCollector()
        data_processor = DataProcessor()
        scheduler = DataIngestionScheduler(data_collector, data_processor)
        
        await data_collector.initialize()
        await data_processor.initialize()
        
        logger.info("Data Ingestor Service initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize Data Ingestor Service", error=e)
        raise


async def cleanup_services():
    """서비스 정리"""
    global scheduler, data_collector, data_processor

    try:
        if scheduler:
            await scheduler.stop()
        if data_collector:
            await data_collector.close()
        if data_processor:
            await data_processor.close()

        db_manager = get_db_manager()
        if db_manager:
            await db_manager.close()
        
        logger.info("Data Ingestor Service stopped")
    except Exception as e:
        logger.error("Error during cleanup", error=e)


def signal_handler(signum, frame):
    """시그널 핸들러"""
    global running
    if running:
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        running = False


async def run_single_collection():
    """단일 데이터 수집 실행 (테스트용)"""
    correlation_id = SecurityUtils.generate_correlation_id()
    set_correlation_id(correlation_id)
    
    logger.info("Starting single data collection run", correlation_id=correlation_id)
    
    try:
        await initialize_services()
        collection_results = await data_collector.collect_all_data()
        
        for result in collection_results:
            if result.success:
                await data_processor.process_exchange_rate_data(result)
            else:
                logger.warning("Collection failed", source=result.source, error=result.error_message)
        
        logger.info("Single data collection completed successfully")
        
    except Exception as e:
        logger.error("Single data collection failed", error=e, exc_info=True)
        raise
    finally:
        await cleanup_services()


async def run_scheduler():
    """스케줄러 실행 (지속적 실행)"""
    logger.info("Starting Data Ingestor Scheduler")
    
    try:
        await initialize_services()
        
        # 시그널 핸들러 등록 (Windows 호환성)
        loop = asyncio.get_running_loop()
        try:
            loop.add_signal_handler(signal.SIGINT, signal_handler, signal.SIGINT, None)
            loop.add_signal_handler(signal.SIGTERM, signal_handler, signal.SIGTERM, None)
        except NotImplementedError:
            # Windows에서는 signal handler를 지원하지 않음
            logger.info("Signal handlers not supported on this platform (Windows)")
            pass
        
        await scheduler.start()
        
        while running:
            await asyncio.sleep(1)
        
        logger.info("Scheduler shutdown requested")
        
    except Exception as e:
        logger.error("Scheduler execution failed", error=e, exc_info=True)
        raise
    finally:
        await cleanup_services()


async def run_kubernetes_cronjob():
    """Kubernetes CronJob 실행 (한 번 실행 후 종료)"""
    correlation_id = SecurityUtils.generate_correlation_id()
    set_correlation_id(correlation_id)
    
    logger.info("Starting Kubernetes CronJob execution", correlation_id=correlation_id)
    
    try:
        await initialize_services()
        collection_results = await data_collector.collect_all_data()
        
        for result in collection_results:
            if result.success:
                await data_processor.process_exchange_rate_data(result)
            else:
                logger.warning("Collection failed", source=result.source, error=result.error_message)
        
        logger.info("Kubernetes CronJob execution completed successfully")
        
    except Exception as e:
        logger.error("Kubernetes CronJob execution failed", error=e, exc_info=True)
        raise
    finally:
        await cleanup_services()


def main():
    """메인 함수"""
    import argparse
    
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="Data Ingestor Service")
    parser.add_argument("mode", nargs="?", choices=["single", "scheduler", "cronjob"], 
                       default=None, help="Execution mode")
    
    args = parser.parse_args()
    
    # 환경 변수 또는 명령행 인자로 모드 결정
    mode = args.mode or os.getenv("EXECUTION_MODE", "scheduler")
    logger.info(f"Starting in '{mode}' mode.")
    
    try:
        if mode == "single":
            asyncio.run(run_single_collection())
        elif mode == "scheduler":
            asyncio.run(run_scheduler())
        elif mode == "cronjob":
            asyncio.run(run_kubernetes_cronjob())
        else:
            logger.error(f"Unknown execution mode: {mode}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.critical("An unhandled exception occurred in main", error=e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()