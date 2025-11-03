if [ -d static-tmp ];
then
    ./scripts/docker-init.sh
fi

if [ -d migration ];
then
    cp config.py migration/
    cd migration
    python3 migration.py
    cd ..
    rm -rf migration
fi

python3 server.py # --log_rotate_mode=time --log_file_prefix=/var/log/ntoj/access.log
