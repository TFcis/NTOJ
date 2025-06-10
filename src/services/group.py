class GroupConst:
    DEFAULT_GROUP = 'normal_user'
    KERNEL_GROUP = 'kernel'


class GroupService:
    DEFAULT_GROUP = 'normal_user'
    KERNEL_GROUP = 'kernel'
    GROUP_NOT_FOUND = 'Group not found'

    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        GroupService.inst = self

    async def add_group(self, gname, gtype, gclas):
        glist = await self.list_group()
        if gname in glist:
            return ('Eexist', 'Group already exists')

        async with self.db.acquire() as con:
            await con.execute(
                '''
                    INSERT INTO "group"
                    ("group_name", "group_type", "group_class")
                    VALUES ($1, $2, $3);
                ''',
                gname,
                gtype,
                gclas,
            )

        return None

    async def del_group(self, gname):
        glist = await self.list_group()
        if gname not in glist:
            return ('Enoext', GroupService.GROUP_NOT_FOUND)

        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "group" WHERE "group"."group_name" = $1;', gname)
        gacct = await self.list_acct_in_group(gname)
        for acct in gacct:
            _ = await self.set_acct_group(acct['acct_id'], self.DEFAULT_GROUP)

        return None

    async def list_group(self):
        async with self.db.acquire() as con:
            result = await con.fetch('SELECT "group_name" FROM "group";')

        glist = [gname['group_name'] for gname in result]

        return glist

    async def list_acct_in_group(self, gname):
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "account"."acct_id", "account"."name" FROM "account"
                    WHERE "account"."group" = $1
                    ORDER BY "account"."acct_id";
                ''',
                gname,
            )

        acct_list = [
            {
                'acct_id': int(acct_id),
                'acct_name': str(acct_name),
            }
            for acct_id, acct_name in result
        ]

        return acct_list

    async def group_of_acct(self, acct_id):
        acct_id = int(acct_id)
        async with self.db.acquire() as con:
            result = await con.fetch('SELECT "account"."group" FROM "account" WHERE "account"."acct_id" = $1', acct_id)

        return result[0]['group']

    async def set_acct_group(self, acct_id, gname):
        acct_id = int(acct_id)
        glist = await self.list_group()
        if gname not in glist:
            return ('Enoext', GroupService.GROUP_NOT_FOUND)

        async with self.db.acquire() as con:
            result = await con.fetchrow(
                '''
                    SELECT "group_type", "group_class" FROM "group"
                    WHERE "group_name" = $1;
                ''',
                gname,
            )

            await con.execute(
                '''
                    UPDATE "account" SET "group" = $1, "acct_type" = $2
                    WHERE "account"."acct_id" = $3;
                ''',
                gname,
                result['group_type'],
                acct_id,
            )

            await con.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')

        await self.rs.delete(f'account@{acct_id}')
        await self.rs.delete('acctlist')
        return None

    async def _update_group(self, gname, gtype, gclas):
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    UPDATE "group"
                    SET "group_type" = $1, "group_class" = $2
                    WHERE "group_name" = $3 RETURNING "group_name";
                ''',
                gtype,
                [gclas],
                gname,
            )

        # TODO: update multiple group should not allow
        if len(result) != 1:
            return ('Eunk', 'Unknown error')

        return None

    async def update_group(self, gname, gtype, gclas):
        glist = await self.list_group()
        if gname not in glist:
            return ('Enoext', GroupService.GROUP_NOT_FOUND)

        if err := await self._update_group(gname, int(gtype), int(gclas)):
            return err

        gacct = await self.list_acct_in_group(gname)
        for acct in gacct:
            _ = await self.set_acct_group(acct['acct_id'], gname)
        return None
