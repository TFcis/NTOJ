#!/bin/bash

if [ -f docker-release ]; then
    echo "Internal Error: "
    echo "This script should not be run in docker-release environment."
    exit 1
fi

if [ -d static-tmp ]; then
    cp -r static-tmp/* static/
    rm -rf static-tmp/
fi

current_pwd=$(pwd)
mv config.py config_dev.py

if [ -f docker-dev ]; then
    mkdir problem_bak code_bak
    $(mv problem/* problem_bak)
    $(mv code/* code_bak)
else
    mv problem problem_dev
    mv code code_dev
    mkdir problem code
fi

if [ -f docker-dev ]; then
    cat <<EOF >config.py
import datetime
TIMEZONE          = datetime.timezone(datetime.timedelta(hours=+8))
PORT              = 5501
REDIS_DB          = 2
REDIS_HOST        = 'cache'
DBNAME_OJ         = 'ntoj_unittest_db_name'
DBUSER_OJ         = 'ntoj_unittest_db_user'
DBHOST_OJ         = 'db'
DBPW_OJ           = 'ntoj_unittest_db_password'
COOKIE_SEC        = 'ntoj-unittest'
SITE_TITLE        = 'ntoj-unittest'
can_see_code_user = [1]
unlock_pwd        = b'vW50b2otdW5pdHRlc3Qtc2VydmVyLXBhc3N3b3Jk'
JUDGE_SERVER_LIST = [
    {
        'name': 'NTOJ_Judge1',
        'url': 'ws://judge:2502/judge',
        'problems_path': '/problem',
        'codes_path': '/code',
    },
]
BASE_URL = '/'
EOF
else
cat <<EOF >config.py
import datetime
TIMEZONE          = datetime.timezone(datetime.timedelta(hours=+8))
PORT              = 5501
REDIS_DB          = 2
REDIS_HOST        = 'localhost'
DBNAME_OJ         = 'ntoj_unittest_db_name'
DBUSER_OJ         = 'ntoj_unittest_db_user'
DBHOST_OJ         = 'localhost'
DBPW_OJ           = 'ntoj_unittest_db_password'
COOKIE_SEC        = 'ntoj-unittest'
SITE_TITLE        = 'ntoj-unittest'
can_see_code_user = [1]
unlock_pwd        = b'vW50b2otdW5pdHRlc3Qtc2VydmVyLXBhc3N3b3Jk'
JUDGE_SERVER_LIST = [
    {
        'name': 'NTOJ_Judge1',
        'url': 'ws://127.0.0.1:2502/judge',
        'problems_path': '${current_pwd}/problem',
        'codes_path': '${current_pwd}/code',
    },
]
BASE_URL = '/'
EOF
fi

cat <<EOF >.coveragerc
[run]
branch = True
concurrency = thread
parallel = True
omit =
    /usr/lib/python3/*
    */site-packages/*
    */dist-packages/*
    *.generated.py
    runintegratedtest.py
    rununittest.py
    rune2etest.py
    tests/*
    server.py
    upgrade.py
EOF


# run migration
if [ -f docker-dev ]; then
    cp config.py migration/
else
    cp config.py ../migration
fi

# remove old report record
rm .coverage.*
rm .coverage
rm -r ./htmlcov

COVERAGE_PROCESS_START=.coveragerc $HOME/.local/bin/poetry run coverage run --branch --source=./ runintegratedtest.py
$HOME/.local/bin/poetry run coverage combine
$HOME/.local/bin/poetry run coverage html

# cleanup
rm config.py
mv config_dev.py config.py

if [ -f docker-dev ]; then
    rm -rf problem/* code/*
    $(mv problem_bak/* problem)
    $(mv code_bak/* code)
    rmdir problem_bak code_bak
else
    rm -rf problem code
    mv problem_dev problem
    mv code_dev code
fi

rm db-inited
if [ -f docker-dev ]; then
    rm migration/config.py
else
    rm ../migration/config.py
fi

if [ "$1" == "web" ]; then
    python3 -m http.server 8080
fi
