async def dochange(db, rs):
    await db.execute("ALTER TABLE account ADD proclass_collection integer[] NOT NULL DEFAULT '{}'::integer[]")
    result = await db.fetch("SELECT last_value FROM account_acct_id_seq;")
    cur_acct_id = int(result[0]['last_value'])

    for acct_id in range(1, cur_acct_id + 1):
        await rs.delete(f"account@{acct_id}")

    await rs.delete('acctlist')
