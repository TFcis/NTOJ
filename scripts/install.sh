#!/bin/bash
set -eo pipefail

# Env
set -o allexport
source .env set
set +o allexport

if [ -z $INSTALL_DIR ]; then
	INSTALL_DIR=/srv
fi

if [ -z $DB_NAME ]; then
	DB_NAME=ntoj
fi

if [ -z $DB_USERNAME ]; then
	DB_USERNAME=ntoj
fi

if [ -z $DB_PASSWORD ]; then
	DB_PASSWORD=DB_PASSWORD
fi

if [ -z $UNLOCK_PWD ]; then
	UNLOCK_PWD=UNLOCK_PASSWORD
fi

if [ -z $ADMIN_NAME ]; then
	ADMIN_NAME=admin
fi

if [ -z $ADMIN_MAIL ]; then
	ADMIN_MAIL=admin@admin
fi

if [ -z $ADMIN_PASSWORD ]; then
	ADMIN_PASSWORD=admin1234
fi

# Update and upgrade
sudo apt update
sudo apt upgrade

# Create Directory
sudo mkdir -p ${INSTALL_DIR}/ntoj
sudo mkdir -p ${INSTALL_DIR}/ntoj_web/oj/

# # Create log file and directory
sudo mkdir -p /var/log/ntoj/
sudo touch /var/log/ntoj/access.log

# # Install PostgreSQL
sudo apt install wget gpg
sudo wget -O- https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor | sudo tee /usr/share/keyrings/postgresql.gpg
echo deb [arch=amd64 signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main | sudo tee /etc/apt/sources.list.d/postgresql.list
sudo apt update
sudo apt install -f postgresql-15 postgresql-client-15
sudo systemctl enable --now postgresql.service

sudo sed -i 's/peer/trust/' /etc/postgresql/15/main/pg_hba.conf
sudo systemctl restart postgresql.service
sudo -u postgres psql <<<"CREATE ROLE ${DB_USERNAME} LOGIN PASSWORD '${DB_PASSWORD}';"
sudo -u postgres createdb ${DB_NAME}
## PostgreSQL 15 or upper
sudo -u postgres psql <<<"GRANT ALL ON DATABASE ${DB_NAME} TO ${DB_USERNAME};"
sudo -u postgres psql <<<"ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USERNAME};"

## Replace db username and db name
sed -i "s/db_username/${DB_USERNAME}/g" ./oj.sql
sed -i "s/db_name/${DB_NAME}/g" ./oj.sql

## Setup db
sudo cp ./oj.sql /var/lib/postgresql/oj.sql
sudo chown postgres /var/lib/postgresql/oj.sql
sudo chmod 644 /var/lib/postgresql/oj.sql
PGPASSWORD=${DB_PASSWORD} sudo -u postgres psql -U ${DB_USERNAME} -d ${DB_NAME} -f /var/lib/postgresql/oj.sql
sudo rm /var/lib/postgresql/oj.sql

# Install Python3
sudo apt install python3 python3-pip dos2unix
sudo pip3 install -r ./requirements.txt

# NTOJ
sudo cp -r ../src/* ${INSTALL_DIR}/ntoj/
sudo cp -r ../src/static/* ${INSTALL_DIR}/ntoj_web/oj/

# Install Nginx
sudo apt install nginx
sudo systemctl enable --now nginx.service

## Replace nginx root directory path
INSTALL_DIR_ESCAPE=$(echo ${INSTALL_DIR} | sed 's/[\/\$]/\\\&/g')
sudo sed -i "s/INSTALL_DIR/${INSTALL_DIR_ESCAPE}/" ./ntoj.conf
sudo cp ./ntoj.conf /etc/nginx/conf.d/
sudo sed -i "s/www-data/root/" /etc/nginx/nginx.conf
sudo rm /etc/nginx/sites-enabled/default

sudo nginx -s reload

# Install Redis
sudo apt install redis
sudo systemctl enable --now redis-server.service

# Create config.py
sudo apt install xxd
COOKIE_SEC=$(head -c 32 /dev/urandom | xxd -ps -c 128)
UNLOCK_PWD=$(python3 get_unlock_pwd.py <<<${UNLOCK_PASSWORD})
cat <<EOF | sudo tee ${INSTALL_DIR}/ntoj/config.py >/dev/null
DBNAME_OJ  = '${DB_NAME}'
DBUSER_OJ  = '${DB_USERNAME}'
DBPW_OJ    = '${DB_PASSWORD}'
COOKIE_SEC = '${COOKIE_SEC}'
lock_user_list = []
can_see_code_user = [1]
unlock_pwd = ${UNLOCK_PWD}
WEB_PROBLEM_STATIC_FILE_DIRECTORY = '${INSTALL_DIR}/ntoj_web/oj/problem'
JUDGE_SERVER_LIST = [
]
EOF

# Create default administrator account
$(python3 add_admin.py ${ADMIN_NAME} ${ADMIN_PASSWORD} ${ADMIN_MAIL} ${INSTALL_DIR}/ntoj/config.py)
