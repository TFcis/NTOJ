from handlers.base import RequestHandler, reqenv
from services.pro import ProConst, ProService
from services.rank import RankService


class ProRankHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        pageoff = int(self.get_argument('pageoff', default=0))
        pagenum = int(self.get_argument('pagenum', default=20))

        pro_id = int(pro_id)
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, _ = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        err, (chal_list, total_cnt) = await RankService.inst.get_pro_rank(pro_id, pageoff, pagenum)
        if err:
            return self.error(err)

        await self.render(
            'pro-rank', pro_id=pro_id, chal_list=chal_list, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt
        )


class UserRankHandler(RequestHandler):
    @reqenv
    async def get(self):
        pageoff = int(self.get_argument('pageoff', default=0))
        pagenum = int(self.get_argument('pagenum', default=20))

        err, (acctlist, total_cnt) = await RankService.inst.get_user_rank(pageoff, pagenum)
        if err:
            return self.error(err)

        await self.render('user-rank', acctlist=acctlist, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt)
