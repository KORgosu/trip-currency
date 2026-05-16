#!/bin/bash
set -e
exec > /var/log/jenkins-master-init.log 2>&1

apt-get update -y
apt-get install -y openjdk-17-jdk curl gnupg

# Jenkins 공식 저장소 추가
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key \
    | tee /etc/apt/trusted.gpg.d/jenkins.asc > /dev/null
echo "deb [signed-by=/etc/apt/trusted.gpg.d/jenkins.asc] \
    https://pkg.jenkins.io/debian-stable binary/" \
    > /etc/apt/sources.list.d/jenkins.list
apt-get update -y
apt-get install -y jenkins

# Jenkins 서비스 시작
systemctl enable jenkins
systemctl start jenkins

echo "Jenkins master setup complete"
echo "Initial admin password will be at: /var/lib/jenkins/secrets/initialAdminPassword"
