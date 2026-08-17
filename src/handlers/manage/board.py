import datetime

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.board import BoardService
from services.user import UserConst
from utils.numeric import parse_str_to_list


board_dispatcher = ActionDispatcher()


def trantime(time):
    if time == '':
        time = None

    else:
        try:
            time = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
            time = time.replace(tzinfo=datetime.timezone.utc)

        except ValueError:
            return ('Eparam', 'Invalid time'), None

    return None, time


class ManageBoardHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, boardlist = await BoardService.inst.get_boardlist()
            await self.render('manage/board/board-list', "Manage Boards",
                              page='board', boardlist=boardlist)

        elif page == "add":
            await self.render('manage/board/add', "Add Board", page='add')

        elif page == "update":
            try:
                board_id = int(self.get_argument("board_id"))
            except ValueError:
                return self.error(("Eparam", "Invalid board ID"))

            err, board = await BoardService.inst.get_board(board_id)
            if err:
                return self.error(err)
            await self.render('manage/board/update', f"Update Board {board['name']}(#{board_id})",
                              page='update', board_id=board_id, board=board)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')
        return await board_dispatcher.dispatch(self, reqtype)

    @board_dispatcher.action('add')
    async def add_board(self):
        try:
            status = int(self.get_argument('status'))
        except ValueError:
            return self.error(('Eparam', 'Invalid status'))
        name = self.get_argument('name')
        start = self.get_argument('start')
        end = self.get_argument('end')

        err, start = trantime(start)
        if err:
            return self.error(err)

        err, end = trantime(end)
        if err:
            return self.error(err)

        acct_list = parse_str_to_list(self.get_argument('acct_list'))
        pro_list = parse_str_to_list(self.get_argument('pro_list'))

        await self.add_log(
            f"{self.acct.name} was added to the board \"{name}\".", 'manage.board.add',
            {
                "name": name,
                "status": status,
                "start": start,
                "end": end,
                "pro_list": pro_list,
                "acct_list": acct_list,
            }
        )

        err, board_id = await BoardService.inst.add_board(name, status, start, end, pro_list, acct_list)
        if err:
            return self.error(err)

        self.error(('S', board_id))

    @board_dispatcher.action('update')
    async def update_board(self):
        try:
            board_id = int(self.get_argument('board_id'))
        except ValueError:
            return self.error(('Eparam', 'Invalid board ID'))
        try:
            status = int(self.get_argument('status'))
        except ValueError:
            return self.error(('Eparam', 'Invalid status'))
        name = self.get_argument('name')
        start = self.get_argument('start')
        end = self.get_argument('end')
        err, start = trantime(start)
        if err:
            return self.error(err)

        err, end = trantime(end)
        if err:
            return self.error(err)

        acct_list = parse_str_to_list(self.get_argument('acct_list'))
        pro_list = parse_str_to_list(self.get_argument('pro_list'))

        await self.add_log(
            f"{self.acct.name} was updated in the board \"{name}\".", 'manage.board.update',
            {
                "name": name,
                "status": status,
                "start": start,
                "end": end,
                "pro_list": pro_list,
                "acct_list": acct_list,
            }
        )
        err, _ = await BoardService.inst.update_board(board_id, name, status, start, end, pro_list, acct_list)
        if err:
            return self.error(err)

        self.error(('S', ''))

    @board_dispatcher.action('remove')
    async def remove_board(self):
        try:
            board_id = int(self.get_argument('board_id'))
        except ValueError:
            return self.error(('Eparam', 'Invalid board ID'))
        err, _ = await BoardService.inst.remove_board(board_id)
        if err:
            return self.error(err)

        await self.add_log(
            f"{self.acct.name} was removed the board \"{board_id}\".", 'manage.board.remove'
        )
        self.error(('S', ''))
