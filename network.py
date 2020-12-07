import os
import sys
import shutil
import subprocess
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
    if os.path.exists('organizations/ordererOrganizations'):
        shutil.rmtree('organizations/ordererOrganizations')
    subprocess.call('cryptogen generate --config=./conf/crypto-config-orderer.yaml --output=organizations', shell=True)

    if os.path.exists('organizations/peerOrganizations'):
        shutil.rmtree('organizations/peerOrganizations')
    subprocess.call('cryptogen generate --config=./conf/crypto-config-org.yaml --output=organizations', shell=True)

def create_consortium():
    subprocess.call('configtxgen -profile DefaultProfile -channelID system-channel -outputBlock ./system-genesis-block/genesis.block', shell=True)

if mode == "init":
    init()
    create_org()
    create_consortium()

