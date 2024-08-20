from flask import Flask, request, jsonify, render_template, Response
from flask_sqlalchemy import SQLAlchemy
import docker
import random
import logging
import json
import time
import threading
import queue

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///containers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = docker.from_env()

SUPPORTED_IMAGES = {
    'ssh-debian': 'ssh-debian',
    'ssh-ubuntu': 'ssh-ubuntu',
    'ssh-centos': 'ssh-centos',
    'ssh-fedora': 'ssh-fedora',
    'ssh-arch': 'ssh-arch',
    'ssh-alpine': 'ssh-alpine'
}

class Container(db.Model):
    id = db.Column(db.String(12), primary_key=True)
    image = db.Column(db.String(80), nullable=False)
    ssh_port = db.Column(db.Integer, unique=True, nullable=False)
    nat_start_port = db.Column(db.Integer, unique=True, nullable=False)
    nat_end_port = db.Column(db.Integer, unique=True, nullable=False)
    disk_size = db.Column(db.String(20), nullable=False)

# 创建一个队列来存储待创建的容器
container_queue = queue.Queue()

def find_available_port_range(start, end, count):
    used_ranges = Container.query.with_entities(Container.nat_start_port, Container.nat_end_port).all()
    available_ranges = set(range(start, end + 1, count))
    for used_start, used_end in used_ranges:
        available_ranges -= set(range(used_start, used_end + 1, count))
    return random.choice(list(available_ranges)) if available_ranges else None

def create_container(image_key, cpu, memory, disk_size):
    if image_key not in SUPPORTED_IMAGES:
        raise ValueError("不支持的镜像类型")

    image = SUPPORTED_IMAGES[image_key]

    ssh_port = find_available_port_range(10000, 10999, 1)
    nat_start_port = find_available_port_range(20000, 60000, 100)

    if not all([ssh_port, nat_start_port]):
        raise Exception("没有足够的可用端口")

    nat_end_port = nat_start_port + 99

    logger.info(f"创建容器，镜像: {image}, SSH端口: {ssh_port}, NAT端口: {nat_start_port}-{nat_end_port}, 磁盘大小: {disk_size}")

    # 创建带有大小限制的卷
    volume_name = f"volume_{ssh_port}"
    client.volumes.create(name=volume_name, driver="local", driver_opts={"type": "tmpfs", "device": "tmpfs", "o": f"size={disk_size}"})

    port_bindings = {
        '22/tcp': ssh_port,
        **{f'{p}/tcp': p for p in range(nat_start_port, nat_end_port + 1)}
    }

    container = client.containers.run(
        image,
        detach=True,
        cpu_period=100000,
        cpu_quota=int(float(cpu) * 100000),
        mem_limit=f"{memory}m",
        memswap_limit=f"{memory}m",  # 限制 swap 使用
        restart_policy={"Name": "always"},
        ports=port_bindings,
        volumes={volume_name: {'bind': '/mnt/data', 'mode': 'rw'}}
    )

    container_id = container.id[:12]
    container_ip = container.attrs['NetworkSettings']['IPAddress']

    logger.info(f"容器创建成功，ID: {container_id}, IP: {container_ip}")

    new_container = Container(id=container_id, image=image, ssh_port=ssh_port,
                              nat_start_port=nat_start_port, nat_end_port=nat_end_port,
                              disk_size=disk_size)
    db.session.add(new_container)
    db.session.commit()

    logger.info(f"容器 {container_id} 创建成功并添加到数据库")

    return {
        "id": container_id,
        "image": image,
        "ip": container_ip,
        "ssh_port": ssh_port,
        "nat_start_port": nat_start_port,
        "nat_end_port": nat_end_port,
        "disk_size": disk_size
    }

def container_creator():
    while True:
        task = container_queue.get()
        try:
            create_container(**task)
        except Exception as e:
            logger.error(f"创建容器时发生错误: {str(e)}")
        container_queue.task_done()

# 启动容器创建线程
threading.Thread(target=container_creator, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html', images=SUPPORTED_IMAGES.keys())

@app.route('/containers')
def containers():
    containers = Container.query.all()
    return render_template('containers.html', containers=containers)

@app.route('/api/create_container', methods=['POST'])
def api_create_container():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "无效的 JSON 数据"}), 400

        count = int(data.get('count', 1))
        
        for _ in range(count):
            container_queue.put({
                'image_key': data.get('image'),
                'cpu': data.get('cpu'),
                'memory': int(data.get('memory', 64)),  # 默认使用64MB
                'disk_size': data.get('disk_size', '1G')
            })

        return jsonify({"message": f"已添加 {count} 个容器到创建队列"}), 202
    except ValueError as e:
        logger.error(f"无效输入: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"添加容器到队列时发生错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/container_count')
def container_count():
    count = Container.query.count()
    return jsonify({"count": count})

@app.route('/api/container_stats/<container_id>')
def container_stats(container_id):
    def generate():
        container = client.containers.get(container_id)
        while True:
            stats = container.stats(stream=False)
            yield f"data: {json.dumps(stats)}\n\n"
            time.sleep(1)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/delete_container', methods=['POST'])
def api_delete_container():
    try:
        container_id = request.json.get('id')
        container = Container.query.get(container_id)
        if container:
            logger.info(f"正在删除容器: {container_id}")
            # 删除 Docker 容器
            docker_container = client.containers.get(container_id)
            docker_container.remove(force=True)
            logger.info(f"Docker 容器 {container_id} 已删除")

            # 删除对应的卷
            volume_name = f"volume_{container.ssh_port}"
            try:
                volume = client.volumes.get(volume_name)
                volume.remove(force=True)
                logger.info(f"卷 {volume_name} 已删除")
            except docker.errors.NotFound:
                logger.warning(f"卷 {volume_name} 不存在，无需删除")

            # 从数据库中删除记录
            db.session.delete(container)
            db.session.commit()
            logger.info(f"容器 {container_id} 已从数据库中删除")
            return jsonify({"message": f"容器 {container_id} 已删除"}), 200
        else:
            logger.warning(f"尝试删除不存在的容器: {container_id}")
            return jsonify({"error": "容器不存在"}), 404
    except Exception as e:
        logger.error(f"删除容器时发生错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/delete_containers', methods=['POST'])
def api_delete_containers():
    try:
        container_ids = request.json.get('ids', [])
        if not container_ids:
            return jsonify({"error": "没有提供容器ID"}), 400

        deleted_count = 0
        for container_id in container_ids:
            container = Container.query.get(container_id)
            if container:
                try:
                    # 删除 Docker 容器
                    docker_container = client.containers.get(container_id)
                    docker_container.remove(force=True)
                    logger.info(f"Docker 容器 {container_id} 已删除")

                    # 删除对应的卷
                    volume_name = f"volume_{container.ssh_port}"
                    try:
                        volume = client.volumes.get(volume_name)
                        volume.remove(force=True)
                        logger.info(f"卷 {volume_name} 已删除")
                    except docker.errors.NotFound:
                        logger.warning(f"卷 {volume_name} 不存在，无需删除")

                    # 从数据库中删除记录
                    db.session.delete(container)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"删除容器 {container_id} 时发生错误: {str(e)}")

        db.session.commit()
        return jsonify({"message": f"成功删除 {deleted_count} 个容器"}), 200
    except Exception as e:
        logger.error(f"批量删除容器时发生错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"未捕获的异常: {str(e)}")
    return jsonify({"error": "服务器内部错误"}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    logger.info("启动应用")
    app.run(host='0.0.0.0', port=88, debug=True)
