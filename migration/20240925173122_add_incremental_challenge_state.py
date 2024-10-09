async def dochange(db, rs):
    await db.execute('DROP MATERIALIZED VIEW challenge_state;')

    await db.execute(
    '''
        CREATE TABLE challenge_state (
            chal_id integer NOT NULL,
            state integer,
            runtime bigint DEFAULT 0,
            memory bigint DEFAULT 0,
            rate integer DEFAULT 0
        );
    ''')
    await db.execute(
    '''
        ALTER TABLE ONLY public.challenge_state
            ADD CONSTRAINT challenge_state_forkey_chal_id FOREIGN KEY (chal_id) REFERENCES public.challenge(chal_id) ON DELETE CASCADE;
    ''')

    await db.execute("ALTER TABLE challenge_state ADD CONSTRAINT challenge_state_unique_chal_id UNIQUE(chal_id);")


    await db.execute(
    '''
        CREATE TABLE last_update_time (
             view_name TEXT PRIMARY KEY,
             last_update TIMESTAMP WITH TIME ZONE
        );
    '''
    )

    await db.execute("INSERT INTO last_update_time (view_name, last_update) VALUES ('challenge_state', NOW());")

    await db.execute("ALTER TABLE test ADD COLUMN last_modified TIMESTAMP WITH TIME ZONE DEFAULT NOW();")

    await db.execute("CREATE INDEX idx_test_last_modified ON test (last_modified);")
    await db.execute("CREATE UNIQUE INDEX ON test_valid_rate (pro_id, test_idx);")

    await db.execute(
    '''
        CREATE OR REPLACE FUNCTION update_test_last_modified()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.last_modified = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    await db.execute(
    '''
        CREATE TRIGGER test_last_modified_trigger
        BEFORE UPDATE ON test
        FOR EACH ROW EXECUTE FUNCTION update_test_last_modified();
    ''')

    await db.execute(
    '''
        CREATE OR REPLACE FUNCTION refresh_challenge_state_incremental()
        RETURNS VOID AS $$
        DECLARE
            last_update_time TIMESTAMP WITH TIME ZONE;
        BEGIN
            SELECT last_update INTO last_update_time
            FROM last_update_time
            WHERE view_name = 'challenge_state';

            WITH challenge_summary AS (
                SELECT
                    t.chal_id,
                    MAX(t.state) AS max_state,
                    SUM(t.runtime) AS total_runtime,
                    SUM(t.memory) AS total_memory,
                    SUM(CASE WHEN t.state = 1 THEN tvr.rate ELSE 0 END) AS total_rate
                FROM test t
                LEFT JOIN test_valid_rate tvr ON t.pro_id = tvr.pro_id AND t.test_idx = tvr.test_idx
                WHERE t.last_modified > last_update_time
                GROUP BY t.chal_id
            ),
            upsert_result AS (
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
                    challenge_state.rate != EXCLUDED.rate
            )

            UPDATE last_update_time
            SET last_update = NOW()
            WHERE view_name = 'challenge_state';
        END;
        $$ LANGUAGE plpgsql;
    ''')
    await db.execute('SELECT refresh_challenge_state_incremental();')
