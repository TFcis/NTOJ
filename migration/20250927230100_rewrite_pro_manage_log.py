import re
async def dochange(db, _):
    for t in ['judge', 'limit']:
        result = await db.fetch(
            '''
                SELECT "log"."log_id", "log"."message"
                FROM "log"
                WHERE "log"."type" = $1;
            ''',
            f'manage.pro.update.{t}',
        )

        for log_id, message in result:
            await db.execute('UPDATE "log" SET "message" = $1 WHERE "log_id" = $2', f"{message} {t} config", log_id)
