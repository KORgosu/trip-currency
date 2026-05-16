# ============================================================
# Step 4: Master / Worker EC2 인스턴스 시작
# ============================================================
# 사전 조건: network-ids.txt, keys/ 디렉토리 존재

$REGION       = "ap-northeast-2"
$SETUP_DIR    = "C:/trip-currency/jenkins-setup"
$KEY_NAME     = "jenkins-ec2-keypair"

# network-ids.txt에서 값 로드
$NET = Get-Content "$SETUP_DIR/network-ids.txt" | ForEach-Object {
    $k, $v = $_ -split '='
    [PSCustomObject]@{ Key=$k; Value=$v }
}
$SUBNET_ID = ($NET | Where-Object Key -eq 'SUBNET_ID').Value
$MASTER_SG = ($NET | Where-Object Key -eq 'MASTER_SG').Value
$WORKER_SG = ($NET | Where-Object Key -eq 'WORKER_SG').Value

# Ubuntu 22.04 LTS AMI (ap-northeast-2 최신 공식 이미지)
$AMI_ID = (aws ec2 describe-images `
    --owners 099720109477 `
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" `
              "Name=state,Values=available" `
    --region $REGION `
    --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)
Write-Host "Ubuntu 22.04 AMI: $AMI_ID"

# Instance Profile ARN 조회
$PROFILE_ARN = (aws iam get-instance-profile `
    --instance-profile-name JenkinsWorkerProfile `
    --query 'InstanceProfile.Arn' --output text)

# ── Master EC2 시작 ───────────────────────────────────────
$MASTER_USERDATA = [Convert]::ToBase64String(
    [System.IO.File]::ReadAllBytes("$SETUP_DIR/master-userdata.sh"))

$MASTER_ID = (aws ec2 run-instances `
    --image-id $AMI_ID `
    --instance-type t3.medium `
    --key-name $KEY_NAME `
    --security-group-ids $MASTER_SG `
    --subnet-id $SUBNET_ID `
    --associate-public-ip-address `
    --user-data $MASTER_USERDATA `
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=jenkins-master},{Key=Role,Value=jenkins-master}]" `
    --region $REGION `
    --query 'Instances[0].InstanceId' --output text)
Write-Host "Master Instance ID: $MASTER_ID"

# ── Worker EC2 시작 ───────────────────────────────────────
$WORKER_USERDATA = [Convert]::ToBase64String(
    [System.IO.File]::ReadAllBytes("$SETUP_DIR/worker-userdata-final.sh"))

$WORKER_ID = (aws ec2 run-instances `
    --image-id $AMI_ID `
    --instance-type t3.large `
    --key-name $KEY_NAME `
    --security-group-ids $WORKER_SG `
    --subnet-id $SUBNET_ID `
    --associate-public-ip-address `
    --iam-instance-profile Arn=$PROFILE_ARN `
    --user-data $WORKER_USERDATA `
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=jenkins-worker-01},{Key=Role,Value=jenkins-worker}]" `
    --region $REGION `
    --query 'Instances[0].InstanceId' --output text)
Write-Host "Worker Instance ID: $WORKER_ID"

# 인스턴스 Running 대기
Write-Host "인스턴스 Running 상태 대기 중..."
aws ec2 wait instance-running --instance-ids $MASTER_ID $WORKER_ID --region $REGION

# Public/Private IP 조회
$MASTER_PUBLIC_IP = (aws ec2 describe-instances `
    --instance-ids $MASTER_ID --region $REGION `
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

$WORKER_PRIVATE_IP = (aws ec2 describe-instances `
    --instance-ids $WORKER_ID --region $REGION `
    --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)

# 결과 저장
@"
MASTER_ID=$MASTER_ID
WORKER_ID=$WORKER_ID
MASTER_PUBLIC_IP=$MASTER_PUBLIC_IP
WORKER_PRIVATE_IP=$WORKER_PRIVATE_IP
"@ | Out-File -Encoding utf8 -FilePath "$SETUP_DIR/instance-ids.txt"

Write-Host "`n인스턴스 시작 완료!"
Write-Host "Master Public IP : $MASTER_PUBLIC_IP"
Write-Host "Worker Private IP: $WORKER_PRIVATE_IP"
Write-Host "`nJenkins UI: http://${MASTER_PUBLIC_IP}:8080"
Write-Host "Jenkins 초기 비밀번호 확인 (3-4분 후):"
Write-Host "  ssh -i $SETUP_DIR/keys/jenkins-ec2-keypair.pem ubuntu@$MASTER_PUBLIC_IP"
Write-Host "  sudo cat /var/lib/jenkins/secrets/initialAdminPassword"
