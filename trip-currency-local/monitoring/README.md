# 쿠버네티스 클러스터 모니터링 설정 가이드

이 가이드는 로컬 PC에서 원격 쿠버네티스 클러스터를 모니터링하기 위한 Prometheus + Grafana 설정 방법을 설명합니다.

## 📁 디렉터리 구조

```
monitoring/
├── docker-compose.yml           # Docker Compose 설정
├── prometheus/
│   ├── prometheus.yml          # Prometheus 메인 설정
│   └── alert_rules.yml         # 알람 룰 정의
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml  # Prometheus 데이터소스 설정
│   │   └── dashboards/
│   │       └── dashboard.yml   # 대시보드 프로비저닝 설정
│   └── dashboards/
│       ├── kubernetes-cluster.json  # 쿠버네티스 클러스터 대시보드
│       └── trip-service.json        # Trip Service 대시보드
├── alertmanager/
│   └── alertmanager.yml        # 알람 매니저 설정
└── README.md                   # 이 파일
```

## 🚀 빠른 시작

### 1. 쿠버네티스 클러스터 접근 설정

#### 방법 1: kubeconfig 파일 사용 (권장)
```bash
# kubeconfig 파일을 monitoring 디렉터리에 복사
cp ~/.kube/config ./monitoring/kubeconfig

# docker-compose.yml에서 볼륨 마운트 주석 해제 및 수정
volumes:
  - ./kubeconfig:/etc/prometheus/kubeconfig:ro
```

**💡 왜 이 명령어를 사용하나요?**
- `cp ~/.kube/config`: kubectl이 사용하는 인증 정보를 복사합니다. 이 파일에는 클러스터 주소, 인증서, 토큰 등이 포함되어 있어 Prometheus가 쿠버네티스 API에 접근할 수 있게 합니다.
- `:ro` (read-only): 보안을 위해 읽기 전용으로 마운트하여 컨테이너가 인증 파일을 수정할 수 없도록 합니다.

#### 방법 2: 서비스 어카운트 토큰 사용
```bash
# 쿠버네티스 클러스터에서 실행
kubectl create serviceaccount prometheus
kubectl create clusterrolebinding prometheus --clusterrole=cluster-admin --serviceaccount=default:prometheus

# 토큰 및 CA 인증서 추출
kubectl get secret $(kubectl get serviceaccount prometheus -o jsonpath='{.secrets[0].name}') -o jsonpath='{.data.token}' | base64 -d > ./monitoring/k8s-token
kubectl get secret $(kubectl get serviceaccount prometheus -o jsonpath='{.secrets[0].name}') -o jsonpath='{.data.ca\.crt}' | base64 -d > ./monitoring/k8s-ca.crt
```

**💡 왜 이 명령어를 사용하나요?**
- `kubectl create serviceaccount`: Prometheus 전용 서비스 계정을 생성합니다. 이는 보안 격리를 위해 별도의 ID를 만드는 것입니다.
- `kubectl create clusterrolebinding`: 서비스 계정에 cluster-admin 권한을 부여합니다. 이는 클러스터 전체의 메트릭을 수집하기 위해 필요합니다.
- `base64 -d`: 쿠버네티스에서 base64로 인코딩된 토큰과 인증서를 디코딩하여 Prometheus가 사용할 수 있는 형태로 변환합니다.

### 2. Prometheus 설정 수정

`monitoring/prometheus/prometheus.yml` 파일에서 다음 부분을 수정:

```yaml
# YOUR_K8S_CLUSTER_IP를 실제 클러스터 IP로 변경
- api_server: 'https://YOUR_K8S_CLUSTER_IP:6443'
```

**💡 왜 이 설정이 필요한가요?**
- `6443`: 쿠버네티스 API 서버의 기본 포트입니다. 모든 클러스터 정보와 메트릭은 이 API를 통해 접근합니다.
- `https`: 쿠버네티스 API는 기본적으로 TLS 암호화를 사용하므로 HTTPS로 접근해야 합니다.

### 3. 모니터링 스택 실행

```bash
cd monitoring
docker-compose up -d
```

**💡 왜 이 명령어를 사용하나요?**
- `docker-compose up`: YAML 파일에 정의된 모든 서비스(Prometheus, Grafana, Node Exporter 등)를 동시에 시작합니다.
- `-d`: 백그라운드에서 실행하여 터미널을 계속 사용할 수 있게 합니다.

### 4. 서비스 접근

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Alertmanager**: http://localhost:9093
- **Node Exporter**: http://localhost:9100
- **cAdvisor**: http://localhost:8080

**💡 포트 번호의 의미:**
- `9090`: Prometheus 기본 포트 - 메트릭 수집 및 쿼리 인터페이스
- `3000`: Grafana 기본 포트 - 시각화 대시보드
- `9093`: Alertmanager 기본 포트 - 알람 관리
- `9100`: Node Exporter 기본 포트 - 시스템 메트릭 수집
- `8080`: cAdvisor 기본 포트 - 컨테이너 메트릭 수집

## 📊 대시보드 설명

### 1. Kubernetes Cluster Dashboard
- 클러스터 전체 상태 모니터링
- 노드별 CPU/메모리 사용률
- Pod 상태 확인

### 2. Trip Service Dashboard
- 마이크로서비스별 상태 모니터링
- HTTP 요청률, 에러율, 응답시간
- 서비스별 리소스 사용률
- 데이터베이스 연결 상태

## 🔧 주요 설정 파일 상세 설명

### Docker Compose 설정 (`docker-compose.yml`)

```yaml
prometheus:
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.retention.time=200h'
    - '--web.enable-lifecycle'
    - '--web.enable-admin-api'
```

**💡 각 명령어 옵션의 역할:**
- `--config.file`: Prometheus 설정 파일 위치를 지정합니다.
- `--storage.tsdb.path`: 메트릭 데이터를 저장할 디렉터리를 지정합니다.
- `--storage.tsdb.retention.time=200h`: 데이터를 200시간(약 8일) 동안 보관합니다. 디스크 공간 관리를 위해 설정합니다.
- `--web.enable-lifecycle`: API를 통해 Prometheus를 재시작하지 않고 설정을 다시 로드할 수 있게 합니다.
- `--web.enable-admin-api`: 관리자 API를 활성화하여 스냅샷 생성 등 고급 기능을 사용할 수 있게 합니다.

### Prometheus 설정 (`prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
```

**💡 왜 15초 간격인가요?**
- `scrape_interval`: 메트릭 수집 주기입니다. 15초는 실시간성과 리소스 사용량의 균형점입니다.
- `evaluation_interval`: 알람 룰 평가 주기입니다. 너무 짧으면 CPU를 많이 사용하고, 너무 길면 알람이 늦어집니다.

```yaml
kubernetes_sd_configs:
  - api_server: 'https://YOUR_K8S_CLUSTER_IP:6443'
    role: endpoints
    bearer_token_file: '/etc/prometheus/k8s-token'
```

**💡 Service Discovery의 역할:**
- `kubernetes_sd_configs`: 수동으로 타겟을 설정하지 않고 쿠버네티스에서 자동으로 모니터링 대상을 찾습니다.
- `role: endpoints`: Service의 엔드포인트를 자동으로 발견합니다.
- `bearer_token_file`: 쿠버네티스 API 인증을 위한 토큰 파일을 지정합니다.

### Grafana 프로비저닝

```yaml
# grafana/provisioning/datasources/prometheus.yml
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
```

**💡 프로비저닝이란?**
- 수동 설정 없이 Grafana 시작 시 자동으로 데이터소스와 대시보드를 구성합니다.
- `access: proxy`: Grafana 서버를 통해 Prometheus에 접근합니다 (브라우저 직접 접근 vs 서버 경유).

## 🔧 설정 커스터마이징

### 서비스 Discovery 설정

Trip Service 관련 Pod들을 자동으로 발견하려면 각 서비스에 다음 어노테이션 추가:

```yaml
apiVersion: v1
kind: Pod
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
  labels:
    app: currency-service  # 또는 ranking-service, history-service 등
```

**💡 어노테이션의 역할:**
- `prometheus.io/scrape: "true"`: 이 Pod를 모니터링 대상으로 표시합니다.
- `prometheus.io/port`: 메트릭을 수집할 포트를 지정합니다.
- `prometheus.io/path`: 메트릭 엔드포인트 경로를 지정합니다 (기본값: /metrics).

### 메트릭 엔드포인트 추가

각 서비스에서 Prometheus 메트릭을 노출하려면:

#### Python (FastAPI/Flask)
```python
from prometheus_client import Counter, Histogram, generate_latest
import time

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')

@app.route('/metrics')
def metrics():
    return generate_latest()
```

**💡 메트릭 타입 설명:**
- `Counter`: 증가만 하는 값 (요청 수, 에러 수 등)
- `Histogram`: 분포를 측정하는 값 (응답 시간, 요청 크기 등)
- `generate_latest()`: 현재 메트릭 값들을 Prometheus 형식으로 출력합니다.

#### Node.js (Express)
```javascript
const promClient = require('prom-client');

const httpRequestsTotal = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status_code']
});

app.get('/metrics', (req, res) => {
  res.set('Content-Type', promClient.register.contentType);
  res.end(promClient.register.metrics());
});
```

**💡 labelNames의 역할:**
- 메트릭을 세분화하여 다양한 관점에서 분석할 수 있게 합니다.
- 예: GET vs POST, 성공 vs 실패, 엔드포인트별 분석

## 🚨 알람 설정

### 주요 알람 룰과 임계값 설명

```yaml
- alert: HighCPUUsage
  expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
  for: 5m
```

**💡 이 쿼리의 의미:**
- `node_cpu_seconds_total{mode="idle"}`: 유휴 CPU 시간을 측정합니다.
- `irate(...[5m])`: 5분간의 평균 변화율을 계산합니다.
- `100 - (avg by(instance) ...)`: 유휴 시간을 사용률로 변환합니다 (100% - 유휴% = 사용률%).
- `> 80`: 80% 이상일 때 알람을 발생시킵니다.
- `for: 5m`: 5분 동안 지속될 때만 알람을 보냅니다 (일시적 스파이크 무시).

```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.1
```

**💡 에러율 계산:**
- `status=~"5.."`: 5xx 상태 코드 (서버 에러)를 정규표현식으로 매칭합니다.
- `rate(...[5m])`: 5분간의 초당 요청률을 계산합니다.
- `> 0.1`: 에러율이 10% 이상일 때 알람을 발생시킵니다.

### 알람 채널 설정

#### 슬랙 알림
```yaml
- name: 'slack-notifications'
  slack_configs:
    - api_url: 'YOUR_SLACK_WEBHOOK_URL'
      channel: '#alerts'
      title: 'Alert: {{ .GroupLabels.alertname }}'
```

**💡 템플릿 변수 설명:**
- `{{ .GroupLabels.alertname }}`: 알람 이름을 동적으로 삽입합니다.
- 이는 Go 템플릿 문법으로, 알람별로 다른 메시지를 생성할 수 있게 합니다.

## 🔍 트러블슈팅

### 1. 쿠버네티스 클러스터 연결 실패

```bash
# 연결 테스트
curl -k -H "Authorization: Bearer $(cat k8s-token)" https://YOUR_K8S_CLUSTER_IP:6443/api/v1/nodes
```

**💡 이 명령어로 확인할 수 있는 것:**
- `-k`: TLS 인증서 검증을 건너뜁니다 (자체 서명 인증서 사용 시).
- `Authorization: Bearer`: 토큰 기반 인증을 테스트합니다.
- `/api/v1/nodes`: 노드 목록을 조회하여 API 접근 권한을 확인합니다.

### 2. 메트릭 수집 안됨

```bash
# Prometheus targets 확인
curl http://localhost:9090/api/v1/targets
```

**💡 targets API의 역할:**
- 현재 모니터링 중인 모든 대상의 상태를 JSON으로 반환합니다.
- `up`/`down` 상태와 마지막 스크래핑 시간, 에러 메시지를 확인할 수 있습니다.

### 3. 메트릭 쿼리 테스트

```bash
# 특정 메트릭 확인
curl 'http://localhost:9090/api/v1/query?query=up'
```

**💡 query API 사용법:**
- PromQL 쿼리를 URL 파라미터로 전달하여 결과를 확인합니다.
- `up` 메트릭은 모든 타겟의 상태를 나타내는 기본 메트릭입니다.

## 📈 성능 최적화

### Prometheus 리텐션 설정
```yaml
command:
  - '--storage.tsdb.retention.time=30d'  # 30일 보관
  - '--storage.tsdb.retention.size=10GB' # 최대 10GB
```

**💡 리텐션 정책의 중요성:**
- `retention.time`: 시간 기반 삭제로 오래된 데이터를 자동 제거합니다.
- `retention.size`: 크기 기반 삭제로 디스크 공간을 보호합니다.
- 둘 중 먼저 도달하는 조건이 적용됩니다.

### 스크래핑 주기 조정
```yaml
global:
  scrape_interval: 30s     # 기본 30초
  evaluation_interval: 30s # 룰 평가 30초
```

**💡 주기 선택 기준:**
- **15초**: 실시간 모니터링, 높은 리소스 사용
- **30초**: 일반적인 운영 환경, 균형잡힌 설정
- **1분**: 리소스 절약, 덜 민감한 환경

### 메트릭 필터링

```yaml
metric_relabel_configs:
  - source_labels: [__name__]
    regex: 'unwanted_metric_.*'
    action: drop
```

**💡 불필요한 메트릭 제거:**
- `regex`: 정규표현식으로 메트릭 이름을 매칭합니다.
- `action: drop`: 매칭된 메트릭을 저장하지 않습니다.
- 이를 통해 스토리지 사용량과 쿼리 성능을 개선할 수 있습니다.

## 🔐 보안 고려사항

### 인증 강화
```yaml
# Grafana 환경변수
- GF_SECURITY_ADMIN_PASSWORD=admin123  # 변경 필요!
- GF_AUTH_ANONYMOUS_ENABLED=false      # 익명 접근 차단
```

**💡 보안 설정 이유:**
- 기본 패스워드는 보안 위험이므로 반드시 변경해야 합니다.
- 익명 접근을 차단하여 인증된 사용자만 접근하게 합니다.

### 네트워크 보안
```yaml
ports:
  - "127.0.0.1:9090:9090"  # 로컬호스트만 접근 허용
```

**💡 포트 바인딩 보안:**
- `127.0.0.1:`: 로컬호스트에서만 접근 가능하도록 제한합니다.
- 외부 네트워크에서의 직접 접근을 차단합니다.

## 📚 유용한 PromQL 쿼리 예제

### 리소스 사용률 쿼리
```promql
# CPU 사용률 (노드별)
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 메모리 사용률 (노드별)
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# 디스크 사용률 (파일시스템별)
(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100
```

**💡 쿼리 패턴 설명:**
- `irate()`: 순간 변화율, 실시간 모니터링에 적합
- `rate()`: 평균 변화율, 안정적인 트렌드 분석에 적합
- `avg by(label)`: 라벨별로 그룹화하여 평균값 계산

### 애플리케이션 성능 쿼리
```promql
# 95퍼센타일 응답 시간
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 에러율 (5분 평균)
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100

# 초당 요청 수 (서비스별)
sum(rate(http_requests_total[1m])) by (service)
```

**💡 성능 메트릭 의미:**
- **95퍼센타일**: 95%의 요청이 이 시간 안에 처리됨을 의미합니다.
- **에러율**: 전체 요청 대비 에러 요청의 비율입니다.
- **RPS**: Requests Per Second, 시스템 처리량을 나타냅니다.

## 📊 대시보드 쿼리 최적화

### 효율적인 쿼리 작성
```promql
# 비효율적: 모든 레이블을 포함
sum(http_requests_total)

# 효율적: 필요한 레이블만 포함
sum(http_requests_total{service="currency-service"}) by (method)
```

**💡 쿼리 최적화 팁:**
- 불필요한 레이블을 제거하여 쿼리 성능을 향상시킵니다.
- `by()` 절을 사용하여 그룹화할 레이블을 명시합니다.
- 시간 범위를 적절히 설정하여 메모리 사용량을 조절합니다.

## 🤝 지원

문제가 발생하면 다음을 확인하세요:

1. **Docker 컨테이너 로그**: `docker-compose logs [service-name]`
   - 각 서비스의 상세한 에러 메시지를 확인할 수 있습니다.

2. **Prometheus targets**: http://localhost:9090/targets
   - 모니터링 대상의 연결 상태와 에러를 확인할 수 있습니다.

3. **Grafana 데이터소스**: http://localhost:3000/datasources
   - Prometheus 연결 상태를 테스트할 수 있습니다.

4. **쿠버네티스 클러스터 상태**: `kubectl cluster-info`
   - 클러스터 자체의 문제를 확인할 수 있습니다.

### 일반적인 문제 해결

| 문제 | 원인 | 해결책 |
|------|------|--------|
| Targets가 down 상태 | 네트워크/인증 문제 | 클러스터 IP, 토큰 확인 |
| 메트릭 없음 | 서비스에 메트릭 엔드포인트 없음 | /metrics 엔드포인트 구현 |
| 높은 메모리 사용량 | 너무 많은 메트릭 수집 | 불필요한 메트릭 필터링 |
| 느린 쿼리 | 비효율적인 PromQL | 쿼리 최적화 및 인덱스 활용 |