from typing import List, Union, Tuple, Literal, Dict
import json
import asyncio

from tornado.websocket import websocket_connect

from req import Service

class JudgeServerSerice:
    def __init__(self, rs, server_name, server_url) -> None:
        self.rs = rs
        self.server_name = server_name
        self.server_url = server_url
        self.running_chal_cnt = 0
        self.status = False
        self.ws = None
        self.ws2 = None

    async def start(self):
        self.main_task = asyncio.create_task(self.connect_server())
        self.heartbeat_task = asyncio.create_task(self.heartbeat())

    async def connect_server(self):
        try:
            self.status = False
            self.ws = await websocket_connect(self.server_url)
        except:
            return 'Ejudge'

        self.status = True

        while self.status:
            ret = await self.ws.read_message()
            if ret == None:
                break

            res = json.loads(ret)
            if res['result'] != None:
                for result in res['result']:
                    #INFO: CE會回傳 result['verdict']

                    err, ret = await Service.Chal.update_test(
                        res['chal_id'],
                        result['test_idx'],
                        result['state'],
                        result['runtime'],
                        result['peakmem'],
                        ret)

                await asyncio.sleep(0.5)
                await self.rs.publish('chalstatesub', res['chal_id'])
                self.running_chal_cnt -= 1


    async def disconnect_server(self) -> Union[str, None]:
        if self.status == False:
            return 'Ejudge'

        try:
            self.status = False
            #BUG: 這樣寫應該會出錯
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
        #INFO: DokiDoki
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
                break
            self.status = True
            await asyncio.sleep(1)

class JudgeServerClusterService:
    def __init__(self, rs, server_urls: List[Dict]) -> None:
        JudgeServerClusterService.inst = self
        self.rs = rs
        self.servers: List[JudgeServerSerice] = []
        self.idx = 0

        for server in server_urls:
            url  = server.get('url')
            name = server.get('name')
            if name == None:
                name = ''

            self.servers.append(JudgeServerSerice(self.rs, name, url))

    async def start(self) -> None:
        for judge_server in self.servers:
            await judge_server.start()

    async def connect_server(self, idx) -> Literal['Eparam', 'Ejudge', 'S']:
        if idx < 0 or idx >= self.servers.__len__():
            return 'Eparam'

        if self.servers[idx].status == True:
            return 'S'

        else:
            asyncio.create_task(self.servers[idx].start())
            await asyncio.sleep(1)

            if self.servers[idx].status == False:
                return 'Ejudge'

            return 'S'

    async def disconnect_server(self, idx) -> Literal['Eparam', 'Ejudge', 'S']:
        if idx < 0 or idx >= self.servers.__len__():
            return 'Eparam'

        err = await self.servers[idx].disconnect_server()
        if err != None:
            return 'Ejudge'

        return 'S'

    async def disconnect_all_server(self) -> None:
        for server in self.servers:
            await server.disconnect_server()

        await asyncio.sleep(3)

    async def get_servers_status(self) -> List[Dict]:
        status_list: List[Dict] = []
        for server in self.servers:
            err, status = await server.get_server_status()
            status_list.append(status)

        return status_list

    async def send(self, data) -> None:
        servers_len = self.servers.__len__()

        while self.idx < servers_len:
            self.idx += 1
            self.idx %= servers_len
            err, status = await self.servers[self.idx].get_server_status()
            if status['status'] == False:
                self.idx += 1
                self.idx %= servers_len
                continue

            await self.servers[self.idx].send(data)
            break
