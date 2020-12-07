import sys
import yaml
from jinja2 import Template, Environment, FileSystemLoader
from pprint import pprint

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

if mode == "init":
    init()

