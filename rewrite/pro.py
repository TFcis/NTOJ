from collections import OrderedDict
import datetime
import asyncio
import json
import time
import math
import re
import os

from msgpack import packb, unpackb
import tornado.web
import redis

from user import UserService, UserConst
from chal import ChalService, ChalConst
from pack import PackService
from log import LogService
from req import RequestHandler, reqenv
from req import WebSocketHandler
from req import Service

from dbg import dbg_print

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
                #INFO: 正式上線要改路徑
                # os.symlink(os.path.abspath(f'problem/{pro_id}/http'), f'/srv/oj_web/oj//problem/{pro_id}')
                os.symlink(os.path.abspath(f'problem/{pro_id}/http'), f'/home/last_order/html/oj/problem/{pro_id}')

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

class ProsetHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            off = int(self.get_argument('off'))
        except tornado.web.HTTPError:
            off = 0

        try:
            clas = int(self.get_argument('class'))
        except tornado.web.HTTPError:
            clas = None

        try:
            pclas_key = str(self.get_argument('pclas_key'))
        except:
            pclas_key = None

        # Backward compatibility
        if pclas_key == None:
            try:
                pclas_name = str(self.get_argument('pclas_name'))
                pclas_key = await Service.Pro.get_pclass_key_by_name(pclas_name)
            except:
                pass

        err, prolist = await ProService.inst.list_pro(
            self.acct, state=True, clas=clas)

        if pclas_key == None:
            pronum = len(prolist)
            prolist = prolist[off:off + 40]
            await self.render('proset', pronum=pronum, prolist=prolist, clas=clas, pclas_key=pclas_key,
                    pclist=await ProService.inst.get_class_list(), pageoff=off)
            return

        else:
            err, p_list = await ProService.inst.get_pclass_list(pclas_key)
            if err:
                self.error(err)
                return

            prolist2 = []
            for pro in prolist:
                if pro['pro_id'] in p_list:
                    prolist2.append(pro)
            prolist = prolist2
            pronum = len(prolist)
            prolist = prolist[off:off + 40]
            await self.render('proset', pronum=pronum, prolist=prolist, clas=clas, pclas_key=pclas_key,
                    pclist=await ProService.inst.get_class_list(), pageoff=off)
            return

    @reqenv
    async def post(self):
        pass

class ProStaticHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id, path):
        pro_id = int(pro_id)

        err, pro = await ProService.inst.get_pro(pro_id, self.acct)
        if err:
            self.error(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.error('Eacces')
            return

        if path[-3:] == 'pdf':
            self.set_header('Pragma', 'public')
            self.set_header('Expires', '0')
            self.set_header('Cache-Control', 'must-revalidate, post-check=0, pre-check=0')
            self.add_header('Content-Type', 'application/pdf')

            try:
                download = self.get_argument('download')
            except tornado.web.HTTPError:
                download = None

            if download:
                self.set_header('Content-Disposition', f'attachment; filename="pro{pro_id}.pdf"')
            else:
                self.set_header('Content-Disposition', 'inline')

        self.set_header('X-Accel-Redirect', f'/oj/problem/{pro_id}/{path}')
        return

class ProHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        pro_id = int(pro_id)

        err, pro = await ProService.inst.get_pro(pro_id, self.acct)
        if err:
            self.error(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.error('Eacces')
            return

        testl = []
        for test_idx, test_conf in pro['testm_conf'].items():
            testl.append({
                'test_idx'  : test_idx,
                'timelimit' : test_conf['timelimit'],
                'memlimit'  : test_conf['memlimit'],
                'weight'    : test_conf['weight'],
                'rate'      : 2000
            })

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "test_idx", "rate" FROM "test_valid_rate"
                    WHERE "pro_id" = $1 ORDER BY "test_idx" ASC;
                ''',
                pro_id
            )

        countmap = {}
        for test_idx, count in result:
            countmap[test_idx] = count

        for test in testl:
            if test['test_idx'] in countmap:
                test['rate'] = math.floor(countmap[test['test_idx']])

        isguest = (self.acct['acct_id'] == UserConst.ACCTID_GUEST)
        isadmin = (self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)

        if isadmin:
            pass

        elif isguest or pro['tags'] == None or pro['tags'] == '':
            pro['tags'] = ''

        else:
            async with self.db.acquire() as con:
                result = await con.fetchrow(
                    '''
                        SELECT MIN("challenge_state"."state") AS "state"
                        FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id"
                        AND "challenge"."acct_id" = $1
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = $3
                        WHERE "problem"."status" <= $2 AND "problem"."pro_id" = $3 AND "problem"."class" && $4;
                    ''',
                    int(self.acct['acct_id']), ChalConst.STATE_AC, int(pro['pro_id']), [1, 2]
                )

            if result['state'] == None or result['state'] != ChalConst.STATE_AC:
                pro['tags'] = ''

        judge_status_list = await Service.Judge.get_servers_status()
        can_submit = False

        for status in judge_status_list:
            if status['status']:
                can_submit = True
                break

        await self.render('pro', pro={
            'pro_id' : pro['pro_id'],
            'name'   : pro['name'],
            'status' : pro['status'],
            'tags'   : pro['tags'],
        }, testl=testl, isadmin=isadmin, can_submit=can_submit)
        return


class ProTagsHandler(RequestHandler):
    @reqenv
    async def post(self):
        if self.acct['acct_id'] == UserConst.ACCTID_GUEST:
            self.error('Esign')
            return

        tags = self.get_argument('tags')
        pro_id = int(self.get_argument('pro_id'))

        if isinstance(tags, str) and self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL:
            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.error(err)
                return

            await LogService.inst.add_log((self.acct['name'] + " updated the tag of problem #" + str(pro_id) + " to: \"" + str(tags) + "\"."), 'manage.pro.update.tag')

            err, ret = await ProService.inst.update_pro(
                pro_id, pro['name'], pro['status'], pro['class'], pro['expire'], '', None, tags)

            if err:
                self.error(err)
                return

        else:
            self.error('Eacces')
            return

        self.finish('setting tags done')
        return


class SubmitHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.error('Esign')
            return

        pro_id = int(pro_id)
        err, pro = await ProService.inst.get_pro(pro_id, self.acct)
        if err:
            self.error(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.error('Eacces')
            return

        judge_status_list = await Service.Judge.get_servers_status()
        can_submit = False

        for status in judge_status_list:
            if status['status']:
                can_submit = True
                break

        if can_submit == False:
            self.finish('<h1 style="color: red;">All Judge Server Offline</h1>')
            return

        await self.render('submit', pro=pro)
        return

    @reqenv
    async def post(self):
        if self.acct['acct_id'] == UserConst.ACCTID_GUEST:
            self.error('Esign')
            return

        judge_status_list = await Service.Judge.get_servers_status()
        can_submit = False

        for status in judge_status_list:
            if status['status']:
                can_submit = True
                break

        if can_submit == False:
            self.error('Ejudge')
            return

        reqtype = self.get_argument('reqtype')
        if reqtype == 'submit':
            pro_id = int(self.get_argument('pro_id'))
            code = self.get_argument('code')

            if len(code.strip()) == 0:
                self.error('Eempty')
                return

            if len(code) > ProService.CODE_MAX:
                self.error('Ecodemax')
                return

            if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
                last_submit_name = f"last_submit_time_{self.acct['acct_id']}"
                if (last_submit_time := (await self.rs.get(last_submit_name))) == None:
                    await self.rs.set(last_submit_name, int(time.time()), ex=600)

                else:
                    last_submit_time = int(str(last_submit_time)[2:-1])
                    if int(time.time()) - last_submit_time < 30:
                        self.error('Einternal')
                        return

                    else:
                        await self.rs.set(last_submit_name, int(time.time()))

            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.error(err)
                return

            if pro['status'] == ProService.STATUS_OFFLINE:
                self.error('Eacces')
                return

            #TODO: code prevent '/dev/random'
            #code = code.replace('bits/stdc++.h','DontUseMe.h')
            err, chal_id = await ChalService.inst.add_chal(
                pro_id, self.acct['acct_id'], code)

            if err:
                self.error(err)
                return

        elif (reqtype == 'rechal'
                and self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL):

            chal_id = int(self.get_argument('chal_id'))

            err, ret = await ChalService.inst.reset_chal(chal_id)
            err, chal = await ChalService.inst.get_chal(chal_id, self.acct)

            pro_id = chal['pro_id']
            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.finish(err)
                return

        else:
            self.error('Eparam')
            return

        err, ret = await ChalService.inst.emit_chal(
            chal_id,
            pro_id,
            pro['testm_conf'],
            f'/nfs/code/{chal_id}/main.cpp',
            f'/nfs/problem/{pro_id}/res')
        if err:
            self.error(err)
            return

        if reqtype == 'submit' and pro['status'] == ProService.STATUS_ONLINE:
            await self.rs.publish('challist_sub', 1)

        self.finish(json.dumps(chal_id))
        return


class ChalListHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            off = int(self.get_argument('off'))

        except tornado.web.HTTPError:
            off = 0

        try:
            ppro_id = str(self.get_argument('proid'))
            tmp_pro_id = ppro_id.replace(' ', '').split(',')
            pro_id = []
            for p in tmp_pro_id:
                try:
                    pro_id.append(int(p))
                except ValueError:
                    pass

            if len(pro_id) == 0:
                pro_id = None

        except tornado.web.HTTPError:
            pro_id = None
            ppro_id = ''

        try:
            pacct_id = str(self.get_argument('acctid'))
            tmp_acct_id = pacct_id.replace(' ', '').split(',')
            acct_id = []
            for a in tmp_acct_id:
                acct_id.append(int(a))

        except tornado.web.HTTPError:
            acct_id = None
            pacct_id = ''

        try:
            state = int(self.get_argument('state'))

        except (tornado.web.HTTPError, ValueError):
            state = 0

        flt = {
            'pro_id' : pro_id,
            'acct_id': acct_id,
            'state'  : state
        }

        err, chalstat = await ChalService.inst.get_stat(
            min(self.acct['acct_type'], UserConst.ACCTTYPE_USER), flt)

        err, challist = await ChalService.inst.list_chal(off, 20,
                                                              min(self.acct['acct_type'], UserService.ACCTTYPE_USER), flt)

        isadmin = (self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)
        chalids = []
        for chal in challist:
            chalids.append(chal['chal_id'])

        await self.render('challist',
                    chalstat=chalstat,
                    challist=challist,
                    flt=flt,
                    pageoff=off,
                    ppro_id=ppro_id,
                    pacct_id=pacct_id,
                    acct=self.acct,
                    chalids=json.dumps(chalids),
                    isadmin=isadmin)
        return

from redis import asyncio as aioredis

class ChalSubHandler(WebSocketHandler):
    async def open(self):
        self.ars = aioredis.Redis(host='localhost', port=6379, db=1)
        self.p = self.ars.pubsub()
        await self.p.subscribe('challist_sub')

        async def test():
            async for msg in self.p.listen():
                if msg['type'] != 'message':
                    continue

                await self.on_message(str(int(msg['data'])))

        self.task = asyncio.tasks.Task(test())

    async def on_message(self, msg):
        self.write_message(msg)

    def on_close(self) -> None:
        self.task.cancel()

    def check_origin(self, origin):
        #TODO: secure
        return True

class ChalHandler(RequestHandler):
    @reqenv
    async def get(self, chal_id):
        chal_id = int(chal_id)

        err, chal = await ChalService.inst.get_chal(chal_id, self.acct)
        if err:
            self.error(err)
            return

        err, pro = await ProService.inst.get_pro(chal['pro_id'], self.acct)
        if err:
            self.error(err)
            return

        if self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
            rechal = True
        else:
            rechal = False

        await self.render('chal', pro=pro, chal=chal, rechal=rechal)
        return

class ChalStateHandler(WebSocketHandler):
    async def open(self):
        self.chal_id = -1
        self.ars = aioredis.Redis(host='localhost', port=6379, db=1)
        self.p = self.ars.pubsub()
        await self.p.subscribe('chalstatesub')

        async def listen_chalstate():
            async for msg in self.p.listen():
                if msg['type'] != 'message':
                    continue

                if int(msg['data']) == self.chal_id:
                    err, chal_states = await ChalService.inst.get_chal_state(self.chal_id)
                    await self.write_message(json.dumps(chal_states))

        self.task = asyncio.tasks.Task(listen_chalstate())

    async def on_message(self, msg):
        self.chal_id = int(msg)

    def on_close(self) -> None:
        self.task.cancel()

    def check_origin(self, origin):
        #TODO: secure
        return True
