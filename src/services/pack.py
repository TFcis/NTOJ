import asyncio
import os
import uuid
import logging

logger = logging.getLogger("tornado.application")

class PackService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        PackService.inst = self

    async def gen_token(self):
        pack_token = str(uuid.uuid1())
        await self.rs.set(f'PACK_TOKEN@{pack_token}', 0)

        return None, pack_token

    async def direct_copy(self, pack_token, dst):
        pack_token = str(uuid.UUID(pack_token))

        if (await self.rs.exists(f'PACK_TOKEN@{pack_token}')) != 1:
            return ('Enoext', 'Pack token not found'), None

        try:
            with open(f'tmp/{pack_token}', 'rb') as inf, open(dst, 'wb') as outf:
                while True:
                    data = inf.read(65536)
                    if len(data) == 0:
                        break

                    outf.write(data)
            os.remove(f'tmp/{pack_token}')
            await self.rs.delete(f'PACK_TOKEN@{pack_token}')
            return None, None
        except OSError as e:
            logger.error(f"Error copying file for pack token {pack_token}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

    async def clear(self, pack_token):
        if (await self.rs.exists(f'PACK_TOKEN@{pack_token}')) != 1:
            return ('Enoext', 'Pack token not found'), None

        try:
            os.remove(f'tmp/{pack_token}')
            await self.rs.delete(f'PACK_TOKEN@{pack_token}')
            return None, None
        except OSError as e:
            logger.error(f"Error clearing file for pack token {pack_token}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

    async def _run_and_wait_process(self, program, *args):
        process = await asyncio.create_subprocess_exec(program, *args)
        returncode = await process.wait()

        return returncode

    async def unpack(self, pack_token, dst, clean=False):
        pack_token = str(uuid.UUID(pack_token))

        if (await self.rs.delete(f'PACK_TOKEN@{pack_token}') != 1):
            return ('Enoext', 'Pack token not found'), None

        if clean:
            if not os.path.exists(dst):
                os.makedirs(dst, 0o700)

            else:
                await self._run_and_wait_process('/bin/rm', '-Rf', dst)
                os.makedirs(dst, 0o700)

        # FIXME: Detect zip bomb
        returncode = await self._run_and_wait_process('/bin/tar', '-Jxf', f'tmp/{pack_token}', '-C', dst)
        if returncode != 0:
            return ('Eunk', 'Unknown error (tar)'), None

        try:
            os.remove(f'tmp/{pack_token}')
        except OSError as e:
            logger.error(f"Error removing tar file for pack token {pack_token}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        await self._run_and_wait_process('/bin/sh', 'newline.sh', f'{dst}/res/testdata')
        def check_file_illegal(path):
            if os.path.islink(path):
                return ('Eparam', f'{path} should not be a link. So suspicious. You maybe a hacker.')

            if not os.path.isfile(path):
                return ('Eparam', f'What the heck about {path}. What file are you uploading? So suspicious.')

            return None

        err = None
        def dfs(path):
            nonlocal err
            if err:
                return
            for name in os.listdir(path):
                if os.path.isdir(os.path.join(path, name)):
                    dfs(os.path.join(path, name))
                else:
                    err = check_file_illegal(os.path.join(path, name))
        dfs(dst)


        return err, None
