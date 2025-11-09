if [ -f docker-release ]; then
    echo "Internal Error: "
    echo "This script should only be run in docker-dev environment."
    exit 1
fi

if [ "$#" -ne 4 ]; then
    echo "Usage: $0 DB_NAME DB_HOST DB_USERNAME DB_PASSWORD"
    exit 1
fi

DB_NAME=$1
DB_HOST=$2
DB_USERNAME=$3
DB_PASSWORD=$4

if [ -f docker-dev ]; then
    PGPASSWORD=${DB_PASSWORD} dropdb -U ${DB_USERNAME} -h db ${DB_NAME}
    PGPASSWORD=ntoj dropuser -U ntoj -h db ${DB_USERNAME}
    PGPASSWORD=ntoj psql -U ntoj -h db <<<"CREATE ROLE ${DB_USERNAME} LOGIN PASSWORD '${DB_PASSWORD}';"
    PGPASSWORD=ntoj createdb -U ntoj -h db ${DB_NAME}
    PGPASSWORD=ntoj psql -U ntoj -h db <<<"GRANT ALL ON DATABASE ${DB_NAME} TO ${DB_USERNAME};"
    PGPASSWORD=ntoj psql -U ntoj -h db <<<"ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USERNAME};"

    sed -i "s/db_username/${DB_USERNAME}/g" ./tests/oj.sql
    sed -i "s/db_name/${DB_NAME}/g" ./tests/oj.sql

    PGPASSWORD=${DB_PASSWORD} psql -U ${DB_USERNAME} -d ${DB_NAME} -h db -f ./tests/oj.sql

    sed -i "s/${DB_USERNAME}/db_username/g" ./tests/oj.sql
    sed -i "s/${DB_NAME}/db_name/g" ./tests/oj.sql

    cd migration
    poetry run python3 migration.py
else
    sudo -u postgres dropdb -h ${DB_HOST} "${DB_NAME}"
    sudo -u postgres dropuser -h ${DB_HOST} "${DB_USERNAME}"

    sudo -u postgres psql -h ${DB_HOST} <<<"CREATE ROLE ${DB_USERNAME} LOGIN PASSWORD '${DB_PASSWORD}';"
    sudo -u postgres createdb -h ${DB_HOST} "${DB_NAME}"
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
fi

