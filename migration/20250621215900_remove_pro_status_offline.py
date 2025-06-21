class OldProConst:
    STATUS_ONLINE = 0
    STATUS_CONTEST = 1
    STATUS_HIDDEN = 2
    STATUS_OFFLINE = 3

class NewProConst:
    STATUS_ONLINE = 0
    STATUS_CONTEST = 1
    STATUS_HIDDEN = 2

async def dochange(db, rs):
    res = await db.fetch('SELECT pro_id, status FROM problem;')
    for pro_id, status in res:
        if status == OldProConst.STATUS_OFFLINE:
            await db.execute('UPDATE problem SET status = $1 WHERE pro_id = $2;', NewProConst.STATUS_HIDDEN, pro_id)

    await rs.delete('prolist')
