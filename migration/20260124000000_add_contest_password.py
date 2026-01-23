async def dochange(db, rs):
    await db.execute("ALTER TABLE contest ADD COLUMN contest_password character varying(255) DEFAULT '';")
