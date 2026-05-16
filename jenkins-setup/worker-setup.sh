#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

JENKINS_PUBKEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDbRbC/7NnozOk08u3OD/hI3rgB8LSTUgEhyM4NPr8ATboRPB2s9UlUX+9jNT4mvTvEPYkqfkNQxPo0Y/CVXhOJgEV7MEUfTIim+EraaAedemKE17dbLW5mwPh6xFQPgRXg6nPX5SDIs5Mk8Xt9jSkbwbANDnwAH2NJ23YHCKmJPkMQ7sT9RNGFRL7+MfNPVWx4lv+sLliL+p0crFeTNLl3NHGYom8mfsrsqZ5rejTvU9UYWODsQ1Y5qmU2vWKjEuQohWxJiNVHC7XIDi+7M6AxqDCzSznXYezijT2X3Un0hL7DRQfkgxszzfG9lpYTZ+zSmYpTAQDni/JeEojxkVtmO6O+mGHtt4LDZmTFmGn7+8+OL11Ca3wGzJhzVFgwucUWwX+Co4fcxazgApMQYHdF3hN56lUxeHPQr1tI38QtTYlSZ58ISE3kAGlBrlJ4kuNspQm0w9rmuBD9oo1H0rFDxuO+Nkf6kxOGNVDYjAyt4Ljj5MtzrhKgYbkeIE0AXSEeOm0Fi5guYOm45Du7gZzCBGCig0fvHVYJKmGCPmEscrzY3pWqK3W7Nk3pt3MWev6jA+hirvTtjREavWwpqwbN4tWy14N8+fKeluVajQ42FYV9ilrkvXsEYhDEKkaj2v4zL3eiv629xW5tYPbHtOmmKKeIt69JqHY2ARsa5Yxhyw== jenkins-agent"

echo "=== 1. Java 21 ==="
if ! java -version 2>&1 | grep -q "21"; then
  sudo apt-get update -qq
  sudo apt-get install -y openjdk-21-jdk
fi
java -version

echo "=== 2. Docker ==="
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable docker --now
docker --version

echo "=== 3. Node.js 18 ==="
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
node --version

echo "=== 4. Python3 + pytest ==="
sudo apt-get install -y python3 python3-pip python3-pytest
python3 --version

echo "=== 5. AWS CLI v2 ==="
if ! command -v aws &>/dev/null; then
  sudo apt-get install -y unzip
  curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp
  sudo /tmp/aws/install
  rm -rf /tmp/aws /tmp/awscliv2.zip
fi
aws --version

echo "=== 6. jenkins 사용자 생성 ==="
if ! id jenkins &>/dev/null; then
  sudo useradd -m -s /bin/bash jenkins
fi
sudo usermod -aG docker jenkins
sudo mkdir -p /home/jenkins/.ssh /home/jenkins/workspace
echo "$JENKINS_PUBKEY" | sudo tee /home/jenkins/.ssh/authorized_keys
sudo chmod 700 /home/jenkins/.ssh
sudo chmod 600 /home/jenkins/.ssh/authorized_keys
sudo chown -R jenkins:jenkins /home/jenkins/.ssh /home/jenkins/workspace

echo "=== 완료 ==="
id jenkins
cat /home/jenkins/.ssh/authorized_keys
