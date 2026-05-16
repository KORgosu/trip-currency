# ============================================================
# Step 3: EC2 접속용 Key Pair + Jenkins Agent용 SSH 키 생성
# ============================================================

$REGION   = "ap-northeast-2"
$KEYDIR   = "C:/trip-currency/jenkins-setup/keys"
New-Item -ItemType Directory -Force -Path $KEYDIR | Out-Null

# ── EC2 관리자 접속용 Key Pair (AWS Key Pair) ──────────────
# EC2 SSH 접속 (관리자용)
aws ec2 create-key-pair `
    --key-name jenkins-ec2-keypair `
    --region $REGION `
    --query 'KeyMaterial' --output text `
    | Out-File -Encoding ascii -FilePath "$KEYDIR/jenkins-ec2-keypair.pem"

Write-Host "EC2 Key Pair 저장: $KEYDIR/jenkins-ec2-keypair.pem"

# ── Jenkins Master → Worker SSH 키 (agent 연결용) ──────────
# OpenSSH로 키 생성 (Windows 10/11 기본 탑재)
$AGENT_KEY = "$KEYDIR/jenkins-agent-key"
if (Test-Path "$AGENT_KEY") { Remove-Item "$AGENT_KEY", "$AGENT_KEY.pub" -Force }

ssh-keygen -t rsa -b 4096 -C "jenkins-agent" -f "$AGENT_KEY" -N '""'

$AGENT_PUBKEY = Get-Content "$AGENT_KEY.pub"
Write-Host "`nJenkins Agent 공개키 (Worker authorized_keys에 삽입됩니다):"
Write-Host $AGENT_PUBKEY

# worker-userdata.sh에 공개키 삽입
$USERDATA = Get-Content "C:/trip-currency/jenkins-setup/worker-userdata.sh" -Raw
$USERDATA = $USERDATA.Replace("__JENKINS_SSH_PUBKEY__", $AGENT_PUBKEY)
$USERDATA | Out-File -Encoding utf8 -FilePath "C:/trip-currency/jenkins-setup/worker-userdata-final.sh"

Write-Host "`n공개키를 worker-userdata-final.sh에 삽입 완료"
Write-Host "Agent 개인키 경로: $AGENT_KEY (Jenkins Credentials에 등록 필요)"
