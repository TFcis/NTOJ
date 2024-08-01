import asyncio

from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst, ChalService
from services.contests import ContestService
from services.judge import JudgeServerClusterService
from services.pro import ProService
from utils.numeric import parse_list_str


class ContestManageProHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        pro_list = []
        for pro_id in self.contest.pro_list:
            err, pro = await ProService.inst.get_pro(pro_id, is_contest=True)
            pro_list.append(pro)

        await self.render('contests/manage/pro', page='pro',
                          contest_id=self.contest.contest_id, pro_list=pro_list)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')
        pro_id = self.get_argument('pro_id')

        if reqtype == "add":
            pro_id = int(pro_id)
            err, _ = await ProService.inst.get_pro(pro_id, is_contest=True)
            if err:
                self.error(err)
                return

            if pro_id in self.contest.pro_list:
                self.error('Eexist')
                return

            self.contest.pro_list.append(pro_id)

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == "remove":
            pro_id = int(pro_id)
            err, _ = await ProService.inst.get_pro(pro_id, is_contest=True)
            if err:
                self.error(err)
                return

            if pro_id not in self.contest.pro_list:
                self.error('Enoext')
                return

            self.contest.pro_list.remove(pro_id)

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == "multi_add":
            pro_list = []

            for p_id in parse_list_str(pro_id):
                err, _ = await ProService.inst.get_pro(p_id, is_contest=True)
                if err:
                    continue

                pro_list.append(p_id)

            pro_list = list(filter(lambda pro_id: pro_id not in self.contest.pro_list, pro_list))
            self.contest.pro_list.extend(pro_list)

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == "multi_remove":
            pro_list = parse_list_str(pro_id)

            self.contest.pro_list = list(filter(lambda pro_id: pro_id not in pro_list, self.contest.pro_list))

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == "rechal":
            pro_id = int(pro_id)
            can_submit = await JudgeServerClusterService.inst.is_server_online()
            if not can_submit:
                self.error('Ejudge')
                return

            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.error(err)
                return

            async with self.db.acquire() as con:
                result = await con.fetch(
                    f'''
                        SELECT "challenge"."chal_id", "challenge"."compiler_type" FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id" AND "challenge"."contest_id" = {self.contest.contest_id}
                        WHERE "pro_id" = $1;
                    ''',
                    pro_id
                )

            # await LogService.inst.add_log(
            #         f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
            #         'manage.chal.rechal',
            #     )

            # TODO: send notify to user
            async def _rechal(rechals):
                for chal_id, comp_type in rechals:
                    file_ext = ChalConst.FILE_EXTENSION[comp_type]
                    _, _ = await ChalService.inst.reset_chal(chal_id)
                    _, _ = await ChalService.inst.emit_chal(
                        chal_id,
                        pro_id,
                        pro['testm_conf'],
                        comp_type,
                        f"/srv/ntoj/code/{chal_id}/main.{file_ext}",
                        f"/srv/ntoj/problem/{pro_id}/res",
                    )

            await asyncio.create_task(_rechal(rechals=result))
            await self.finish('S')

        else:
            self.error('Eunk')
