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

            try:
                await self.response_handle(ret)
            except Exception as e:
                import traceback
                traceback.print_exception(e)

    async def response_handle(self, ret: str):
        from services.chal import ChalService, ChalConst, TotalResult, SubtaskResult, TestdataResult, MessageType
        res: dict = json.loads(ret)

        chal_id = res['chal_id']
        task_type = res['task']

        if task_type == "execute":
            result = res["testdata_result"]
            result["time"] = result["time"] // 10 ** 6
            result["memory"] = result["memory"] // 1024
            await ChalService.inst.update_testdata_result(
                chal_id,
                TestdataResult(
                    result["id"],
                    ChalConst.STATE_JUDGE,
                    result["time"],
                    result["memory"],
                    result["message"],
                    result["message_type"],
                ),
            )

        elif task_type == "scoring":
            result = res["testdata_result"]
            result["time"] = result["time"] // 10 ** 6
            result["memory"] = result["memory"] // 1024
            await ChalService.inst.update_testdata_result(
                chal_id,
                TestdataResult(
                    result["id"],
                    result["status"],
                    result["time"],
                    result["memory"],
                    result["message"],
                    result["message_type"],
                ),
            )
            await self.rs.publish('chalstatesub', json.dumps({'chal_id': chal_id, **result}))

        elif task_type == "summary":
            result = res["result"]
            total_result = result["total_result"]
            message = ""
            if total_result["status"] in [ChalConst.STATE_CE, ChalConst.STATE_CLE]:
                message = total_result["ce_message"]
            elif total_result["status"] in [ChalConst.STATE_ERR, ChalConst.STATE_JE]:
                message = total_result["ie_message"]
            total_result["time"] = total_result["time"] // 10 ** 6
            total_result["memory"] = total_result["memory"] // 1024

            await ChalService.inst.update_total_result(
                chal_id,
                TotalResult(
                    total_result["status"],
                    total_result["time"],
                    total_result["memory"],
                    decimal.Decimal(total_result["score"]),
                    message,
                    total_result["message_type"],
                ),
            )

            for subtask_id, subtask_result in result["subtask_results"].items():
                subtask_result["time"] = subtask_result["time"] // 10 ** 6
                subtask_result["memory"] = subtask_result["memory"] // 1024
                await ChalService.inst.update_subtask_result(
                    chal_id,
                    SubtaskResult(
                        int(subtask_id),
                        subtask_result["status"],
                        subtask_result["time"],
                        subtask_result["memory"],
                        decimal.Decimal(subtask_result["score"]),
                    ),
                )

            for testdata_result in result["testdata_results"].values():
                testdata_result["time"] = testdata_result["time"] // 10 ** 6
                testdata_result["memory"] = testdata_result["memory"] // 1024
                await ChalService.inst.update_testdata_result(
                    chal_id,
                    TestdataResult(
                        testdata_result["id"],
                        testdata_result["status"],
                        testdata_result["time"],
                        testdata_result["memory"],
                        testdata_result["message"],
                        MessageType(testdata_result["message_type"]),
                    ),
                )

            self.running_chal_cnt -= 1
            await self.rs.publish(
                'judgechalcnt_sub',
                json.dumps(
                    {
                        "judge_id": self.judge_id,
                        "chal_cnt": self.running_chal_cnt,
                    }
                ),
            )
            await self.rs.publish('challiststatesub', chal_id)
            await self.rs.publish('chalstatesub', json.dumps({'chal_id': chal_id, **result}))

            pro_id = self.chal_map[chal_id]['pro_id']
            contest_id = self.chal_map[chal_id]['contest_id']
            if contest_id != 0:
                await self.rs.publish('contestnewchalsub', contest_id)
                await self.rs.hdel(f'contest_{contest_id}_scores', str(pro_id))

            # NOTE: Recalculate problem rate
            await self.rs.hdel('pro_rate', f"pro_id_{pro_id}_contest_id_{contest_id}")
            await self.rs.hdel('pro_topcoder', str(pro_id))
            self.chal_map.pop(res['chal_id'])


    async def disconnect_server(self):
        if not self.status:
            return ('Ejudge', 'Judge already disconnected')

        try:
            self.status = False
            self.running_chal_cnt = 0
            self.ws.close()
            self.main_task.cancel()
            self.main_task = None
        except:
            return ('Ejudge', 'Disconnect judge failed')

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

    async def connect_server(self, idx):
        if idx < 0 or idx >= len(self.servers):
            return ('Eparam', 'Invalid judge index')

        if not self.servers[idx].status:
            await self.servers[idx].start()

            if not self.servers[idx].status:
                return ('Ejudge', 'Connect judge failed')

        await self.queue.put([0, idx])
        return ('S', '')

    async def disconnect_server(self, idx):
        if idx < 0 or idx >= len(self.servers):
            return ('Eparam', 'Invalid judge index')

        if err := await self.servers[idx].disconnect_server():
            return err

        return ('S', '')

    async def disconnect_all_server(self) -> None:
        for server in self.servers:
            await self.queue.get()
            await server.disconnect_server()

    def get_server_status(self, idx):
        if idx < 0 or idx >= len(self.servers):
            return ('Eparam', 'Invalid judge index')

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
