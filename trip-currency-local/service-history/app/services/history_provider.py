"""
History Provider - 환율 이력 데이터 제공 서비스
Aurora DB에서 환율 이력 조회 및 차트 데이터 생성
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import json

from shared.database import RedisHelper, MySQLHelper
import logging
from shared.models import HistoryDataPoint, HistoryStatistics
from shared.exceptions import (
    DatabaseError, NotFoundError, InvalidPeriodError,
    handle_database_exception
)

logger = logging.getLogger(__name__)


class HistoryProvider:
    """환율 이력 데이터 제공자"""
    
    # TODO: 실시간 서비스 변경 - mock 데이터 생성 대신 data-ingestor의 실제 환율 이력 사용
    # - _generate_mock_history_data: 제거, 실제 DB 쿼리만 사용 (data-ingestor 매 5분 업데이트)
    # - _fetch_history_from_db: 파티셔닝 테이블 사용으로 대용량 쿼리 최적화 (월별 파티션)
    # AWS 연결: Aurora Global Database로 멀티 리전 읽기, ElastiCache Redis 캐싱 (TTL 기간별 다름)
    
    def __init__(self):
        self.redis_helper = RedisHelper()
        self.mysql_helper = MySQLHelper()
        self.cache_ttl = {
            "1w": 900,   # 15분
            "1m": 1800,  # 30분
            "6m": 3600   # 1시간
        }
    
    async def get_exchange_rate_history(
        self,
        period: str,
        target_currency: str,
        base_currency: str = "KRW",
        interval: str = "daily"
    ) -> Dict[str, Any]:
        """
        환율 이력 데이터 조회 (실제 MySQL 데이터 사용)
        
        Args:
            period: 조회 기간 (1d, 1w, 1m, 6m)
            target_currency: 대상 통화
            base_currency: 기준 통화
            interval: 데이터 간격 (daily, hourly)
            
        Returns:
            환율 이력 데이터
        """
        try:
            # 캐시 키 생성
            cache_key = f"history:{period}:{base_currency}:{target_currency}:{interval}"
            
            # 캐시에서 먼저 조회
            cached_data = await self.redis_helper.get_json(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {target_currency} history")
                return cached_data
            
            logger.info(f"Fetching real data for {target_currency} history from database")
            
            # 기간 계산
            start_date, end_date = self._calculate_date_range(period)
            
            # 실제 DB에서 데이터 조회
            raw_data = await self._fetch_history_from_db(target_currency, start_date, end_date, interval)
            
            # 데이터 처리 및 분석
            processed_data = self._process_history_data(raw_data, period, target_currency, base_currency, interval)
            
            # 캐시에 저장
            await self.redis_helper.set_json(cache_key, processed_data, self.cache_ttl.get(period, 900))
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Failed to get exchange rate history for {target_currency}: {e}")
            # 폴백: Mock 데이터 사용
            logger.warning(f"Falling back to mock data for {target_currency}")
            return await self._get_fallback_mock_data(target_currency, period, interval, base_currency)
    
    def _calculate_date_range(self, period: str) -> tuple:
        """기간에 따른 날짜 범위 계산"""
        end_date = datetime.utcnow()
        
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "1w":
            start_date = end_date - timedelta(weeks=1)
        elif period == "1m":
            start_date = end_date - timedelta(days=30)
        elif period == "6m":
            start_date = end_date - timedelta(days=180)
        else:
            raise InvalidPeriodError(period, ["1d", "1w", "1m", "6m"])
        
        return start_date, end_date
    
    async def _fetch_history_from_db(self, currency_code: str, start_date: datetime, end_date: datetime, interval: str) -> List[Dict[str, Any]]:
        """MySQL에서 실제 환율 이력 데이터 조회"""
        try:
            if interval == "hourly":  # 프론트엔드가 요청하는 5분 단위 데이터
                # 5분 단위로 정확한 데이터 조회
                query = """
                    SELECT 
                        recorded_at,
                        deal_base_rate,
                        tts,
                        ttb,
                        source
                    FROM exchange_rate_history 
                    WHERE currency_code = %s 
                      AND recorded_at BETWEEN %s AND %s
                    ORDER BY recorded_at ASC
                """
                
                results = await self.mysql_helper.execute_query(
                    query, 
                    (currency_code, start_date, end_date)
                )
                
                return [
                    {
                        "date": result["recorded_at"].isoformat(),
                        "rate": float(result["deal_base_rate"]),
                        "tts": float(result["tts"]) if result["tts"] else None,
                        "ttb": float(result["ttb"]) if result["ttb"] else None,
                        "source": result["source"]
                    }
                    for result in results
                ]
            
            elif interval == "daily":
                # 일별 집계 데이터 조회 (daily_exchange_rates 테이블 활용)
                query = """
                    SELECT 
                        trade_date,
                        open_rate,
                        close_rate,
                        high_rate,
                        low_rate,
                        avg_rate,
                        volatility,
                        volume
                    FROM daily_exchange_rates 
                    WHERE currency_code = %s 
                      AND trade_date BETWEEN %s AND %s
                    ORDER BY trade_date ASC
                """
                
                results = await self.mysql_helper.execute_query(
                    query, 
                    (currency_code, start_date.date(), end_date.date())
                )
                
                return [
                    {
                        "date": result["trade_date"].isoformat(),
                        "rate": float(result["close_rate"]),  # 프론트엔드 호환성을 위해 rate 필드 추가
                        "open": float(result["open_rate"]),
                        "close": float(result["close_rate"]),
                        "high": float(result["high_rate"]),
                        "low": float(result["low_rate"]),
                        "average": float(result["avg_rate"]),
                        "volatility": float(result["volatility"]) if result["volatility"] else 0.0,
                        "volume": result["volume"] or 0,
                        "change": float(result["close_rate"]) - float(result["open_rate"]),
                        "change_percent": ((float(result["close_rate"]) - float(result["open_rate"])) / float(result["open_rate"]) * 100) if result["open_rate"] else 0.0
                    }
                    for result in results
                ]
            
            elif interval == "weekly":
                # 주별 집계 데이터 (daily_exchange_rates에서 주별로 집계)
                return await self._fetch_weekly_aggregated_data(currency_code, start_date, end_date)
            
            elif interval == "monthly":
                # 월별 집계 데이터 (daily_exchange_rates에서 월별로 집계)
                return await self._fetch_monthly_aggregated_data(currency_code, start_date, end_date)
            
            else:
                # 기본적으로 hourly 데이터 반환
                return await self._fetch_history_from_db(currency_code, start_date, end_date, "hourly")
                
        except Exception as e:
            logger.error(f"Failed to fetch history from database: {e}")
            raise handle_database_exception(e, "fetch_history_from_db")
    
    async def _fetch_weekly_aggregated_data(self, currency_code: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """주별 집계 데이터 조회"""
        try:
            query = """
                SELECT 
                    YEARWEEK(trade_date) as week_year,
                    MIN(trade_date) as week_start,
                    MAX(trade_date) as week_end,
                    MIN(open_rate) as open_rate,
                    MAX(close_rate) as close_rate,
                    MAX(high_rate) as high_rate,
                    MIN(low_rate) as low_rate,
                    AVG(avg_rate) as avg_rate,
                    AVG(volatility) as volatility,
                    SUM(volume) as volume
                FROM daily_exchange_rates 
                WHERE currency_code = %s 
                  AND trade_date BETWEEN %s AND %s
                GROUP BY YEARWEEK(trade_date)
                ORDER BY week_start ASC
            """
            
            results = await self.mysql_helper.execute_query(
                query, 
                (currency_code, start_date.date(), end_date.date())
            )
            
            return [
                {
                    "date": result["week_start"].isoformat(),
                    "rate": float(result["close_rate"]),
                    "open": float(result["open_rate"]),
                    "close": float(result["close_rate"]),
                    "high": float(result["high_rate"]),
                    "low": float(result["low_rate"]),
                    "average": float(result["avg_rate"]),
                    "volatility": float(result["volatility"]) if result["volatility"] else 0.0,
                    "volume": result["volume"] or 0,
                    "change": float(result["close_rate"]) - float(result["open_rate"]),
                    "change_percent": ((float(result["close_rate"]) - float(result["open_rate"])) / float(result["open_rate"]) * 100) if result["open_rate"] else 0.0,
                    "week_year": result["week_year"],
                    "week_end": result["week_end"].isoformat()
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to fetch weekly aggregated data: {e}")
            return []
    
    async def _fetch_monthly_aggregated_data(self, currency_code: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """월별 집계 데이터 조회"""
        try:
            query = """
                SELECT 
                    YEAR(trade_date) as year,
                    MONTH(trade_date) as month,
                    MIN(trade_date) as month_start,
                    MAX(trade_date) as month_end,
                    MIN(open_rate) as open_rate,
                    MAX(close_rate) as close_rate,
                    MAX(high_rate) as high_rate,
                    MIN(low_rate) as low_rate,
                    AVG(avg_rate) as avg_rate,
                    AVG(volatility) as volatility,
                    SUM(volume) as volume
                FROM daily_exchange_rates 
                WHERE currency_code = %s 
                  AND trade_date BETWEEN %s AND %s
                GROUP BY YEAR(trade_date), MONTH(trade_date)
                ORDER BY month_start ASC
            """
            
            results = await self.mysql_helper.execute_query(
                query, 
                (currency_code, start_date.date(), end_date.date())
            )
            
            return [
                {
                    "date": result["month_start"].isoformat(),
                    "rate": float(result["close_rate"]),
                    "open": float(result["open_rate"]),
                    "close": float(result["close_rate"]),
                    "high": float(result["high_rate"]),
                    "low": float(result["low_rate"]),
                    "average": float(result["avg_rate"]),
                    "volatility": float(result["volatility"]) if result["volatility"] else 0.0,
                    "volume": result["volume"] or 0,
                    "change": float(result["close_rate"]) - float(result["open_rate"]),
                    "change_percent": ((float(result["close_rate"]) - float(result["open_rate"])) / float(result["open_rate"]) * 100) if result["open_rate"] else 0.0,
                    "year": result["year"],
                    "month": result["month"],
                    "month_end": result["month_end"].isoformat()
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to fetch monthly aggregated data: {e}")
            return []
    
    async def _get_fallback_mock_data(self, target_currency: str, period: str, interval: str, base_currency: str) -> Dict[str, Any]:
        """폴백용 Mock 데이터 생성"""
        try:
            # 기간 계산
            start_date, end_date = self._calculate_date_range(period)
            
            # Mock 데이터 생성
            raw_data = self._generate_mock_history_data(
                target_currency, start_date, end_date, interval
            )
            
            # 데이터 처리 및 분석
            processed_data = self._process_history_data(raw_data, period, target_currency, base_currency, interval)
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Failed to generate fallback mock data: {e}")
            # 최종 폴백: 빈 데이터 반환
            return {
                "success": True,
                "currency": target_currency,
                "base_currency": base_currency,
                "period": period,
                "interval": interval,
                "results": [],
                "statistics": {
                    "average": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "volatility": 0.0,
                    "trend": "stable",
                    "data_points": 0
                }
            }
    
    async def _fetch_history_from_db_old(
        self,
        currency_code: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """기존 데이터베이스에서 환율 이력 조회 (레거시)"""
        try:
            if interval == "daily":
                # 일별 집계 데이터 사용 (성능 최적화)
                query = """
                    SELECT
                        trade_date as date,
                        close_rate as rate,
                        (close_rate - open_rate) as `change`,
                        ((close_rate - open_rate) / open_rate * 100) as change_percent,
                        volume
                    FROM daily_exchange_rates
                    WHERE currency_code = %s
                        AND trade_date BETWEEN %s AND %s
                    ORDER BY trade_date ASC
                """
                params = (currency_code, start_date.date(), end_date.date())
            else:
                # 5분 단위 데이터 조회 (하루 데이터용)
                query = """
                    SELECT
                        recorded_at as date,
                        deal_base_rate as rate,
                        LAG(deal_base_rate) OVER (ORDER BY recorded_at) as prev_rate,
                        COUNT(*) OVER (PARTITION BY DATE(recorded_at)) as volume
                    FROM exchange_rate_history
                    WHERE currency_code = %s
                        AND recorded_at BETWEEN %s AND %s
                    ORDER BY recorded_at ASC
                """
                params = (currency_code, start_date, end_date)
            
            result = await self.mysql_helper.execute_query(query, params)
            
            # hourly 데이터의 경우 change 계산
            if interval == "hourly" and result:
                for i, row in enumerate(result):
                    if i > 0 and row.get('prev_rate'):
                        change = row['rate'] - row['prev_rate']
                        change_percent = (change / row['prev_rate']) * 100 if row['prev_rate'] != 0 else 0
                        row['change'] = change
                        row['change_percent'] = change_percent
                    else:
                        row['change'] = 0
                        row['change_percent'] = 0
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch history from DB for {currency_code}: {e}")
            return []
    
    def _generate_mock_history_data(
        self,
        currency_code: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """모의 환율 이력 데이터 생성"""
        try:
            # 기본 환율 설정
            base_rates = {
                "USD": 1350.0,
                "JPY": 9.2,
                "EUR": 1450.0,
                "GBP": 1650.0,
                "CNY": 185.0
            }
            
            base_rate = base_rates.get(currency_code, 1000.0)
            current_rate = base_rate
            
            mock_data = []
            current_date = start_date
            
            while current_date <= end_date:
                # 랜덤한 변동 생성 (±2% 범위)
                import random
                change_percent = random.uniform(-2.0, 2.0)
                change = current_rate * (change_percent / 100)
                current_rate += change
                
                mock_data.append({
                    "date": current_date.date(),
                    "rate": round(current_rate, 4),
                    "change": round(change, 4),
                    "change_percent": round(change_percent, 4),
                    "volume": random.randint(10, 50)
                })
                
                # 다음 날짜로 이동
                if interval == "daily":
                    current_date += timedelta(days=1)
                else:
                    current_date += timedelta(hours=1)
            
            return mock_data
            
        except Exception as e:
            logger.error(f"Failed to generate mock history data for {currency_code}: {e}")
            return []
    
    def _process_history_data(
        self,
        raw_data: List[Dict[str, Any]],
        period: str,
        target_currency: str,
        base_currency: str,
        interval: str
    ) -> Dict[str, Any]:
        """이력 데이터 처리 (5분 단위 데이터 지원)"""
        try:
            if not raw_data:
                return {
                    "base": base_currency,
                    "target": target_currency,
                    "period": period,
                    "interval": interval,
                    "data_points": 0,
                    "results": [],
                    "statistics": {
                        "average": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                        "volatility": 0.0,
                        "trend": "stable",
                        "data_points": 0
                    }
                }
            
            # 데이터 포인트 처리
            results = []
            rates = []
            
            for i, data_point in enumerate(raw_data):
                rate = float(data_point["rate"])
                rates.append(rate)
                
                # 변동률 계산 (이전 데이터와 비교)
                if i > 0:
                    prev_rate = float(raw_data[i-1]["rate"])
                    change = rate - prev_rate
                    change_percent = (change / prev_rate) * 100 if prev_rate != 0 else 0
                else:
                    change = 0
                    change_percent = 0
                
                # 날짜 형식 처리 (5분 단위 데이터 지원)
                if hasattr(data_point["date"], 'strftime'):
                    if interval == "hourly":
                        # 5분 단위 데이터는 ISO 형식으로 (프론트엔드 호환성)
                        date_str = data_point["date"].isoformat() + 'Z' if data_point["date"].tzinfo is None else data_point["date"].isoformat()
                    else:
                        # 일별 데이터는 날짜만
                        date_str = data_point["date"].strftime('%Y-%m-%d')
                else:
                    # 문자열인 경우 그대로 사용 (ISO 형식일 가능성)
                    date_str = str(data_point["date"])
                
                results.append({
                    "date": date_str,
                    "rate": rate,
                    "change": round(change, 4),
                    "change_percent": round(change_percent, 4),
                    "volume": data_point.get("volume", 0)
                })
            
            # 통계 계산
            statistics = self._calculate_statistics(rates)
            
            # 5분 단위 데이터인 경우 추가 정보 제공
            if interval == "hourly" and period == "1d":
                # 하루 5분 단위 데이터 특별 처리
                statistics.update({
                    "interval_type": "5min",
                    "total_intervals": 288,  # 24시간 * 12개/시간
                    "data_coverage": len(results) / 288 * 100,  # 데이터 커버리지 %
                    "last_updated": results[-1]["date"] if results else None
                })
            
            return {
                "success": True,
                "base": base_currency,
                "target": target_currency,
                "period": period,
                "interval": interval,
                "data_points": len(results),
                "results": results,
                "statistics": statistics
            }
            
        except Exception as e:
            logger.error(f"Failed to process history data: {e}")
            raise
    
    def _calculate_statistics(self, rates: List[float]) -> Dict[str, Any]:
        """환율 통계 계산"""
        try:
            if not rates:
                return {
                    "average": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "volatility": 0.0,
                    "trend": "stable",
                    "data_points": 0
                }
            
            # 기본 통계
            average = sum(rates) / len(rates)
            min_rate = min(rates)
            max_rate = max(rates)
            
            # 변동성 계산 (표준편차)
            if len(rates) > 1:
                variance = sum((rate - average) ** 2 for rate in rates) / (len(rates) - 1)
                volatility = variance ** 0.5
            else:
                volatility = 0.0
            
            # 트렌드 계산 (선형 회귀 기울기)
            trend = self._calculate_trend(rates)
            
            return {
                "average": round(average, 4),
                "min": round(min_rate, 4),
                "max": round(max_rate, 4),
                "volatility": round(volatility, 4),
                "trend": trend,
                "data_points": len(rates)
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate statistics: {e}")
            return {
                "average": 0.0,
                "min": 0.0,
                "max": 0.0,
                "volatility": 0.0,
                "trend": "stable",
                "data_points": 0
            }
    
    def _calculate_trend(self, rates: List[float]) -> str:
        """트렌드 방향 계산"""
        try:
            if len(rates) < 2:
                return "stable"
            
            # 간단한 선형 회귀 (최소제곱법)
            n = len(rates)
            x_values = list(range(n))
            
            # 기울기 계산
            x_mean = sum(x_values) / n
            y_mean = sum(rates) / n
            
            numerator = sum((x_values[i] - x_mean) * (rates[i] - y_mean) for i in range(n))
            denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
            
            if denominator == 0:
                return "stable"
            
            slope = numerator / denominator
            
            # 트렌드 판단 (기울기 기준)
            if slope > 0.1:
                return "upward"
            elif slope < -0.1:
                return "downward"
            else:
                return "stable"
                
        except Exception as e:
            logger.error(f"Failed to calculate trend: {e}")
            return "stable"
    
    async def clear_currency_history_cache(self, currency_code: str):
        """
        특정 통화의 이력 캐시 클리어
        
        Args:
            currency_code: 캐시를 클리어할 통화 코드
        """
        try:
            # 해당 통화의 모든 이력 캐시 키 패턴
            patterns = [
                f"history:*:{currency_code}:*",
                f"history:{currency_code}:*",
                f"stats:*:{currency_code}:*"
            ]
            
            for pattern in patterns:
                await self.redis_helper.delete_pattern(pattern)
            
            logger.info(f"History cache cleared for currency: {currency_code}")
                
        except Exception as e:
            logger.error(f"Failed to clear history cache for {currency_code}: {e}")
    
    async def clear_all_history_cache(self):
        """
        모든 이력 캐시 클리어
        """
        try:
            # 모든 이력 관련 캐시 키 패턴
            patterns = [
                "history:*",
                "stats:*"
            ]
            
            for pattern in patterns:
                await self.redis_helper.delete_pattern(pattern)
            
            logger.info("All history cache cleared")
                
        except Exception as e:
            logger.error(f"Failed to clear all history cache: {e}")