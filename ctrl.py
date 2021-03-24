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
os.environ['CORE_PEER_TLS_ENABLED'] = 'true'
print(os.getenv('PATH'))

connection_list = None

with open('./secret/connection_list.yaml') as f:
    connection_list = yaml.safe_load(f)

mode = sys.argv[1]

gconf = None
with open('config-network.yaml') as f:
    gconf = yaml.safe_load(f)

g_pwd = os.getcwd()
g_orderer_domain = gconf['orderer']['domain']
g_channel = gconf['channel']
g_path_orderer_ca = f'{g_pwd}/conf/organizations/ordererOrganizations/{g_orderer_domain}/orderers/orderer.{g_orderer_domain}/msp/tlscacerts/tlsca.{g_orderer_domain}-cert.pem'

env = Environment(loader=FileSystemLoader('template'))

def print_bannar(text):
    print(f"> {text}")

def load_crypto_config_org():
    if os.path.exists('./conf/crypto-config-org.yaml'):
        with open('./conf/crypto-config-org.yaml') as f:
            return yaml.safe_load(f)
    return None

def get_org_conf(org_name):
    org_conf = None
    for o in gconf['orgs']:
        if o['name'] == org_name:
            org_conf = o
    return org_conf

def set_org_env(org):
    org_conf = get_org_conf(org)
    domain = org_conf['domain']
    os.environ['CORE_PEER_LOCALMSPID'] = org_conf['name']
    os.environ['CORE_PEER_TLS_ROOTCERT_FILE'] = f"{g_pwd}/conf/organizations/peerOrganizations/{domain}/peers/peer0.{domain}/tls/ca.crt"
    os.environ['CORE_PEER_MSPCONFIGPATH'] = f"{g_pwd}/conf/organizations/peerOrganizations/{domain}/users/Admin@{domain}/msp"
    os.environ['CORE_PEER_ADDRESS'] = f"peer0.{domain}:7051"

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

def create_settings():

    print_bannar('create settings')

    ret_text = render('configtx.yaml.tmpl', gconf)
    save_file('conf/configtx.yaml', ret_text)

    ret_text = render('core.yaml.tmpl', gconf)
    save_file('conf/core.yaml', ret_text)

    ret_text = render('crypto-config-orderer.yaml.tmpl', gconf)
    save_file('conf/crypto-config-orderer.yaml', ret_text)

    ret_text = render('crypto-config-org.yaml.tmpl', gconf)
    save_file('conf/crypto-config-org.yaml', ret_text)

    ret_text = render('docker-compose-orderer.yaml.tmpl', gconf)
    save_file('docker/docker-compose.yaml', ret_text)

    for o in gconf['orgs']:
        org_name = o['name']
        domain = o['domain']
        for p in o['peers']:
            print(f"=== {o['name']} -- {p['name']} ===")
            peer_name = p['name']
            peer_conf = {
                'domain': domain,
                'org': org_name,
                'peer': peer_name
            }
            ret_text = render('docker-compose-peer.yaml.tmpl', peer_conf)
            save_file(f"cache/docker-compose-{peer_name}.{domain}.yaml", ret_text)

    data = {}
    for o in gconf['orgs']:
        data['domain'] = o['domain']
        data['org'] = o['name']
        for p in o['peers']:
            data['peer'] = p['name']
            ret_text = render('config-peer.yaml.tmpl', data)
            save_file(f"cache/config-peer-{p['name']}.{o['domain']}.yaml", ret_text)

def create_org():

    print_bannar('create org')

    path = 'conf/organizations/ordererOrganizations'
    if os.path.exists(path):
        shutil.rmtree(path)

    path = 'conf/organizations/peerOrganizations'
    if os.path.exists(path):
        shutil.rmtree(path)

    subprocess.call('cryptogen generate --config=./conf/crypto-config-orderer.yaml --output=conf/organizations', shell=True)
    subprocess.call('cryptogen generate --config=./conf/crypto-config-org.yaml --output=conf/organizations', shell=True)

def create_consortium():

    print_bannar('create consortium')

    subprocess.call('configtxgen -profile DefaultProfile -channelID system-channel -outputBlock ./system-genesis-block/genesis.block', shell=True)

def make_tarfile(output_filename, source_dir, peer, domain):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir)

def packing_conf(peer, domain):
    print(f"> packing conf ({peer} + '.' + {domain})")
    path = "conf/organizations"
    tar_file = f"cache/{peer}.{domain}.tar.gz"
    make_tarfile(tar_file, path, peer, domain)

def packing_conf_r(crypto_config_org):
    for x in crypto_config_org['PeerOrgs']:
        org = x['Name']
        org_conf = get_org_conf(org)
        for peer_conf in org_conf['peers']:
            peer = peer_conf['name']
            packing_conf(peer, org_conf['domain'])

def distribution(crypto_config_org):
    print_bannar('distribution')
    for x in crypto_config_org['PeerOrgs']:
        org = x['Name']
        org_conf = get_org_conf(org)
        domain = org_conf['domain']
        for peer_conf in org_conf['peers']:
            peer = peer_conf['name']
            with paramiko.SSHClient() as sshc:
                sshc.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                hostname = f"{peer}.{domain}"
                sshc.connect(
                    hostname=hostname,
                    port=connection_list[org][peer]['port'],
                    username=connection_list[org][peer]['username'],
                    password=connection_list[org][peer]['password'])
                with scp.SCPClient(sshc.get_transport()) as scpc:
                    print(hostname)
                    scpc.put(
                        files=f"cache/{peer}.{domain}.tar.gz",
                        remote_path='/tmp/organizations.tar.gz')
                    scpc.put(
                        files=f"cache/docker-compose-{peer}.{domain}.yaml",
                        remote_path='/tmp/docker-compose.yaml')
                    scpc.put(
                        files=f"cache/config-peer-{peer}.{domain}.yaml",
                        remote_path='/tmp/config-peer.yaml')
                    scpc.put(
                        files=f"config-network.yaml",
                        remote_path='/tmp/config-network.yaml')
                    scpc.put(
                        files=f"conf/configtx.yaml",
                        remote_path='/tmp/configtx.yaml')
                    scpc.put(
                        files=f"conf/core.yaml",
                        remote_path='/tmp/core.yaml')

def create_channel_tx():
    command = f' \
        bin/configtxgen \
            -profile SampleSingleMSPChannel \
            -outputCreateChannelTx ./channel-artifacts/{g_channel}.tx \
            -channelID {g_channel}'
    print(command)
    subprocess.call(command, shell=True)

def create_anchor_peer_tx():
    for org_conf in gconf['orgs']:
        org = org_conf['name']
        command = f' \
            bin/configtxgen \
                -profile SampleSingleMSPChannel \
                -outputAnchorPeersUpdate ./channel-artifacts/{org}-anchors.tx \
                -channelID {g_channel} \
                -asOrg {org}'
        subprocess.call(command, shell=True)

def create_channel():
    print('------------------------------------')
    print(' create channel')
    print('------------------------------------')
    org = gconf['orgs'][0]['name']
    set_org_env(org)
    command = f" \
        bin/peer channel create \
            -o orderer.{g_orderer_domain}:7050 \
            -c {g_channel} \
            -f ./channel-artifacts/{g_channel}.tx \
            --outputBlock ./channel-artifacts/{g_channel}.block \
            --tls \
            --cafile {g_path_orderer_ca}"
    subprocess.call(command, shell=True)

def join_channel():
    print('------------------------------------')
    print(' join channel')
    print('------------------------------------')
    for org_conf in gconf['orgs']:
        org = org_conf['name']
        set_org_env(org)
        command = f" \
            bin/peer channel join \
                -b ./channel-artifacts/{g_channel}.block"
        subprocess.call(command, shell=True)

def update_anchor_peers():
    print('------------------------------------')
    print(' update anchor peers')
    print('------------------------------------')
    for org_conf in gconf['orgs']:
        org = org_conf['name']
        set_org_env(org)
        command = f" \
            bin/peer channel update \
                -o orderer.{g_orderer_domain}:7050 \
                -c {g_channel} \
                -f ./channel-artifacts/{org}-anchors.tx \
                --tls \
                --cafile {g_path_orderer_ca}"
        subprocess.call(command, shell=True)

def network_up():
    subprocess.call('docker-compose -f docker/docker-compose.yaml up -d', shell=True)

def clean():
    subprocess.call('script/clean_all.sh', shell=True)

if mode == "install":
    install()
elif mode == "create-consortium":
    create_settings()
    create_org()
    create_consortium()
elif mode == "packaging":
    crypto_config_org = load_crypto_config_org()
    packing_conf_r(crypto_config_org)
elif mode == "distribution":
    crypto_config_org = load_crypto_config_org()
    distribution(crypto_config_org)
elif mode == "up":
    network_up()
elif mode == "startup-network":
    create_settings()
    create_org()
    create_consortium()
    crypto_config_org = load_crypto_config_org()
    packing_conf_r(crypto_config_org)
    distribution(crypto_config_org)
    network_up()
elif mode == "startup-channel":
    create_channel_tx()
    create_anchor_peer_tx()
    create_channel()
    #join_channel()
    #update_anchor_peers()
elif mode == "clean":
    clean()

