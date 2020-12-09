import glob
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

crypto_config_org = None
with open('./conf/crypto-config-org.yaml') as f:
    crypto_config_org = yaml.safe_load(f)

connection_list = None
with open('./secret/connection_list.yaml') as f:
    connection_list = yaml.safe_load(f)

mode = sys.argv[1]

all_conf = None
with open('env.yaml') as f:
    all_conf = yaml.safe_load(f)

g_pwd = os.getcwd()
g_domain  = all_conf['domain']
g_channel = all_conf['channel']
g_path_orderer_ca = f'{g_pwd}/organizations/ordererOrganizations/{g_domain}/orderers/orderer.{g_domain}/msp/tlscacerts/tlsca.{g_domain}-cert.pem'

env = Environment(loader=FileSystemLoader('template'))

def set_org_env(org):
    os.environ['CORE_PEER_LOCALMSPID'] = org
    os.environ['CORE_PEER_TLS_ROOTCERT_FILE'] = f'{g_pwd}/organizations/peerOrganizations/{org}.{g_domain}/peers/peer0.{org}.{g_domain}/tls/ca.crt'
    os.environ['CORE_PEER_MSPCONFIGPATH'] = f'{g_pwd}/organizations/peerOrganizations/{org}.{g_domain}/users/Admin@{org}.{g_domain}/msp'
    os.environ['CORE_PEER_ADDRESS'] = f'peer0-{org}.{g_domain}:7051'

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
    save_file('docker/docker-compose.yaml', ret_text)

    domain = all_conf['domain']

    for o in all_conf['orgs']:
        for peer_num in range(int(o['peers'])):
            print(f"=== {o['name']} -- peer{peer_num} ===")
            peer_name = f"peer{peer_num}"
            peer_conf = {
                'domain': domain,
                'org': o['name'],
                'peer': peer_name
            }
            ret_text = render('docker-compose-peer.yaml.tmpl', peer_conf)
            save_file(f"cache/docker-compose-{peer_name}-{o['name']}.{domain}.yaml", ret_text)

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

def make_tarfile(output_filename, source_dir, peer, org, domain):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir)

def packing_conf(peer, org, domain):
    print(peer + '-' + org + '.' + domain)
    path = f"organizations/peerOrganizations/{org}.{domain}/"
    tar_file = f"cache/{peer}-{org}.{domain}.tar.gz"
    make_tarfile(tar_file, path, peer, org, domain)

def packing_conf_r():
    for x in crypto_config_org['PeerOrgs']:
        org = x['Name']
        for i in range(x['Template']['Count']):
            peer = 'peer' + str(i)
            packing_conf(peer, org, all_conf['domain'])

def distribution():
    domain = all_conf['domain']
    for x in crypto_config_org['PeerOrgs']:
        org = x['Name']
        for i in range(x['Template']['Count']):
            peer = 'peer' + str(i)
            with paramiko.SSHClient() as sshc:
                sshc.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                hostname = f"{peer}-{org}.{domain}"
                sshc.connect(
                    hostname=hostname,
                    port=connection_list[org][peer]['port'],
                    username=connection_list[org][peer]['username'],
                    password=connection_list[org][peer]['password'])
                with scp.SCPClient(sshc.get_transport()) as scpc:
                    print(hostname)
                    scpc.put(
                        files=f"cache/{peer}-{org}.{domain}.tar.gz",
                        remote_path='/tmp')
                    scpc.put(
                        files=f"cache/docker-compose-{peer}-{org}.{domain}.yaml",
                        remote_path='/tmp')
                    scpc.put(
                        files=f"conf/configtx.yaml",
                        remote_path='/tmp')

def create_channel_tx():
    command = f' \
        bin/configtxgen \
            -profile SampleSingleMSPChannel \
            -outputCreateChannelTx ./channel-artifacts/{g_channel}.tx \
            -channelID {g_channel}'
    print(command)
    subprocess.call(command, shell=True)

def create_anchor_peer_tx():
    for org_conf in all_conf['orgs']:
        org = org_conf['name']
        command = f' \
            bin/configtxgen \
                -profile SampleSingleMSPChannel \
                -outputAnchorPeersUpdate ./channel-artifacts/{org}-anchors.tx \
                -channelID {g_channel} \
                -asOrg {org}'
        subprocess.call(command, shell=True)

def create_channel():
    org = all_conf['orgs'][0]['name']
    set_org_env(org)
    command = f" \
        bin/peer channel create \
            -o orderer.{g_domain}:7050 \
            -c {g_channel} \
            -f ./channel-artifacts/{g_channel}.tx \
            --outputBlock ./channel-artifacts/{g_channel}.block \
            --tls \
            --cafile {g_path_orderer_ca}"
    subprocess.call(command, shell=True)

def network_up():
    subprocess.call('docker-compose -f docker/docker-compose.yaml up -d', shell=True)

if mode == "install":
    install()
elif mode == "init":
    init()
    create_org()
    create_consortium()
elif mode == "packaging":
    packing_conf_r()
elif mode == "distribution":
    distribution()
elif mode == "channel":
    create_channel_tx()
    create_anchor_peer_tx()
    create_channel()
elif mode == "up":
    network_up()
elif mode == "all":
    init()
    create_org()
    create_consortium()
    packing_conf_r()
    distribution()
    network_up()

