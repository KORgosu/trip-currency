# Trip Service 개발 환경 쿠버네티스 시작 스크립트 (PowerShell)
# 기존 배포 정리 + 인프라 구축 + 애플리케이션 이미지 빌드 + 쿠버네티스 배포

param(
    [string]$Tag = "dev-latest",
    [string]$Registry = "trip-service",
    [string]$Environment = "dev",
    [switch]$SkipCleanup = $false,
    [switch]$SkipBuild = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "🚀 Trip Service 개발 환경 쿠버네티스 시작..." -ForegroundColor Green

# 프로젝트 루트 디렉토리로 이동
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptPath
Set-Location $ProjectRoot

Write-Host "📦 이미지 태그: $Tag" -ForegroundColor Yellow
Write-Host "🏷️  레지스트리: $Registry" -ForegroundColor Yellow
Write-Host "🌍 환경: $Environment" -ForegroundColor Yellow
Write-Host "🧹 정리 건너뛰기: $SkipCleanup" -ForegroundColor Yellow
Write-Host "🔨 빌드 건너뛰기: $SkipBuild" -ForegroundColor Yellow

# ===========================================
# 0단계: 기존 배포 정리 (선택적)
# ===========================================

if (-not $SkipCleanup) {
    Write-Host ""
    Write-Host "🧹 0단계: 기존 배포 정리 시작..." -ForegroundColor Magenta

    # 기존 네임스페이스가 있는지 확인
    try {
        kubectl get namespace "trip-service-$Environment" | Out-Null
        Write-Host "🗑️  기존 배포 삭제 중..." -ForegroundColor Yellow

        # 기존 배포 삭제
        kubectl delete -k "k8s/overlays/$Environment" --timeout=60s --ignore-not-found=true

        # 네임스페이스 삭제
        kubectl delete namespace "trip-service-$Environment" --timeout=60s --ignore-not-found=true

        # 완전 삭제 대기
        Write-Host "⏳ 기존 리소스 정리 완료 대기 중..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10

        Write-Host "✅ 기존 배포 정리 완료!" -ForegroundColor Green
    } catch {
        Write-Host "ℹ️  기존 배포가 없거나 이미 정리됨" -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "⏭️  기존 배포 정리 건너뛰기" -ForegroundColor Gray
}

# ===========================================
# 1단계: 인프라 사전 구축
# ===========================================

Write-Host ""
Write-Host "🏗️  1단계: 인프라 사전 구축 시작..." -ForegroundColor Magenta

# MetalLB 설치 확인 및 설치
Write-Host "📡 MetalLB 설치 확인 중..." -ForegroundColor Cyan
try {
    kubectl get namespace metallb-system | Out-Null
    Write-Host "✅ MetalLB 이미 설치됨" -ForegroundColor Green
} catch {
    Write-Host "📡 MetalLB 설치 중..." -ForegroundColor Yellow
    kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml
    Write-Host "⏳ MetalLB 설치 완료 대기 중..." -ForegroundColor Yellow
    kubectl wait --namespace metallb-system --for=condition=ready pod --selector=app=metallb --timeout=90s
}

# Nginx Ingress Controller 설치 확인 및 설치
Write-Host "🌐 Nginx Ingress Controller 설치 확인 중..." -ForegroundColor Cyan
try {
    kubectl get namespace ingress-nginx | Out-Null
    Write-Host "✅ Nginx Ingress Controller 이미 설치됨" -ForegroundColor Green
} catch {
    Write-Host "🌐 Nginx Ingress Controller 설치 중..." -ForegroundColor Yellow
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml
    Write-Host "⏳ Nginx Ingress Controller 설치 완료 대기 중..." -ForegroundColor Yellow
    kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s
}

# 네임스페이스 생성
Write-Host "📁 네임스페이스 생성 중..." -ForegroundColor Cyan
kubectl create namespace "trip-service-$Environment" --dry-run=client -o yaml | kubectl apply -f -

Write-Host "✅ 인프라 사전 구축 완료!" -ForegroundColor Green

# ===========================================
# 2단계: 애플리케이션 이미지 빌드 (선택적)
# ===========================================

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "🔨 2단계: 애플리케이션 이미지 빌드 시작..." -ForegroundColor Magenta

    # 공유 패키지 빌드
    Write-Host "📚 공유 패키지 빌드 중..." -ForegroundColor Cyan
    Set-Location package-shared
    try {
        # build 패키지가 없으면 설치
        $null = python -c "import build" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "📦 build 패키지 설치 중..." -ForegroundColor Yellow
            python -m pip install build
        }
        python -m build --wheel --outdir dist/
    } catch {
        Write-Host "🔄 Python3으로 재시도 중..." -ForegroundColor Yellow
        try {
            $null = python3 -c "import build" 2>&1
            if ($LASTEXITCODE -ne 0) {
                python3 -m pip install build
            }
            python3 -m build --wheel --outdir dist/
        } catch {
            Write-Host "❌ 공유 패키지 빌드 실패" -ForegroundColor Red
            throw
        }
    }
    Set-Location ..

    # 순차적으로 이미지 빌드 (안정성 우선)
    Write-Host "🏗️  Docker 이미지 빌드 시작..." -ForegroundColor Cyan

    # Frontend 이미지 빌드
    Write-Host "🌐 Frontend 이미지 빌드 중..." -ForegroundColor Cyan
    docker build -f frontend/Dockerfile -t "$Registry/frontend:$Tag" .
    if ($LASTEXITCODE -ne 0) { throw "Frontend 이미지 빌드 실패" }

    # Currency Service 이미지 빌드
    Write-Host "💰 Currency Service 이미지 빌드 중..." -ForegroundColor Cyan
    docker build -f service-currency/Dockerfile -t "$Registry/currency-service:$Tag" .
    if ($LASTEXITCODE -ne 0) { throw "Currency Service 이미지 빌드 실패" }

    # History Service 이미지 빌드
    Write-Host "📊 History Service 이미지 빌드 중..." -ForegroundColor Cyan
    docker build -f service-history/Dockerfile -t "$Registry/history-service:$Tag" .
    if ($LASTEXITCODE -ne 0) { throw "History Service 이미지 빌드 실패" }

    # Ranking Service 이미지 빌드
    Write-Host "🏆 Ranking Service 이미지 빌드 중..." -ForegroundColor Cyan
    docker build -f service-ranking/Dockerfile -t "$Registry/ranking-service:$Tag" .
    if ($LASTEXITCODE -ne 0) { throw "Ranking Service 이미지 빌드 실패" }

    # Data Ingestor Service 이미지 빌드
    Write-Host "📥 Data Ingestor Service 이미지 빌드 중..." -ForegroundColor Cyan
    docker build -f service-dataingestor/Dockerfile -t "$Registry/dataingestor-service:$Tag" .
    if ($LASTEXITCODE -ne 0) { throw "Data Ingestor Service 이미지 빌드 실패" }

    Write-Host "✅ 모든 애플리케이션 이미지 빌드 완료!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⏭️  이미지 빌드 건너뛰기 (기존 이미지 사용)" -ForegroundColor Gray
}

# ===========================================
# 3단계: 쿠버네티스 배포
# ===========================================

Write-Host ""
Write-Host "🚀 3단계: 쿠버네티스 배포 시작..." -ForegroundColor Magenta

# 전체 k8s 리소스 배포
Write-Host "📦 쿠버네티스 리소스 배포 중..." -ForegroundColor Cyan
kubectl apply -k "k8s/overlays/$Environment"

# 인프라 서비스 우선 대기 (MySQL, MongoDB, Redis, Kafka)
Write-Host "⏳ 인프라 서비스 준비 대기 중..." -ForegroundColor Yellow
$InfraServices = @("mysql", "mongodb", "redis", "zookeeper")
foreach ($service in $InfraServices) {
    try {
        Write-Host "🔍 $service 서비스 대기 중..." -ForegroundColor Cyan
        kubectl wait --for=condition=ready pod -l app=$service -n "trip-service-$Environment" --timeout=120s
        Write-Host "✅ $service 준비 완료" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  $service 대기 시간 초과 (계속 진행)" -ForegroundColor Yellow
    }
}

# Kafka 대기 (Zookeeper 다음)
try {
    Write-Host "🔍 Kafka 서비스 대기 중..." -ForegroundColor Cyan
    kubectl wait --for=condition=ready pod -l app=kafka -n "trip-service-$Environment" --timeout=120s
    Write-Host "✅ Kafka 준비 완료" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Kafka 대기 시간 초과 (계속 진행)" -ForegroundColor Yellow
}

# 애플리케이션 서비스 대기
Write-Host "⏳ 애플리케이션 서비스 배포 대기 중..." -ForegroundColor Yellow
$AppServices = @("frontend", "currency-service", "history-service", "ranking-service")
foreach ($service in $AppServices) {
    try {
        Write-Host "🔍 $service 대기 중..." -ForegroundColor Cyan
        kubectl wait --for=condition=ready pod -l app=$service -n "trip-service-$Environment" --timeout=180s
        Write-Host "✅ $service 준비 완료" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  $service 대기 시간 초과 (계속 진행)" -ForegroundColor Yellow
    }
}

Write-Host "✅ 쿠버네티스 배포 완료!" -ForegroundColor Green

# ===========================================
# 4단계: 배포 상태 확인
# ===========================================

Write-Host ""
Write-Host "🔍 4단계: 배포 상태 확인..." -ForegroundColor Magenta

# 최종 상태 확인 및 문제 진단
Write-Host "📋 최종 배포 상태 확인:" -ForegroundColor Cyan

# Pod 상태 확인
$Pods = kubectl get pods -n "trip-service-$Environment" --no-headers
Write-Host ""
Write-Host "🔍 Pod 상태 분석:" -ForegroundColor Yellow
kubectl get pods -n "trip-service-$Environment" -o wide

# 실패한 파드 확인
$FailedPods = kubectl get pods -n "trip-service-$Environment" --field-selector=status.phase!=Running --no-headers 2>$null
if ($FailedPods) {
    Write-Host ""
    Write-Host "⚠️  문제가 있는 Pod들:" -ForegroundColor Red
    Write-Host $FailedPods

    Write-Host ""
    Write-Host "🔧 문제 해결 명령어:" -ForegroundColor Yellow
    Write-Host "kubectl describe pods -n trip-service-$Environment" -ForegroundColor White
    Write-Host "kubectl logs -n trip-service-$Environment [pod-name]" -ForegroundColor White
}

Write-Host ""
Write-Host "🌐 서비스 상태:" -ForegroundColor Cyan
kubectl get services -n "trip-service-$Environment" -o wide

Write-Host ""
Write-Host "🌍 Ingress 상태:" -ForegroundColor Cyan
kubectl get ingress -n "trip-service-$Environment"

Write-Host ""
Write-Host "📊 리소스 사용량:" -ForegroundColor Cyan
kubectl top pods -n "trip-service-$Environment" 2>$null || Write-Host "리소스 모니터링을 위해 metrics-server가 필요합니다" -ForegroundColor Yellow

# ===========================================
# 5단계: 접속 정보 출력
# ===========================================

Write-Host ""
Write-Host "🎯 배포 완료! 접속 정보:" -ForegroundColor Green
Write-Host ""

# LoadBalancer IP 확인
try {
    $LB_IP = kubectl get service frontend-service -n "trip-service-$Environment" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>$null
    if ($LB_IP -and $LB_IP -ne "") {
        Write-Host "🌐 Frontend: http://$LB_IP" -ForegroundColor Green
        Write-Host "🔧 API: http://$LB_IP/api" -ForegroundColor Green
        Write-Host ""
        Write-Host "📝 hosts 파일에 다음을 추가하세요:" -ForegroundColor Yellow
        Write-Host "$LB_IP dev.trip-service.local" -ForegroundColor White
        Write-Host "$LB_IP api-dev.trip-service.local" -ForegroundColor White
    } else {
        Write-Host "⏳ LoadBalancer IP 할당 대기 중..." -ForegroundColor Yellow
        Write-Host "다음 명령어로 확인하세요:" -ForegroundColor Yellow
        Write-Host "kubectl get service frontend-service -n trip-service-$Environment" -ForegroundColor White
    }
} catch {
    Write-Host "⏳ LoadBalancer IP 할당 대기 중..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📊 모니터링 명령어:" -ForegroundColor Yellow
Write-Host "kubectl get pods -n trip-service-$Environment -w" -ForegroundColor White
Write-Host "kubectl logs -f -n trip-service-$Environment deployment/currency-service" -ForegroundColor White
Write-Host "kubectl logs -f -n trip-service-$Environment deployment/history-service" -ForegroundColor White

Write-Host ""
Write-Host "🧹 정리 명령어:" -ForegroundColor Yellow
Write-Host "kubectl delete -k k8s/overlays/$Environment" -ForegroundColor White
Write-Host "kubectl delete namespace trip-service-$Environment" -ForegroundColor White

Write-Host ""
Write-Host "🎉 개발 환경 쿠버네티스 배포 완료!" -ForegroundColor Green

# ===========================================
# 사용법 안내
# ===========================================

Write-Host ""
Write-Host "📚 스크립트 사용법:" -ForegroundColor Yellow
Write-Host ""
Write-Host "🔄 전체 재배포 (정리 + 빌드 + 배포):" -ForegroundColor White
Write-Host "  .\scripts\start-dev-kube.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "⚡ 빠른 재배포 (기존 이미지 사용):" -ForegroundColor White
Write-Host "  .\scripts\start-dev-kube.ps1 -SkipBuild" -ForegroundColor Gray
Write-Host ""
Write-Host "🧹 정리 없이 배포 (기존 리소스 유지):" -ForegroundColor White
Write-Host "  .\scripts\start-dev-kube.ps1 -SkipCleanup" -ForegroundColor Gray
Write-Host ""
Write-Host "🚀 최고속 배포 (정리/빌드 모두 스킵):" -ForegroundColor White
Write-Host "  .\scripts\start-dev-kube.ps1 -SkipCleanup -SkipBuild" -ForegroundColor Gray