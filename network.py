import os
import paramiko
import scp
import sys
import shutil
import subprocess
import tarfile
import yaml
from jinja2 import Template, Environment, FileSystemLoader
from pprint import pprint

ENV_PATH = os.getenv('PATH')
os.environ['PATH'] = os.getcwd() + '/bin' + ':' + ENV_PATH
os.environ['FABRIC_CFG_PATH'] = './conf'
print(os.getenv('PATH'))

mode = sys.argv[1]

all_conf = None

with open('env.yaml') as f:
    all_conf = yaml.safe_load(f)

env = Environment(loader=FileSystemLoader('template'))

def render(file_name, conf):
    template = env.get_template(file_name)
    return template.render(conf)

def save_file(path, data):
    with open(path, 'w') as f:
        f.write(data)

def install():
    # install binaries
    files = os.listdir('bin')
    files = [ f for f in files if not f.startswith('.') ]
    if not files:
        subprocess.call('script/install-fabric.sh binary', shell=True)

    # install docker images
    subprocess.call('script/install-fabric.sh docker', shell=True)

def init():
    ret_text = render('configtx.yaml.tmpl', all_conf)
    save_file('conf/configtx.yaml', ret_text)

    ret_text = render('crypto-config-orderer.yaml.tmpl', all_conf)
    save_file('conf/crypto-config-orderer.yaml', ret_text)

    ret_text = render('crypto-config-org.yaml.tmpl', all_conf)
    save_file('conf/crypto-config-org.yaml', ret_text)

    ret_text = render('docker-compose-orderer.yaml.tmpl', all_conf)
    save_file('conf/docker-compose-orderer.yaml', ret_text)

    for o in all_conf['orgs']:
        for peer_num in range(int(o['peers'])):
            print(f"=== {o['name']} -- peer{peer_num} ===")
            peer_name = f"peer{peer_num}"
            peer_conf = {
                'domain': all_conf['domain'],
                'org': o['name'],
                'peer': peer_name
            }
            ret_text = render('docker-compose-peer.yaml.tmpl', peer_conf)
            save_file(f"conf/docker-compose-{peer_name}-{o['name']}.yaml", ret_text)

def create_org():
    path = 'organizations/ordererOrganizations'
    if os.path.exists(path):
        shutil.rmtree(path)

    path = 'organizations/peerOrganizations'
    if os.path.exists(path):
        shutil.rmtree(path)

    subprocess.call('cryptogen generate --config=./conf/crypto-config-orderer.yaml --output=organizations', shell=True)
    subprocess.call('cryptogen generate --config=./conf/crypto-config-org.yaml --output=organizations', shell=True)

def create_consortium():
    subprocess.call('configtxgen -profile DefaultProfile -channelID system-channel -outputBlock ./system-genesis-block/genesis.block', shell=True)

def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

def distribute_conf(peer, org, domain, conf):
    print(peer + '.' + org + '.' + domain)
    path = f"organizations/peerOrganizations/{org}.{domain}/"
    tar_file = f"cache/{peer}.{org}.{domain}.tar.gz"
    make_tarfile(tar_file, path)

    with paramiko.SSHClient() as sshc:
        sshc.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        hostname = f"{peer}.{org}.{domain}"
        sshc.connect(
            hostname=hostname,
            port=conf['port'],
            username=conf['username'],
            password=conf['password'])
        with scp.SCPClient(sshc.get_transport()) as scpc:
            scpc.put(files=tar_file, remote_path='/tmp')


def distribute_conf_r():
    conf = None
    with open('./conf/crypto-config-org.yaml') as f:
        conf = yaml.safe_load(f)
    conn_list = None
    with open('./secret/connection_list.yaml') as f:
        conn_list = yaml.safe_load(f)

    for x in conf['PeerOrgs']:
        org = (x['Name'])
        for i in range(x['Template']['Count']):
            peer = 'peer' + str(i)
            distribute_conf(peer, org, all_conf['domain'], conn_list[org][peer])

if mode == "install":
    install()
elif mode == "init":
    init()
    create_org()
    create_consortium()
elif mode == "distribution":
    distribute_conf_r()


