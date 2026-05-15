# Trip Service 전체 재빌드 및 재배포 스크립트
Write-Host "🧹 Trip Service 전체 재빌드 및 재배포 시작..." -ForegroundColor Green

# 1. 현재 쿠버네티스 리소스 정리
Write-Host "📦 기존 쿠버네티스 리소스 정리 중..." -ForegroundColor Yellow
try {
    kubectl delete all --all 2>$null
    kubectl delete pvc --all 2>$null
    kubectl delete configmap --all 2>$null
    kubectl delete secret --all 2>$null
    kubectl delete cronjob --all 2>$null
} catch {
    Write-Host "⚠️ 일부 리소스 정리 실패 (정상)" -ForegroundColor Yellow
}

# 2. Docker 이미지 정리
Write-Host "🐳 기존 Docker 이미지 정리 중..." -ForegroundColor Yellow
try {
    $images = docker images "trip-service/*" -q
    if ($images) {
        docker rmi $images 2>$null
    }
} catch {
    Write-Host "⚠️ 일부 이미지 정리 실패 (정상)" -ForegroundColor Yellow
}

# 3. 서비스 이미지 빌드
Write-Host "🔨 서비스 이미지 빌드 시작..." -ForegroundColor Green

$services = @("frontend", "service-currency", "service-history", "service-ranking", "service-dataingestor")

foreach ($service in $services) {
    Write-Host "📦 $service 빌드 중..." -ForegroundColor Cyan

    if ($service -eq "frontend") {
        $result = docker build -f frontend/Dockerfile -t trip-service/frontend:latest .
    } else {
        $serviceName = $service -replace "service-", ""
        $result = docker build -f $service/Dockerfile -t "trip-service/$serviceName-service:latest" .
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ $service 빌드 실패" -ForegroundColor Red
        exit 1
    }

    Write-Host "✅ $service 빌드 완료" -ForegroundColor Green
}

# 4. 쿠버네티스 리소스 배포
Write-Host "🚀 쿠버네티스 리소스 배포 시작..." -ForegroundColor Green

# Phase 0: MetalLB 배포 (LoadBalancer 지원)
Write-Host "🔧 Phase 0: MetalLB 배포 중..." -ForegroundColor Cyan
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

# MetalLB 준비 대기
Write-Host "⏳ MetalLB 준비 대기 중..." -ForegroundColor Yellow
kubectl wait --namespace metallb-system --for=condition=ready pod --selector=app=metallb --timeout=300s

# MetalLB 설정 적용
kubectl apply -f k8s/base/metallb/

Write-Host "✅ MetalLB 설정 완료" -ForegroundColor Green

# Phase 1: Infrastructure
Write-Host "📊 Phase 1: 인프라 배포 중..." -ForegroundColor Cyan
kubectl apply -f k8s/base/secrets.yaml
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/mysql/
kubectl apply -f k8s/base/mongodb/
kubectl apply -f k8s/base/redis/
kubectl apply -f k8s/base/kafka/

# 데이터베이스 시작 대기
Write-Host "⏳ 데이터베이스 준비 대기 중..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=mysql --timeout=300s
kubectl wait --for=condition=ready pod -l app=mongodb --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis --timeout=300s
kubectl wait --for=condition=ready pod -l app=kafka --timeout=300s

# Phase 2: Application Services
Write-Host "🎯 Phase 2: 애플리케이션 서비스 배포 중..." -ForegroundColor Cyan
kubectl apply -f k8s/base/services/currency-service/
kubectl apply -f k8s/base/services/history-service/
kubectl apply -f k8s/base/services/ranking-service/
kubectl apply -f k8s/base/services/dataingestor-service/
kubectl apply -f k8s/base/services/frontend/

# 서비스 시작 대기
Write-Host "⏳ 애플리케이션 서비스 준비 대기 중..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=currency-service --timeout=300s
kubectl wait --for=condition=ready pod -l app=history-service --timeout=300s
kubectl wait --for=condition=ready pod -l app=ranking-service --timeout=300s
kubectl wait --for=condition=ready pod -l app=frontend --timeout=300s

# Phase 3: HPA 배포
Write-Host "📈 Phase 3: HPA 배포 중..." -ForegroundColor Cyan
try {
    kubectl apply -f k8s/base/hpa/ 2>$null
} catch {
    Write-Host "⚠️ HPA 배포 건너뜀 (Metrics Server 필요)" -ForegroundColor Yellow
}

# 5. 최종 상태 확인
Write-Host "🔍 최종 배포 상태 확인..." -ForegroundColor Green

Write-Host "📦 Pod 상태:" -ForegroundColor Cyan
kubectl get pods -o wide

Write-Host "`n🔗 Service 상태:" -ForegroundColor Cyan
kubectl get svc

Write-Host "`n📊 CronJob 상태:" -ForegroundColor Cyan
kubectl get cronjob

# 6. 접속 정보 표시
try {
    $frontendPort = kubectl get svc frontend-service -o jsonpath='{.spec.ports[0].nodePort}' 2>$null
    if (-not $frontendPort) { $frontendPort = "30793" }

    $nodeIP = kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>$null
    if (-not $nodeIP) { $nodeIP = "192.168.201.85" }
} catch {
    $frontendPort = "30793"
    $nodeIP = "192.168.201.85"
}

Write-Host "`n🎉 배포 완료!" -ForegroundColor Green
Write-Host "🌐 Frontend 접속: http://$nodeIP`:$frontendPort" -ForegroundColor White
Write-Host "📊 서비스 상태 모니터링: kubectl get pods" -ForegroundColor White
Write-Host "📝 로그 확인: kubectl logs <pod-name>" -ForegroundColor White

# 7. 초기 데이터 설정
Write-Host "`n📊 초기 환율 데이터 설정 중..." -ForegroundColor Cyan
Start-Sleep -Seconds 30  # 서비스 완전 시작 대기

try {
    $redisPod = kubectl get pods -l app=redis -o jsonpath='{.items[0].metadata.name}' 2>$null
    if ($redisPod) {
        $currentTime = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

        kubectl exec $redisPod -- redis-cli HSET "rate:USD" currency_code "USD" currency_name "미국 달러" deal_base_rate "1300.50" source "initial" last_updated_at $currentTime
        kubectl exec $redisPod -- redis-cli HSET "rate:EUR" currency_code "EUR" currency_name "유로" deal_base_rate "1450.25" source "initial" last_updated_at $currentTime
        kubectl exec $redisPod -- redis-cli HSET "rate:JPY" currency_code "JPY" currency_name "일본 엔" deal_base_rate "9.15" source "initial" last_updated_at $currentTime
        kubectl exec $redisPod -- redis-cli HSET "rate:GBP" currency_code "GBP" currency_name "영국 파운드" deal_base_rate "1650.75" source "initial" last_updated_at $currentTime

        Write-Host "✅ 초기 환율 데이터 설정 완료" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️ 초기 데이터 설정 실패 (수동 설정 필요)" -ForegroundColor Yellow
}

Write-Host "`n🚀 모든 배포가 완료되었습니다!" -ForegroundColor Green
Write-Host "💡 팁: DataIngestor CronJob이 5분마다 환율 데이터를 자동 수집합니다." -ForegroundColor White