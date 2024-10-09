async def dochange(db, rs):
    await db.execute('ALTER TABLE problem ADD allow_submit boolean DEFAULT true')
