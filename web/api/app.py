from flask import Flask, request, jsonify, render_template
import docker
import subprocess
import random
import string

app = Flask(__name__)

def generate_password(length=12):
    """生成一个随机密码"""
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))

def find_available_ports(ssh_range=(10000, 19999), nat_range=(20000, 65535), nat_count=500):
    """找到可用的端口范围"""
    used_ports = set()
    client = docker.from_env()
    for container in client.containers.list():
        ports = container.attrs['NetworkSettings']['Ports']
        for port_mappings in ports.values():
            if port_mappings:
                used_ports.add(int(port_mappings[0]['HostPort']))
    
    available_ssh_ports = list(set(range(ssh_range[0], ssh_range[1] + 1)) - used_ports)
    available_nat_ports = list(set(range(nat_range[0], nat_range[1] + 1)) - used_ports)
    
    if not available_ssh_ports or len(available_nat_ports) < nat_count:
        raise Exception("没有足够的可用端口")
    
    ssh_port = random.choice(available_ssh_ports)
    nat_ports = sorted(random.sample(available_nat_ports, nat_count))
    
    return ssh_port, nat_ports[0], nat_ports[-1]

def create_container(image, name, cpu, memory, disk, bandwidth):
    client = docker.from_env()

    # 生成端口和密码
    ssh_port, nat_start_port, nat_end_port = find_available_ports()
    password = generate_password()

    # 创建容器
    container = client.containers.run(
        image,
        name=name,
        detach=True,
        cpu_period=100000,
        cpu_quota=int(cpu * 100000),
        mem_limit=f"{memory}m",
        storage_opt={"size": f"{disk}G"},
        restart_policy={"Name": "always"},
        ports={f'22/tcp': ssh_port}
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

    # 设置 SSH 密码（这里假设容器是基于 Ubuntu 的）
    container.exec_run(f"echo 'root:{password}' | chpasswd")

    return {
        "name": name,
        "ip": container.attrs['NetworkSettings']['IPAddress'],
        "ssh_port": ssh_port,
        "ssh_password": password,
        "nat_start_port": nat_start_port,
        "nat_end_port": nat_end_port
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/create_container', methods=['POST'])
def api_create_container():
    data = request.json
    try:
        result = create_container(
            data['image'],
            data['name'],
            float(data['cpu']),
            int(data['memory']),
            int(data['disk']),
            int(data['bandwidth'])
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
