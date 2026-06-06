from handlers.base import RequestHandler, reqenv
from services.pro import ProConst, ProService
from services.rank import RankService


class ProRankHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id: int = None):
        try:
            pageoff = int(self.get_argument('pageoff', default="0"))
            if pageoff < 0:
                pageoff = 0
        except ValueError:
            return self.error(("Eparam", "Invalid pageoff"))

        try:
            pagenum = int(self.get_argument('pagenum', default="20"))
            if pagenum <= 0:
                pagenum = 20
        except ValueError:
            return self.error(("Eparam", "Invalid pagenum"))

        try:
            pro_id = int(pro_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid pro_id"))

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        err, (chal_list, total_cnt) = await RankService.inst.get_pro_rank(pro_id, pageoff, pagenum)
        if err:
            return self.error(err)

        await self.render(
            'pro-rank', f'{pro.name} - Rank', pro_id=pro_id, chal_list=chal_list, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt
        )


class UserRankHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff', default="0"))
            if pageoff < 0:
                pageoff = 0
        except ValueError:
            return self.error(("Eparam", "Invalid pageoff"))

        try:
            pagenum = int(self.get_argument('pagenum', default="20"))
            if pagenum <= 0:
                pagenum = 20
        except ValueError:
            return self.error(("Eparam", "Invalid pagenum"))

        err, (acctlist, total_cnt) = await RankService.inst.get_user_rank(pageoff, pagenum)
        if err:
            return self.error(err)

        await self.render('user-rank', 'User Rank', acctlist=acctlist, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt)
