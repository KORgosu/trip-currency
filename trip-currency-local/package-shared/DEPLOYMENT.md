# Trip Currency Shared Package v1.0.0 배포 가이드

## 📦 패키지 정보

- **패키지명**: `trip-currency-shared`
- **버전**: `1.0.0`
- **작성자**: KORgosu
- **라이선스**: MIT
- **Python 버전**: >= 3.8

## 🚀 배포 방법

### 1. 로컬 빌드 및 테스트

```bash
# package-shared 디렉토리로 이동
cd package-shared

# 빌드 스크립트 실행
python build_package.py
```

### 2. GitHub에 코드 푸시

```bash
# Git 초기화 (필요한 경우)
git init

# 원격 저장소 추가
git remote add origin https://github.com/KORgosu/shared_package_local.git

# 파일 추가 및 커밋
git add .
git commit -m "Initial release v1.0.0"

# 메인 브랜치에 푸시
git push -u origin main
```

### 3. 버전 태그 생성

```bash
# v1.0.0 태그 생성
git tag v1.0.0

# 태그 푸시
git push origin v1.0.0
```

### 4. PyPI 배포

#### 방법 1: PyPI Public (권장)

```bash
# PyPI 계정 생성 및 API 토큰 발급
# https://pypi.org/manage/account/token/

# 환경 변수 설정
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your-api-token

# PyPI에 업로드
python -m twine upload dist/*
```

#### 방법 2: GitHub Packages

```bash
# GitHub Personal Access Token 발급
# https://github.com/settings/tokens

# 환경 변수 설정
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=ghp_your-github-token

# GitHub Packages에 업로드
python -m twine upload --repository github dist/*
```

#### 방법 3: Git Direct (개발용)

```bash
# requirements.txt에서 직접 설치
git+https://github.com/KORgosu/shared_package_local.git@v1.0.0#egg=trip-currency-shared
```

## 📋 서비스 코드 수정

### 1. Dockerfile 수정

**기존:**
```dockerfile
# shared 모듈 복사
COPY ./package-shared /app/../shared

# shared 모듈을 위한 Python 경로 설정
ENV PYTHONPATH=/app:/app/..
```

**변경 후:**
```dockerfile
# 패키지 설치
RUN pip install trip-currency-shared==1.0.0

# 또는 Git에서 직접 설치
RUN pip install git+https://github.com/KORgosu/shared_package_local.git@v1.0.0#egg=trip-currency-shared
```

### 2. requirements.txt 수정

**기존:**
```txt
# 개별 의존성들...
fastapi==0.104.1
uvicorn[standard]==0.24.0
# ... 기타 의존성들
```

**변경 후:**
```txt
# Trip Currency Shared Package
trip-currency-shared==1.0.0

# 또는 Git에서 직접 설치
git+https://github.com/KORgosu/shared_package_local.git@v1.0.0#egg=trip-currency-shared
```

### 3. Import 코드 (변경 불필요)

```python
# 기존 코드 그대로 사용 가능
from shared.config import init_config, get_config
from shared.database import init_database, get_db_manager
from shared.models import ExchangeRate, CurrencyInfo
from shared.exceptions import BaseServiceException
from shared.logging import get_logger
from shared.utils import SecurityUtils, DateTimeUtils
```

## 🔧 서비스별 수정 파일

### service-currency
- `service-currency/Dockerfile`
- `service-currency/requirements.txt`

### service-ranking
- `service-ranking/Dockerfile`
- `service-ranking/requirements.txt`

### service-history
- `service-history/Dockerfile`
- `service-history/requirements.txt`

### service-dataingestor
- `service-dataingestor/Dockerfile`
- `service-dataingestor/requirements.txt`

## 🧪 테스트 및 검증

### 1. 패키지 설치 테스트

```bash
# 가상환경 생성
python -m venv test_env
source test_env/bin/activate  # Windows: test_env\Scripts\activate

# 패키지 설치
pip install trip-currency-shared==1.0.0

# 설치 확인
python -c "import shared; print(shared.__version__)"
```

### 2. 서비스 동작 테스트

```bash
# Docker 이미지 빌드
docker-compose build

# 서비스 시작
docker-compose up -d

# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs service-currency
```

## 📈 버전 관리

### 버전 업데이트 시

1. **버전 번호 수정**
   - `setup.py`: `version = "1.0.1"`
   - `pyproject.toml`: `version = "1.0.1"`
   - `__init__.py`: `__version__ = "1.0.1"`

2. **변경사항 문서화**
   - `CHANGELOG.md` 업데이트
   - `README.md` 업데이트

3. **태그 생성 및 배포**
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

## 🚨 문제 해결

### 1. 패키지 설치 실패

```bash
# 캐시 정리
pip cache purge

# 강제 재설치
pip install --no-cache-dir --force-reinstall trip-currency-shared==1.0.0
```

### 2. Import 에러

```bash
# Python 경로 확인
python -c "import sys; print(sys.path)"

# 패키지 위치 확인
python -c "import shared; print(shared.__file__)"
```

### 3. 의존성 충돌

```bash
# 의존성 트리 확인
pip show trip-currency-shared

# 충돌하는 패키지 확인
pip check
```

## 📞 지원

- **GitHub Issues**: https://github.com/KORgosu/shared_package_local/issues
- **문서**: https://github.com/KORgosu/shared_package_local#readme
- **이메일**: korgosu@example.com

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.
