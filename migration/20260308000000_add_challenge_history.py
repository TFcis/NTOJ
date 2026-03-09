async def dochange(db, rs):
    # NOTE: total_result_history — records old total_result values before UPDATE/DELETE
    #       Skips STATE_JUDGE (100) and STATE_NOTSTARTED (101) as they are transient states
    await db.execute(
    '''
        CREATE TABLE total_result_history (
            history_id BIGSERIAL PRIMARY KEY,
            chal_id INTEGER NOT NULL,
            state INTEGER NOT NULL,
            time BIGINT NOT NULL DEFAULT 0,
            memory BIGINT NOT NULL DEFAULT 0,
            rate NUMERIC(10, 3) NOT NULL DEFAULT 0,
            message CHARACTER VARYING NOT NULL DEFAULT '',
            message_type INTEGER NOT NULL DEFAULT 1,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            operation CHAR(1) NOT NULL  -- 'U' = UPDATE, 'D' = DELETE
        );
    ''')

    # NOTE: subtask_result_history — records old subtask_result values before UPDATE/DELETE
    await db.execute(
    '''
        CREATE TABLE subtask_result_history (
            history_id BIGSERIAL PRIMARY KEY,
            chal_id INTEGER NOT NULL,
            subtask_id INTEGER NOT NULL,
            state INTEGER NOT NULL,
            time BIGINT NOT NULL DEFAULT 0,
            memory BIGINT NOT NULL DEFAULT 0,
            rate NUMERIC(10, 3) NOT NULL DEFAULT 0,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            operation CHAR(1) NOT NULL  -- 'U' = UPDATE, 'D' = DELETE
        );
    ''')

    # NOTE: testdata_result_history — records old testdata_result values before UPDATE/DELETE
    await db.execute(
    '''
        CREATE TABLE testdata_result_history (
            history_id BIGSERIAL PRIMARY KEY,
            chal_id INTEGER NOT NULL,
            testdata_id INTEGER NOT NULL,
            state INTEGER NOT NULL,
            time BIGINT NOT NULL DEFAULT 0,
            memory BIGINT NOT NULL DEFAULT 0,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            operation CHAR(1) NOT NULL  -- 'U' = UPDATE, 'D' = DELETE
        );
    ''')

    await db.execute('CREATE INDEX idx_total_result_history_chal_id ON total_result_history (chal_id, recorded_at DESC);')
    await db.execute('CREATE INDEX idx_subtask_result_history_chal_id ON subtask_result_history (chal_id, recorded_at DESC, subtask_id ASC);')
    await db.execute('CREATE INDEX idx_testdata_result_history_chal_id ON testdata_result_history (chal_id, recorded_at DESC, testdata_id ASC);')

    # NOTE: Trigger function for total_result
    await db.execute(
    '''
        CREATE OR REPLACE FUNCTION record_total_result_history()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Skip STATE_JUDGE (100) and STATE_NOTSTARTED (101)
            IF OLD.state IN (100, 101) THEN
                RETURN NULL;
            END IF;

            IF TG_OP = 'UPDATE' THEN
                INSERT INTO total_result_history
                    (chal_id, state, time, memory, rate, message, message_type, operation)
                VALUES
                    (OLD.chal_id, OLD.state, OLD.time, OLD.memory, OLD.rate,
                     OLD.message, OLD.message_type, 'U');
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO total_result_history
                    (chal_id, state, time, memory, rate, message, message_type, operation)
                VALUES
                    (OLD.chal_id, OLD.state, OLD.time, OLD.memory, OLD.rate,
                     OLD.message, OLD.message_type, 'D');
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    await db.execute(
    '''
        CREATE TRIGGER trigger_record_total_result_history
        AFTER UPDATE OR DELETE ON total_result
        FOR EACH ROW
        EXECUTE FUNCTION record_total_result_history();
    ''')

    # NOTE: Trigger function for subtask_result
    await db.execute(
    '''
        CREATE OR REPLACE FUNCTION record_subtask_result_history()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Skip STATE_JUDGE (100) and STATE_NOTSTARTED (101)
            IF OLD.state IN (100, 101) THEN
                RETURN NULL;
            END IF;

            IF TG_OP = 'UPDATE' THEN
                INSERT INTO subtask_result_history
                    (chal_id, subtask_id, state, time, memory, rate, operation)
                VALUES
                    (OLD.chal_id, OLD.subtask_id, OLD.state, OLD.time, OLD.memory, OLD.rate, 'U');
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO subtask_result_history
                    (chal_id, subtask_id, state, time, memory, rate, operation)
                VALUES
                    (OLD.chal_id, OLD.subtask_id, OLD.state, OLD.time, OLD.memory, OLD.rate, 'D');
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    await db.execute(
    '''
        CREATE TRIGGER trigger_record_subtask_result_history
        AFTER UPDATE OR DELETE ON subtask_result
        FOR EACH ROW
        EXECUTE FUNCTION record_subtask_result_history();
    ''')

    # NOTE: Trigger function for testdata_result
    await db.execute(
    '''
        CREATE OR REPLACE FUNCTION record_testdata_result_history()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Skip STATE_JUDGE (100) and STATE_NOTSTARTED (101)
            IF OLD.state IN (100, 101) THEN
                RETURN NULL;
            END IF;

            IF TG_OP = 'UPDATE' THEN
                INSERT INTO testdata_result_history
                    (chal_id, testdata_id, state, time, memory, operation)
                VALUES
                    (OLD.chal_id, OLD.id, OLD.state, OLD.time, OLD.memory, 'U');
            ELSIF TG_OP = 'DELETE' THEN
                INSERT INTO testdata_result_history
                    (chal_id, testdata_id, state, time, memory, operation)
                VALUES
                    (OLD.chal_id, OLD.id, OLD.state, OLD.time, OLD.memory, 'D');
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    await db.execute(
    '''
        CREATE TRIGGER trigger_record_testdata_result_history
        AFTER UPDATE OR DELETE ON testdata_result
        FOR EACH ROW
        EXECUTE FUNCTION record_testdata_result_history();
    ''')

