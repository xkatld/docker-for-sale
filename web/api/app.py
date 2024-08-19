from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import docker
import random
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///containers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    image = db.Column(db.String(80), nullable=False)
    ssh_port = db.Column(db.Integer, unique=True, nullable=False)
    nat_start_port = db.Column(db.Integer, unique=True, nullable=False)
    nat_end_port = db.Column(db.Integer, unique=True, nullable=False)

def find_available_port(start, end):
    used_ports = set(Container.query.with_entities(Container.ssh_port).all())
    available_ports = set(range(start, end + 1)) - used_ports
    return random.choice(list(available_ports)) if available_ports else None

def create_container(image_key, name, cpu, memory):
    if image_key not in SUPPORTED_IMAGES:
        raise ValueError("不支持的镜像类型")

    image = SUPPORTED_IMAGES[image_key]

    ssh_port = find_available_port(10000, 10999)
    nat_start_port = find_available_port(20000, 60000)
    nat_end_port = nat_start_port + 99  # 分配100个NAT端口

    if not all([ssh_port, nat_start_port]):
        raise Exception("没有足够的可用端口")

    container = client.containers.run(
        image,
        name=name,
        detach=True,
        cpu_period=100000,
        cpu_quota=int(float(cpu) * 100000),
        mem_limit=f"{memory}m",
        restart_policy={"Name": "always"},
        ports={'22/tcp': ssh_port}
    )

    new_container = Container(name=name, image=image, ssh_port=ssh_port,
                              nat_start_port=nat_start_port, nat_end_port=nat_end_port)
    db.session.add(new_container)
    db.session.commit()

    return {
        "name": name,
        "image": image,
        "ip": container.attrs['NetworkSettings']['IPAddress'],
        "ssh_port": ssh_port,
        "nat_start_port": nat_start_port,
        "nat_end_port": nat_end_port
    }

@app.route('/')
def index():
    containers = Container.query.all()
    return render_template('index.html', images=SUPPORTED_IMAGES.keys(), containers=containers)

@app.route('/api/create_container', methods=['POST'])
def api_create_container():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "无效的 JSON 数据"}), 400

        result = create_container(
            data.get('image'),
            data.get('name'),
            data.get('cpu'),
            int(data.get('memory', 0))
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        app.logger.error(f"创建容器时发生错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/delete_container', methods=['POST'])
def api_delete_container():
    try:
        name = request.json.get('name')
        container = Container.query.filter_by(name=name).first()
        if container:
            client.containers.get(name).remove(force=True)
            db.session.delete(container)
            db.session.commit()
            return jsonify({"message": f"容器 {name} 已删除"}), 200
        else:
            return jsonify({"error": "容器不存在"}), 404
    except Exception as e:
        app.logger.error(f"删除容器时发生错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"未捕获的异常: {str(e)}")
    return jsonify({"error": "服务器内部错误"}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=88, debug=True)
