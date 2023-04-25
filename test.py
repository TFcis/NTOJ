import redis
import msgpack
import datetime

print(datetime.datetime.now().astimezone(datetime.timezone.utc))

# rs = redis.Redis(host='localhost', port=6379, db=1)
# rs.scard
# rs.srem
# rs.set
# informs = msgpack.unpackb(rs.get('inform'))
#
# for inform in informs:
#     inform['color'] = 'white'
#
# rs.set('inform', msgpack.packb(informs))

# import asyncio
#
# async def t():
#     while True:
#         print('run')
#         pass
#
# async def main():
#     task = asyncio.create_task(t())
#     await asyncio.sleep(3)
#
#     task.cancel()
#     await asyncio.sleep(3)
#     task.cancel()
#
# asyncio.run(main())

def test(a, b=None, **kwargs):
    print(a, b, kwargs)
    pass

# test(1, c=3, d=4, e=5)
