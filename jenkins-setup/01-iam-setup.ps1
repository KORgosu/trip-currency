# ============================================================
# Step 1: Jenkins Worker IAM Role + Instance Profile 생성
# ============================================================

$REGION = "ap-northeast-2"
$POLICY_NAME = "JenkinsWorkerPolicy"
$ROLE_NAME   = "JenkinsWorkerRole"
$PROFILE_NAME= "JenkinsWorkerProfile"

# Trust Policy (EC2가 Assume할 수 있도록)
$TRUST_POLICY = @'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "ec2.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
'@
$TRUST_POLICY | Out-File -Encoding utf8 -FilePath "trust-policy.json"

# IAM Policy 생성
$POLICY_ARN = (aws iam create-policy `
    --policy-name $POLICY_NAME `
    --policy-document file://C:/trip-currency/jenkins-setup/worker-iam-policy.json `
    --region $REGION `
    --query 'Policy.Arn' --output text)
Write-Host "Policy ARN: $POLICY_ARN"

# IAM Role 생성
aws iam create-role `
    --role-name $ROLE_NAME `
    --assume-role-policy-document file://trust-policy.json `
    --region $REGION

# Policy를 Role에 연결
aws iam attach-role-policy `
    --role-name $ROLE_NAME `
    --policy-arn $POLICY_ARN

# Instance Profile 생성 및 Role 연결
aws iam create-instance-profile --instance-profile-name $PROFILE_NAME
aws iam add-role-to-instance-profile `
    --instance-profile-name $PROFILE_NAME `
    --role-name $ROLE_NAME

Remove-Item trust-policy.json -ErrorAction SilentlyContinue
Write-Host "IAM 설정 완료: Role=$ROLE_NAME, Profile=$PROFILE_NAME"
