# History Service Dockerfile
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치 (네트워크 문제 해결을 위한 재시도 로직)
RUN for i in 1 2 3; do \
        apt-get update && \
        apt-get install -y \
            gcc \
            default-libmysqlclient-dev \
            pkg-config \
            curl \
        && rm -rf /var/lib/apt/lists/* \
        && break || \
        (echo "시도 $i 실패, 10초 후 재시도..." && sleep 10); \
    done

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 공유 패키지 복사 및 설치
COPY package-shared /app/package-shared
RUN pip install -e /app/package-shared

# 애플리케이션 코드 복사
COPY . /app

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 애플리케이션 실행
CMD ["python", "main.py"]