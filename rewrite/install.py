import os
import redis
import msgpack

def main():

    rs = redis.Redis(host='localhost', port=6379, db=1)
    rs.set('contest_list', msgpack.packb([]))
    rs.set('inform', msgpack.packb([]))
    rs.set('lock_list', msgpack.packb([]))
    rs.set('someoneask', msgpack.packb(False))

    pass

if __name__ == "__main__":
    # miyuki is my wife and sister

    main()
