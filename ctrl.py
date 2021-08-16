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

mode = sys.argv[1]
proj = sys.argv[2]

g_pwd = os.getcwd() + '/projects/' + proj
print(g_pwd)

ENV_PATH = os.getenv('PATH')
os.environ['PATH'] = f"{g_pwd}/bin:{ENV_PATH}"
os.environ['FABRIC_CFG_PATH'] = f'{g_pwd}/conf'
os.environ['CORE_PEER_TLS_ENABLED'] = 'true'

gconf = None
g_orderer_domain = None
g_path_orderer_ca = None

env = Environment(loader=FileSystemLoader('template'))

def print_bannar(text):
    print(f"> {text}")

def load_network_config():
    global gconf
    global g_orderer_domain
    global g_path_orderer_ca
    with open(f'{g_pwd}/config-network.yaml') as f:
        gconf = yaml.safe_load(f)
    g_orderer_domain = gconf['orderer']['domain']
    g_path_orderer_ca = f'{g_pwd}/conf/organizations/ordererOrganizations/{g_orderer_domain}/orderers/orderer.{g_orderer_domain}/msp/tlscacerts/tlsca.{g_orderer_domain}-cert.pem'

def load_crypto_config_org():
    if os.path.exists(f'{g_pwd}/conf/crypto-config-org.yaml'):
        with open(f'{g_pwd}/conf/crypto-config-org.yaml') as f:
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
    files = os.listdir(f'{g_pwd}/bin')
    files = [ f for f in files if not f.startswith('.') ]
    if not files:
        subprocess.call(f'script/install-fabric.sh binary {g_pwd}', shell=True)

    # install docker images
    subprocess.call('script/install-fabric.sh docker', shell=True)

def create_project(_org_num):
    os.mkdir(g_pwd)
    os.mkdir(g_pwd + '/bin')
    os.mkdir(g_pwd + '/public')
    os.mkdir(g_pwd + '/channel-artifacts')
    os.mkdir(g_pwd + '/conf')
    os.mkdir(g_pwd + '/conf/organizations')
    os.mkdir(g_pwd + '/system-genesis-block')

    shutil.copyfile("template/orderer.yaml", f"{g_pwd}/orderer.yaml")

    data = {
        'org_num': int(_org_num)
    }

    ret_text = render('config-network.yaml.tmpl', data)
    save_file(f'{g_pwd}/config-network.yaml', ret_text)

    install()

def create_settings():

    print_bannar('create settings')

    ret_text = render('configtx.yaml.tmpl', gconf)
    save_file(f'{g_pwd}/conf/configtx.yaml', ret_text)

    ret_text = render('core.yaml.tmpl', gconf)
    save_file(f'{g_pwd}/conf/core.yaml', ret_text)

    ret_text = render('crypto-config-orderer.yaml.tmpl', gconf)
    save_file(f'{g_pwd}/conf/crypto-config-orderer.yaml', ret_text)

    ret_text = render('crypto-config-org.yaml.tmpl', gconf)
    save_file(f'{g_pwd}/conf/crypto-config-org.yaml', ret_text)

    ret_text = render('docker-compose.yaml.tmpl', gconf)
    save_file(f'{g_pwd}/docker-compose.yaml', ret_text)

def create_org():

    print_bannar('create org')

    path = f'{g_pwd}/conf/organizations/ordererOrganizations'
    if os.path.exists(path):
        shutil.rmtree(path)

    path = f'{g_pwd}/conf/organizations/peerOrganizations'
    if os.path.exists(path):
        shutil.rmtree(path)

    subprocess.call(f'cryptogen generate --config={g_pwd}/conf/crypto-config-orderer.yaml --output={g_pwd}/conf/organizations', shell=True)
    subprocess.call(f'cryptogen generate --config={g_pwd}/conf/crypto-config-org.yaml --output={g_pwd}/conf/organizations', shell=True)

def create_consortium():

    print_bannar('create consortium')

    subprocess.call(f'configtxgen -profile DefaultProfile -channelID system-channel -outputBlock {g_pwd}/system-genesis-block/genesis.block', shell=True)

def make_tarfile(output_filename, source_dir, peer, domain):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir)

def packing_conf(org, peer, domain):
    print(f"> packing conf ({peer} + '.' + {domain})")

    os.mkdir(f"{g_pwd}/public/{org}")
    os.mkdir(f"{g_pwd}/public/{org}/{peer}.{domain}")

    path = f"{g_pwd}/conf/organizations"
    tar_file = f"{g_pwd}/public/{org}/{peer}.{domain}/organizations.tar.gz"
    make_tarfile(tar_file, path, peer, domain)

    data = {
        'domain': domain,
        'org': org
    }
    ret_text = render('config-peer.yaml.tmpl', data)
    save_file(f"{g_pwd}/public/{org}/{peer}.{domain}/config-peer.yaml", ret_text)
    #for o in gconf['orgs']:
    #    data['domain'] = o['domain']
    #    data['org'] = o['name']
    #    for p in o['peers']:
    #        data['peer'] = p['name']
    #        ret_text = render('config-peer.yaml.tmpl', data)
    #        save_file(f"{g_pwd}/public/{p['name']}.{o['domain']}/config-peer.yaml", ret_text)

    shutil.copyfile(f"{g_pwd}/config-network.yaml", f"{g_pwd}/public/{org}/{peer}.{domain}/config-network.yaml")
    shutil.copyfile(f"{g_pwd}/conf/configtx.yaml", f"{g_pwd}/public/{org}/{peer}.{domain}/configtx.yaml")
    shutil.copyfile(f"{g_pwd}/conf/core.yaml", f"{g_pwd}/public/{org}/{peer}.{domain}/core.yaml")

def packing_conf_r(crypto_config_org):
    for x in crypto_config_org['PeerOrgs']:
        org = x['Name']
        org_conf = get_org_conf(org)
        for peer_conf in org_conf['peers']:
            peer = peer_conf['name']
            packing_conf(org, peer, org_conf['domain'])

def distribution(crypto_config_org):
    connection_list = None
    with open(f'{g_pwd}/connection_list.yaml') as f:
        connection_list = yaml.safe_load(f)
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
                        files=f"{g_pwd}/public/{peer}.{domain}/organizations.tar.gz",
                        remote_path='/tmp/organizations.tar.gz')
                    scpc.put(
                        files=f"{g_pwd}/public/{peer}.{domain}/config-peer.yaml",
                        remote_path='/tmp/config-peer.yaml')
                    scpc.put(
                        files=f"config-network.yaml",
                        remote_path='/tmp/config-network.yaml')
                    scpc.put(
                        files=f"{g_pwd}/conf/configtx.yaml",
                        remote_path='/tmp/configtx.yaml')
                    scpc.put(
                        files=f"{g_pwd}/conf/core.yaml",
                        remote_path='/tmp/core.yaml')

def network_up():
    subprocess.call('docker-compose -f {g_pwd}/docker-compose.yaml up -d', shell=True)

def network_down():
    subprocess.call('docker-compose -f {g_pwd}/docker-compose.yaml down', shell=True)

def clean():
    subprocess.call('script/clean_all.sh', shell=True)

if mode == "create-project":
    org_num = sys.argv[3]
    create_project(org_num)
elif mode == "create-consortium":
    load_network_config()
    create_settings()
    create_org()
    create_consortium()
elif mode == "packaging":
    load_network_config()
    crypto_config_org = load_crypto_config_org()
    packing_conf_r(crypto_config_org)
elif mode == "distribution":
    load_network_config()
    crypto_config_org = load_crypto_config_org()
    distribution(crypto_config_org)
elif mode == "up":
    load_network_config()
    network_up()
elif mode == "down":
    load_network_config()
    network_down()
elif mode == "startup-network":
    load_network_config()
    create_settings()
    create_org()
    create_consortium()
    crypto_config_org = load_crypto_config_org()
    packing_conf_r(crypto_config_org)
    distribution(crypto_config_org)
    network_up()
elif mode == "clean":
    clean()
else:
    print_bannar(f"unknown mode: {mode}")

