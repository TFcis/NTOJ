import base64
import msgpack

pwd = input()
print(base64.b64encode(msgpack.packb(pwd)))
