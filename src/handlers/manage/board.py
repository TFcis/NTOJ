import datetime

from handlers.base import RequestHandler, reqenv, require_permission
from services.board import BoardService
from services.group import GroupService
from services.log import LogService
from services.user import UserConst


def trantime(time):
    if time == '':
        time = None

    else:
        try:
            time = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
            time = time.replace(tzinfo=datetime.timezone.utc)

        except ValueError:
            return 'Eparam', None

    return None, time


class ManageBoardHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, boardlist = await BoardService.inst.get_boardlist()
            await self.render('manage/board/board-list', page='board', boardlist=boardlist)

        elif page == "add":
            await self.render('manage/board/add', page='add')

        elif page == "update":
            board_id = int(self.get_argument('boardid'))
            _, board = await BoardService.inst.get_board(board_id)
            await self.render('manage/board/update', page='add', board_id=board_id, board=board)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')

        if page == "add" and reqtype == 'add':
            name = str(self.get_argument('name'))
            status = int(self.get_argument('status'))
            start = self.get_argument('start')
            end = self.get_argument('end')
            pro_list_str = str(self.get_argument('pro_list'))
            acct_list_str = str(self.get_argument('acct_list'))

            err, start = trantime(start)
            if err:
                self.error(err)
                return

            err, end = trantime(end)
            if err:
                self.error(err)
                return

            acct_list = await self._get_acct_list(acct_list_str)
            pro_list = self._get_pro_list(pro_list_str)
            await LogService.inst.add_log(
                f"{self.acct.name} was added the contest \"{name}\".", 'manage.board.add',
                {
                    "name": name,
                    "status": status,
                    "start": start,
                    "end": end,
                    "pro_list": pro_list,
                    "acct_list": acct_list,
                }
            )

            await BoardService.inst.add_board(name, status, start, end, pro_list, acct_list)

            self.finish('S')

        elif page == "update" and reqtype == 'update':
            board_id = int(self.get_argument('board_id'))
            name = str(self.get_argument('name'))
            status = int(self.get_argument('status'))
            start = self.get_argument('start')
            end = self.get_argument('end')
            err, start = trantime(start)
            if err:
                self.error(err)
                return

            err, end = trantime(end)
            if err:
                self.error(err)
                return

            pro_list_str = str(self.get_argument('pro_list'))
            acct_list_str = str(self.get_argument('acct_list'))
            acct_list = await self._get_acct_list(acct_list_str)
            pro_list = self._get_pro_list(pro_list_str)

            await LogService.inst.add_log(
                f"{self.acct.name} was updated the contest \"{name}\".", 'manage.board.update',
                {
                    "name": name,
                    "status": status,
                    "start": start,
                    "end": end,
                    "pro_list": pro_list,
                    "acct_list": acct_list,
                }
            )
            await BoardService.inst.update_board(board_id, name, status, start, end, pro_list, acct_list)

            self.finish('S')

        elif page == "update" and reqtype == 'remove':
            board_id = int(self.get_argument('board_id'))
            await BoardService.inst.remove_board(board_id)
            self.finish('S')
            await LogService.inst.add_log(
                f"{self.acct.name} was removed the contest \"{board_id}\".", 'manage.board.remove'
            )

    async def _get_acct_list(self, acct_list_str: str) -> list[int]:
        acct_list = acct_list_str.replace(' ', '').split(',')

        res = []
        for acct in acct_list:
            if acct != '':
                if acct.isnumeric():
                    res.append(int(acct))

                elif acct.find("_group") != -1:
                    gacct = await GroupService.inst.list_acct_in_group(acct[:-6])
                    for ga in gacct:
                        res.append(ga['acct_id'])

        return res

    def _get_pro_list(self, pro_list_str: str) -> list[int]:
        pro_list = pro_list_str.replace(' ', '').split(',')
        return [int(pro) for pro in pro_list if pro.isnumeric()]
