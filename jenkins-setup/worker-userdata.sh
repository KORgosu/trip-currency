#!/bin/bash
set -e
exec > /var/log/jenkins-worker-init.log 2>&1

JENKINS_SSH_PUBKEY="__JENKINS_SSH_PUBKEY__"

apt-get update -y
apt-get install -y openjdk-17-jdk curl gnupg unzip git

# Docker 설치
apt-get install -y docker.io
systemctl enable docker
systemctl start docker

# Node.js 18 설치
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

# Python 3 + pip + pytest 설치
apt-get install -y python3 python3-pip
pip3 install pytest

# AWS CLI v2 설치
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/awscliv2.zip /tmp/aws

# Jenkins agent 전용 유저 생성
useradd -m -s /bin/bash jenkins || true
usermod -aG docker jenkins

# Jenkins master의 SSH 공개키 등록 (agent 접속용)
mkdir -p /home/jenkins/.ssh
chmod 700 /home/jenkins/.ssh
echo "${JENKINS_SSH_PUBKEY}" >> /home/jenkins/.ssh/authorized_keys
chmod 600 /home/jenkins/.ssh/authorized_keys
chown -R jenkins:jenkins /home/jenkins/.ssh

# 빌드 워크스페이스 디렉토리
mkdir -p /home/jenkins/workspace
chown -R jenkins:jenkins /home/jenkins/workspace

echo "Jenkins worker setup complete"
