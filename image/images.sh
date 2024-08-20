#!/bin/bash

DOCKER_ORG="fsynet"
IMAGES=("ssh-alpine" "ssh-arch" "ssh-centos" "ssh-fedora" "ssh-debian" "ssh-ubuntu")

for IMAGE in "${IMAGES[@]}"
do
    # 拉取镜像
    docker pull $DOCKER_ORG/$IMAGE:latest

    # 重新标记镜像，移除组织名和版本标签
    docker tag $DOCKER_ORG/$IMAGE:latest $IMAGE

    # 删除原始标签
    docker rmi $DOCKER_ORG/$IMAGE:latest

    echo "Processed $IMAGE"
done

# 显示结果
echo "Current images:"
docker images
