#!/bin/bash

echo "🧹 Trip Service 전체 재빌드 및 재배포 시작..."

# 1. 현재 쿠버네티스 리소스 정리
echo "📦 기존 쿠버네티스 리소스 정리 중..."
kubectl delete all --all 2>/dev/null || true
kubectl delete pvc --all 2>/dev/null || true
kubectl delete configmap --all 2>/dev/null || true
kubectl delete secret --all 2>/dev/null || true
kubectl delete cronjob --all 2>/dev/null || true

# 2. Docker 이미지 정리
echo "🐳 기존 Docker 이미지 정리 중..."
docker rmi $(docker images "trip-service/*" -q) 2>/dev/null || true

# 3. 서비스 이미지 빌드
echo "🔨 서비스 이미지 빌드 시작..."

# 전체 이미지 빌드
services=("frontend" "service-currency" "service-history" "service-ranking" "service-dataingestor")

for service in "${services[@]}"; do
    echo "📦 $service 빌드 중..."
    if [[ "$service" == "frontend" ]]; then
        docker build -f frontend/Dockerfile -t trip-service/frontend:latest . || {
            echo "❌ Frontend 빌드 실패"
            exit 1
        }
    else
        service_name="${service#service-}"
        docker build -f $service/Dockerfile -t trip-service/$service_name-service:latest . || {
            echo "❌ $service 빌드 실패"
            exit 1
        }
    fi
    echo "✅ $service 빌드 완료"
done

# 4. 쿠버네티스 리소스 배포
echo "🚀 쿠버네티스 리소스 배포 시작..."

# 네임스페이스 확인/생성
kubectl get namespace default >/dev/null 2>&1 || kubectl create namespace default

# Phase 0: MetalLB 배포 (LoadBalancer 지원)
echo "🔧 Phase 0: MetalLB 배포 중..."
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

# MetalLB 준비 대기
echo "⏳ MetalLB 준비 대기 중..."
kubectl wait --namespace metallb-system --for=condition=ready pod --selector=app=metallb --timeout=300s

# MetalLB 설정 적용
kubectl apply -f k8s/base/metallb/

echo "✅ MetalLB 설정 완료"

# Phase 1: Infrastructure (Database, Cache, Message Queue)
echo "📊 Phase 1: 인프라 배포 중..."
kubectl apply -f k8s/base/secrets.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/mysql/
kubectl apply -f k8s/base/mongodb/
kubectl apply -f k8s/base/redis/
kubectl apply -f k8s/base/kafka/

# 데이터베이스 시작 대기
echo "⏳ 데이터베이스 준비 대기 중..."
kubectl wait --for=condition=ready pod -l app=mysql --timeout=300s
kubectl wait --for=condition=ready pod -l app=mongodb --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis --timeout=300s
kubectl wait --for=condition=ready pod -l app=kafka --timeout=300s

# Phase 2: Application Services
echo "🎯 Phase 2: 애플리케이션 서비스 배포 중..."
kubectl apply -f k8s/base/services/currency-service/
kubectl apply -f k8s/base/services/history-service/
kubectl apply -f k8s/base/services/ranking-service/
kubectl apply -f k8s/base/services/dataingestor-service/
kubectl apply -f k8s/base/services/frontend/

# 서비스 시작 대기
echo "⏳ 애플리케이션 서비스 준비 대기 중..."
kubectl wait --for=condition=ready pod -l app=currency-service --timeout=300s
kubectl wait --for=condition=ready pod -l app=history-service --timeout=300s
kubectl wait --for=condition=ready pod -l app=ranking-service --timeout=300s
kubectl wait --for=condition=ready pod -l app=frontend --timeout=300s

# Phase 3: HPA 배포
echo "📈 Phase 3: HPA 배포 중..."
kubectl apply -f k8s/base/hpa/ 2>/dev/null || echo "⚠️ HPA 배포 건너뜀 (Metrics Server 필요)"

# 5. 최종 상태 확인
echo "🔍 최종 배포 상태 확인..."
echo "📦 Pod 상태:"
kubectl get pods -o wide

echo ""
echo "🔗 Service 상태:"
kubectl get svc

echo ""
echo "📊 CronJob 상태:"
kubectl get cronjob

# 6. 접속 정보 표시
FRONTEND_PORT=$(kubectl get svc frontend-service -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "30793")
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || echo "192.168.201.85")

echo ""
echo "🎉 배포 완료!"
echo "🌐 Frontend 접속: http://$NODE_IP:$FRONTEND_PORT"
echo "📊 서비스 상태 모니터링: kubectl get pods"
echo "📝 로그 확인: kubectl logs <pod-name>"

# 7. 초기 데이터 설정
echo "📊 초기 환율 데이터 설정 중..."
sleep 30  # 서비스 완전 시작 대기

# Redis에 환율 데이터 추가
REDIS_POD=$(kubectl get pods -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ ! -z "$REDIS_POD" ]; then
    kubectl exec $REDIS_POD -- redis-cli HSET "rate:USD" currency_code "USD" currency_name "미국 달러" deal_base_rate "1300.50" source "initial" last_updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    kubectl exec $REDIS_POD -- redis-cli HSET "rate:EUR" currency_code "EUR" currency_name "유로" deal_base_rate "1450.25" source "initial" last_updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    kubectl exec $REDIS_POD -- redis-cli HSET "rate:JPY" currency_code "JPY" currency_name "일본 엔" deal_base_rate "9.15" source "initial" last_updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    kubectl exec $REDIS_POD -- redis-cli HSET "rate:GBP" currency_code "GBP" currency_name "영국 파운드" deal_base_rate "1650.75" source "initial" last_updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "✅ 초기 환율 데이터 설정 완료"
fi

echo ""
echo "🚀 모든 배포가 완료되었습니다!"
echo "💡 팁: DataIngestor CronJob이 5분마다 환율 데이터를 자동 수집합니다."