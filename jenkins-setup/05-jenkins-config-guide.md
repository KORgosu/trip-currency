# Jenkins 초기 설정 가이드 (04-launch-ec2.ps1 완료 후)

## 1. Jenkins UI 접속 및 초기 설정

```bash
# 초기 비밀번호 확인
ssh -i keys/jenkins-ec2-keypair.pem ubuntu@<MASTER_PUBLIC_IP>
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

브라우저: http://<MASTER_PUBLIC_IP>:8080

1. 초기 비밀번호 입력
2. "Install suggested plugins" 선택
3. 관리자 계정 생성

---

## 2. 추가 플러그인 설치

Manage Jenkins → Plugins → Available plugins:

| 플러그인 | 용도 |
|---------|------|
| Pipeline: AWS Steps | `withAWS()` 지원 |
| Docker Pipeline | `docker.build()` 지원 |
| SSH Build Agents | Master → Worker SSH 연결 |
| Git / GitHub Integration | 소스 체크아웃 |

설치 후 재시작.

---

## 3. Global Environment Variable 설정

Manage Jenkins → System → Global properties → Environment variables:

| 변수명 | 값 |
|-------|-----|
| AWS_ACCOUNT_ID | (Jenkins UI에만 설정 — 저장소에 커밋하지 않음) |

> `worker-iam-policy.json`의 ECR ARN 계정 자리는 예시 `123456789012`입니다. 적용 전 본인 AWS 계정 ID로 바꿉니다.

---

## 4. Credentials 등록

Manage Jenkins → Credentials → System → Global credentials:

### 4-1. GitHub Token (GitOps 커밋용)
- Kind: Username with password
- ID: github-token
- Username: KORgosu
- Password: <GitHub Personal Access Token (repo 권한)>

### 4-2. Jenkins Agent SSH Key (Worker 연결용)
- Kind: SSH Username with private key
- ID: jenkins-agent-ssh
- Username: jenkins
- Private Key: keys/jenkins-agent-key 파일 내용 붙여넣기

---

## 5. Worker 노드 등록

Manage Jenkins → Nodes → New Node:

| 항목 | 값 |
|------|-----|
| Node Name | jenkins-worker-01 |
| Type | Permanent Agent |
| # of executors | 4 |
| Remote root directory | /home/jenkins/workspace |
| Labels | ec2-worker-ubuntu |
| Usage | Only build jobs with label expressions |
| Launch method | Launch agents via SSH |
| Host | <WORKER_PRIVATE_IP> |
| Credentials | jenkins-agent-ssh |
| Host Key Verification | Non verifying |

Save → 노드 페이지에서 "Launch" 클릭 → 로그에 "Agent successfully connected" 확인

---

## 6. Jenkins Pipeline Job 생성

New Item → Pipeline:

| 항목 | 값 |
|------|-----|
| Definition | Pipeline script from SCM |
| SCM | Git |
| Repository URL | https://github.com/KORgosu/trip-currency-local.git |
| Credentials | github-token |
| Branch | */main |
| Script Path | Jenkinsfile.production |

---

## 7. 첫 빌드 실행 확인 순서

1. "Build Now" 클릭
2. Stage View에서 각 단계 확인:
   - Checkout ✅
   - Init Workspace Paths ✅
   - ECR Login ✅
   - Build & Test (병렬) ✅
   - Docker Build & Push ✅
   - SBOM & Vulnerability Scan ✅
   - Update GitOps ✅
3. trip-currency-local-gitops GitHub에서 새 커밋 확인
4. ArgoCD sync 트리거 확인 (ArgoCD 설치 후)

---

## 8. 아키텍처 최종 구조

```
개발자 PC
    │ git push
    ▼
GitHub (trip-currency-local)
    │ webhook (선택) 또는 polling
    ▼
Jenkins Master (EC2 t3.medium, Public IP)
    │ SSH
    ▼
Jenkins Worker (EC2 t3.large, Private IP only)
    ├── npm build / pytest
    ├── docker build → ECR push (prod-N)
    ├── trivy SBOM scan
    └── git push → GitHub (trip-currency-local-gitops)
                       │
                       ▼ (ArgoCD polling)
               ArgoCD (EKS argocd ns)
                       │ kubectl apply -k k8s/overlays/eks
                       ▼
               trip-service-prod (EKS)
```
