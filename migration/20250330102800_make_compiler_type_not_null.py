async def dochange(db, _):
    await db.execute('ALTER TABLE challenge ALTER COLUMN compiler_type SET NOT NULL;')
