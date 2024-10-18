class NewStatus:
    STATE_AC = 1
    STATE_PC = 2
    STATE_WA = 3
    STATE_RE = 4
    STATE_RESIG = 5
    STATE_TLE = 6
    STATE_MLE = 7
    STATE_OLE = 8
    STATE_CE = 9
    STATE_CLE = 10
    STATE_ERR = 11
    STATE_SJE = 12
    STATE_JUDGE = 100
    STATE_NOTSTARTED = 101

OldStatusMapper = {
    1: NewStatus.STATE_AC,
    2: NewStatus.STATE_WA,
    3: NewStatus.STATE_RE,
    9: NewStatus.STATE_RESIG,
    4: NewStatus.STATE_TLE,
    5: NewStatus.STATE_MLE,
    6: NewStatus.STATE_CE,
    10: NewStatus.STATE_CLE,
    7: NewStatus.STATE_ERR,
    8: NewStatus.STATE_OLE,
    100: NewStatus.STATE_JUDGE,
    101: NewStatus.STATE_NOTSTARTED,
}

async def dochange(db, rs):

    res = await db.fetch('SELECT chal_id, test_idx, state FROM test;')
    for test in res:
        chal_id, test_idx, old_state = test['chal_id'], test['test_idx'], test['state']
        await db.execute('UPDATE test SET state = $1 WHERE chal_id = $2 AND test_idx = $3',
                         OldStatusMapper[old_state], chal_id, test_idx)
        await db.execute(f'SELECT update_challenge_state({chal_id});')

    await db.execute('ALTER TABLE test ADD COLUMN rate NUMERIC(10, 3);')
    await db.execute('ALTER TABLE problem ADD COLUMN rate_precision INTEGER DEFAULT 0;')
    await db.execute('ALTER TABLE challenge_state ALTER COLUMN rate TYPE NUMERIC(10, 3);')

    await rs.delete('rate')

    await db.execute(
    '''
    CREATE OR REPLACE FUNCTION update_challenge_state(p_chal_id INTEGER)
    RETURNS VOID AS $$
    BEGIN
        WITH challenge_summary AS (
            SELECT
                t.chal_id,
                MAX(t.state) AS max_state,
                SUM(t.runtime) AS total_runtime,
                SUM(t.memory) AS total_memory,
                SUM(
                    CASE
                        WHEN (t.state = 1 OR t.state = 2) AND t.rate IS NOT NULL THEN t.rate -- special score
                        WHEN t.state = 1 AND t.rate IS NULL THEN tvr.rate -- default score
                        ELSE 0
                    END
                ) AS total_rate
            FROM test t
            LEFT JOIN test_valid_rate tvr ON t.pro_id = tvr.pro_id AND t.test_idx = tvr.test_idx
            WHERE t.chal_id = p_chal_id
            GROUP BY t.chal_id
        )
        INSERT INTO challenge_state (chal_id, state, runtime, memory, rate)
        SELECT
            chal_id,
            max_state,
            total_runtime,
            total_memory,
            total_rate
        FROM challenge_summary
        ON CONFLICT (chal_id) DO UPDATE
        SET
            state = EXCLUDED.state,
            runtime = EXCLUDED.runtime,
            memory = EXCLUDED.memory,
            rate = EXCLUDED.rate
        WHERE
            challenge_state.state != EXCLUDED.state OR
            challenge_state.runtime != EXCLUDED.runtime OR
            challenge_state.memory != EXCLUDED.memory OR
            challenge_state.rate != EXCLUDED.rate;

        RETURN;
    END;
    $$ LANGUAGE plpgsql;
    '''
    )
