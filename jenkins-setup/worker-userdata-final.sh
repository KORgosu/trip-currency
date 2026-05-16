#!/bin/bash
set -e
exec > /var/log/jenkins-worker-init.log 2>&1

JENKINS_SSH_PUBKEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDbRbC/7NnozOk08u3OD/hI3rgB8LSTUgEhyM4NPr8ATboRPB2s9UlUX+9jNT4mvTvEPYkqfkNQxPo0Y/CVXhOJgEV7MEUfTIim+EraaAedemKE17dbLW5mwPh6xFQPgRXg6nPX5SDIs5Mk8Xt9jSkbwbANDnwAH2NJ23YHCKmJPkMQ7sT9RNGFRL7+MfNPVWx4lv+sLliL+p0crFeTNLl3NHGYom8mfsrsqZ5rejTvU9UYWODsQ1Y5qmU2vWKjEuQohWxJiNVHC7XIDi+7M6AxqDCzSznXYezijT2X3Un0hL7DRQfkgxszzfG9lpYTZ+zSmYpTAQDni/JeEojxkVtmO6O+mGHtt4LDZmTFmGn7+8+OL11Ca3wGzJhzVFgwucUWwX+Co4fcxazgApMQYHdF3hN56lUxeHPQr1tI38QtTYlSZ58ISE3kAGlBrlJ4kuNspQm0w9rmuBD9oo1H0rFDxuO+Nkf6kxOGNVDYjAyt4Ljj5MtzrhKgYbkeIE0AXSEeOm0Fi5guYOm45Du7gZzCBGCig0fvHVYJKmGCPmEscrzY3pWqK3W7Nk3pt3MWev6jA+hirvTtjREavWwpqwbN4tWy14N8+fKeluVajQ42FYV9ilrkvXsEYhDEKkaj2v4zL3eiv629xW5tYPbHtOmmKKeIt69JqHY2ARsa5Yxhyw== jenkins-agent"

apt-get update -y
apt-get install -y openjdk-17-jdk curl gnupg unzip git

# Docker ?ㅼ튂
apt-get install -y docker.io
systemctl enable docker
systemctl start docker

# Node.js 18 ?ㅼ튂
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

# Python 3 + pip + pytest ?ㅼ튂
apt-get install -y python3 python3-pip
pip3 install pytest

# AWS CLI v2 ?ㅼ튂
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/awscliv2.zip /tmp/aws

# Jenkins agent ?꾩슜 ?좎? ?앹꽦
useradd -m -s /bin/bash jenkins || true
usermod -aG docker jenkins

# Jenkins master??SSH 怨듦컻???깅줉 (agent ?묒냽??
mkdir -p /home/jenkins/.ssh
chmod 700 /home/jenkins/.ssh
echo "${JENKINS_SSH_PUBKEY}" >> /home/jenkins/.ssh/authorized_keys
chmod 600 /home/jenkins/.ssh/authorized_keys
chown -R jenkins:jenkins /home/jenkins/.ssh

# 鍮뚮뱶 ?뚰겕?ㅽ럹?댁뒪 ?붾젆?좊━
mkdir -p /home/jenkins/workspace
chown -R jenkins:jenkins /home/jenkins/workspace

echo "Jenkins worker setup complete"

