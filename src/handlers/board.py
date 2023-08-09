import os
import time
import datetime

import tornado.web

from services.user import UserService, UserConst
from services.contest import ContestService, ContestConst
from services.pro import ProService
from services.rate import RateService
from handlers.base import RequestHandler, reqenv


class BoardHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            cont_name = str(self.get_argument('cont'))

        except tornado.web.HTTPError:
            cont_name = 'default'

        err, meta = await ContestService.inst.get(cont_name)
        if err:
            self.finish(err)
            return

        delta = meta['end'] - datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        deltasecond = delta.days * 24 * 60 * 60 + delta.seconds
        cont_list = await ContestService.inst.get_list()
        boardtempl = 'board'

        if self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL and cont_name != 'default':
            if os.path.exists(f'/srv/oj/backend/templ/{cont_name}_board.templ'):
                boardtempl = f'{cont_name}_board'

        if meta['status'] == ContestConst.STATUS_OFFLINE:
            self.error('Eacces')
            return

        if (meta['status'] == ContestConst.STATUS_HIDDEN and
                self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL):
            self.error('Eacces')
            return

        min_type = UserConst.ACCTTYPE_USER
        if self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL:
            min_type = UserConst.ACCTTYPE_KERNEL

        if cont_name == 'default':
            clas = meta['class']
            err, prolist = await ProService.inst.list_pro(acct=self.acct, clas=clas)
            err, acctlist = await UserService.inst.list_acct(min_type=min_type)
            err, ratemap = await RateService.inst.map_rate(clas=clas, starttime=meta['start'], endtime=meta['end'])

            # TODO: performance test
            for acct in acctlist:
                acct_id = acct['acct_id']
                acct['rate'] = 0
                for pro in prolist:
                    pro_id = pro['pro_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate = ratemap[acct_id][pro_id]
                        acct['rate'] += rate['rate']

            def turn(acct):
                acct_id = acct['acct_id']
                count = 0
                for pro in prolist:
                    pro_id = pro['pro_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate = ratemap[acct_id][pro_id]
                        if rate['rate'] > 0:
                            count = count - rate['count']

                return acct['rate'], count

            submit_count = {None: None}
            for acct in acctlist:
                acct_id = acct['acct_id']
                submit_count.update({acct_id: turn(acct)})
            acctlist.sort(key=lambda acct: submit_count[acct['acct_id']], reverse=True)

            acct_submit = {None: None}
            for acct in acctlist:
                acct_id = acct['acct_id']
                acct_submit.update({acct_id: 0})

            pro_sc_sub = {None: None}
            for pro in prolist:
                pro_id = pro['pro_id']
                sc_add = 0
                sub_add = 0
                for acct in acctlist:
                    acct_id = acct['acct_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate = ratemap[acct_id][pro_id]
                        sub_add += rate['count']
                        sc_add += rate['rate']
                        if rate['rate'] > 0:
                            acct_submit[acct_id] += rate['count']
                pro_sc_sub.update({pro_id: (sc_add, sub_add)})

            rank = 0
            last_rate = None
            last_submit = None
            for acct in acctlist:
                submit = submit_count[acct['acct_id']][1]
                if acct['rate'] != last_rate:
                    rank += 1
                    last_rate = acct['rate']
                    last_submit = submit

                elif submit != last_submit and last_rate != 0:
                    rank += 1
                    last_submit = submit

                acct['rank'] = rank

            await self.render('board',
                              prolist=prolist,
                              acctlist=acctlist,
                              ratemap=ratemap,
                              pro_sc_sub=pro_sc_sub,
                              acct_submit=acct_submit,
                              cont_name=cont_name,
                              cont_list=cont_list,
                              end=str(meta['end']).split('+')[0].replace('-', '/'),
                              timestamp=int(time.time()))

        else:

            # TODO: performance test
            err, prolist = await ProService.inst.list_pro(acct=self.acct)
            err, acctlist = await UserService.inst.list_acct(min_type=min_type)
            err, ratemap = await RateService.inst.map_rate(starttime=meta['start'], endtime=meta['end'])

            prolist2 = []
            for pro in prolist:
                if pro['pro_id'] in meta['pro_list']:
                    prolist2.append(pro)

            acctlist2 = []
            submit_count = {}
            for acct in acctlist:
                if acct['acct_id'] in meta['acct_list']:
                    acct['rate'] = 0
                    acct_id = acct['acct_id']
                    count = 0

                    for pro in prolist2:
                        pro_id = pro['pro_id']
                        if acct_id in ratemap and pro_id in ratemap[acct_id]:
                            rate = ratemap[acct_id][pro_id]
                            acct['rate'] += rate['rate']

                            if rate['rate'] > 0:
                                count -= rate['count']
                    acctlist2.append(acct)
                    submit_count.update({acct_id: (acct['rate'], count)})

            acctlist2.sort(key=lambda acct: submit_count[acct['acct_id']], reverse=True)
            # dbg_print(__file__, 301, acctlist2=acctlist2)
            # dbg_print(__file__, 302, submit_count=submit_count)

            rank = 0
            last_sc = None
            last_sb = None
            acct_submit = {}
            for acct in acctlist2:
                acct_id = acct['acct_id']
                sc = submit_count[acct_id][0]
                sb = -submit_count[acct_id][1]
                acct_submit.update({acct_id: sb})

                if sc != last_sc:
                    last_sc = sc
                    last_sb = sb
                    rank += 1

                elif sb != last_sb:
                    last_sb = sb
                    rank += 1

                acct['rank'] = rank

            # dbg_print(__file__, 325, acctlist2=acctlist2)
            # dbg_print(__file__, 326, acct_submit=acct_submit)
            # dbg_print(__file__, 327, submit_count=submit_count)

            # INFO: board最下面的score/submit那行
            pro_sc_sub = {}
            for pro in prolist2:
                pro_id = pro['pro_id']
                sc = 0
                sub = 0
                for acct in acctlist2:
                    acct_id = acct['acct_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate = ratemap[acct_id][pro_id]
                        sc += rate['rate']
                        sub += rate['count']

                pro_sc_sub.update({pro_id: (sc, sub)})

            # dbg_print(__file__, 344, pro_sc_sub=pro_sc_sub)

            await self.render(boardtempl,
                              prolist=prolist2,
                              acctlist=acctlist2,
                              ratemap=ratemap,
                              pro_sc_sub=pro_sc_sub,
                              acct_submit=acct_submit,
                              cont_name=cont_name,
                              cont_list=cont_list,
                              end=str(meta['end']).split('+')[0].replace('-', '/'),
                              timestamp=int(time.time()))

        return
