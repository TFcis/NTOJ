async def dochange(db, rs):
    await db.execute(
        "ALTER TABLE log ALTER COLUMN params TYPE jsonb USING params::jsonb"
    )
    await db.execute(
        "ALTER TABLE log ALTER COLUMN params SET DEFAULT '{}'::jsonb"
    )
