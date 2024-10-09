#!/bin/bash

current_pwd=$(pwd)

mkdir -p /tmp/ntoj_test_web/oj/problem
cat <<EOF >config.py
DBNAME_OJ = 'ntoj_unittest_db_name'
DBUSER_OJ = 'ntoj_unittest_db_user'
DBPW_OJ = 'ntoj_unittest_db_password'
REDIS_DB = 2
PORT = 5501
COOKIE_SEC = 'ntoj-unittest'
SITE_TITLE = 'ntoj-unittest'
lock_user_list = []
can_see_code_user = [1]
unlock_pwd = b'vW50b2otdW5pdHRlc3Qtc2VydmVyLXBhc3N3b3Jk'
JUDGE_SERVER_LIST = [
    {
        'name': 'NTOJ_Judge1',
        'url': 'ws://127.0.0.1:2502/judge',
        'problems_path': '${current_pwd}/problem',
        'codes_path': '${current_pwd}/code',
    },
]

WEB_PROBLEM_STATIC_FILE_DIRECTORY = '/tmp/ntoj_test_web/oj/problem'
EOF

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
    runtests.py
    server.py
    */e2e/*
    upgrade.py
EOF


# run migration
cp config.py ../migration/

# remove old report record
rm .coverage.*
rm .coverage
rm -r ./htmlcov

COVERAGE_PROCESS_START=.coveragerc $HOME/.local/bin/poetry run coverage run --branch --source=./ runtests.py
$HOME/.local/bin/poetry run coverage combine
$HOME/.local/bin/poetry run coverage html

# cleanup
rm config.py
rm db-inited
rm -rf /tmp/ntoj_test_web
rm ../migration/config.py

if [ "$1" == "web" ]; then
    python3 -m http.server 8080
fi
