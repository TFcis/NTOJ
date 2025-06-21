async def dochange(db, _):
    await db.execute('ALTER TABLE account DROP COLUMN "group";')
    await db.execute('DROP TABLE "group";')
