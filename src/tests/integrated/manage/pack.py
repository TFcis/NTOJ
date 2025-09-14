import os
import json
import asyncio
import hashlib

from tornado.websocket import websocket_connect

from tests.integrated.util import AsyncTest, AccountContext


class ManagePackTest(AsyncTest):
    async def s(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            pack_token = self.get_upload_token(admin_session)

            file = open("tests/static_file/code/toj3.ac.py", "rb")
            md5 = hashlib.md5()
            filesize = os.path.getsize("tests/static_file/code/toj3.ac.py")

            remain = filesize
            while True:
                data = file.read(65535)
                if not data:
                    break

                md5.update(data)
            file.seek(0, 0)

            ws = await websocket_connect("ws://localhost:5501/pack")
            await ws.write_message(
                json.dumps(
                    {
                        "pack_token": pack_token,
                        "pack_size": filesize,
                        "md5": md5.hexdigest(),
                    }
                )
            )

            msg = await ws.read_message()
            self.assertEqual(msg, "S")

            while remain != 0:
                size = min(remain, 65535)
                await ws.write_message(file.read(size), binary=True)
                remain -= size

                msg = await ws.read_message()
                self.assertNotEqual(msg, "Echunk")
                self.assertNotEqual(msg, "Ehash")
                if msg is None:
                    break

            ws.close()
            self.assertTrue(os.path.exists(f"tmp/{pack_token}"))
            os.remove(f"tmp/{pack_token}")

    async def h(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            pack_token = self.get_upload_token(admin_session)

            file = open("tests/static_file/code/toj3.ac.py", "rb")
            md5 = hashlib.md5()
            filesize = os.path.getsize("tests/static_file/code/toj3.ac.py")

            remain = filesize
            md5.update(b'123')

            ws = await websocket_connect("ws://localhost:5501/pack")
            await ws.write_message(
                json.dumps(
                    {
                        "pack_token": pack_token,
                        "pack_size": filesize,
                        "md5": md5.hexdigest(),
                    }
                )
            )

            msg = await ws.read_message()
            self.assertEqual(msg, "S")

            while remain != 0:
                size = min(remain, 65535)
                await ws.write_message(file.read(size), binary=True)
                remain -= size

                msg = await ws.read_message()
                self.assertNotEqual(msg, "Echunk")
                self.assertEqual(msg, "Ehash")
                if msg is None:
                    break

            ws.close()
            self.assertFalse(os.path.exists(f"tmp/{pack_token}"))

    async def d(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            pack_token = self.get_upload_token(admin_session)

            file = open("tests/static_file/code/toj3.ac.py", "rb")
            md5 = hashlib.md5()
            filesize = os.path.getsize("tests/static_file/code/toj3.ac.py")

            remain = filesize
            while True:
                data = file.read(65535)
                if not data:
                    break

                md5.update(data)
            file.seek(0, 0)

            ws = await websocket_connect("ws://localhost:5501/pack")
            await ws.write_message(
                json.dumps(
                    {
                        "pack_token": pack_token,
                        "pack_size": filesize,
                        "md5": md5.hexdigest(),
                    }
                )
            )

            msg = await ws.read_message()
            self.assertEqual(msg, "S")

            while remain != 0:
                size = min(remain, 1)
                await ws.write_message(file.read(size), binary=True)
                remain -= size

                msg = await ws.read_message()
                self.assertNotEqual(msg, "Echunk")
                self.assertNotEqual(msg, "Ehash")
                if msg is None:
                    break
                break

            ws.close()
            await asyncio.sleep(1)
            self.assertFalse(os.path.exists(f"tmp/{pack_token}"))

    async def main(self):
        await self.s()
        await self.h()
        await self.d()
