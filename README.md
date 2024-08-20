# docker-for-sale
docker销售系统，web前后端，api功能文档，镜像制作。
# 环境
基于Debian12,docker,python3开发
```shell
apt update -y
apt install wget curl sudo git screen nano unzip -y
git clone https://github.com/xkatld/docker-for-sale.git
chmod +x ./docker-for-sale/setup.sh
bash ./docker-for-sale/setup.sh
```
# 构建docker镜像
```shell
# 构建 Ubuntu 镜像
docker build --target ubuntu -t ssh-ubuntu ./docker-for-sale/image
# 构建 Debian 镜像
docker build --target debian -t ssh-debian ./docker-for-sale/image
# 构建 CentOS 镜像
docker build --target centos -t ssh-centos ./docker-for-sale/image
# 构建 Fedora 镜像
docker build --target fedora -t ssh-fedora ./docker-for-sale/image
# 构建 Arch Linux 镜像
docker build --target arch -t ssh-arch ./docker-for-sale/image
# 构建 Alpine Linux 镜像
docker build --target alpine -t ssh-alpine ./docker-for-sale/image
```
默认端口密码都是22/password

```
#也可以使用脚本直接完成构建
bash ./docker-for-sale/image/images.sh
```

# 启动web-api
```
python3 ./docker-for-sale/web/api/app.py
```
浏览器中访问 http://0.0.0.0:88 使用 Web 界面，或使用 API 客户端调用 /api/create_container 端点
API 使用示例（使用 curl）：
```
#创建容器：
curl -X POST http://0.0.0.0:88/api/create_container \
     -H "Content-Type: application/json" \
     -d '{
         "image": "ssh-ubuntu",
         "cpu": 0.5,
         "memory": 512
     }'

#删除容器（假设容器 ID 为 "35195543422b"）：
curl -X POST http://0.0.0.0:88/api/delete_container \
     -H "Content-Type: application/json" \
     -d '{
         "id": "35195543422b"
     }'
```
