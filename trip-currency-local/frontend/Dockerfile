# Frontend Dockerfile for React + Vite Application
# Multi-stage build for optimized production image

# Stage 1: Build stage
FROM node:20-alpine AS builder

# 작업 디렉토리 설정
WORKDIR /app

# package.json과 package-lock.json 복사 (캐시 최적화)
COPY package*.json ./

# 의존성 설치 (빌드용이므로 devDependencies 포함)
RUN npm install --legacy-peer-deps --silent

# 소스 코드 복사
COPY . .

# 애플리케이션 빌드
RUN npm run build

# Stage 2: Production stage
FROM nginx:alpine AS production

# Nginx 설정 파일 복사
COPY nginx.conf /etc/nginx/nginx.conf

# 빌드된 파일들을 Nginx 서빙 디렉토리로 복사
COPY --from=builder /app/dist /usr/share/nginx/html

# 포트 노출
EXPOSE 80

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/ || exit 1

# Nginx 시작
CMD ["nginx", "-g", "daemon off;"]
