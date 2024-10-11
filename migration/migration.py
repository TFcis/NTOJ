import asyncio
import importlib
import inspect
import os
import traceback

import asyncpg
import config
from redis import asyncio as aioredis


async def main():
    db_conn = await asyncpg.connect(
        database=config.DBNAME_OJ, user=config.DBUSER_OJ, password=config.DBPW_OJ, host='localhost'
    )
    redis_conn = await aioredis.Redis(host='localhost', port=6379, db=config.REDIS_DB)

    db_version = None
    result = await db_conn.fetch(
        '''
        SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'db_version'
        ) AS is_exist;
    '''
    )
    result = result[0]

    if not result['is_exist']:
        # create version table
        await db_conn.execute(
            '''
        CREATE TABLE db_version (
            "version" integer
        );
        '''
        )
        await db_conn.execute('INSERT INTO db_version ("version") VALUES (0)')
        db_version = 0

    else:
        result = await db_conn.fetch("SELECT * FROM db_version")
        db_version = int(result[0]['version'])

    migration_files = sorted(
        (file for file in os.listdir('./') if file.endswith('.py') and file not in {"migration.py", "config.py"}),
        key=lambda filename: filename[:14],  # Sort by timestamp (yyyymmddHHMMSS)
    )

    for version, filename in enumerate(migration_files, start=1):
        if version <= db_version:
            continue

        if filename.endswith('.py'):
            module_name = filename[:-3]
            module = importlib.import_module(module_name)

            if not hasattr(module, 'dochange'):
                print(f"{filename} is an illegal migration file because dochange() was not found in {filename}")
                continue

            if not inspect.iscoroutinefunction(module.dochange):
                print("dochange() must be an async function")
                continue

            try:
                async with db_conn.transaction():
                    await module.dochange(db_conn, redis_conn)

            except Exception as e:
                print(f"Error running migration file {filename}: {e}")
                traceback.print_exc()
                break

        await db_conn.execute('UPDATE db_version SET "version"=$1', version)


if __name__ == "__main__":
    asyncio.run(main())
