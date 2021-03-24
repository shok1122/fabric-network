# Requirements

## miniconda

https://docs.conda.io/en/latest/miniconda.html#linux-installers

## docker

https://docs.docker.com/engine/install/ubuntu/
https://docs.docker.com/compose/install/

# Getting Start

The following steps guide you through the installation and the building network.

## Setup your Development Environment

Install the Hyperledger Fabric binaries and the Hyperledger Fabric docker images by following the command.

```
python ctrl.py install
```

## Create consortiums

All configurations, which is needed to create consortiums, will be listed in `config-network.yaml`.
You need to create `config-network.yaml` from scratch, but you can refer to `config-network.sample.yaml`.

Once you configure `config-network.yaml`, you can execute the following command.
Using `config-network.yaml`, this command creates configuration files of a Hyperledger Fabric network and key materials for an orderer and peers.

```
python ctrl.py create-consortium
```

## Distribute key materials to all the peers

The packaging option packs each key material for each peer into tar.gz files.
The distribution option sends the tar.gz files to each peer.
To send these files, it uses the FQDN of peers.

```
python ctrl.py packaging
python ctrl.py distribution
```

## Run the orderer

You can run the orderer by the following command.
The orderer works with Docker.

```
python ctrl.py up
```

