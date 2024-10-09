async def dochange(db_conn, rs_conn):
    await db_conn.execute('CREATE INDEX challenge_idx_contest_id ON public.challenge USING btree (contest_id)')
