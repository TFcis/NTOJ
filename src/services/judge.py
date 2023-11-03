import json
import asyncio
import smtplib
from queue import PriorityQueue
from email.header import Header
from email.mime.text import MIMEText
from typing import List, Union, Literal, Dict

from tornado.websocket import websocket_connect

import config
from services.log import LogService


class JudgeServerService:
    def __init__(self, rs, server_name, server_url) -> None:
        self.rs = rs
        self.server_name = server_name
        self.server_url = server_url
        self.running_chal_cnt = 0
        self.status = True
        self.ws = None

        self.main_task = None

    async def start(self):
        self.main_task = asyncio.create_task(self.connect_server())

    async def connect_server(self):
        from services.chal import ChalService

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
                # 這東西實際上就是個心跳包啊啊啊
                await self.offline_notice()
                self.status = False
                self.running_chal_cnt = 0
                break

            res = json.loads(ret)
            if res['results'] is not None:
                for test_idx, result in enumerate(res['results']):
                    # INFO: CE會回傳 result['verdict']

                    err, ret = await ChalService.inst.update_test(
                        res['chal_id'],
                        test_idx,
                        result['status'],
                        int(result['time'] / 10 ** 6),  # ns to ms
                        result['memory'],
                        result['verdict'])

                await self.rs.publish('chalstatesub', res['chal_id'])
                self.running_chal_cnt -= 1

    async def disconnect_server(self) -> Union[str, None]:
        if not self.status:
            return 'Ejudge'

        try:
            self.status = False
            self.ws.close()
            self.main_task.cancel()
            self.main_task = None
        except:
            return 'Ejudge'

        return None

    async def get_server_status(self):
        return (None, {
            'name': self.server_name,
            'status': self.status,
            'running_chal_cnt': self.running_chal_cnt
        })

    async def send(self, data):
        if self.status:
            self.running_chal_cnt += 1
            await self.ws.write_message(data)

    async def offline_notice(self):
        # log
        await LogService.inst.add_log(f"Judge {self.server_name} offline", "judge.offline")
        return

        # send email notify

        # setup smtp
        smtp = smtplib.SMTP()
        smtp.connect(config.SMTP_SERVER, config.SMTP_SERVER_PORT)
        smtp.starttls()
        smtp.login(config.SENDER_EMAIL, config.SENDER_APPLICATION_PASSWORD)

        mail_title = "TOJ Judge Offline"
        mail_body = f'''
            您好，管理員
            系統偵測到Judge {self.server_name}意外離線
            請您檢查該Judge Server狀態
        '''
        sender_email = config.SENDER_EMAIL

        message = MIMEText(mail_body, 'plain', 'utf-8')
        message['From'] = sender_email
        message['Subject'] = Header(mail_title, 'utf-8')

        for receiver in config.RECEIVER_LIST:
            message['To'] = receiver
            smtp.sendmail(sender_email, receiver, message.as_string())

        smtp.quit()


class JudgeServerClusterService:
    def __init__(self, rs, server_urls: List[Dict]) -> None:
        JudgeServerClusterService.inst = self
        self.queue = PriorityQueue()
        self.rs = rs
        self.servers: List[JudgeServerService] = []
        self.idx = 0

        for server in server_urls:
            url = server.get('url')
            name = server.get('name')
            if name is None:
                name = ''

            self.servers.append(JudgeServerService(self.rs, name, url))

    async def start(self) -> None:
        for idx, judge_server in enumerate(self.servers):
            self.queue.put([0, idx])
            await judge_server.start()

    async def connect_server(self, idx) -> Literal['Eparam', 'Ejudge', 'S']:
        if idx < 0 or idx >= self.servers.__len__():
            return 'Eparam'

        if self.servers[idx].status:
            pass

        else:
            await self.servers[idx].start()

            if not self.servers[idx].status:
                return 'Ejudge'

        self.queue.put([0, idx])
        return 'S'

    async def disconnect_server(self, idx) -> Literal['Eparam', 'Ejudge', 'S']:
        if idx < 0 or idx >= self.servers.__len__():
            return 'Eparam'

        err = await self.servers[idx].disconnect_server()
        if err is not None:
            return 'Ejudge'

        return 'S'

    async def disconnect_all_server(self) -> None:
        for server in self.servers:
            self.queue.get()
            await server.disconnect_server()

    async def get_server_status(self, idx):
        if idx < 0 or idx >= self.servers.__len__():
            return 'Eparam'

        err, status = await self.servers[idx].get_server_status()
        return None, status

    async def get_servers_status(self) -> List[Dict]:
        status_list: List[Dict] = []
        for server in self.servers:
            err, status = await server.get_server_status()
            status_list.append(status)

        return status_list

    async def is_server_online(self) -> bool:
        for server in self.servers:
            err, status = await server.get_server_status()
            if status['status']:
                return True

        return False

    async def send(self, data, pri) -> None:
        # Priority impl
        while not self.queue.empty():
            cur_pri, idx = self.queue.get()
            if not self.servers[idx].status:
                continue

            await self.servers[idx].send(data)
            self.queue.put([cur_pri + pri, idx])
            return
