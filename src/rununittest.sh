#!/bin/bash

current_pwd=$(pwd)

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
    rune2etest.py
    rununittest.py
    server.py
    */e2e/*
    */unit/*
    upgrade.py
EOF

# remove old report record
rm .coverage.*
rm .coverage
rm -r ./htmlcov

COVERAGE_PROCESS_START=.coveragerc $HOME/.local/bin/poetry run coverage run --branch --source=./ rununittest.py
$HOME/.local/bin/poetry run coverage combine
$HOME/.local/bin/poetry run coverage html
