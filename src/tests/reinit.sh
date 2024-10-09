DB_NAME=$1
DB_USERNAME=$2
DB_PASSWORD=$3

sudo -u postgres dropdb "${DB_NAME}"
sudo -u postgres dropuser "${DB_USERNAME}"

sudo -u postgres psql <<<"CREATE ROLE ${DB_USERNAME} LOGIN PASSWORD '${DB_PASSWORD}';"
sudo -u postgres createdb "${DB_NAME}"
## PostgreSQL 15 or upper
sudo -u postgres psql <<<"GRANT ALL ON DATABASE ${DB_NAME} TO ${DB_USERNAME};"
sudo -u postgres psql <<<"ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USERNAME};"

## Replace db username and db name
sed -i "s/db_username/${DB_USERNAME}/g" ./tests/oj.sql
sed -i "s/db_name/${DB_NAME}/g" ./tests/oj.sql

## Setup db
sudo cp ./tests/oj.sql /var/lib/postgresql/oj.sql
sudo chown postgres /var/lib/postgresql/oj.sql
sudo chmod 644 /var/lib/postgresql/oj.sql
PGPASSWORD=${DB_PASSWORD} sudo -u postgres psql -U "${DB_USERNAME}" -d "${DB_NAME}" -f /var/lib/postgresql/oj.sql
sudo rm /var/lib/postgresql/oj.sql

sed -i "s/${DB_USERNAME}/db_username/g" ./tests/oj.sql
sed -i "s/${DB_NAME}/db_name/g" ./tests/oj.sql

cd ../migration/
$HOME/.local/bin/poetry run python3 migration.py
