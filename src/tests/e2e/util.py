import hashlib
import asyncio
import datetime
import json
import os
import unittest

import requests
from bs4 import BeautifulSoup
from tornado.websocket import websocket_connect

from runtests import testing_loop, db


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

    def get_html(self, url, session):
        res = session.get(url)
        return BeautifulSoup(res.text, 'html.parser')

    def get_isoformat(self, time: datetime.datetime) -> str:
        return time.isoformat(timespec='milliseconds') + 'Z'

    def get_chal_state(self, chal_id: int, session):
        html = self.get_html(f'http://localhost:5501/chal/{chal_id}', session)
        all_states = []
        for tr in html.select('tr.states'):
            td = tr.select_one('td.state')
            # NOTE: <td class="state state-1"></td>
            state = int(td.attrs['class'][1].split('-')[1])
            all_states.append(state)

        return all_states

    async def upload_file(self, file, file_size: int, pack_token: str):
        sha1 = hashlib.sha1()
        remain = file_size
        while True:
            data = file.read(65536)
            if not data:
                break

            sha1.update(data)

        ws = await websocket_connect('ws://localhost:5501/pack')
        await ws.write_message(json.dumps({
            'pack_token': pack_token,
            'pack_size': file_size,
            'sha-1': sha1.hexdigest(),
        }))
        file.seek(0, 0)
        msg = await ws.read_message()
        self.assertEqual(msg, 'S')

        while remain != 0:
            size = min(remain, 65535)
            await ws.write_message(file.read(size), binary=True)
            remain -= size

            msg = await ws.read_message()
            self.assertNotEqual(msg, 'Echunk')
            self.assertNotEqual(msg, 'Ehash')
            if msg is None:
                break
        ws.close()

    async def upload_problem(self, file, name, status, expected_pro_id, session):
        pack_token = self.get_upload_token(session)
        file_path = f'tests/static_file/{file}'
        file_size = os.path.getsize(file_path)
        with open(file_path, 'rb') as f:
            await self.upload_file(f, file_size, pack_token)

        res = session.post('http://localhost:5501/manage/pro/add', data={
            'reqtype': 'addpro',
            'name': name,
            'status': status,
            'pack_token': pack_token,
            'mode': 'upload',
        })

        self.assertEqual(res.text, str(expected_pro_id))

        html = self.get_html('http://localhost:5501/manage/pro', session)
        self.assertIsNotNone(html.select_one(f'td[proid="{expected_pro_id}"]'))

    def get_upload_token(self, session):
        res = session.post('http://localhost:5501/manage/pack', data={
            'reqtype': 'gettoken'
        })
        pack_token = json.loads(res.text)
        self.assertNotEqual(pack_token, '')
        return pack_token

    def submit_problem(self, pro_id: int, code: str, comp_type: str, session) -> int:
        res = session.post('http://localhost:5501/submit', data={
            'reqtype': 'submit',
            'pro_id': pro_id,
            'code': code,
            'comp_type': comp_type,
        })
        self.assertNotEqual(res.text[0], 'E')
        chal_id = json.loads(res.text)
        return chal_id

    def signup(self, name: str, mail: str, pw: str):
        session = requests.Session()
        res = session.post('http://localhost:5501/sign', data={
            'reqtype': 'signup',
            'name': name,
            'mail': mail,
            'pw': pw,
        })
        self.assertEqual(res.text, 'S')
        self.assertIn('id', session.cookies.get_dict())

        res = session.post('http://localhost:5501/sign', data={
            'reqtype': 'signout',
        })
        self.assertEqual(res.text, 'S')
        self.assertNotIn('id', session.cookies.get_dict())

    async def wait_for_judge_finish(self, callback):
        ws = await websocket_connect('ws://localhost:5501/manage/judgecntws')

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


class AccountContext:
    def __init__(self, mail: str, pw: str):
        self.mail = mail
        self.pw = pw
        self.session = requests.Session()

    def __enter__(self):
        res = self.session.post('http://localhost:5501/sign', data={
            'reqtype': 'signin',
            'mail': self.mail,
            'pw': self.pw,
        })
        for cookie in self.session.cookies:
            cookie.path = '/'

        assert res.text == 'S'
        assert 'id' in self.session.cookies.get_dict()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = self.session.post('http://localhost:5501/sign', data={
            'reqtype': 'signout',
        })
        assert res.text == 'S'
        assert 'id' not in self.session.cookies.get_dict()


PROBLEMS = {}
