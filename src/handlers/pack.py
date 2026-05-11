import hashlib
import json
import os
import uuid
import logging
from typing import IO

from services.user import UserService
from handlers.base import WebSocketHandler

logger = logging.getLogger("tornado.application")

class PackHandler(WebSocketHandler):
    STATE_HDR = 0
    STATE_DTAT = 1
    CHUNK_MAX = 65536

    def check_origin(self, _: str) -> bool:
        # TODO: secure
        return True

    async def open(self):
        acct_id_cookie = self.get_secure_cookie("id")
        if not acct_id_cookie:
            return self.close()

        try:
            acct_id = int(acct_id_cookie)
        except ValueError:
            return self.close()

        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            return self.close()
        assert acct

        if not acct.is_kernel():
            return self.close()

        self.state = PackHandler.STATE_HDR
        self.output: IO | None = None
        self.remain: int = 0
        self.md5 = hashlib.md5()
        self.received_md5 = ''

    async def on_message(self, msg):
        if self.state == PackHandler.STATE_DTAT:
            assert self.output is not None
            size = len(msg)
            if size > PackHandler.CHUNK_MAX or size > self.remain:
                self.output.close()
                self.output = None
                try:
                    os.remove(f'tmp/{self.pack_token}')
                except OSError:
                    logger.warning(f"Failed to remove temporary file tmp/{self.pack_token}", exc_info=True)

                self.write_message('Echunk')
                return

            self.output.write(msg)
            self.remain -= size
            self.md5.update(msg)

            if self.remain == 0:
                self.output.close()
                self.output = None

                if self.md5.hexdigest().lower() != self.received_md5.lower():
                    try:
                        os.remove(f'tmp/{self.pack_token}')
                    except OSError:
                        logger.warning(f"Failed to remove temporary file tmp/{self.pack_token}", exc_info=True)

                    self.write_message('Ehash')
                    return

            self.write_message('S')

        elif self.state == PackHandler.STATE_HDR:
            try:
                hdr = json.loads(msg)
                self.pack_token = str(uuid.UUID(hdr['pack_token']))
                if (await self.rs.exists(f'PACK_TOKEN@{self.pack_token}')) != 1:
                    self.write_message('Etoken')
                    return self.close()

                self.remain = hdr['pack_size']
                self.received_md5 = hdr['md5']
            except (ValueError, KeyError, json.JSONDecodeError):
                self.write_message('Eparam')
                return self.close()

            try:
                self.output = open(f'tmp/{self.pack_token}', 'wb')
            except OSError:
                logger.error(f"Failed to open file tmp/{self.pack_token} for writing", exc_info=True)
                self.write_message('Eio')
                return self.close()

            self.state = PackHandler.STATE_DTAT
            self.write_message('S')

    def on_close(self) -> None:
        if self.output is not None:
            self.output.close()

        if self.remain > 0:
            try:
                os.remove(f'tmp/{self.pack_token}')
            except OSError:
                logger.warning(f"Failed to remove temporary file tmp/{self.pack_token}", exc_info=True)
