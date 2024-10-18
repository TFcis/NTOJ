import json
import decimal
import asyncio
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from typing import Dict, List, Literal, Union

from tornado.websocket import websocket_connect

import config
from services.log import LogService


class JudgeServerService:
    def __init__(self, rs, server_name: str, server_url: str, codes_path: str, problems_path: str, judge_id) -> None:
        self.rs = rs
        self.server_name = server_name
        self.server_url = server_url
        self.judge_id = judge_id
        self.codes_path = codes_path
        self.problems_path = problems_path
        self.status = True
        self.ws = None

        self.chal_map = {}
        self.running_chal_cnt = 0

        self.main_task = None

    async def start(self):
        self.main_task = asyncio.create_task(self.connect_server())

    async def connect_server(self):
        try:
            self.ws = await websocket_connect(self.server_url)
        except:
            self.status = False
            return

        self.status = True
        self.running_chal_cnt = 0
        while self.status:
            ret = await self.ws.read_message()
            if ret is None:
                await self.offline_notice()
                self.status = False
                self.running_chal_cnt = 0
                break

            await self.response_handle(ret)

    async def response_handle(self, ret):
        from services.chal import ChalService, ChalConst

        res = json.loads(ret)

        if res['results'] is not None:
            for test_idx, result in enumerate(res['results']):

                score = None
                is_cms_type = False
                if 'score_type' in result and result['score_type'] in ["CMS", "CF"]:
                    is_cms_type = result['score_type'] == "CMS"
                    if 'score' in result:
                        try:
                            score = decimal.Decimal(result['score'])
                        except decimal.DecimalException:
                            score = None
                            result['status'] = ChalConst.STATE_SJE

                _, ret = await ChalService.inst.update_test(
                    res['chal_id'],
                    test_idx,
                    result['status'],
                    int(result['time'] / 10 ** 6),  # ns to ms
                    result['memory'],
                    score,
                    result['verdict'],
                    rate_is_cms_type=is_cms_type,
                    refresh_db=False,
                )

            self.running_chal_cnt -= 1
            await ChalService.inst.update_challenge_state(res['chal_id'])

            await self.rs.publish('chalstatesub', res['chal_id'])
            await self.rs.publish('challiststatesub', res['chal_id'])
            await self.rs.publish(
                'judgechalcnt_sub',
                json.dumps(
                    {
                        "judge_id": self.judge_id,
                        "chal_cnt": self.running_chal_cnt,
                    }
                ),
            )

            pro_id = self.chal_map[res['chal_id']]['pro_id']
            contest_id = self.chal_map[res['chal_id']]['contest_id']
            if contest_id != 0:
                await self.rs.publish('contestnewchalsub', contest_id)
                await self.rs.hdel(f'contest_{contest_id}_scores', str(pro_id))

            # NOTE: Recalculate problem rate
            await self.rs.hdel('pro_rate', str(pro_id))
            self.chal_map.pop(res['chal_id'])

    async def disconnect_server(self) -> Union[str, None]:
        if not self.status:
            return 'Ejudge'

        try:
            self.status = False
            self.running_chal_cnt = 0
            self.ws.close()
            self.main_task.cancel()
            self.main_task = None
        except:
            return 'Ejudge'

        return None

    def get_server_status(self):
        return (
            None,
            {
                'name': self.server_name,
                'judge_id': self.judge_id,
                'status': self.status,
                'running_chal_cnt': self.running_chal_cnt,
            },
        )

    async def send(self, data):
        if self.status:
            self.running_chal_cnt += 1
            await self.rs.publish(
                'judgechalcnt_sub',
                json.dumps(
                    {
                        "judge_id": self.judge_id,
                        "chal_cnt": self.running_chal_cnt,
                    }
                ),
            )

            data['code_path'] = f"{self.codes_path}/{data['code_path']}"
            data['res_path'] = f"{self.problems_path}/{data['res_path']}"

            await self.ws.write_message(json.dumps(data))

    async def offline_notice(self):
        await LogService.inst.add_log(f"Judge {self.server_name} offline", "judge.offline")


class JudgeServerClusterService:
    def __init__(self, rs, server_urls: List[Dict]) -> None:
        JudgeServerClusterService.inst = self
        self.queue = asyncio.PriorityQueue()
        self.rs = rs
        self.servers: List[JudgeServerService] = []
        self.idx = 0

        for judge_id, server in enumerate(server_urls):
            url = server.get('url')
            name = server.get('name')
            codes_path = server.get('codes_path')
            problems_path = server.get('problems_path')

            # TODO: add log
            if url is None:
                continue

            if codes_path is None:
                continue

            if problems_path is None:
                continue

            if name is None:
                name = f'JudgeServer-{judge_id}'

            self.servers.append(JudgeServerService(self.rs, name, url, codes_path, problems_path, judge_id))

    async def start(self) -> None:
        for idx, judge_server in enumerate(self.servers):
            await self.queue.put([0, idx])
            await judge_server.start()

    async def connect_server(self, idx) -> Literal['Eparam', 'Ejudge', 'S']:
        if idx < 0 or idx >= len(self.servers):
            return 'Eparam'

        if not self.servers[idx].status:
            await self.servers[idx].start()

            if not self.servers[idx].status:
                return 'Ejudge'

        await self.queue.put([0, idx])
        return 'S'

    async def disconnect_server(self, idx) -> Literal['Eparam', 'Ejudge', 'S']:
        if idx < 0 or idx >= len(self.servers):
            return 'Eparam'

        err = await self.servers[idx].disconnect_server()
        if err is not None:
            return 'Ejudge'

        return 'S'

    async def disconnect_all_server(self) -> None:
        for server in self.servers:
            await self.queue.get()
            await server.disconnect_server()

    def get_server_status(self, idx):
        if idx < 0 or idx >= len(self.servers):
            return 'Eparam'

        _, status = self.servers[idx].get_server_status()
        return None, status

    def get_servers_status(self) -> List[Dict]:
        status_list: List[Dict] = []
        for server in self.servers:
            _, status = server.get_server_status()
            status_list.append(status)

        return status_list

    def is_server_online(self) -> bool:
        for server in self.servers:
            _, status = server.get_server_status()
            if status['status']:
                return True

        return False

    async def send(self, data, pro_id, contest_id) -> None:
        # priority impl

        if not self.is_server_online():
            return

        while True:
            running_cnt, idx = await self.queue.get()
            _, status = self.get_server_status(idx)
            if not status['status']:
                continue

            judge_id = status['judge_id']

            if data['chal_id'] in self.servers[judge_id].chal_map:
                await self.queue.put([running_cnt, idx])
                break

            await self.servers[judge_id].send(data)
            _, status = self.get_server_status(idx)

            await self.queue.put([status['running_chal_cnt'], judge_id])
            self.servers[idx].chal_map[data['chal_id']] = {"pro_id": pro_id, "contest_id": contest_id}

            break
