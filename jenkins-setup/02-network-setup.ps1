# ============================================================
# Step 2: Security Group 생성
# ============================================================

$REGION   = "ap-northeast-2"
$MY_IP    = (Invoke-RestMethod http://checkip.amazonaws.com/).Trim()
Write-Host "내 IP: $MY_IP"

# VPC ID 조회 (192.168.0.0/16)
$VPC_ID = (aws ec2 describe-vpcs `
    --filters "Name=cidr,Values=192.168.0.0/16" `
    --region $REGION `
    --query 'Vpcs[0].VpcId' --output text)
Write-Host "VPC ID: $VPC_ID"

# 퍼블릭 서브넷 ID 조회 (첫 번째 퍼블릭 서브넷)
$SUBNET_ID = (aws ec2 describe-subnets `
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" `
    --region $REGION `
    --query 'Subnets[0].SubnetId' --output text)
Write-Host "Public Subnet ID: $SUBNET_ID"

# ── Master Security Group ──────────────────────────────────
$MASTER_SG = (aws ec2 create-security-group `
    --group-name jenkins-master-sg `
    --description "Jenkins Master - UI and SSH" `
    --vpc-id $VPC_ID `
    --region $REGION `
    --query 'GroupId' --output text)
Write-Host "Master SG: $MASTER_SG"

# Jenkins UI (8080) - 내 IP만 허용
aws ec2 authorize-security-group-ingress `
    --group-id $MASTER_SG --region $REGION `
    --protocol tcp --port 8080 --cidr "$MY_IP/32"

# SSH (22) - 내 IP만 허용
aws ec2 authorize-security-group-ingress `
    --group-id $MASTER_SG --region $REGION `
    --protocol tcp --port 22 --cidr "$MY_IP/32"

# ── Worker Security Group ──────────────────────────────────
$WORKER_SG = (aws ec2 create-security-group `
    --group-name jenkins-worker-sg `
    --description "Jenkins Worker - SSH from Master only" `
    --vpc-id $VPC_ID `
    --region $REGION `
    --query 'GroupId' --output text)
Write-Host "Worker SG: $WORKER_SG"

# Worker SSH (22) - Master SG에서만 허용
aws ec2 authorize-security-group-ingress `
    --group-id $WORKER_SG --region $REGION `
    --protocol tcp --port 22 `
    --source-group $MASTER_SG

# SSH (22) - 내 IP (초기 설정용, 나중에 제거 가능)
aws ec2 authorize-security-group-ingress `
    --group-id $WORKER_SG --region $REGION `
    --protocol tcp --port 22 --cidr "$MY_IP/32"

# 결과 저장
@"
VPC_ID=$VPC_ID
SUBNET_ID=$SUBNET_ID
MASTER_SG=$MASTER_SG
WORKER_SG=$WORKER_SG
"@ | Out-File -Encoding utf8 -FilePath "C:/trip-currency/jenkins-setup/network-ids.txt"

Write-Host "네트워크 설정 완료. 값을 network-ids.txt에 저장했습니다."
