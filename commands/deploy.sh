#!/bin/bash

cd /home/ubuntu/cinema-project

git fetch origin
git checkout develop
git pull origin develop

docker compose up --build -d