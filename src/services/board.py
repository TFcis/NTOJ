import datetime

class BoardConst:
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2


class BoardService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        BoardService.inst = self

    async def get_boardlist(self):
        async with self.db.acquire() as con:
            res = await con.fetch(
                'SELECT "board_id", "name", "status", "start", "end" FROM "board" ORDER BY "board_id" ASC;'
            )

        return None, res

    async def get_board(self, board_id):
        board_id = int(board_id)

        async with self.db.acquire() as con:
            res = await con.fetchrow('SELECT * FROM "board" WHERE "board_id" = $1', board_id)

            if res is None:
                return 'Enoext', None

        name, status, start, end, pro_list, acct_list = (
            res['name'],
            res['status'],
            res['start'],
            res['end'],
            res['pro_list'],
            res['acct_list'],
        )

        meta = {
            'name': name,
            'status': status,
            'pro_list': pro_list,
            'acct_list': acct_list,
            'start': start.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))),
            'end': end.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))),
        }

        return None, meta

    async def add_board(self, name, status, start, end, pro_list: list[int], acct_list: list[int]):
        pro_list = list(set(pro_list))
        acct_list = list(set(acct_list))

        async with self.db.acquire() as con:
            await con.execute(
                '''
                    INSERT INTO "board" ("name", "status", "start", "end", "pro_list", "acct_list")
                    VALUES ($1, $2, $3, $4, $5, $6);
                ''',
                name,
                status,
                start,
                end,
                pro_list,
                acct_list,
            )

        return None, None

    async def update_board(self, board_id, name, status, start, end, pro_list: list[int], acct_list: list[int]):
        board_id = int(board_id)

        pro_list = list(set(pro_list))
        acct_list = list(set(acct_list))

        async with self.db.acquire() as con:
            res = await con.fetch(
                '''
                    UPDATE "board" SET "name" = $1, "status" = $2, "start" = $3, "end" = $4, "pro_list" = $5,
                    "acct_list" = $6 WHERE "board_id" = $7 RETURNING "board_id";
                ''',
                name,
                status,
                start,
                end,
                pro_list,
                acct_list,
                board_id,
            )
            if len(res) != 1:
                return 'Enoext', None

        return None, None

    async def remove_board(self, board_id):
        board_id = int(board_id)
        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "board" WHERE "board_id" = $1', board_id)

        return None, None
