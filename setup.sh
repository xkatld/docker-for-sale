#!/bin/bash

# 确保脚本以root权限运行
if [ "$(id -u)" != "0" ]; then
   echo "此脚本必须以root权限运行" 1>&2
   exit 1
fi

# 更新系统包列表
apt-get update

# 安装 Docker（如果尚未安装）
if ! command -v docker &> /dev/null; then
    echo "正在安装 Docker..."
    apt-get install -y docker.io
    systemctl enable docker
    systemctl start docker
else
    echo "Docker 已安装"
fi

# 安装 Python3 和 pip（如果尚未安装）
apt-get install -y python3 python3-pip
rm /usr/lib/python3.11/EXTERNALLY-MANAGED

# 安装 Python 依赖
pip3 install flask flask-sqlalchemy docker

# 创建用于存储数据库的目录
mkdir -p /var/lib/docker-for-sale
chown -R $SUDO_USER:$SUDO_USER /var/lib/docker-for-sale

# 确保 Docker 服务启动
systemctl start docker

# 允许当前用户（如果不是root）使用 Docker
if [ -n "$SUDO_USER" ]; then
    usermod -aG docker $SUDO_USER
    echo "已将用户 $SUDO_USER 添加到 docker 组。请注销并重新登录以使更改生效。"
fi

echo "环境配置完成。"
echo "请确保您的防火墙（如果启用）允许必要的端口访问。"
