class OldBoardConst:
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

class NewBoardConst:
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1

async def dochange(db, _):
    res = await db.fetch('SELECT board_id, status FROM "board";')
    for board_id, status in res:
        if status == OldBoardConst.STATUS_OFFLINE:
            await db.execute('UPDATE board SET status = $1 WHERE board_id = $2;', NewBoardConst.STATUS_HIDDEN, board_id)
