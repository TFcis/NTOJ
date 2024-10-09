import asyncio
import os
import uuid


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

        ret = await self.rs.get(f'PACK_TOKEN@{pack_token}')
        if ret is None:
            return 'Enoext', None

        await self.rs.delete(f'PACK_TOKEN@{pack_token}')

        inf = open(f'tmp/{pack_token}', 'rb')
        outf = open(dst, 'wb')
        while True:
            data = inf.read(65536)
            if len(data) == 0:
                break

            outf.write(data)

        inf.close()
        outf.close()

        os.remove(f'tmp/{pack_token}')

    def clear(self, pack_token):
        if os.path.exists(f'tmp/{pack_token}'):
            os.remove(f'tmp/{pack_token}')

    async def _run_and_wait_process(self, program, *args):
        process = await asyncio.create_subprocess_exec(program, *args)
        returncode = await process.wait()

        return returncode

    async def unpack(self, pack_token, dst, clean=False):
        pack_token = str(uuid.UUID(pack_token))

        ret = await self.rs.get(f'PACK_TOKEN@{pack_token}')
        if ret is None:
            return 'Enoext', None

        await self.rs.delete(f'PACK_TOKEN@{pack_token}')

        if clean:
            if not os.path.exists(dst):
                os.makedirs(dst, 0o700)

            else:
                await self._run_and_wait_process('/bin/rm', '-Rf', dst)
                os.makedirs(dst, 0o700)

        # FIXME: Detect zip bomb
        returncode = await self._run_and_wait_process('/bin/tar', '-Jxf', f'tmp/{pack_token}', '-C', dst)
        if returncode != 0:
            return 'Eunk', None

        os.remove(f'tmp/{pack_token}')
        await self._run_and_wait_process('/bin/bash', 'newline.sh', f'{dst}/res/testdata')

        return None, None
