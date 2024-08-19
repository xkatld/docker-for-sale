from flask import Flask, request, jsonify, render_template
import docker
import subprocess
import random

app = Flask(__name__)

client = docker.from_env()

SUPPORTED_IMAGES = {
    'ssh-debian': 'ssh-debian',
    'ssh-ubuntu': 'ssh-ubuntu',
    'ssh-centos': 'ssh-centos',
    'ssh-fedora': 'ssh-fedora',
    'ssh-arch': 'ssh-arch',
    'ssh-alpine': 'ssh-alpine'
}

def find_available_ports(ssh_range=(10000, 19999), nat_range=(20000, 65535), nat_count=500):
    used_ports = set()
    for container in client.containers.list():
        for port_config in container.ports.values():
            if port_config:
                used_ports.add(int(port_config[0]['HostPort']))
    
    available_ssh_ports = list(set(range(ssh_range[0], ssh_range[1] + 1)) - used_ports)
    available_nat_ports = list(set(range(nat_range[0], nat_range[1] + 1)) - used_ports)
    
    if not available_ssh_ports or len(available_nat_ports) < nat_count:
        raise Exception("没有足够的可用端口")
    
    ssh_port = random.choice(available_ssh_ports)
    nat_ports = sorted(random.sample(available_nat_ports, nat_count))
    
    return ssh_port, nat_ports[0], nat_ports[-1]

def create_container(image_key, name, cpu, memory, bandwidth):
    if image_key not in SUPPORTED_IMAGES:
        raise ValueError("不支持的镜像类型")

    image = SUPPORTED_IMAGES[image_key]

    # 生成端口
    ssh_port, nat_start_port, nat_end_port = find_available_ports()

    # 创建容器
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

    # 设置带宽限制
    container_id = container.id[:12]
    subprocess.run([
        "tc", "qdisc", "add", "dev", f"docker0", "root", "handle", "1:", "htb", "default", "10"
    ])
    subprocess.run([
        "tc", "class", "add", "dev", f"docker0", "parent", "1:", "classid", "1:1", "htb", "rate", f"{bandwidth}mbit"
    ])
    subprocess.run([
        "tc", "filter", "add", "dev", f"docker0", "protocol", "ip", "parent", "1:0", "prio", "1", "u32", "match", "ip", "dst", container.attrs['NetworkSettings']['IPAddress'], "flowid", "1:1"
    ])

    # 设置 NAT 端口转发
    for port in range(nat_start_port, nat_end_port + 1):
        subprocess.run([
            "iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "--dport", str(port),
            "-j", "DNAT", "--to", f"{container.attrs['NetworkSettings']['IPAddress']}:{port}"
        ])

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
    return render_template('index.html', images=SUPPORTED_IMAGES.keys())

@app.route('/api/create_container', methods=['POST'])
def api_create_container():
    data = request.json
    try:
        result = create_container(
            data['image'],
            data['name'],
            data['cpu'],
            int(data['memory']),
            int(data['bandwidth'])
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=88, debug=True)
