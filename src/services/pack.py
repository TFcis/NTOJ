import os
import uuid

import tornado.process



class PackService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        PackService.inst = self

    async def gen_token(self):
        pack_token = str(uuid.uuid1())
        await self.rs.set(f'PACK_TOKEN@{pack_token}', 0)

        return (None, pack_token)

    async def direct_copy(self, pack_token, dst):
        pack_token = str(uuid.UUID(pack_token))

        ret = await self.rs.get(f'PACK_TOKEN@{pack_token}')
        if ret == None:
            return ('Enoext', None)

        await self.rs.delete(f'PACK_TOKEN@{pack_token}')

        inf = open(f'templ/tmp/{pack_token}', 'rb')
        outf = open(dst, 'wb')
        while True:
            data = inf.read(65536)
            if len(data) == 0:
                break

            outf.write(data)

        inf.close()
        outf.close()

        os.remove(f'templ/tmp/{pack_token}')

    async def unpack(self, pack_token, dst, clean=False):
        def _unpack():
            def __rm_cb(code):
                os.makedirs(dst, 0o700)
                __tar()

            def __tar():
                sub = tornado.process.Subprocess(
                        ['/bin/tar', '-Jxf', f'tmp/{pack_token}', '-C', dst])
                sub.set_exit_callback(__tar_cb)

            def __tar_cb(code):
                if code != 0:
                    return ('Eunk', None)

                #os.remove('tmp/%s'%pack_token)

                sub = tornado.process.Subprocess(
                        ['/bin/bash', 'newline.sh', f'{dst}/res/testdata'])

            if clean == False:
                __tar()

            else:
                sub = tornado.process.Subprocess(
                        ['/bin/rm', '-Rf', dst])
                sub.set_exit_callback(__rm_cb)

        pack_token = str(uuid.UUID(pack_token))

        ret = await self.rs.get(f'PACK_TOKEN@{pack_token}')
        if ret == None:
            return ('Enoext', None)

        await self.rs.delete(f'PACK_TOKEN@{pack_token}')

        ret = _unpack()
        return ret

