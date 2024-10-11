async def dochange(db, rs):
    await db.execute('DROP TABLE last_update_time;')
    await db.execute('DROP INDEX idx_test_last_modified;')
    await db.execute('ALTER TABLE test DROP COLUMN last_modified')
    await db.execute('DROP TRIGGER IF EXISTS test_last_modified_trigger ON test')
    await db.execute('DROP FUNCTION IF EXISTS update_test_last_modified()')
    await db.execute('DROP FUNCTION IF EXISTS refresh_challenge_state_incremental()')

    await db.execute('CREATE INDEX challenge_state_idx_chal_id ON challenge_state USING btree (chal_id);')
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
                SUM(CASE WHEN t.state = 1 THEN tvr.rate ELSE 0 END) AS total_rate
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
    ''')
