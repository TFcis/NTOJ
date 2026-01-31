if [ ! -f docker-dev ] && [ ! -f docker-release ]; then
    echo "Internal Error: "
    echo "This script should only be run in docker-dev or docker-release environment."
    exit 1
fi

if [ ! -f scripts/.docker-init.env ]; then
    echo "Internal Error: "
    echo "Missing scripts/.docker-init.env file."
    exit 1
fi

source scripts/.docker-init.env set

cp -r static-tmp/* static/
rm -rf static-tmp/
if [ -f docker-dev ]; then
    mv config-tmp.py config.py
else
    mv config-tmp.py config/config.py
    ln -s config/config.py config.py
fi
cp config.py scripts/

until pg_isready -h ${DB_CONTAINER_NAME} -p 5432; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

if PGPASSWORD=${DB_PASSWORD} psql -U ntoj -d ntoj -h ${DB_CONTAINER_NAME} -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='challenge';" | grep -q 1; then
    echo "db exists"
else
    sed -i "s/db_username/ntoj/g" ./scripts/oj.sql
    sed -i "s/db_name/ntoj/g" ./scripts/oj.sql

    ## Setup db
    PGPASSWORD=${DB_PASSWORD} psql -U ntoj -d ntoj -h ${DB_CONTAINER_NAME} -f scripts/oj.sql
    if [ -f docker-dev ]; then
        poetry run python3 scripts/add_admin.py ${ADMIN_NAME} ${ADMIN_PASSWORD} ${ADMIN_MAIL}
    else
        python3 scripts/add_admin.py ${ADMIN_NAME} ${ADMIN_PASSWORD} ${ADMIN_MAIL}
    fi
fi


rm scripts/oj.sql
rm scripts/add_admin.py
rm scripts/docker-init.sh
rm scripts/get_unlock_pwd.py
rm scripts/.docker-init.env
rm scripts/config.py
