#!/usr/bin/env python3
"""
서비스 초기화 스크립트
MySQL, Redis 초기 설정 및 데이터 로드
"""
import os
import sys
import asyncio
import time
import json
from datetime import datetime, timedelta
from decimal import Decimal

# 상위 디렉토리의 shared 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services'))

import aiomysql
import redis.asyncio as aioredis
import boto3
from botocore.exceptions import ClientError


class ServiceInitializer:
    """서비스 초기화 클래스"""
    
    def __init__(self):
        self.mysql_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '3306')),
            'user': os.getenv('DB_USER', 'currency_user'),
            'password': os.getenv('DB_PASSWORD', 'password'),
            'db': os.getenv('DB_NAME', 'currency_db')
        }
        
        self.redis_config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'password': os.getenv('REDIS_PASSWORD', '')
        }
        
        # AWS 설정은 실제 AWS 환경에서만 사용
    
    async def initialize_all(self):
        """모든 서비스 초기화"""
        print("🚀 Starting service initialization...")
        
        try:
            # 1. MySQL 초기화
            await self.initialize_mysql()
            
            # 2. Redis 초기화
            await self.initialize_redis()
            
            # AWS 서비스는 실제 AWS 환경에서만 초기화
            
            print("✅ All services initialized successfully!")
            
        except Exception as e:
            print(f"❌ Service initialization failed: {e}")
            raise
    
    async def initialize_mysql(self):
        """MySQL 데이터베이스 초기화"""
        print("📊 Initializing MySQL database...")
        
        try:
            # MySQL 연결 대기
            await self.wait_for_mysql()
            
            # 데이터베이스 연결
            connection = await aiomysql.connect(**self.mysql_config)
            
            try:
                async with connection.cursor() as cursor:
                    # 통화 마스터 데이터 삽입
                    await self.insert_currency_master_data(cursor)
                    
                    # 샘플 환율 데이터 삽입
                    await self.insert_sample_exchange_rates(cursor)
                    
                    # 일별 집계 테이블 데이터 생성
                    await self.generate_daily_aggregates(cursor)
                
                await connection.commit()
                print("✅ MySQL initialization completed")
                
            finally:
                connection.close()
                
        except Exception as e:
            print(f"❌ MySQL initialization failed: {e}")
            raise
    
    async def wait_for_mysql(self, max_retries=30):
        """MySQL 연결 대기"""
        for i in range(max_retries):
            try:
                connection = await aiomysql.connect(**self.mysql_config)
                connection.close()
                print("✅ MySQL is ready")
                return
            except Exception as e:
                print(f"⏳ Waiting for MySQL... ({i+1}/{max_retries})")
                await asyncio.sleep(2)
        
        raise Exception("MySQL connection timeout")
    
    async def insert_currency_master_data(self, cursor):
        """통화 마스터 데이터 삽입"""
        currencies = [
            # 주요 통화 (24개)
            ('USD', '미국 달러', 'US Dollar', 'US', '미국', 'United States', '$', 2, True, 1),
            ('JPY', '일본 엔', 'Japanese Yen', 'JP', '일본', 'Japan', '¥', 0, True, 2),
            ('EUR', '유로', 'Euro', 'EU', '유럽연합', 'European Union', '€', 2, True, 3),
            ('GBP', '영국 파운드', 'British Pound', 'GB', '영국', 'United Kingdom', '£', 2, True, 4),
            ('CNY', '중국 위안', 'Chinese Yuan', 'CN', '중국', 'China', '¥', 2, True, 5),
            ('AUD', '호주 달러', 'Australian Dollar', 'AU', '호주', 'Australia', 'A$', 2, True, 6),
            ('CAD', '캐나다 달러', 'Canadian Dollar', 'CA', '캐나다', 'Canada', 'C$', 2, True, 7),
            ('CHF', '스위스 프랑', 'Swiss Franc', 'CH', '스위스', 'Switzerland', 'CHF', 2, True, 8),
            ('SGD', '싱가포르 달러', 'Singapore Dollar', 'SG', '싱가포르', 'Singapore', 'S$', 2, True, 9),
            ('HKD', '홍콩 달러', 'Hong Kong Dollar', 'HK', '홍콩', 'Hong Kong', 'HK$', 2, True, 10),
            ('THB', '태국 바트', 'Thai Baht', 'TH', '태국', 'Thailand', '฿', 2, True, 11),
            ('VND', '베트남 동', 'Vietnamese Dong', 'VN', '베트남', 'Vietnam', '₫', 0, True, 12),
            ('INR', '인도 루피', 'Indian Rupee', 'IN', '인도', 'India', '₹', 2, True, 13),
            ('BRL', '브라질 헤알', 'Brazilian Real', 'BR', '브라질', 'Brazil', 'R$', 2, True, 14),
            ('RUB', '러시아 루블', 'Russian Ruble', 'RU', '러시아', 'Russia', '₽', 2, True, 15),
            ('MXN', '멕시코 페소', 'Mexican Peso', 'MX', '멕시코', 'Mexico', '$', 2, True, 16),
            ('ZAR', '남아프리카 랜드', 'South African Rand', 'ZA', '남아프리카', 'South Africa', 'R', 2, True, 17),
            ('TRY', '터키 리라', 'Turkish Lira', 'TR', '터키', 'Turkey', '₺', 2, True, 18),
            ('PLN', '폴란드 즐로티', 'Polish Zloty', 'PL', '폴란드', 'Poland', 'zł', 2, True, 19),
            ('CZK', '체코 코루나', 'Czech Koruna', 'CZ', '체코', 'Czech Republic', 'Kč', 2, True, 20),
            ('HUF', '헝가리 포린트', 'Hungarian Forint', 'HU', '헝가리', 'Hungary', 'Ft', 2, True, 21),
            ('NOK', '노르웨이 크로네', 'Norwegian Krone', 'NO', '노르웨이', 'Norway', 'kr', 2, True, 22),
            ('SEK', '스웨덴 크로나', 'Swedish Krona', 'SE', '스웨덴', 'Sweden', 'kr', 2, True, 23),
            ('DKK', '덴마크 크로네', 'Danish Krone', 'DK', '덴마크', 'Denmark', 'kr', 2, True, 24),
            ('KRW', '대한민국 원', 'South Korean Won', 'KR', '대한민국', 'South Korea', '₩', 0, True, 25),
            
            # 추가 아시아 통화
            ('TWD', '대만 달러', 'Taiwan Dollar', 'TW', '대만', 'Taiwan', 'NT$', 2, True, 26),
            ('MYR', '말레이시아 링깃', 'Malaysian Ringgit', 'MY', '말레이시아', 'Malaysia', 'RM', 2, True, 27),
            ('PHP', '필리핀 페소', 'Philippine Peso', 'PH', '필리핀', 'Philippines', '₱', 2, True, 28),
            ('IDR', '인도네시아 루피아', 'Indonesian Rupiah', 'ID', '인도네시아', 'Indonesia', 'Rp', 0, True, 29),
            ('NZD', '뉴질랜드 달러', 'New Zealand Dollar', 'NZ', '뉴질랜드', 'New Zealand', 'NZ$', 2, True, 30),
            ('ILS', '이스라엘 세켈', 'Israeli Shekel', 'IL', '이스라엘', 'Israel', '₪', 2, True, 31),
            ('AED', '아랍에미리트 디르함', 'UAE Dirham', 'AE', '아랍에미리트', 'United Arab Emirates', 'د.إ', 2, True, 32),
            
            # 추가 유럽 통화
            ('ISK', '아이슬란드 크로나', 'Icelandic Krona', 'IS', '아이슬란드', 'Iceland', 'kr', 0, True, 33),
            ('RON', '루마니아 레우', 'Romanian Leu', 'RO', '루마니아', 'Romania', 'lei', 2, True, 34),
            ('BGN', '불가리아 레프', 'Bulgarian Lev', 'BG', '불가리아', 'Bulgaria', 'лв', 2, True, 35),
            ('HRK', '크로아티아 쿠나', 'Croatian Kuna', 'HR', '크로아티아', 'Croatia', 'kn', 2, True, 36),
            ('RSD', '세르비아 디나르', 'Serbian Dinar', 'RS', '세르비아', 'Serbia', 'дин', 2, True, 37),
            ('UAH', '우크라이나 흐리브냐', 'Ukrainian Hryvnia', 'UA', '우크라이나', 'Ukraine', '₴', 2, True, 38),
            ('BYN', '벨라루스 루블', 'Belarusian Ruble', 'BY', '벨라루스', 'Belarus', 'Br', 2, True, 39),
            
            # 추가 아메리카 통화
            ('ARS', '아르헨티나 페소', 'Argentine Peso', 'AR', '아르헨티나', 'Argentina', '$', 2, True, 40),
            ('CLP', '칠레 페소', 'Chilean Peso', 'CL', '칠레', 'Chile', '$', 0, True, 41),
            ('COP', '콜롬비아 페소', 'Colombian Peso', 'CO', '콜롬비아', 'Colombia', '$', 2, True, 42),
            ('PEN', '페루 솔', 'Peruvian Sol', 'PE', '페루', 'Peru', 'S/', 2, True, 43),
            ('UYU', '우루과이 페소', 'Uruguayan Peso', 'UY', '우루과이', 'Uruguay', '$', 2, True, 44),
            ('BOB', '볼리비아 볼리비아노', 'Bolivian Boliviano', 'BO', '볼리비아', 'Bolivia', 'Bs', 2, True, 45),
            ('PYG', '파라과이 과라니', 'Paraguayan Guarani', 'PY', '파라과이', 'Paraguay', '₲', 0, True, 46),
            ('VES', '베네수엘라 볼리바르', 'Venezuelan Bolivar', 'VE', '베네수엘라', 'Venezuela', 'Bs.S', 2, True, 47),
            
            # 추가 아프리카/중동 통화
            ('EGP', '이집트 파운드', 'Egyptian Pound', 'EG', '이집트', 'Egypt', '£', 2, True, 48),
            ('MAD', '모로코 디르함', 'Moroccan Dirham', 'MA', '모로코', 'Morocco', 'د.م.', 2, True, 49),
            ('TND', '튀니지 디나르', 'Tunisian Dinar', 'TN', '튀니지', 'Tunisia', 'د.ت', 3, True, 50),
            ('NGN', '나이지리아 나이라', 'Nigerian Naira', 'NG', '나이지리아', 'Nigeria', '₦', 2, True, 51),
            ('KES', '케냐 실링', 'Kenyan Shilling', 'KE', '케냐', 'Kenya', 'KSh', 2, True, 52),
            ('UGX', '우간다 실링', 'Ugandan Shilling', 'UG', '우간다', 'Uganda', 'USh', 0, True, 53),
            ('TZS', '탄자니아 실링', 'Tanzanian Shilling', 'TZ', '탄자니아', 'Tanzania', 'TSh', 2, True, 54),
            
            # 기타 주요 통화
            ('QAR', '카타르 리얄', 'Qatari Riyal', 'QA', '카타르', 'Qatar', 'ر.ق', 2, True, 55),
            ('KWD', '쿠웨이트 디나르', 'Kuwaiti Dinar', 'KW', '쿠웨이트', 'Kuwait', 'د.ك', 3, True, 56),
            ('BHD', '바레인 디나르', 'Bahraini Dinar', 'BH', '바레인', 'Bahrain', 'د.ب', 3, True, 57),
            ('OMR', '오만 리얄', 'Omani Rial', 'OM', '오만', 'Oman', 'ر.ع.', 3, True, 58),
            ('JOD', '요르단 디나르', 'Jordanian Dinar', 'JO', '요르단', 'Jordan', 'د.ا', 3, True, 59),
            ('LBP', '레바논 파운드', 'Lebanese Pound', 'LB', '레바논', 'Lebanon', 'ل.ل', 2, True, 60),
            ('PKR', '파키스탄 루피', 'Pakistani Rupee', 'PK', '파키스탄', 'Pakistan', '₨', 2, True, 61),
            ('BDT', '방글라데시 타카', 'Bangladeshi Taka', 'BD', '방글라데시', 'Bangladesh', '৳', 2, True, 62),
            ('LKR', '스리랑카 루피', 'Sri Lankan Rupee', 'LK', '스리랑카', 'Sri Lanka', '₨', 2, True, 63),
            ('NPR', '네팔 루피', 'Nepalese Rupee', 'NP', '네팔', 'Nepal', '₨', 2, True, 64),
            ('AFN', '아프가니스탄 아프가니', 'Afghan Afghani', 'AF', '아프가니스탄', 'Afghanistan', '؋', 2, True, 65),
            ('KZT', '카자흐스탄 텡게', 'Kazakhstani Tenge', 'KZ', '카자흐스탄', 'Kazakhstan', '₸', 2, True, 66),
            ('UZS', '우즈베키스탄 숨', 'Uzbekistani Som', 'UZ', '우즈베키스탄', 'Uzbekistan', 'лв', 2, True, 67),
            ('KGS', '키르기스스탄 솜', 'Kyrgyzstani Som', 'KG', '키르기스스탄', 'Kyrgyzstan', 'лв', 2, True, 68),
            ('TJS', '타지키스탄 소모니', 'Tajikistani Somoni', 'TJ', '타지키스탄', 'Tajikistan', 'SM', 2, True, 69),
            ('TMT', '투르크메니스탄 마나트', 'Turkmenistani Manat', 'TM', '투르크메니스탄', 'Turkmenistan', 'T', 2, True, 70)
        ]
        
        # 기존 데이터 확인
        await cursor.execute("SELECT COUNT(*) FROM currencies")
        count = await cursor.fetchone()
        
        if count[0] == 0:
            insert_query = """
                INSERT INTO currencies (
                    currency_code, currency_name_ko, currency_name_en,
                    country_code, country_name_ko, country_name_en,
                    symbol, decimal_places, is_active, display_order
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            await cursor.executemany(insert_query, currencies)
            print(f"✅ Inserted {len(currencies)} currency records")
        else:
            print(f"ℹ️ Currency master data already exists ({count[0]} records)")
    
    async def insert_sample_exchange_rates(self, cursor):
        """샘플 환율 데이터 삽입"""
        # 기존 데이터 확인
        await cursor.execute("SELECT COUNT(*) FROM exchange_rate_history")
        count = await cursor.fetchone()
        
        if count[0] > 0:
            print(f"ℹ️ Exchange rate data already exists ({count[0]} records)")
            return
        
        # 샘플 환율 데이터 생성 (최근 30일) - 주요 통화 20개
        base_rates = {
            'USD': 1350.0,
            'JPY': 9.2,
            'EUR': 1450.0,
            'GBP': 1650.0,
            'CNY': 185.0,
            'AUD': 900.0,
            'CAD': 1000.0,
            'CHF': 1500.0,
            'SGD': 1000.0,
            'HKD': 175.0,
            'THB': 37.5,
            'VND': 0.055,
            'INR': 16.2,
            'BRL': 270.0,
            'RUB': 14.8,
            'MXN': 75.0,
            'ZAR': 72.0,
            'TRY': 45.0,
            'PLN': 340.0,
            'CZK': 60.0
        }
        
        currency_names = {
            'USD': '미국 달러',
            'JPY': '일본 엔',
            'EUR': '유로',
            'GBP': '영국 파운드',
            'CNY': '중국 위안',
            'AUD': '호주 달러',
            'CAD': '캐나다 달러',
            'CHF': '스위스 프랑',
            'SGD': '싱가포르 달러',
            'HKD': '홍콩 달러',
            'THB': '태국 바트',
            'VND': '베트남 동',
            'INR': '인도 루피',
            'BRL': '브라질 헤알',
            'RUB': '러시아 루블',
            'MXN': '멕시코 페소',
            'ZAR': '남아프리카 랜드',
            'TRY': '터키 리라',
            'PLN': '폴란드 즐로티',
            'CZK': '체코 코루나'
        }
        
        insert_query = """
            INSERT INTO exchange_rate_history (
                currency_code, currency_name, deal_base_rate, tts, ttb,
                source, recorded_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        records = []
        
        for days_ago in range(30, 0, -1):
            record_date = datetime.now() - timedelta(days=days_ago)
            
            for currency_code, base_rate in base_rates.items():
                # 약간의 랜덤 변동 추가
                import random
                variation = random.uniform(-0.02, 0.02)  # ±2% 변동
                current_rate = base_rate * (1 + variation)
                
                # TTS/TTB 계산 (매매기준율 기준 ±2%)
                tts = current_rate * 1.02
                ttb = current_rate * 0.98
                
                records.append((
                    currency_code,
                    currency_names[currency_code],
                    round(current_rate, 4),
                    round(tts, 4),
                    round(ttb, 4),
                    'BOK',  # 한국은행
                    record_date,
                    datetime.now()
                ))
        
        await cursor.executemany(insert_query, records)
        print(f"✅ Inserted {len(records)} exchange rate records")
    
    async def generate_daily_aggregates(self, cursor):
        """일별 집계 데이터 생성"""
        # 기존 데이터 확인
        await cursor.execute("SELECT COUNT(*) FROM daily_exchange_rates")
        count = await cursor.fetchone()
        
        if count[0] > 0:
            print(f"ℹ️ Daily aggregate data already exists ({count[0]} records)")
            return
        
        # 일별 집계 데이터 생성
        aggregate_query = """
            INSERT INTO daily_exchange_rates (
                currency_code, trade_date, open_rate, close_rate,
                high_rate, low_rate, avg_rate, volume
            )
            SELECT 
                currency_code,
                DATE(recorded_at) as trade_date,
                MIN(deal_base_rate) as open_rate,
                MAX(deal_base_rate) as close_rate,
                MAX(deal_base_rate) as high_rate,
                MIN(deal_base_rate) as low_rate,
                AVG(deal_base_rate) as avg_rate,
                COUNT(*) as volume
            FROM exchange_rate_history 
            GROUP BY currency_code, DATE(recorded_at)
        """
        
        await cursor.execute(aggregate_query)
        affected_rows = cursor.rowcount
        print(f"✅ Generated {affected_rows} daily aggregate records")
    
    async def initialize_redis(self):
        """Redis 초기화"""
        print("🔴 Initializing Redis...")
        
        try:
            # Redis 연결
            redis_url = f"redis://{self.redis_config['host']}:{self.redis_config['port']}"
            redis = aioredis.from_url(redis_url, decode_responses=True)
            
            # 연결 테스트
            await redis.ping()
            
            # 샘플 환율 데이터를 Redis에 캐시
            await self.cache_sample_rates(redis)
            
            await redis.close()
            print("✅ Redis initialization completed")
            
        except Exception as e:
            print(f"❌ Redis initialization failed: {e}")
            # Redis 실패는 치명적이지 않으므로 계속 진행
            print("⚠️ Continuing without Redis cache")
    
    async def cache_sample_rates(self, redis):
        """샘플 환율 데이터를 Redis에 캐시"""
        sample_rates = {
            'USD': {'currency_name': '미국 달러', 'deal_base_rate': '1350.0', 'tts': '1377.0', 'ttb': '1323.0'},
            'JPY': {'currency_name': '일본 엔', 'deal_base_rate': '9.2', 'tts': '9.38', 'ttb': '9.02'},
            'EUR': {'currency_name': '유로', 'deal_base_rate': '1450.0', 'tts': '1479.0', 'ttb': '1421.0'},
            'GBP': {'currency_name': '영국 파운드', 'deal_base_rate': '1650.0', 'tts': '1683.0', 'ttb': '1617.0'},
            'CNY': {'currency_name': '중국 위안', 'deal_base_rate': '185.0', 'tts': '188.7', 'ttb': '181.3'}
        }
        
        for currency_code, rate_data in sample_rates.items():
            cache_key = f"rate:{currency_code}"
            rate_data['source'] = 'BOK'
            rate_data['last_updated_at'] = datetime.now().isoformat() + 'Z'
            
            await redis.hset(cache_key, mapping=rate_data)
            await redis.expire(cache_key, 600)  # 10분 TTL
        
        print(f"✅ Cached {len(sample_rates)} exchange rates in Redis")
    


async def main():
    """메인 함수"""
    initializer = ServiceInitializer()
    await initializer.initialize_all()


if __name__ == "__main__":
    asyncio.run(main())