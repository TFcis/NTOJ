source scripts/.env set

cp -r static-tmp/* static/
rm -rf static-tmp/
cp config-tmp.py config.py
rm config-tmp.py
cp config.py scripts/

until pg_isready -h db -p 5432; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

if PGPASSWORD=${DB_PASSWORD} psql -U ntoj -d ntoj -h db -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='challenge';" | grep -q 1; then
    echo "exists"
else
    sed -i "s/db_username/ntoj/g" ./scripts/oj.sql
    sed -i "s/db_name/ntoj/g" ./scripts/oj.sql

    ## Setup db
    PGPASSWORD=${DB_PASSWORD} psql -U ntoj -d ntoj -h db -f scripts/oj.sql
    python3 scripts/add_admin.py ${ADMIN_NAME} ${ADMIN_PASSWORD} ${ADMIN_MAIL}
fi


rm scripts/oj.sql
rm scripts/add_admin.py
rm scripts/docker-init.sh
rm scripts/get_unlock_pwd.py
rm scripts/.env
rm scripts/config.py
