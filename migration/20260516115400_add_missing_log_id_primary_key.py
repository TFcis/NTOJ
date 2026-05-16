async def dochange(db, _):
    res = await db.execute(
        '''
        DELETE FROM log a USING log b
        WHERE a.ctid < b.ctid
            AND a.log_id = b.log_id
            AND a.message IS NOT DISTINCT FROM b.message
            AND a.timestamp IS NOT DISTINCT FROM b.timestamp
            AND a.type IS NOT DISTINCT FROM b.type
            AND a.params IS NOT DISTINCT FROM b.params
            AND a.operator_acct_id IS NOT DISTINCT FROM b.operator_acct_id
            AND a.operator_ip IS NOT DISTINCT FROM b.operator_ip
            AND a.contest_id IS NOT DISTINCT FROM b.contest_id;
        '''
    )
    print(f"Deleted {str(res).split(' ')[1]} duplicate log entries")
    await db.execute('DROP INDEX IF EXISTS log_idx_log_id;')
    await db.execute('ALTER TABLE log ADD PRIMARY KEY (log_id);')
