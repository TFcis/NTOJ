#!/bin/bash

if [[ -f scripts/.env.example ]]; then
    cp scripts/.env.example .env
    $EDITOR .env
else
    echo "scripts/.env.example not found."
fi

docker compose up # -d
