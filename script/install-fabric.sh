#/bin/sh

if [ "binary" = "$1" ]; then
    pushd /tmp
    curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.3.0 1.4.9 -ds
    popd
    cp -r /tmp/bin .
fi

if [ "docker" = "$1" ]; then
    curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.3.0 1.4.9 -bs
fi
