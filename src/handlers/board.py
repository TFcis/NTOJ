import time

from handlers.base import RequestHandler, reqenv
from services.board import BoardConst, BoardService
from services.pro import ProService
from services.rate import RateService
from services.user import UserConst, UserService


class BoardHandler(RequestHandler):
    @reqenv
    async def get(self, board_id=None):
        _, board_list = await BoardService.inst.get_boardlist()
        if board_id is None:
            await self.render('board-list', boardlist=board_list)
            return

        board_id = int(board_id)
        err, meta = await BoardService.inst.get_board(board_id)
        if err:
            self.error(err)
            return

        if meta['status'] == BoardConst.STATUS_OFFLINE:
            self.error('Eacces')
            return

        if meta['status'] == BoardConst.STATUS_HIDDEN and not self.acct.is_kernel():
            self.error('Eacces')
            return

        # delta = meta['end'] - datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))

        min_type = UserConst.ACCTTYPE_USER
        if self.acct.is_kernel():
            min_type = UserConst.ACCTTYPE_KERNEL

        # TODO: performance test
        err, prolist = await ProService.inst.list_pro(acct=self.acct)
        err, acctlist = await UserService.inst.list_acct(min_type=min_type)
        err, ratemap = await RateService.inst.map_rate(starttime=meta['start'], endtime=meta['end'])

        p_list = meta['pro_list']
        prolist = list(filter(lambda pro: pro['pro_id'] in p_list, prolist))

        acctlist2 = []
        submit_count = {}
        for acct in acctlist:
            if acct.acct_id in meta['acct_list']:
                acct.rate = 0
                acct_id = acct.acct_id
                count = 0

                for pro in prolist:
                    pro_id = pro['pro_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate = ratemap[acct_id][pro_id]
                        acct.rate += rate['rate']

                        if rate['rate'] > 0:
                            count -= rate['count']
                acctlist2.append(acct)
                submit_count.update({acct_id: (acct.rate, count)})

        acctlist2.sort(key=lambda acct: submit_count[acct.acct_id], reverse=True)

        rank = 0
        last_sc = None
        last_sb = None
        acct_submit = {}
        for acct in acctlist2:
            acct_id = acct.acct_id
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

            acct.rank = rank

        # NOTE: board最下面的score/submit那行
        pro_sc_sub = {}
        for pro in prolist:
            pro_id = pro['pro_id']
            sc = 0
            sub = 0
            for acct in acctlist2:
                acct_id = acct.acct_id
                if acct_id in ratemap and pro_id in ratemap[acct_id]:
                    rate = ratemap[acct_id][pro_id]
                    sc += rate['rate']
                    sub += rate['count']

            pro_sc_sub.update({pro_id: (sc, sub)})

        await self.render('board',
                          prolist=prolist,
                          acctlist=acctlist2,
                          ratemap=ratemap,
                          pro_sc_sub=pro_sc_sub,
                          acct_submit=acct_submit,
                          name=meta['name'],
                          board_list=board_list,
                          end=str(meta['end']).split('+')[0].replace('-', '/'),
                          timestamp=int(time.time()))
