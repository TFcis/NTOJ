import json
import os
import uuid

from handlers.base import WebSocketHandler


class PackHandler(WebSocketHandler):
    STATE_HDR = 0
    STATE_DTAT = 1
    CHUNK_MAX = 65536

    def check_origin(self, origin: str) -> bool:
        # TODO: secure
        return True

    async def open(self):
        self.state = PackHandler.STATE_HDR
        self.output = None
        self.remain = 0

    async def on_message(self, msg):
        if self.state == PackHandler.STATE_DTAT:
            size = len(msg)
            if size > PackHandler.CHUNK_MAX or size > self.remain:
                self.write_message('Echunk')
                self.output.close()
                self.output = None
                return

            self.output.write(msg)
            self.remain -= size

            if self.remain == 0:
                self.output.close()
                self.output = None

            self.write_message('S')

        elif self.state == PackHandler.STATE_HDR:
            hdr = json.loads(msg)

            self.pack_token = str(uuid.UUID(hdr['pack_token']))
            self.remain = hdr['pack_size']
            self.output = open(f'tmp/{self.pack_token}', 'wb')
            self.state = PackHandler.STATE_DTAT

            self.write_message('S')

    def on_close(self) -> None:
        if self.output is not None:
            self.output.close()

        if self.remain > 0:
            os.remove(f'tmp/{self.pack_token}')
