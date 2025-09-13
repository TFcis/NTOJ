import decimal
import hashlib
import time
import asyncio
import datetime
import json
import os
import unittest

import requests
from bs4 import BeautifulSoup
from tornado.websocket import websocket_connect
from services.chal import Compiler, TotalResult, SubtaskResult, TestdataResult, MessageType

from rune2etest import testing_loop, db


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

    def assertAPIReturnValue(self, text: str, structure):
        s = json.loads(text)
        self.assertEqual(s['status'], structure[0])
        self.assertEqual(s['data'], structure[1])

    def assertAPIReturnSuccess(self, text: str, msg=None):
        s = json.loads(text)
        self.assertEqual(s['status'], 'S')
        if msg and isinstance(msg, str):
            self.assertEqual(s['data'], msg)

    def get_html(self, url, session, full_url=None):
        if full_url is not None:
            res = session.get(full_url=full_url)
        else:
            res = session.get(url)

        return BeautifulSoup(res.text, "html.parser")

    def get_isoformat(self, time: datetime.datetime) -> str:
        return time.isoformat(timespec="milliseconds") + "Z"

    def get_chal_results(self, chal_id: int, session) -> tuple[TotalResult, dict[int, SubtaskResult], dict[int, TestdataResult]]:
        html = self.get_html(f"chal/{chal_id}", session)

        tds = html.select("#total > tbody > tr > td")
        # NOTE: <td class="state state-\d+"></td>
        total_result_message = html.select_one('#challengeTotalResultMessage')
        self.assertIsNotNone(total_result_message)
        message_type = MessageType.NONE
        message = ""
        if total_result_message.select_one('pre') is not None:
            message_type = MessageType.TEXT
            message = total_result_message.select_one('pre').text.strip()
        elif total_result_message.select_one('div') is not None:
            message = total_result_message.select_one('div').decode_contents()
            message_type = MessageType.HTML

        total_result = TotalResult(int(tds[1].attrs['class'][1].split("-")[1]), int(tds[2].text.strip()),
                    int(tds[3].text.strip()), decimal.Decimal(tds[4].text.strip()), message, message_type)
        subtask_results = {}
        for tr in html.select("#subtasks > tbody > tr"):
            tds = tr.select('td')
            id = int(tds[0].text.strip())
            subtask_results[id] = SubtaskResult(id, int(tds[1].attrs['class'][1].split("-")[1]), int(tds[2].text.strip()),
                    int(tds[3].text.strip()), decimal.Decimal(tds[4].text.strip()))

        testdata_results = {}
        for tr in html.select("#testdatas > tbody > tr"):
            if 'collapse' in tr.attrs['class']:
                continue
            tds = tr.select('td')
            id = int(tds[0].text.strip().removesuffix('(Expand)').strip())

            testdata_result_message = html.select_one(f"#challengeTestdataResultMessage{id - 1}").select_one('.card')
            message_type = MessageType.NONE
            message = ""
            if testdata_result_message.select_one('pre') is not None:
                message = testdata_result_message.select_one('pre').text.strip()
                message_type = MessageType.TEXT
            elif testdata_result_message.select_one('div') is not None:
                message_type = testdata_result_message.select_one('div').decode_contents()
                message_type = MessageType.HTML

            testdata_results[id] = TestdataResult(id, int(tds[1].attrs['class'][1].split("-")[1]), int(tds[2].text.strip()),
                    int(tds[3].text.strip()), message, message_type)


        return total_result, subtask_results, testdata_results



    async def upload_file(self, file, file_size: int, pack_token: str):
        md5 = hashlib.md5()
        remain = file_size
        while True:
            data = file.read(65536)
            if not data:
                break

            md5.update(data)

        ws = await websocket_connect("ws://localhost:5501/pack")
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

        html = self.get_html("manage/pro", session)
        self.assertIsNotNone(html.select_one(f'td[proid="{expected_pro_id}"]'))

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
            "http://localhost:5501/sign",
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
            "http://localhost:5501/sign",
            data={
                "reqtype": "signout",
            },
        )
        self.assertAPIReturnSuccess(res.text)
        self.assertNotIn("id", session.cookies.get_dict())

    async def wait_for_judge_finish(self, callback):
        ws = await websocket_connect("ws://localhost:5501/manage/judgecntws")

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


class BaseUrlSession(requests.Session):
    def request(self, method: str | bytes, url: str | bytes, *args, **kwargs):
        if "full_url" in kwargs:
            url = kwargs.pop("full_url")
        else:
            url = f"http://localhost:5501/{url}"
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
