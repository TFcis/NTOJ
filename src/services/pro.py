import re
import os
import json
import datetime
import asyncio
from collections import OrderedDict

from msgpack import packb, unpackb

import config
from services.pack import PackService
from services.user import UserConst


class ProConst:
    NAME_MIN = 1
    NAME_MAX = 64
    CODE_MAX = 16384
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

class ProService:
    NAME_MIN = 1
    NAME_MAX = 64
    CODE_MAX = 16384
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

    PACKTYPE_FULL = 1
    PACKTYPE_CONTHTML = 2
    PACKTYPE_CONTPDF = 3

    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ProService.inst = self

    async def get_pclass_list(self, pro_clas):
        if (clas := (await self.rs.get(f'{pro_clas}_pro_list'))) == None:
            return ('Enoext', None)

        return (None, unpackb(clas))

    async def get_class_list_old(self):
        if (clas_list := (await self.rs.get('pro_class_list'))) == None:
            await self.rs.set('pro_class_list', packb([]))
            return []

        return unpackb(clas_list)


    async def get_class_list(self):
        if (clas_list := (await self.rs.get('pro_class_list2'))) == None:
            res = []
            for row in await self.get_class_list_old():
                res.append({
                    'key'  : row,
                    'name' : row,
                })
            await self.rs.set('pro_class_list2', packb(res))
            return res

        return unpackb(clas_list)

    async def get_pclass_name_by_key(self, pclas_key):
        pclas_key = str(pclas_key)
        clas_list = await self.get_class_list()
        for row in clas_list:
            if row['key'] == pclas_key:
                return row['name']

        return None

    async def get_pclass_key_by_name(self, pclas_name):
        pclas_name = str(pclas_name)
        clas_list = await self.get_class_list()
        for row in clas_list:
            if row['name'] == pclas_name:
                return row['key']

        return None


    async def add_pclass(self, pclas_key, pclas_name, p_list):
        if (pclas_key := str(pclas_key)) == '':
            return 'EbadKey'

        clas_list = await self.get_class_list()
        clas_list_keys = [row['key'] for row in clas_list]
        if pclas_key in clas_list_keys:
            return 'Eexist'

        clas_list.append({
            'key'  : pclas_key,
            'name' : pclas_name
        })
        await self.rs.set('pro_class_list2', packb(clas_list))
        await self.rs.set(f'{pclas_key}_pro_list', packb(p_list))
        return None

    async def remove_pclass(self, pclas_key):
        clas_list = await self.get_class_list()
        clas_list_keys = [row['key'] for row in clas_list]

        try:
            clas_index = clas_list_keys.index(str(pclas_key))

        except ValueError:
            return 'Eexist'

        clas_list.pop(clas_index)
        await self.rs.set('pro_class_list2', packb(clas_list))
        await self.rs.delete(f'{pclas_key}_pro_list')
        return None


    async def edit_pclass(self, pclas_key, new_pclas_key, pclas_name, p_list):
        if (new_pclas_key := str(new_pclas_key)) == '':
            return 'EbadKey'

        clas_list = await self.get_class_list()
        clas_list_keys = [row['key'] for row in clas_list]

        try:
            pclas_key = str(pclas_key)
            clas_index = clas_list_keys.index(pclas_key)

        except ValueError:
            return 'Eexist'

        clas_list[clas_index]['key'] = new_pclas_key
        clas_list[clas_index]['name'] = str(pclas_name)
        await self.rs.set('pro_class_list2', packb(clas_list))

        if pclas_key != new_pclas_key:
            await self.rs.delete(f'{pclas_key}_pro_list')

        await self.rs.set(f'{new_pclas_key}_pro_list', packb(p_list))
        return None

    async def get_pro(self, pro_id, acct=None, special=None):
        pro_id = int(pro_id)
        max_status = await self.get_acct_limit(acct, special)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "name", "status", "class", "expire", "tags"
                    FROM "problem" WHERE "pro_id" = $1 AND "status" <= $2;
                ''',
                pro_id, max_status
            )
            if result.__len__() != 1:
                return ('Enoext', None)
            result = result[0]

            name, status, clas, expire, tags = result['name'], result['status'], result['class'][0], result['expire'], result['tags']
            if expire == datetime.datetime.max:
                expire = None

            result = await con.fetch(
                '''
                    SELECT "test_idx", "compile_type", "score_type",
                    "check_type", "timelimit", "memlimit", "weight", "metadata", "chalmeta"
                    FROM "test_config" WHERE "pro_id" = $1 ORDER BY "test_idx" ASC;
                ''',
                pro_id
            )
            if result.__len__() == 0:
                return ('Econf', None)

        testm_conf = OrderedDict()
        for (test_idx, comp_type, score_type, check_type, timelimit, memlimit, weight, metadata, chalmeta) in result:
            testm_conf[test_idx] = {
                'comp_type'  : comp_type,
                'score_type' : score_type,
                'check_type' : check_type,
                'timelimit'  : timelimit,
                'memlimit'   : memlimit,
                'weight'     : weight,
                'chalmeta'   : json.loads(chalmeta),
                'metadata'   : json.loads(metadata),
            }

        return (None, {
            'pro_id'     : pro_id,
            'name'       : name,
            'status'     : status,
            'expire'     : expire,
            'class'      : clas,
            'testm_conf' : testm_conf,
            'tags'       : tags,
        })

    async def list_pro(self, acct=None, state=False, clas=None, reload=False):
        def _mp_encoder(obj):
            if isinstance(obj, datetime.datetime):
                return obj.astimezone(datetime.timezone.utc).timestamp()

            return obj

        if acct == None:
            max_status = ProService.STATUS_ONLINE
            isguest = True
            isadmin = False

        else:
            max_status = await self.get_acct_limit(acct)
            isguest = (acct['acct_id'] == UserConst.ACCTID_GUEST)
            isadmin = (acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)

        if clas == None:
            clas = [1, 2]

        else:
            clas = [clas]


        statemap = {}

        #TODO: decrease sql search times
        if state == True and isguest == False:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "problem"."pro_id",
                        MIN("challenge_state"."state") AS "state"
                        FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id" AND "challenge"."acct_id" = $1
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = "problem"."pro_id"
                        WHERE "problem"."status" <= $2 AND "problem"."class" && $3
                        GROUP BY "problem"."pro_id"
                        ORDER BY "pro_id" ASC;
                    ''',
                    int(acct['acct_id']), max_status, clas
                )

            for pro_id, state in result:
                statemap[pro_id] = state

        field = f'{max_status}|{clas}'
        if (prolist := (await self.rs.hget('prolist', field))) != None and reload == False:
            prolist = unpackb(prolist)

            for pro in prolist:
                if (expire := pro['expire']) != None:
                    expire = datetime.datetime.fromtimestamp(expire)
                    expire = expire.replace(tzinfo=datetime.timezone(
                        datetime.timedelta(hours=8)
                    ))

                pro['expire'] = expire

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "problem"."pro_id", "problem"."name", "problem"."status", "problem"."expire",
                        "problem"."class", "problem"."tags"
                        FROM "problem"
                        WHERE "problem"."status" <= $1 AND "problem"."class" && $2
                        ORDER BY "pro_id" ASC;
                    ''',
                    max_status, clas
                )

            prolist = []
            for pro_id, name, status, expire, clas, tags in result:
                if expire == datetime.datetime.max:
                    expire = None

                prolist.append({
                    'pro_id' : pro_id,
                    'name'   : name,
                    'status' : status,
                    'expire' : expire,
                    'class'  : clas[0],
                    'tags'   : tags,
                })

            await self.rs.hset('prolist', field, packb(prolist, default=_mp_encoder))

        now = datetime.datetime.utcnow()
        now = now.replace(tzinfo=datetime.timezone.utc)

        for pro in prolist:
            pro_id = pro['pro_id']
            pro['state'] = statemap.get(pro_id)

            if isadmin:
                pass

            elif isguest or pro['tags'] == None or pro['tags'] == '':
                pro['tags'] = ''

            else:
                if pro['state'] == None:
                    pro['tags'] = ''

            if pro['expire'] == None:
                pro['outdate'] = False

            else:
                delta = (pro['expire'] - now).total_seconds()
                if delta < 0:
                    pro['outdate'] = True
                else:
                    pro['outdate'] = False

        return (None, prolist)

    async def add_pro(self, name, status, clas, expire, pack_token):
        name_len = len(name)
        if name_len < ProService.NAME_MIN:
            return ('Enamemin', None)
        if name_len > ProService.NAME_MAX:
            return ('Enamemax', None)
        del name_len
        if (status < ProService.STATUS_ONLINE or status > ProService.STATUS_OFFLINE):
            return ('Eparam', None)
        if clas not in [1, 2]:
            return ('Eparam', None)

        if expire == None:
            expire = datetime.datetime(2099, 12, 31, 0, 0, 0, 0, tzinfo=datetime.timezone.utc)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    INSERT INTO "problem"
                    ("name", "status", "class", "expire")
                    VALUES ($1, $2, $3, $4) RETURNING "pro_id";
                ''',
                name, status, [clas], expire
            )
            if result.__len__() != 1:
                return ('Eunk', None)

            pro_id = int(result[0]['pro_id'])

            err, ret = await self._unpack_pro(pro_id, ProService.PACKTYPE_FULL, pack_token)

            await con.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')

        await self.rs.delete('prolist')

        return (None, pro_id)

    async def update_pro(self, pro_id, name, status, clas, expire, pack_type, pack_token=None, tags=''):
        name_len = len(name)
        if name_len < ProService.NAME_MIN:
            return ('Enamemin', None)
        if name_len > ProService.NAME_MAX:
            return ('Enamemax', None)
        del name_len
        if (status < ProService.STATUS_ONLINE or status > ProService.STATUS_OFFLINE):
            return ('Eparam', None)
        if clas not in [1, 2]:
            return ('Eparam', None)
        if tags and not re.match(r'^[a-zA-Z0-9-_, ]+$', tags):
            return ('Etags', None)

        if expire == None:
            expire = datetime.datetime(2099, 12, 31, 0, 0, 0, 0, tzinfo=datetime.timezone.utc)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    UPDATE "problem"
                    SET "name" = $1, "status" = $2, "class" = $3, "expire" = $4, "tags" = $5
                    WHERE "pro_id" = $6 RETURNING "pro_id";
                ''',
                name, status, [clas], expire, tags, int(pro_id)
            )
            if result.__len__() != 1:
                return ('Enoext', None)

            if pack_token != None:
                err, _ = await self._unpack_pro(pro_id, pack_type, pack_token)
                if err:
                    return (err, None)

                await con.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')

        await self.rs.delete('prolist')

        return (None, None)

    async def update_limit(self, pro_id, timelimit, memlimit):
        if timelimit <= 0:
            return ('Etimelimitmin', None)
        if memlimit <= 0:
            return ('Ememlimitmin', None)

        memlimit = memlimit * 1024

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    UPDATE "test_config"
                    SET "timelimit" = $1, "memlimit" = $2
                    WHERE "pro_id" = $3 RETURNING "pro_id";
                ''',
                int(timelimit), int(memlimit), int(pro_id)
            )
        if result.__len__() == 0:
            return ('Enoext', None)

        return (None, None)


    #TODO: 把這破函數命名改一下
    async def get_acct_limit(self, acct, special=None):
        if special == True:
            return ProService.STATUS_OFFLINE

        if acct['acct_type'] == UserConst.ACCTTYPE_KERNEL:
            return ProService.STATUS_OFFLINE
        else:
            return ProService.STATUS_ONLINE

    async def _unpack_pro(self, pro_id, pack_type, pack_token):
        def _clean_cont(prefix):
            try:
                os.remove(f'{prefix}cont.html')

            except OSError:
                pass

            try:
                os.remove(f'{prefix}cont.pdf')

            except OSError:
                pass

        if (pack_type != ProService.PACKTYPE_FULL
                and pack_type != ProService.PACKTYPE_CONTHTML
                and pack_type != ProService.PACKTYPE_CONTPDF):
            return ('Eparam', None)

        if pack_type == ProService.PACKTYPE_CONTHTML:
            prefix = f'problem/{pro_id}/http/'
            _clean_cont(prefix)
            await PackService.inst.direct_copy(pack_token, f'{prefix}cont.html')

        elif pack_type == ProService.PACKTYPE_CONTPDF:
            prefix = f'problem/{pro_id}/http/'
            _clean_cont(prefix)
            await PackService.inst.direct_copy(pack_token, f'{prefix}cont.pdf')

        elif pack_type == ProService.PACKTYPE_FULL:
            err = await PackService.inst.unpack(pack_token, f'problem/{pro_id}', True)
            await asyncio.sleep(5)
            if err:
                return (err, None)

            try:
                os.chmod(os.path.abspath(f'problem/{pro_id}'), 0o755)
                #INFO: 正式上線請到config.py修改成正確路徑
                os.symlink(os.path.abspath(f"problem/{pro_id}/http"), f"{config.WEB_PROBLEM_STATIC_FILE_DIRECTORY}/{pro_id}")

            except FileExistsError:
                pass

            try:
                with open(f'problem/{pro_id}/conf.json') as conf_f:
                    conf = json.load(conf_f)
            except Exception:
                return ('Econf', None)

            comp_type  = conf['compile']
            score_type = conf['score']
            check_type = conf['check']
            timelimit  = conf['timelimit']
            memlimit   = conf['memlimit'] * 1024
            chalmeta   = conf['metadata']

            async with self.db.acquire() as con:
                await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))

                for test_idx, test_conf in enumerate(conf['test']):
                    metadata = { 'data': test_conf['data'] }

                    await con.execute(
                        '''
                            INSERT INTO "test_config"
                            ("pro_id", "test_idx", "compile_type", "score_type", "check_type",
                            "timelimit", "memlimit", "weight", "metadata", "chalmeta")
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
                        ''',
                        int(pro_id), int(test_idx), comp_type, score_type, check_type,
                        int(timelimit), int(memlimit), int(test_conf['weight']), json.dumps(metadata), json.dumps(chalmeta)
                    )

        return (None, None)