import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shutil
import asyncpg
import asyncio

from redis import asyncio as aioredis

from services.pro import ProService
from services.pack import PackService
import config

async def main():
    db = await asyncpg.create_pool(database=config.DBNAME_OJ, user=config.DBUSER_OJ, password=config.DBPW_OJ, host=config.DBHOST_OJ)
    rs = aioredis.Redis(host=config.REDIS_HOST, port=6379, db=config.REDIS_DB)
    pro_service = ProService(db, rs)
    pack_service = PackService(db, rs)

    _, pro_id = await pro_service.add_pro(name="HelloTOJ", status=2) # pro_name: "HelloTOJ", pro_statu: "Hidden"
    _, token = await pack_service.gen_token()
    if not os.path.exists('scripts/toj1.tar.xz'):
        print("Internal Error")
        exit(1)
    shutil.copy('scripts/toj1.tar.xz', f'tmp/{token}')
    await pro_service.unpack_pro(pro_id, token)

asyncio.run(main())
