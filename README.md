# docker-for-sale
docker销售系统，web前后端，api功能文档，镜像制作。
# 环境
基于Debian12开发
```
apt update -y
apt install docker.io python3 python3-pip git -y
rm /usr/lib/python3.11/EXTERNALLY-MANAGED
systemctl enable docker
systemctl restart docker
git clone https://github.com/xkatld/docker-for-sale.git
```
# 构建docker镜像
```
cd docker-for-sale/image
# 构建 Ubuntu 镜像
docker build --target ubuntu -t ssh-ubuntu .
# 构建 Debian 镜像
docker build --target debian -t ssh-debian .
# 构建 CentOS 镜像
docker build --target centos -t ssh-centos .
# 构建 Fedora 镜像
docker build --target fedora -t ssh-fedora .
# 构建 Arch Linux 镜像
docker build --target arch -t ssh-arch .
# 构建 Alpine Linux 镜像
docker build --target alpine -t ssh-alpine .
```
默认端口密码都是22/password
