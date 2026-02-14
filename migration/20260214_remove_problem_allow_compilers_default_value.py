async def dochange(db, rs):
    # Happy Valentine's Day :cry:
    await db.execute('ALTER TABLE problem ALTER COLUMN allow_compilers DROP DEFAULT')
