#!/bin/sh

echo 'stop docker images...'
docker-compose -f docker/docker-compose.yaml down --volumes

echo 'remove cache/*...'
rm -rf cache/*
echo 'remove channel-artifacts/*...'
rm -rf channel-artifacts/*
echo 'remove conf/*...'
rm -rf conf/*
echo 'remove docker/*...'
rm -rf docker/*
echo 'remove organizations/*...'
rm -rf organizations/*
echo 'remove system-genesis-block/*...'
rm -rf system-genesis-block/*
