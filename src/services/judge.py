import asyncio
import json
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from typing import List, Union, Literal, Dict

from tornado.websocket import websocket_connect

import config
from services.log import LogService


class JudgeServerSerice:
    def __init__(self, rs, server_name, server_url) -> None:
        self.rs = rs
        self.server_name = server_name
        self.server_url = server_url
        self.running_chal_cnt = 0
        self.status = False
        self.ws = None
        self.ws2 = None

        self.heartbeat_task = None
        self.main_task = None

    async def start(self):
        self.heartbeat_task = asyncio.create_task(self.heartbeat())
        await asyncio.sleep(3)

        if self.status:
            self.main_task = asyncio.create_task(self.connect_server())

    async def connect_server(self):
        from services.chal import ChalService

        if not self.status:
            return 'Ejudge'

        try:
            self.status = False
            self.ws = await websocket_connect(self.server_url)
        except:
            return 'Ejudge'

        self.status = True

        while self.status:
            ret = await self.ws.read_message()
            if ret is None:
                break

            res = json.loads(ret)
            if res['result'] is not None:
                for result in res['result']:
                    # INFO: CE會回傳 result['verdict']

                    err, ret = await ChalService.inst.update_test(
                        res['chal_id'],
                        result['test_idx'],
                        result['state'],
                        result['runtime'],
                        result['peakmem'],
                        result['verdict'][0])

                await asyncio.sleep(0.5)
                await self.rs.publish('chalstatesub', res['chal_id'])
                self.running_chal_cnt -= 1

    async def disconnect_server(self) -> Union[str, None]:
        if not self.status:
            return 'Ejudge'

        try:
            self.status = False
            # BUG: 這樣寫應該會出錯
            self.ws.close()
            self.ws2.close()
            self.main_task.cancel()
            self.heartbeat_task.cancel()
        except:
            return 'Ejudge'

        await asyncio.sleep(3)
        return None

    async def get_server_status(self):
        return (None, {
            'name': self.server_name,
            'status': self.status,
            'running_chal_cnt': self.running_chal_cnt
        })

    async def send(self, data):
        self.running_chal_cnt += 1
        await self.ws.write_message(data)

    async def heartbeat(self):
        # INFO: DokiDoki
        self.status = True

        try:
            self.ws2 = await websocket_connect(self.server_url)
        except:
            self.status = False
            return

        while self.status:
            try:
                self.ws2.ping()
            except:
                self.status = False
                await self.offline_notice()
                return
            await asyncio.sleep(1)

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
            通知：偵測到Judge {self.server_name}意外離線
            請檢查Judge狀態
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
        self.rs = rs
        self.servers: List[JudgeServerSerice] = []
        self.idx = 0

        for server in server_urls:
            url = server.get('url')
            name = server.get('name')
            if name is None:
                name = ''

            self.servers.append(JudgeServerSerice(self.rs, name, url))

    async def start(self) -> None:
        for judge_server in self.servers:
            await judge_server.start()

    async def connect_server(self, idx) -> Literal['Eparam', 'Ejudge', 'S']:
        if idx < 0 or idx >= self.servers.__len__():
            return 'Eparam'

        if self.servers[idx].status:
            pass

        else:
            asyncio.create_task(self.servers[idx].start())
            await asyncio.sleep(3)

            if not self.servers[idx].status:
                return 'Ejudge'

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
            await server.disconnect_server()

        await asyncio.sleep(3)

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

    async def send(self, data) -> None:
        # simple round-robin impl

        for i in range(self.idx + 1, len(self.servers)):
            if self.servers[i].ws is None:
                continue

            _, status = await self.servers[i].get_server_status()
            if not status['status']:
                continue

            await self.servers[i].send(data)
            self.idx = i
            return

        for i in range(0, len(self.servers)):
            if self.servers[i].ws is None:
                continue

            _, status = await self.servers[i].get_server_status()
            if not status['status']:
                continue

            await self.servers[i].send(data)
            self.idx = i
            return
