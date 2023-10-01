import base64
import datetime
import json

import tornado.web
from msgpack import packb, unpackb

import config
from services.chal import ChalService
from services.contest import ContestService
from services.group import GroupService, GroupConst
from services.bulletin import BulletinService
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pack import PackService
from services.pro import ProService
from services.ques import QuestionService
from services.user import UserService, UserConst
from handlers.base import RequestHandler, reqenv, require_permission


class ManageHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page='dash'):
        if page == 'dash':
            await self.render('manage/manage-dash', page=page)
            return

        elif page == 'judge':
            judge_status_list = await JudgeServerClusterService.inst.get_servers_status()
            await self.render('manage/manage-judge', page=page, judge_status_list=judge_status_list)
            return

        elif page == 'pro':
            err, prolist = await ProService.inst.list_pro(self.acct)

            if (lock_list := (await self.rs.get('lock_list'))) is not None:
                lock_list = unpackb(lock_list)
            else:
                lock_list = []

            await self.render('manage/manage-pro', page=page, prolist=prolist, lock_list=lock_list)
            return

        elif page == 'addpro':
            await self.render('manage/manage-pro-add', page=page)
            return

        elif page == 'reinitpro':
            pro_id = int(self.get_argument('proid'))

            await self.render('manage/manage-pro-reinit', page=page, pro_id=pro_id)
            return

        elif page == 'updatepro':
            pro_id = int(self.get_argument('proid'))

            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err == 'Econf':
                self.finish(
                    '''
                        <script type="text/javascript" id="contjs">
                            function init() {
                    '''
                    f"index.go('/oj/manage/reinitpro/?proid={pro_id}')"
                    '''
                            }
                        </script>
                    '''
                )
                return
            elif err != None:
                self.error(err)
                return

            lock = await self.rs.get(f"{pro['pro_id']}_owner")

            testl = []
            for test_idx, test_conf in pro['testm_conf'].items():
                testl.append({
                    'test_idx': test_idx,
                    'timelimit': test_conf['timelimit'],
                    'memlimit': test_conf['memlimit'],
                    'weight': test_conf['weight'],
                    'rate': 2000
                })

            try:
                with open(f"problem/{pro_id}/conf.json", 'r') as conf_file:
                    conf_content = conf_file.read()
            except FileNotFoundError:
                conf_content = ''

            await self.render('manage/manage-pro-update', page=page, pro=pro, lock=lock, testl=testl,
                              problem_config_json=conf_content)
            return

        elif page == 'contest':
            try:
                cont_name = str(self.get_argument('cont'))
                if cont_name != 'Add_cont':
                    err, cont_meta = await ContestService.inst.get(cont_name)
                    if err:
                        self.error('Eexist')
                        return

                else:
                    cont_meta = {
                        'start': datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))),
                        'end': datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))}

            except tornado.web.HTTPError:
                cont_name = 'Add_cont'
                cont_meta = {
                    'start': datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))),
                    'end': datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))}

            await self.render('manage/manage-contest',
                              page=page,
                              meta=(await ContestService.inst.get('default'))[1],
                              contlist=await ContestService.inst.get_list(),
                              cont_meta=cont_meta,
                              cont_name=cont_name)
            return

        elif page == 'acct':
            err, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, True)

            await self.render('manage/manage-acct', page=page, acctlist=acctlist)
            return

        elif page == 'updateacct':
            acct_id = int(self.get_argument('acctid'))

            err, acct = await UserService.inst.info_acct(acct_id)
            glist = await GroupService.inst.list_group()
            group = await GroupService.inst.group_of_acct(acct_id)
            await self.render('manage/manage-acct-update', page=page, acct=acct, glist=glist, group=group)
            return

        elif page == 'question':
            err, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, True)
            asklist = {}
            for acct in acctlist:

                if (ask := (await self.rs.get(f"{acct['acct_id']}_msg_ask"))) is None:
                    asklist.update({acct['acct_id']: False})
                else:
                    asklist.update({acct['acct_id']: unpackb(ask)})

            await self.render('manage/manage-question', page=page, acctlist=acctlist, asklist=asklist)
            return

        elif page == 'rquestion':
            qacct_id = int(self.get_argument('qacct'))
            err, ques_list = await QuestionService.inst.get_queslist(acct_id=qacct_id)
            # await self.rs.set(f'{qacct_id}_msg_ask', packb(False))
            await self.render('manage/manage-rquestion', page=page, qacct_id=qacct_id, ques_list=ques_list)
            return

        elif page == 'inform':
            if (inform_list := (await self.rs.get('inform'))) is not None:
                inform_list = unpackb(inform_list)
            else:
                inform_list = []

            await self.render('manage/manage-inform', page=page, inform_list=inform_list)
            return

        elif page == 'proclass':
            try:
                pclas_key = str(self.get_argument('pclas_key'))

            except tornado.web.HTTPError:
                pclas_key = None

            if pclas_key is None:
                await self.render('manage/manage-proclass', page=page, pclas_key=pclas_key, pclas_name='',
                                  clas_list=await ProService.inst.get_class_list(), p_list=None)
                return

            else:
                pclas_name = await ProService.inst.get_pclass_name_by_key(pclas_key)
                if pclas_name is None:
                    self.error('Eexist')
                    return

                err, p_list = await ProService.inst.get_pclass_list(pclas_key)
                if err:
                    self.error(err)
                    return

                await self.render('manage/manage-proclass', page=page, pclas_key=pclas_key, pclas_name=pclas_name,
                                  clas_list=(await ProService.inst.get_class_list()), p_list=p_list)
            return

        elif page == 'group':
            try:
                gname = str(self.get_argument('gname'))

                async with self.db.acquire() as con:
                    result = await con.fetchrow(
                        '''
                            SELECT "group"."group_type", "group"."group_class"
                            FROM "group"
                            WHERE "group"."group_name" = $1
                        ''',
                        gname
                    )
                gtype = int(result['group_type'])
                gclas = int(result['group_class'])

            except tornado.web.HTTPError:
                gname = None
                gtype = None
                gclas = None

            glist = await GroupService.inst.list_group()
            if gname is not None:
                gacct = await GroupService.inst.list_acct_in_group(gname)
            else:
                gacct = None

            await self.render('manage/manage-group', page=page, gname=gname, glist=glist, gacct=gacct, gtype=gtype,
                              gclas=gclas)
            return

    @reqenv
    async def post(self, page):
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.error('Eacces')
            return

        if page == 'pack':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'gettoken':
                err, pack_token = await PackService.inst.gen_token()
                self.finish(json.dumps(pack_token))
                return

        elif page == 'judge':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'connect':
                index = int(self.get_argument('index'))

                err, server_inform = await JudgeServerClusterService.inst.get_server_status(index)
                if (server_name := server_inform['name']) == '':
                    server_name = f"server-{index}"

                err = await JudgeServerClusterService.inst.connect_server(index)
                if err:
                    await LogService.inst.add_log(f"{self.acct['name']} tried connected {server_name} but failed.",
                                                  'manage.judge.connect.failure')
                    self.error(err)
                    return

                await LogService.inst.add_log(f"{self.acct['name']} had been connected {server_name} succesfully.",
                                              'manage.judge.connect')

                self.finish('S')
                return

            elif reqtype == 'disconnect':
                index = int(self.get_argument('index'))
                pwd = str(self.get_argument('pwd'))

                err, server_inform = await JudgeServerClusterService.inst.get_server_status(index)
                if (server_name := server_inform['name']) == '':
                    server_name = f"server-{index}"

                if config.unlock_pwd != base64.b64encode(packb(pwd)):
                    await LogService.inst.add_log(f"{self.acct['name']} tried to disconnect {server_name} but failed.",
                                                  'manage.judge.disconnect.failure')
                    self.error('Eacces')
                    return

                err = await JudgeServerClusterService.inst.disconnect_server(index)
                await LogService.inst.add_log(f"{self.acct['name']} had been disconnected {server_name} succesfully.",
                                              'manage.judge.disconnect')
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

        elif page == 'pro':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'addpro':
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                clas = int(self.get_argument('class'))
                expire = None
                pack_token = self.get_argument('pack_token')

                err, pro_id = await ProService.inst.add_pro(
                    name, status, clas, expire, pack_token)
                await LogService.inst.add_log(
                    f"{self.acct['name']} had been send a request to add the problem #{pro_id}", 'manage.pro.add.pro')
                if err:
                    self.error(err)
                    return

                self.finish(json.dumps(pro_id))
                return

            elif reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                clas = int(self.get_argument('class'))
                expire = None
                pack_type = int(self.get_argument('pack_type'))
                pack_token = self.get_argument('pack_token')
                tags = self.get_argument('tags')

                if pack_token == '':
                    pack_token = None

                err, ret = await ProService.inst.update_pro(
                    pro_id, name, status, clas, expire, pack_type, pack_token, tags)
                await LogService.inst.add_log(
                    f"{self.acct['name']} had been send a request to update the problem #{pro_id}",
                    'manage.pro.update.pro')
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'reinitpro':
                pro_id = int(self.get_argument('pro_id'))
                pack_token = self.get_argument('pack_token')
                pack_type = ProService.inst.PACKTYPE_FULL
                err, _ = await ProService.inst._unpack_pro(pro_id, pack_type, pack_token)
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'updatelimit':
                pro_id = int(self.get_argument('pro_id'))
                timelimit = int(self.get_argument('timelimit'))
                memlimit = int(self.get_argument('memlimit'))

                err, ret = await ProService.inst.update_limit(pro_id, timelimit, memlimit)
                await LogService.inst.add_log(
                    f"{self.acct['name']} had been send a request to update the problem #{pro_id}",
                    'manage.pro.update.limit')
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'updateconf':
                pro_id = int(self.get_argument('pro_id'))
                conf_json_text = self.get_argument('conf')

                try:
                    conf_json = json.loads(conf_json_text)
                except json.decoder.JSONDecodeError:
                    self.error('Econf')
                    return

                with open(f'problem/{pro_id}/conf.json', 'w') as conf_f:
                    conf_f.write(conf_json_text)

                comp_type = conf_json['compile']
                score_type = conf_json['score']
                check_type = conf_json['check']
                timelimit = conf_json['timelimit']
                memlimit = conf_json['memlimit'] * 1024
                chalmeta = conf_json['metadata']

                async with self.db.acquire() as con:
                    await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))

                    for test_idx, test_conf in enumerate(conf_json['test']):
                        metadata = {'data': test_conf['data']}

                        await con.execute(
                            '''
                                INSERT INTO "test_config"
                                ("pro_id", "test_idx", "compile_type", "score_type", "check_type",
                                "timelimit", "memlimit", "weight", "metadata", "chalmeta")
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
                            ''',
                            int(pro_id), int(test_idx), comp_type, score_type, check_type,
                            int(timelimit), int(memlimit), int(test_conf['weight']), json.dumps(metadata),
                            json.dumps(chalmeta)
                        )

                await LogService.inst.add_log(
                    f"{self.acct['name']} had been send a request to update the problem #{pro_id}",
                    'manage.pro.update.conf')

                self.finish('S')
                return

            elif reqtype == 'rechal':
                pro_id = int(self.get_argument('pro_id'))

                judge_status_list = await JudgeServerClusterService.inst.get_servers_status()
                can_submit = False

                for status in judge_status_list:
                    if status['status']:
                        can_submit = True
                        break

                if not can_submit:
                    self.error('Ejudge')
                    return

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                if err:
                    self.error(err)
                    return

                async with self.db.acquire() as con:
                    result = await con.fetch(
                        '''
                            SELECT "challenge"."chal_id" FROM "challenge"
                            LEFT JOIN "challenge_state"
                            ON "challenge"."chal_id" = "challenge_state"."chal_id"
                            WHERE "pro_id" = $1 AND "challenge_state"."state" IS NULL;
                        ''',
                        pro_id
                    )
                    result = result[0]
                await LogService.inst.add_log(
                    f"{self.acct['name']} made a request to rejudge the problem #{pro_id} with {result.__len__()} chals",
                    'manage.chal.rechal')

                for chal_id in result:
                    err, ret = await ChalService.inst.reset_chal(chal_id)
                    err, ret = await ChalService.inst.emit_chal(
                        chal_id,
                        pro_id,
                        pro['testm_conf'],
                        f'/nfs/code/{chal_id}/main.cpp',
                        f'/nfs/problem/{pro_id}/res'
                    )

                self.finish('S')
                return

            elif reqtype == 'pro-lock':
                pro_id = int(self.get_argument('pro_id'))
                await self.rs.set(f'{pro_id}_owner', packb(1))

                if (lock_list := (await self.rs.get('lock_list'))) is not None:
                    lock_list = unpackb(lock_list)
                else:
                    lock_list = []

                if pro_id not in lock_list:
                    lock_list.append(pro_id)

                await self.rs.set('lock_list', packb(lock_list))
                self.finish('S')
                return

            elif reqtype == 'pro-unlock':
                pro_id = int(self.get_argument('pro_id'))
                pwd = str(self.get_argument('pwd'))

                if config.unlock_pwd != base64.b64encode(packb(pwd)):
                    self.error('Eacces')
                    return

                lock_list = unpackb((await self.rs.get('lock_list')))
                lock_list.remove(pro_id)
                await self.rs.set('lock_list', packb(lock_list))
                await self.rs.delete(f"{pro_id}_owner")
                self.finish('S')
                return

        elif page == 'contest':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'set':
                cont_name = str(self.get_argument('cont_name'))
                clas = int(self.get_argument('class'))
                status = int(self.get_argument('status'))
                start = self.get_argument('start')
                end = self.get_argument('end')
                await LogService.inst.add_log(f"{self.acct['name']} was setting the contest \"{cont_name}\".",
                                              'manage.contest.set')
                err, start = self.trantime(start)
                if err:
                    self.error(err)
                    return

                err, end = self.trantime(end)
                if err:
                    self.error(err)
                    return

                if cont_name == 'default':
                    await ContestService.inst.set('default', clas, status, start, end)

                else:
                    pro_list = str(self.get_argument('pro_list'))
                    acct_list = str(self.get_argument('acct_list'))
                    await ContestService.inst.set(cont_name=cont_name, clas=None, status=status, start=start, end=end,
                                                  pro_list=pro_list, acct_list=acct_list)

                self.finish('S')
                return

            elif reqtype == 'del':
                cont_name = self.get_argument('cont_name')
                await ContestService.inst.remove_cont(cont_name)
                self.finish('S')
                await LogService.inst.add_log(f"{self.acct['name']} was removing the contest \"{cont_name}\".",
                                              'manage.contest.remove')
                return

        elif page == 'acct':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'updateacct':
                acct_id = int(self.get_argument('acct_id'))
                acct_type = int(self.get_argument('acct_type'))
                clas = int(self.get_argument('class'))
                group = str(self.get_argument('group'))
                # if group == GroupConst.KERNEL_GROUP:
                #    self.finish('Ekernel')
                #    return
                err, acct = await UserService.inst.info_acct(acct_id)
                if err:
                    await LogService.inst.add_log(
                        f"{self.acct['name']}(#{self.acct['acct_id']}) had been send a request to update the account #{acct_id} but not found",
                        'manage.acct.update.failure')
                    self.error(err)
                    return

                await LogService.inst.add_log(
                    f"{self.acct['name']}(#{self.acct['acct_id']}) had been send a request to update the account {acct['name']}(#{acct['acct_id']})",
                    'manage.acct.update')

                err, ret = await UserService.inst.update_acct(acct_id,
                                                              acct_type, clas, acct['name'], acct['photo'],
                                                              acct['cover'])
                if err:
                    self.error(err)
                    return

                err = await GroupService.inst.set_acct_group(acct_id, group)
                self.finish('S')
                return

        elif page == 'rquestion':
            reqtype = self.get_argument('reqtype')
            if reqtype == 'rpl':
                await LogService.inst.add_log(
                    f"{self.acct['name']} replyed a question from user #{self.get_argument('qacct_id')}:\"{self.get_argument('rtext')}\".",
                    'manage.question.reply')

                index = self.get_argument('index')
                rtext = self.get_argument('rtext')
                qacct_id = int(self.get_argument('qacct_id'))
                await QuestionService.inst.reply(qacct_id, index, rtext)
                self.finish('S')
                return

            if reqtype == 'rrpl':
                await LogService.inst.add_log(
                    f"{self.acct['name']} re-replyed a question from user #{self.get_argument('qacct_id')}:\"{self.get_argument('rtext')}\".",
                    'manage.question.re-reply')

                index = self.get_argument('index')
                rtext = self.get_argument('rtext')
                qacct_id = int(self.get_argument('qacct_id'))
                await QuestionService.inst.reply(qacct_id, index, rtext)
                self.finish('S')
                return

        elif page == 'inform':
            reqtype = str(self.get_argument('reqtype'))

            if reqtype == 'add':
                # TODO: 改成Title and Content
                title = self.get_argument('title')
                content = self.get_argument('content')
                pinned = self.get_argument('pinned')
                color = self.get_argument('color')
                await BulletinService.inst.add_bulletin(title, content, self.acct['acct_id'], color, pinned)

                await LogService.inst.add_log(f"{self.acct['name']} added a line on bulletin: \"{title}\".",
                                              'manage.inform.add')
                return

            elif reqtype == 'edit':
                bulletin_id = int(self.get_argument('bulletin_id'))
                title = self.get_argument('title')
                content = self.get_argument('content')
                pinned = self.get_argument('pinned')
                color = self.get_argument('color')

                await LogService.inst.add_log(
                    f"{self.acct['name']} updated a line on bulletin: \"{title}\" which id is #{bulletin_id}.",
                    'manage.inform.update')
                await BulletinService.inst.edit_bulletin(bulletin_id, title, content, self.acct['acct_id'], color, pinned)
                return

            elif reqtype == 'del':
                bulletin_id = int(self.get_argument('bulletin_id'))
                await LogService.inst.add_log(
                    f"{self.acct['name']} removed a line on bulletin which id is #{bulletin_id}.",
                    'manage.inform.remove')
                await BulletinService.inst.del_bulletin(bulletin_id)
                return
            return

        elif page == 'proclass':
            reqtype = str(self.get_argument('reqtype'))

            if reqtype == 'add':
                pclas_key = str(self.get_argument('pclas_key'))
                pclas_name = str(self.get_argument('pclas_name'))
                p_list = str(self.get_argument('p_list'))
                p_list = p_list.replace(' ', '').split(',')
                p_list2 = []
                for p in p_list:
                    try:
                        p_list2.append(int(p))
                    except ValueError:
                        pass
                p_list = p_list2
                await LogService.inst.add_log(
                    f"{self.acct['name']} add proclass key={pclas_key} name={pclas_name} list={p_list}",
                    'manage.proclass.add')
                err = await ProService.inst.add_pclass(pclas_key, pclas_name, p_list)
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'remove':
                pclas_key = str(self.get_argument('pclas_key'))
                await LogService.inst.add_log(f"{self.acct['name']} remove proclass key={pclas_key}",
                                              'manage.proclass.remove')
                err = await ProService.inst.remove_pclass(pclas_key)
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'edit':
                pclas_key = str(self.get_argument('pclas_key'))
                new_pclas_key = str(self.get_argument('new_pclas_key'))
                pclas_name = str(self.get_argument('pclas_name'))
                p_list = str(self.get_argument('p_list'))
                p_list = p_list.replace(' ', '').split(',')
                p_list2 = []

                for p in p_list:
                    try:
                        p_list2.append(int(p))
                    except ValueError:
                        pass

                p_list = p_list2
                await LogService.inst.add_log(
                    f"{self.acct['name']} update proclass key={pclas_key} newkey={new_pclas_key} name={pclas_name} list={p_list}",
                    'manage.proclass.update')
                err = await ProService.inst.edit_pclass(pclas_key, new_pclas_key, pclas_name, p_list)
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

        elif page == 'group':
            reqtype = str(self.get_argument('reqtype'))
            if reqtype == 'edit':
                gname = str(self.get_argument('gname'))
                gtype = int(self.get_argument('gtype'))
                gclas = int(self.get_argument('gclas'))
                if gname == GroupConst.KERNEL_GROUP:
                    self.error('Ekernel')
                    return

                await LogService.inst.add_log(
                    f"{self.acct['name']} updated group={gname} group_type={gtype} group_class={gclas}.",
                    'manage.group.update')
                err = await GroupService.inst.update_group(gname, gtype, gclas)
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'add_group':
                gname = str(self.get_argument('gname'))
                gtype = int(self.get_argument('gtype'))
                gclas = int(self.get_argument('gclas'))

                await LogService.inst.add_log(
                    f"{self.acct['name']} added group={gname} group_type={gtype} group_class={gclas}.",
                    'manage.group.add')
                err = await GroupService.inst.add_group(gname, gtype, gclas)
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'del_group':
                gname = str(self.get_argument('gname'))
                if gname in [GroupConst.KERNEL_GROUP, GroupConst.DEFAULT_GROUP]:
                    self.error('Ekernel')
                    return

                await LogService.inst.add_log(f"{self.acct['name']} deleted group={gname}", 'manage.group.delete')
                err = await GroupService.inst.del_group(gname)
                if err:
                    self.error(err)
                    return

                self.finish('S')
                return

        self.error('Eunk')
        return

    def trantime(self, time):
        if time == '':
            time = None

        else:
            try:
                time = datetime.datetime.strptime(time,
                                                  '%Y-%m-%dT%H:%M:%S.%fZ')
                time = time.replace(tzinfo=datetime.timezone.utc)

            except ValueError:
                return 'Eparam', None

        return None, time