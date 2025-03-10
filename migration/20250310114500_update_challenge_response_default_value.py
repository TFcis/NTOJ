async def dochange(db, rs):
    await db.execute("ALTER TABLE test ALTER COLUMN response SET DEFAULT ''::character varying;")
