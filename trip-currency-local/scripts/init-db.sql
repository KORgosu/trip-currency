-- Currency Travel Service Database Schema
-- MySQL/Aurora 호환 스키마 (최종 수정본)

-- 데이터베이스 생성 (필요시)
CREATE DATABASE IF NOT EXISTS currency_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE currency_db;

-- 통화 마스터 테이블
CREATE TABLE IF NOT EXISTS currencies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    currency_code VARCHAR(10) NOT NULL UNIQUE,
    currency_name_ko VARCHAR(100) NOT NULL,
    currency_name_en VARCHAR(100) NOT NULL,
    country_code VARCHAR(10) NOT NULL,
    country_name_ko VARCHAR(100) NOT NULL,
    country_name_en VARCHAR(100) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    decimal_places INT DEFAULT 2,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INT DEFAULT 999,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_currency_code (currency_code),
    INDEX idx_country_code (country_code),
    INDEX idx_active_order (is_active, display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 환율 이력 테이블 (메인 데이터)
CREATE TABLE IF NOT EXISTS exchange_rate_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_code VARCHAR(10) NOT NULL,
    currency_name VARCHAR(100) NOT NULL,
    deal_base_rate DECIMAL(18, 4) NOT NULL,
    tts DECIMAL(18, 4) NULL COMMENT '송금 보낼 때',
    ttb DECIMAL(18, 4) NULL COMMENT '받을 때',
    source VARCHAR(50) NOT NULL,
    recorded_at DATETIME NOT NULL COMMENT '환율 기준 시점',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성 시점',
    
    INDEX idx_currency_date (currency_code, recorded_at DESC),
    INDEX idx_recorded_at (recorded_at DESC),
    INDEX idx_currency_source (currency_code, source),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_exchange_rate_latest (currency_code, recorded_at DESC, deal_base_rate),
    
    FOREIGN KEY (currency_code) REFERENCES currencies(currency_code) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 일별 집계 테이블 (성능 최적화용)
CREATE TABLE IF NOT EXISTS daily_exchange_rates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    open_rate DECIMAL(18, 4) NOT NULL COMMENT '시가',
    close_rate DECIMAL(18, 4) NOT NULL COMMENT '종가',
    high_rate DECIMAL(18, 4) NOT NULL COMMENT '고가',
    low_rate DECIMAL(18, 4) NOT NULL COMMENT '저가',
    avg_rate DECIMAL(18, 4) NOT NULL COMMENT '평균가',
    volume INT DEFAULT 0 COMMENT '데이터 포인트 수',
    volatility DECIMAL(10, 6) NULL COMMENT '변동성',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_currency_date (currency_code, trade_date),
    INDEX idx_trade_date (trade_date DESC),
    INDEX idx_currency_date_desc (currency_code, trade_date DESC),
    INDEX idx_daily_rates_latest (currency_code, trade_date DESC, close_rate),
    
    FOREIGN KEY (currency_code) REFERENCES currencies(currency_code) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 데이터 수집 로그 테이블
CREATE TABLE IF NOT EXISTS collection_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    correlation_id VARCHAR(100) NOT NULL,
    source VARCHAR(50) NOT NULL,
    status ENUM('SUCCESS', 'FAILED', 'PARTIAL') NOT NULL,
    currency_count INT DEFAULT 0,
    error_message TEXT NULL,
    processing_time_ms INT DEFAULT 0,
    collected_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_collected_at (collected_at DESC),
    INDEX idx_source_status (source, status),
    INDEX idx_correlation_id (correlation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 기본 통화 데이터 삽입 (69개 통화)
INSERT INTO currencies (currency_code, currency_name_ko, currency_name_en, country_code, country_name_ko, country_name_en, symbol, decimal_places, display_order) 
VALUES
-- 주요 통화
('USD', '미국 달러', 'US Dollar', 'US', '미국', 'United States', '$', 2, 1),
('JPY', '일본 엔', 'Japanese Yen', 'JP', '일본', 'Japan', '¥', 2, 2),
('EUR', '유럽연합 유로', 'Euro', 'EU', '유럽연합', 'European Union', '€', 2, 3),
('GBP', '영국 파운드', 'British Pound', 'GB', '영국', 'United Kingdom', '£', 2, 4),
('CNY', '중국 위안', 'Chinese Yuan', 'CN', '중국', 'China', '¥', 2, 5),
('AUD', '호주 달러', 'Australian Dollar', 'AU', '호주', 'Australia', 'A$', 2, 6),
('CAD', '캐나다 달러', 'Canadian Dollar', 'CA', '캐나다', 'Canada', 'C$', 2, 7),
('CHF', '스위스 프랑', 'Swiss Franc', 'CH', '스위스', 'Switzerland', 'CHF', 2, 8),
('HKD', '홍콩 달러', 'Hong Kong Dollar', 'HK', '홍콩', 'Hong Kong', 'HK$', 2, 9),
('SGD', '싱가포르 달러', 'Singapore Dollar', 'SG', '싱가포르', 'Singapore', 'S$', 2, 10),
('KRW', '한국 원', 'Korean Won', 'KR', '한국', 'South Korea', '₩', 2, 11),
-- 추가 아시아 통화
('TWD', '대만 달러', 'Taiwan Dollar', 'TW', '대만', 'Taiwan', 'NT$', 2, 12),
('MYR', '말레이시아 링깃', 'Malaysian Ringgit', 'MY', '말레이시아', 'Malaysia', 'RM', 2, 13),
('PHP', '필리핀 페소', 'Philippine Peso', 'PH', '필리핀', 'Philippines', '₱', 2, 14),
('IDR', '인도네시아 루피아', 'Indonesian Rupiah', 'ID', '인도네시아', 'Indonesia', 'Rp', 2, 15),
('NZD', '뉴질랜드 달러', 'New Zealand Dollar', 'NZ', '뉴질랜드', 'New Zealand', 'NZ$', 2, 16),
('ILS', '이스라엘 세켈', 'Israeli Shekel', 'IL', '이스라엘', 'Israel', '₪', 2, 17),
('AED', '아랍에미리트 디르함', 'UAE Dirham', 'AE', '아랍에미리트', 'United Arab Emirates', 'د.إ', 2, 18),
('QAR', '카타르 리얄', 'Qatari Rial', 'QA', '카타르', 'Qatar', 'ر.ق', 2, 19),
('KWD', '쿠웨이트 디나르', 'Kuwaiti Dinar', 'KW', '쿠웨이트', 'Kuwait', 'د.ك', 3, 20),
('BHD', '바레인 디나르', 'Bahraini Dinar', 'BH', '바레인', 'Bahrain', 'د.ب', 3, 21),
('OMR', '오만 리얄', 'Omani Rial', 'OM', '오만', 'Oman', 'ر.ع.', 3, 22),
('JOD', '요르단 디나르', 'Jordanian Dinar', 'JO', '요르단', 'Jordan', 'د.ا', 3, 23),
('LBP', '레바논 파운드', 'Lebanese Pound', 'LB', '레바논', 'Lebanon', 'ل.ل', 2, 24),
('PKR', '파키스탄 루피', 'Pakistani Rupee', 'PK', '파키스탄', 'Pakistan', '₨', 2, 25),
('BDT', '방글라데시 타카', 'Bangladeshi Taka', 'BD', '방글라데시', 'Bangladesh', '৳', 2, 26),
('LKR', '스리랑카 루피', 'Sri Lankan Rupee', 'LK', '스리랑카', 'Sri Lanka', '₨', 2, 27),
('NPR', '네팔 루피', 'Nepalese Rupee', 'NP', '네팔', 'Nepal', '₨', 2, 28),
('AFN', '아프가니스탄 아프가니', 'Afghan Afghani', 'AF', '아프가니스탄', 'Afghanistan', '؋', 2, 29),
('KZT', '카자흐스탄 텡게', 'Kazakhstani Tenge', 'KZ', '카자흐스탄', 'Kazakhstan', '₸', 2, 30),
('UZS', '우즈베키스탄 숨', 'Uzbekistani Som', 'UZ', '우즈베키스탄', 'Uzbekistan', 'лв', 2, 31),
('KGS', '키르기스스탄 솜', 'Kyrgyzstani Som', 'KG', '키르기스스탄', 'Kyrgyzstan', 'лв', 2, 32),
('TJS', '타지키스탄 소모니', 'Tajikistani Somoni', 'TJ', '타지키스탄', 'Tajikistan', 'SM', 2, 33),
('TMT', '투르크메니스탄 마나트', 'Turkmenistani Manat', 'TM', '투르크메니스탄', 'Turkmenistan', 'T', 2, 34),
-- 추가 유럽 통화
('ISK', '아이슬란드 크로나', 'Icelandic Krona', 'IS', '아이슬란드', 'Iceland', 'kr', 0, 35),
('RON', '루마니아 레우', 'Romanian Leu', 'RO', '루마니아', 'Romania', 'lei', 2, 36),
('BGN', '불가리아 레프', 'Bulgarian Lev', 'BG', '불가리아', 'Bulgaria', 'лв', 2, 37),
('HRK', '크로아티아 쿠나', 'Croatian Kuna', 'HR', '크로아티아', 'Croatia', 'kn', 2, 38),
('RSD', '세르비아 디나르', 'Serbian Dinar', 'RS', '세르비아', 'Serbia', 'дин', 2, 39),
('UAH', '우크라이나 흐리브냐', 'Ukrainian Hryvnia', 'UA', '우크라이나', 'Ukraine', '₴', 2, 40),
('BYN', '벨라루스 루블', 'Belarusian Ruble', 'BY', '벨라루스', 'Belarus', 'Br', 2, 41),
-- 추가 아메리카 통화
('ARS', '아르헨티나 페소', 'Argentine Peso', 'AR', '아르헨티나', 'Argentina', '$', 2, 42),
('CLP', '칠레 페소', 'Chilean Peso', 'CL', '칠레', 'Chile', '$', 0, 43),
('COP', '콜롬비아 페소', 'Colombian Peso', 'CO', '콜롬비아', 'Colombia', '$', 2, 44),
('PEN', '페루 솔', 'Peruvian Sol', 'PE', '페루', 'Peru', 'S/', 2, 45),
('UYU', '우루과이 페소', 'Uruguayan Peso', 'UY', '우루과이', 'Uruguay', '$U', 2, 46),
('BOB', '볼리비아 볼리비아노', 'Bolivian Boliviano', 'BO', '볼리비아', 'Bolivia', 'Bs', 2, 47),
('PYG', '파라과이 과라니', 'Paraguayan Guarani', 'PY', '파라과이', 'Paraguay', '₲', 0, 48),
('VES', '베네수엘라 볼리바르', 'Venezuelan Bolivar', 'VE', '베네수엘라', 'Venezuela', 'Bs.S', 2, 49),
-- 추가 아프리카/중동 통화
('EGP', '이집트 파운드', 'Egyptian Pound', 'EG', '이집트', 'Egypt', '£', 2, 50),
('MAD', '모로코 디르함', 'Moroccan Dirham', 'MA', '모로코', 'Morocco', 'د.م.', 2, 51),
('TND', '튀니지 디나르', 'Tunisian Dinar', 'TN', '튀니지', 'Tunisia', 'د.ت', 3, 52),
('NGN', '나이지리아 나이라', 'Nigerian Naira', 'NG', '나이지리아', 'Nigeria', '₦', 2, 53),
('KES', '케냐 실링', 'Kenyan Shilling', 'KE', '케냐', 'Kenya', 'KSh', 2, 54),
('UGX', '우간다 실링', 'Ugandan Shilling', 'UG', '우간다', 'Uganda', 'USh', 0, 55),
('TZS', '탄자니아 실링', 'Tanzanian Shilling', 'TZ', '탄자니아', 'Tanzania', 'TSh', 2, 56),
-- 기타 주요 통화
('CZK', '체코 코루나', 'Czech Koruna', 'CZ', '체코', 'Czech Republic', 'Kč', 2, 57),
('DKK', '덴마크 크로네', 'Danish Krone', 'DK', '덴마크', 'Denmark', 'kr', 2, 58),
('HUF', '헝가리 포린트', 'Hungarian Forint', 'HU', '헝가리', 'Hungary', 'Ft', 2, 59),
('NOK', '노르웨이 크로네', 'Norwegian Krone', 'NO', '노르웨이', 'Norway', 'kr', 2, 60),
('SEK', '스웨덴 크로나', 'Swedish Krona', 'SE', '스웨덴', 'Sweden', 'kr', 2, 61),
('THB', '태국 바트', 'Thai Baht', 'TH', '태국', 'Thailand', '฿', 2, 62),
('VND', '베트남 동', 'Vietnamese Dong', 'VN', '베트남', 'Vietnam', '₫', 0, 63),
('INR', '인도 루피', 'Indian Rupee', 'IN', '인도', 'India', '₹', 2, 64),
('BRL', '브라질 헤알', 'Brazilian Real', 'BR', '브라질', 'Brazil', 'R$', 2, 65),
('RUB', '러시아 루블', 'Russian Ruble', 'RU', '러시아', 'Russia', '₽', 2, 66),
('MXN', '멕시코 페소', 'Mexican Peso', 'MX', '멕시코', 'Mexico', '$', 2, 67),
('ZAR', '남아프리카 공화국 랜드', 'South African Rand', 'ZA', '남아프리카 공화국', 'South Africa', 'R', 2, 68),
('TRY', '터키 리라', 'Turkish Lira', 'TR', '터키', 'Turkey', '₺', 2, 69)
ON DUPLICATE KEY UPDATE
    currency_name_ko = VALUES(currency_name_ko),
    currency_name_en = VALUES(currency_name_en),
    country_name_ko = VALUES(country_name_ko),
    country_name_en = VALUES(country_name_en),
    symbol = VALUES(symbol),
    decimal_places = VALUES(decimal_places),
    display_order = VALUES(display_order);

-- 샘플 환율 데이터 삽입 (테스트용)
INSERT INTO exchange_rate_history (currency_code, currency_name, deal_base_rate, tts, ttb, source, recorded_at) 
VALUES
('USD', '미국 달러', 1392.40, 1420.85, 1363.95, 'sample', NOW() - INTERVAL 1 HOUR),
('JPY', '일본 엔', 9.46, 9.65, 9.27, 'sample', NOW() - INTERVAL 1 HOUR),
('EUR', '유럽연합 유로', 1456.80, 1486.94, 1426.66, 'sample', NOW() - INTERVAL 1 HOUR),
('GBP', '영국 파운드', 1678.50, 1712.07, 1644.93, 'sample', NOW() - INTERVAL 1 HOUR),
('CNY', '중국 위안', 192.30, 196.15, 188.45, 'sample', NOW() - INTERVAL 1 HOUR)
ON DUPLICATE KEY UPDATE
    deal_base_rate = VALUES(deal_base_rate),
    tts = VALUES(tts),
    ttb = VALUES(ttb),
    recorded_at = VALUES(recorded_at);

-- 뷰 생성: 최신 환율 조회용
CREATE OR REPLACE VIEW latest_exchange_rates AS
SELECT 
    h.currency_code,
    c.currency_name_ko as currency_name,
    c.symbol,
    h.deal_base_rate,
    h.tts,
    h.ttb,
    h.source,
    h.recorded_at,
    h.created_at
FROM exchange_rate_history h
INNER JOIN currencies c ON h.currency_code = c.currency_code
INNER JOIN (
    SELECT currency_code, MAX(recorded_at) as max_recorded_at
    FROM exchange_rate_history 
    GROUP BY currency_code
) latest ON h.currency_code = latest.currency_code 
          AND h.recorded_at = latest.max_recorded_at
WHERE c.is_active = TRUE
ORDER BY c.display_order;

-- 프로시저: 일별 집계 데이터 생성 (수정된 버전)
DELIMITER //
DROP PROCEDURE IF EXISTS GenerateDailyAggregates;

CREATE PROCEDURE GenerateDailyAggregates(IN in_target_date DATE)
BEGIN
    START TRANSACTION;

    INSERT INTO daily_exchange_rates
        (currency_code, trade_date, open_rate, close_rate, high_rate, low_rate, avg_rate, volume, volatility)
    WITH DailyDataWithWindowFunctions AS (
        SELECT
            h.currency_code,
            h.deal_base_rate,
            FIRST_VALUE(h.deal_base_rate) OVER w AS open_rate,
            LAST_VALUE(h.deal_base_rate) OVER w AS close_rate,
            MAX(h.deal_base_rate) OVER w_partition AS high_rate,
            MIN(h.deal_base_rate) OVER w_partition AS low_rate
        FROM exchange_rate_history h
        WHERE DATE(h.recorded_at) = in_target_date   -- ✅ 파라미터 직접 사용
        WINDOW w AS (
            PARTITION BY h.currency_code
            ORDER BY h.recorded_at
            RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ),
        w_partition AS (
            PARTITION BY h.currency_code
        )
    ),
    AggregatedData AS (
        SELECT
            currency_code,
            in_target_date AS trade_date,           -- ✅ 그대로 사용
            MAX(open_rate) AS open_rate,
            MAX(close_rate) AS close_rate,
            MAX(high_rate) AS high_rate,
            MIN(low_rate) AS low_rate,
            AVG(deal_base_rate) AS avg_rate,
            COUNT(deal_base_rate) AS volume,
            STDDEV(deal_base_rate) AS volatility
        FROM DailyDataWithWindowFunctions
        GROUP BY currency_code
    )
    SELECT
        currency_code,
        trade_date,
        open_rate,
        close_rate,
        high_rate,
        low_rate,
        avg_rate,
        volume,
        volatility
    FROM AggregatedData AS new
    ON DUPLICATE KEY UPDATE
        open_rate = new.open_rate,
        close_rate = new.close_rate,
        high_rate = new.high_rate,
        low_rate = new.low_rate,
        avg_rate = new.avg_rate,
        volume = new.volume,
        volatility = new.volatility,
        updated_at = CURRENT_TIMESTAMP;

    COMMIT;
END //
DELIMITER ;

-- 함수: 환율 변화율 계산

DROP FUNCTION IF EXISTS CalculateChangePercent;

DELIMITER //
CREATE FUNCTION CalculateChangePercent(current_rate DECIMAL(18,4), previous_rate DECIMAL(18,4))
RETURNS DECIMAL(10,4)
READS SQL DATA
DETERMINISTIC
BEGIN
    IF previous_rate IS NULL OR previous_rate = 0 THEN
        RETURN 0;
    END IF;
    
    RETURN ((current_rate - previous_rate) / previous_rate) * 100;
END //
DELIMITER ;

COMMIT;



-- 데이터 정리를 위한 이벤트 스케줄러 (선택사항 - 활성화 시 아래 주석 해제)
-- SET GLOBAL event_scheduler = ON;
-- 
-- CREATE EVENT IF NOT EXISTS cleanup_old_exchange_rates
-- ON SCHEDULE EVERY 1 DAY
-- STARTS CURRENT_TIMESTAMP
-- DO
--   DELETE FROM exchange_rate_history 
--   WHERE recorded_at < DATE_SUB(NOW(), INTERVAL 2 YEAR);