#!/bin/bash

# 确保脚本以root权限运行
if [ "$(id -u)" != "0" ]; then
   echo "此脚本必须以root权限运行" 1>&2
   exit 1
fi

# 安装必要的软件包
apt-get update
apt-get install -y iptables-persistent python3 python3-pip docker.io
rm /usr/lib/python3.11/EXTERNALLY-MANAGED
systemctl enable docker
systemctl restart docker

# 创建 iptables 规则保存目录
mkdir -p /etc/iptables

# 允许 Docker 容器之间的通信
iptables -A FORWARD -i docker0 -o docker0 -j ACCEPT

# 允许 Docker 容器访问外网
iptables -A FORWARD -i docker0 ! -o docker0 -j ACCEPT
iptables -A FORWARD -o docker0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

# 设置 DOCKER-USER 链以允许所有流量
iptables -N DOCKER-USER || true
iptables -F DOCKER-USER
iptables -A DOCKER-USER -j RETURN

# 保存 iptables 规则
iptables-save > /etc/iptables/rules.v4

# 确保系统启动时加载 iptables 规则
cat > /etc/systemd/system/iptables-restore.service <<EOL
[Unit]
Description=Restore iptables firewall rules
Before=network-pre.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/rules.v4

[Install]
WantedBy=multi-user.target
EOL

# 启用并启动 iptables-restore 服务
systemctl enable iptables-restore.service
systemctl start iptables-restore.service

# 安装 Python 依赖
pip3 install flask flask-sqlalchemy docker

echo "环境配置完成。"
