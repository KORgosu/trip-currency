# Trip Currency Shared Package

여행 환율 서비스의 공통 모듈 라이브러리입니다.

## 📁 구조

```
package-shared/
├── __init__.py          # 패키지 초기화
├── config.py            # 환경 설정 관리
├── database.py          # 데이터베이스 연결 (MySQL, Redis, MongoDB, DynamoDB)
├── models.py            # Pydantic 모델 정의
├── exceptions.py        # 커스텀 예외 클래스
├── logging.py           # 구조화된 로깅
├── messaging.py         # Kafka/SQS 메시징
├── utils.py             # 유틸리티 함수들
└── README.md            # 이 파일
```

## 🚀 주요 기능

### Config (config.py)
- 환경별 설정 관리 (local, dev, staging, prod)
- 데이터베이스 연결 설정
- 메시징 시스템 설정
- CORS 및 로깅 설정

### Database (database.py)
- **MySQLHelper**: MariaDB 연결 및 쿼리 실행
- **RedisHelper**: Redis 캐시 관리
- **MongoDBHelper**: MongoDB 연결 및 컬렉션 관리
- **DynamoDBHelper**: DynamoDB 연결 (로컬에서는 Mock)
- **DatabaseManager**: 통합 데이터베이스 관리

### Models (models.py)
- **ExchangeRate**: 환율 정보
- **CurrencyInfo**: 통화 정보
- **UserSelection**: 사용자 선택
- **RankingItem**: 랭킹 항목
- **HistoryDataPoint**: 히스토리 데이터 포인트
- **SuccessResponse/ErrorResponse**: API 응답 모델

### Exceptions (exceptions.py)
- **BaseServiceException**: 기본 서비스 예외
- **InvalidCurrencyCodeError**: 잘못된 통화 코드
- **DatabaseError**: 데이터베이스 에러
- **ExternalAPIError**: 외부 API 에러
- **RateLimitExceededError**: 요청 제한 초과

### Logging (logging.py)
- 구조화된 로깅 (structlog)
- 상관관계 ID 관리
- 환경별 로그 포맷 (로컬: 텍스트, 프로덕션: JSON)

### Messaging (messaging.py)
- **MessageProducer**: Kafka/SQS 메시지 전송
- **MessageConsumer**: Kafka 메시지 수신
- **send_exchange_rate_update**: 환율 업데이트 이벤트 전송

### Utils (utils.py)
- **SecurityUtils**: UUID 생성, 해시화
- **DateTimeUtils**: 날짜/시간 유틸리티
- **DataUtils**: 데이터 정리 및 변환
- **PerformanceUtils**: 성능 측정
- **ValidationUtils**: 데이터 검증
- **HTTPUtils**: HTTP 요청 유틸리티

## 📦 사용법

### 기본 import
```python
from shared.config import init_config, get_config
from shared.database import init_database, get_db_manager
from shared.models import ExchangeRate, CurrencyInfo
from shared.exceptions import BaseServiceException
from shared.logging import get_logger
from shared.utils import SecurityUtils, DateTimeUtils
```

### 설정 초기화
```python
# 서비스별 설정 초기화
config = init_config("currency-service")

# 데이터베이스 초기화
await init_database()

# 데이터베이스 매니저 가져오기
db_manager = get_db_manager()
```

### 로깅 사용
```python
logger = get_logger(__name__)

# 상관관계 ID 설정
set_correlation_id("corr_12345")

# 로그 출력
logger.info("Service started", service_name="currency-service")
```

### 데이터베이스 사용
```python
# MySQL 쿼리 실행
result = await db_manager.mysql.execute_query(
    "SELECT * FROM exchange_rate_history WHERE currency_code = %s",
    ("USD",)
)

# Redis 캐시 조회
cached_data = await db_manager.redis.get("rate:USD")

# MongoDB 컬렉션 사용
collection = await db_manager.mongodb.get_collection("rankings")
```

### 메시징 사용
```python
# 환율 업데이트 이벤트 전송
event_data = {
    "currency_code": "USD",
    "deal_base_rate": 1300.50,
    "updated_at": "2024-01-01T12:00:00Z"
}
await send_exchange_rate_update(event_data)
```

## 🔧 환경 변수

### 데이터베이스 설정
```bash
# MySQL
DB_HOST=localhost
DB_PORT=3306
DB_NAME=currency_db
DB_USER=currency_user
DB_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_USER=admin
MONGODB_PASSWORD=password
MONGODB_DATABASE=currency_db
```

### 메시징 설정
```bash
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# SQS (선택사항)
SQS_QUEUE_URL=https://sqs.region.amazonaws.com/account/queue-name
```

### 서비스 설정
```bash
# 환경
ENVIRONMENT=local
SERVICE_NAME=currency-service
PORT=8000

# 로깅
LOG_LEVEL=INFO
LOG_FORMAT=text

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## 🚀 Docker에서 사용

모든 서비스의 Dockerfile에서 shared 모듈을 복사하여 사용:

```dockerfile
# shared 모듈 복사
COPY ./package-shared /app/../shared

# Python 경로 설정
ENV PYTHONPATH=/app:/app/..
```

## 📝 참고사항

- 모든 모듈은 비동기(async/await) 방식으로 구현되어 있습니다
- 로컬 개발 환경에서는 DynamoDB가 Mock 모드로 동작합니다
- 프로덕션 환경에서는 실제 AWS 서비스를 사용합니다
- 모든 데이터베이스 연결은 연결 풀을 사용하여 성능을 최적화합니다
