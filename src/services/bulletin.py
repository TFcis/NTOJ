import logging

logger = logging.getLogger("tornado.application")

class BulletinConst:
    TITLE_MIN = 1
    TITLE_MAX = 50
    CONTENT_MIN = 0
    CONTENT_MAX = 2048

class BulletinService:
    BULLETIN_NOT_FOUND = 'Bulletin not found'
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        BulletinService.inst = self

    async def list_bulletin(self):
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "bulletin"."bulletin_id", "bulletin"."title", "bulletin"."timestamp",
                        "bulletin"."color", "bulletin"."pinned", "account"."name", "account"."acct_id"
                        FROM "bulletin" INNER JOIN "account" ON "account"."acct_id" = "bulletin"."author_id";
                    '''
                )
        except Exception as e:
            logger.error(f"Error fetching bulletin list: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        bulletin_list = []
        for b_id, title, timestamp, color, pinned, name, acct_id in result:
            bulletin_list.append(
                {
                    "bulletin_id": b_id,
                    "title": title,
                    "timestamp": timestamp,
                    "color": color,
                    "pinned": pinned,
                    "acct_id": acct_id,
                    "name": name,
                }
            )

        return None, bulletin_list

    async def get_bulletin(self, bulletin_id):
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "bulletin"."title", "bulletin"."content", "bulletin"."timestamp", "account"."name",
                        "bulletin"."color", "bulletin"."pinned", "account"."name", "account"."acct_id"
                        FROM "bulletin"
                        INNER JOIN "account" ON "account"."acct_id" = "bulletin"."author_id"
                        WHERE "bulletin"."bulletin_id" = $1
                    ''',
                    int(bulletin_id),
                )
        except Exception as e:
            logger.error(f"Error fetching bulletin {bulletin_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        if len(result) != 1:
            return ('Enoext', BulletinService.BULLETIN_NOT_FOUND), None
        result = result[0]
        result = {
            'title': result['title'],
            'content': result['content'],
            'timestamp': result['timestamp'],
            'name': result['name'],
            'color': result['color'],
            'pinned': result['pinned'],
            'acct_id': result['acct_id'],
        }

        return None, result

    async def add_bulletin(self, title, content, acct_id, color='White', pinned=False):
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        INSERT INTO "bulletin" ("title", "content", "color", "pinned", "author_id")
                        VALUES ($1, $2, $3, $4, $5) RETURNING "bulletin_id";
                    ''',
                    title,
                    content,
                    color,
                    pinned,
                    acct_id,
                )
        except Exception as e:
            logger.error(f"Error adding bulletin: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        if len(result) != 1:
            return ('Eunk', 'Unknown error'), None

        return None, result[0]['bulletin_id']

    async def edit_bulletin(self, bulletin_id, title, content, acct_id, color, pinned):
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        UPDATE "bulletin" SET "title" = $1, "content" = $2, "author_id" = $3, "color" = $4, "pinned" = $5
                        WHERE "bulletin_id" = $6 RETURNING "bulletin_id";
                    ''',
                    title,
                    content,
                    int(acct_id),
                    color,
                    pinned,
                    int(bulletin_id),
                )
        except Exception as e:
            logger.error(f"Error editing bulletin {bulletin_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        if len(result) != 1:
            return ('Eunk', 'Unknown error'), None

        return None, None

    async def del_bulletin(self, bulletin_id):
        try:
            async with self.db.acquire() as con:
                result: str = await con.execute('DELETE FROM "bulletin" WHERE "bulletin_id" = $1', int(bulletin_id))
                affected_row_cnt = int(result.split(" ")[1]) # DELETE \d+
                if affected_row_cnt == 0:
                    return ('Enoext', BulletinService.BULLETIN_NOT_FOUND), None
        except Exception as e:
            logger.error(f"Error deleting bulletin {bulletin_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        return None, None
