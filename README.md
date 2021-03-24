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

## Create Consortiums

All configurations, which is needed to create consortiums, will be listed in `config-network.yaml`.
You need to create `config-network.yaml` from scratch, but you can refer to `config-network.sample.yaml`.

Once you configure `config-network.yaml`, you can execute the following command.
This command creates the configuration for the Hyperledger Fabric network and the Hyperledger Fabric key materials for orderer and peers using `config-network.yaml`.

```
python ctrl.py create-consortium
```

## Distribute a Key Material to a Peer

The packaging option packs each key material for each peer into tar.gz files.
The distribution option sends the tar.gz files to each peer.
To send these files, you need to be able to communicate by hostname.

```
python ctrl.py packaging
python ctrl.py distribution
```

## Run an Orderer

You can run orderer by the up option.
The orderer works with Docker.

```
python ctrl.py up
```

