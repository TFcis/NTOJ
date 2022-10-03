import asyncio

import asyncpg
import redis

import config

async def materialized_view_task():
    db = await asyncpg.connect(database=config.DBNAME_OJ, user=config.DBUSER_OJ, password='322752278227', host='localhost')
    rs = redis.Redis(host='localhost', port=6379, db=1)
    p = rs.pubsub()
    p.subscribe('materialized_view_req')

    async def _update():
        ret = rs.incr('materialized_view_counter') - 1
        await db.execute('REFRESH MATERIALIZED VIEW challenge_state;')
        return ret

    counter = await _update()
    for msg in p.listen():
        if msg['type'] != 'message':
            continue

        ind = int(msg['data'])
        if ind <= counter:
            continue

        counter = await _update()

if __name__ == "__main__":
    asyncio.run(materialized_view_task())
