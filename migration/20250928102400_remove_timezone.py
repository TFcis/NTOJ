import config
async def dochange(db, rs):
    await db.execute("SET timezone TO 'UTC';")
    await db.execute(f"ALTER DATABASE {config.DBNAME_OJ} SET timezone TO 'UTC';")
    await rs.delete("contest")
