if [[ -f docker-dev || -f docker-release ]] && [ -d static-tmp ]; then
    ./scripts/docker-init.sh
fi

if [ -d migration ] && [[ -f docker-dev || -f docker-release ]];
then
    cp config.py migration/
    cd migration

    if [ -f ../docker-release ]; then
        python3 migration.py
        cd ..
        rm -rf migration
    else
        poetry run python3 migration.py
        cd ..
    fi
fi

if [ -f docker-release ]; then
    python3 server.py
elif [ -f docker-dev ]; then
    poetry run python3 server.py
else
    $HOME/.local/bin/poetry run python3 server.py --log_rotate_mode=time --log_file_prefix=/var/log/ntoj/access.log
fi
