import datetime


class BulletinService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        BulletinService.inst = self
        self.tz = datetime.timezone(datetime.timedelta(hours=+8))

    async def list_bulletin(self):
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "bulletin"."bulletin_id", "bulletin"."title", "bulletin"."timestamp", 
                    "bulletin"."color", "bulletin"."pinned", "account"."name", "account"."acct_id"
                    FROM "bulletin" INNER JOIN "account" ON "account"."acct_id" = "bulletin"."author_id";
                '''
            )

        bulletin_list = []
        for (b_id, title, timestamp, color, pinned, name, acct_id) in result:
            bulletin_list.append({
                "bulletin_id": b_id,
                "title": title,
                "timestamp": timestamp.astimezone(self.tz),
                "color": color,
                "pinned": pinned,
                "acct_id": acct_id,
                "name": name,
            })

        return None, bulletin_list

    async def get_bulletin(self, bulletin_id):
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "bulletin"."title", "bulletin"."content", "bulletin"."timestamp", "account"."name",
                    "bulletin"."color", "bulletin"."pinned", "account"."name", "account"."acct_id"
                    FROM "bulletin" 
                    INNER JOIN "account" ON "account"."acct_id" = "bulletin"."author_id"
                    WHERE "bulletin"."bulletin_id" = $1
                ''',
                int(bulletin_id)
            )

        if result.__len__() != 1:
            return 'Noext', None
        result = result[0]
        result = {
            'title': result['title'],
            'content': result['content'],
            'timestamp': result['timestamp'].astimezone(self.tz),
            'name': result['name'],
            'color': result['color'],
            'pinned': result['pinned'],
            'acct_id': result['acct_id'],
        }

        return None, result

    async def add_bulletin(self, title, content, acct_id, color='White', pinned=False):
        async with self.db.acquire() as con:
            result = await con.execute(
                '''
                    INSERT INTO "bulletin" ("title", "content", "color", "pinned", "author_id")
                    VALUES ($1, $2, $3, $4, $5) RETURNING "bulletin_id";
                ''',
                title, content, color, pinned, acct_id
            )
        if result.__len__() != 1:
            return 'Eunk', None

        await self.rs.publish('bulletinsub', 1)

    async def edit_bulletin(self, bulletin_id, title, content, acct_id, color, pinned):
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    UPDATE "bulletin" SET "title" = $1, "content" = $2, "author_id" = $3, "color" = $4, "pinned" = $5 
                    WHERE "bulletin_id" = $6;
                ''',
                title, content, int(acct_id), color, pinned, int(bulletin_id)
            )

        await self.rs.publish('bulletinsub', 1)

    async def del_bulletin(self, bulletin_id):
        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "bulletin" WHERE "bulletin_id" = $1', int(bulletin_id))

        await self.rs.publish('bulletinsub', 1)
