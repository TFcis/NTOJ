import copy
import hashlib
import time
import asyncio
import datetime
import json
import os
import unittest

import requests
from tornado.websocket import websocket_connect

from services.chal import Compiler
from services.pro import ProConst, ProService
from runintegratedtest import testing_loop, db


class AsyncTest(unittest.IsolatedAsyncioTestCase):
    def __init__(self, *args, **kwargs):
        self.db = db
        super().__init__(*args, **kwargs)

    def run(self, result=None):
        runner = asyncio.Runner(debug=True, loop_factory=lambda: testing_loop)
        self._asyncioRunner = runner
        try:
            return super(unittest.IsolatedAsyncioTestCase, self).run(result)
        finally:
            pass

    def __del__(self):
        pass

    def assertAPIReturnValue(self, text: str, structure, msg: str = ''):
        s = json.loads(text)
        self.assertEqual(s['status'], structure[0], msg)
        self.assertEqual(s['data'], structure[1], msg)

    def assertAPIReturnSuccess(self, text: str, msg=None):
        s = json.loads(text)
        self.assertEqual(s['status'], 'S')
        if msg and isinstance(msg, str):
            self.assertEqual(s['data'], msg)

    def get_isoformat(self, time: datetime.datetime) -> str:
        return time.isoformat(timespec="microseconds") + "Z"

    async def upload_file(self, file, file_size: int, pack_token: str):
        md5 = hashlib.md5()
        remain = file_size
        while True:
            data = file.read(65536)
            if not data:
                break

            md5.update(data)

        ws = await websocket_connect("ws://localhost:5501/be/pack")
        await ws.write_message(
            json.dumps(
                {
                    "pack_token": pack_token,
                    "pack_size": file_size,
                    "md5": md5.hexdigest(),
                }
            )
        )
        file.seek(0, 0)
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

    async def upload_problem(self, file, name, status, expected_pro_id, session):
        pack_token = self.get_upload_token(session)
        file_path = f"tests/static_file/{file}"
        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            await self.upload_file(f, file_size, pack_token)

        res = session.post(
            "manage/pro/add",
            data={
                "reqtype": "addpro",
                "name": name,
                "status": status,
                "pack_token": pack_token,
                "mode": "upload",
            },
        )

        self.assertAPIReturnValue(res.text, ('S', expected_pro_id))

        err, pro = await ProService.inst.get_pro(expected_pro_id, ProConst.PRO_STATUS_FULL)
        self.assertIsNone(err)
        self.assertEqual(pro.name, name)
        self.assertEqual(pro.status, status)

    def get_upload_token(self, session):
        res = session.post("manage/pack", data={"reqtype": "gettoken"})

        res = json.loads(res.text)
        self.assertEqual(res['status'], 'S')
        pack_token = res['data']
        self.assertNotEqual(pack_token, "")
        return pack_token

    def submit_problem(self, pro_id: int, code: str, compiler_type: Compiler, session) -> int:
        res = session.post(
            "submit",
            data={
                "reqtype": "submit",
                "pro_id": pro_id,
                "code": code,
                "compiler_type": compiler_type,
            },
        )
        res = json.loads(res.text)
        self.assertEqual(res['status'], 'S')
        chal_id = int(res['data'])
        return chal_id

    def signup(self, name: str, mail: str, pw: str):
        session = requests.Session()
        res = session.post(
            "http://localhost:5501/be/sign",
            data={
                "reqtype": "signup",
                "name": name,
                "mail": mail,
                "pw": pw,
            },
        )
        self.assertAPIReturnSuccess(res.text)
        self.assertIn("id", session.cookies.get_dict())

        res = session.post(
            "http://localhost:5501/be/sign",
            data={
                "reqtype": "signout",
            },
        )
        self.assertAPIReturnSuccess(res.text)
        self.assertNotIn("id", session.cookies.get_dict())

    async def wait_for_judge_finish(self, callback):
        ws = await websocket_connect("ws://localhost:5501/be/manage/judgecntws")

        callback()

        judges_cnt = {}
        while True:
            msg = await ws.read_message()
            if msg is None:
                break

            j = json.loads(msg)
            judge_id = j["judge_id"]
            cnt = j["chal_cnt"]

            judges_cnt[judge_id] = cnt

            if cnt == 0:
                judges_cnt.pop(judge_id)

            if not len(judges_cnt):
                break

    def assertTable(self, url: str, default_data: dict, assert_tables: list[dict], session):
        for table in assert_tables:
            equal_value = table.pop("equal_value")

            d = copy.copy(default_data)
            for key, val in table.items():
                d[key] = val

            res = session.post(url, data=d)
            self.assertAPIReturnValue(res.text, equal_value, f'{table}')


class BaseUrlSession(requests.Session):
    def request(self, method: str | bytes, url: str | bytes, *args, **kwargs):
        if "full_url" in kwargs:
            url = kwargs.pop("full_url")
        else:
            url = f"http://localhost:5501/be/{url}"
        return super().request(method, url, *args, **kwargs)


class AccountContext:
    LAST_TIME = time.time()
    def __init__(self, mail: str, pw: str):
        self.mail = mail
        self.pw = pw
        self.session = BaseUrlSession()

    def __enter__(self):
        diff = time.time() - AccountContext.LAST_TIME
        if diff < 1:
            time.sleep(1) # NOTE: Make two session cookies different by introducing a time difference
        AccountContext.LAST_TIME = time.time()
        res = self.session.post(
            "sign",
            data={
                "reqtype": "signin",
                "mail": self.mail,
                "pw": self.pw,
            },
        )
        for cookie in self.session.cookies:
            cookie.path = "/"

        res = json.loads(res.text)
        assert res['status'] == 'S'
        assert "id" in self.session.cookies.get_dict()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = self.session.post(
            "sign",
            data={
                "reqtype": "signout",
            },
        )
        res = json.loads(res.text)
        assert res['status'] == 'S'
        assert "id" not in self.session.cookies.get_dict()


PROBLEMS = {}
