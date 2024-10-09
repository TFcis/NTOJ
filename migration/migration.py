import os
import asyncio
import inspect
import importlib
import traceback

import asyncpg
from redis import asyncio as aioredis

import config

async def main():
    db_conn = await asyncpg.connect(
        database=config.DBNAME_OJ, user=config.DBUSER_OJ, password=config.DBPW_OJ, host='localhost'
    )
    redis_conn = await aioredis.Redis(host='localhost', port=6379, db=config.REDIS_DB)

    db_version = None
    result = await db_conn.fetch('''
        SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'db_version'
        ) AS is_exist;
    ''')
    result = result[0]

    if not result['is_exist']:
        # create version table
        await db_conn.execute('''
        CREATE TABLE db_version (
            "version" integer
        );
        ''')
        await db_conn.execute('INSERT INTO db_version ("version") VALUES (0)')
        db_version = 0

    else:
        result = await db_conn.fetch("SELECT * FROM db_version")
        db_version = int(result[0]['version'])

    migration_files = (file for file in os.listdir('./') if file.endswith('.py') and file != "migration.py" and file != "config.py")
    migration_files = sorted(migration_files, key=lambda filename: filename[0:14])  # 0:14 means yyyymmddHHMMSS

    for version, filename in enumerate(migration_files):
        version += 1
        if version <= db_version:
            continue

        if filename.endswith('.py'):
            module_name = filename[:-3]
            module = importlib.import_module(f"{module_name}")

            try:
                if hasattr(module, 'dochange') and inspect.iscoroutinefunction(module.dochange):
                    await module.dochange(db_conn, redis_conn)

            except Exception as e:
                print(f'run migration file {filename} have error', e)
                traceback.print_exc()
                break

            print(f'run migration file {filename} success')

        await db_conn.execute('UPDATE db_version SET "version"=$1', version)

if __name__ == "__main__":
    asyncio.run(main())
