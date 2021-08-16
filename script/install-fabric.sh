#/bin/sh

if [ "binary" = "$1" ]; then
    (
        cd /tmp
        curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.3.0 1.4.9 -ds
    )
    cp -r /tmp/bin $2
fi

if [ "docker" = "$1" ]; then
    curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.3.0 1.4.9 -bs
fi
