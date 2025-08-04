import json
async def dochange(db, rs):
    res = await db.fetch('SELECT pro_id, "limit" FROM problem;')
    for pro_id, limit in res:
        limit: dict[str, dict[str, int]] = json.loads(limit)

        for lim in limit.values():
            lim['time'] = lim.pop('timelimit')
            lim['memory'] = lim.pop('memlimit')

        await db.execute('UPDATE problem SET "limit" = $1 WHERE pro_id = $2;', json.dumps(limit), pro_id)
    await db.execute('''ALTER TABLE problem ALTER COLUMN "limit" SET DEFAULT '{"default": {"time": 0, "memory":0}}'::jsonb;''')

    await db.execute("ALTER TABLE test_config RENAME COLUMN weight TO rate;")
    await db.execute("ALTER TABLE test_config RENAME COLUMN test_idx TO subtask_id;")
    await db.execute("ALTER TABLE test RENAME COLUMN test_idx TO subtask_id;")
    await db.execute("ALTER TABLE test RENAME COLUMN runtime TO time;")
    await db.execute("ALTER TABLE challenge_state RENAME COLUMN runtime TO time;")
    await db.execute('ALTER TABLE problem RENAME COLUMN "limit" TO limits;')
    await db.execute("ALTER TABLE problem RENAME COLUMN check_type TO checker_type;")

    await db.execute("ALTER INDEX challenge_state_idx_chal_id RENAME TO total_result_idx_chal_id;")
    await db.execute("ALTER TABLE challenge_state RENAME CONSTRAINT challenge_state_forkey_chal_id TO total_result_forkey_chal_id;")
    await db.execute("ALTER TABLE challenge_state RENAME CONSTRAINT challenge_state_unique_chal_id TO total_result_unique_chal_id;")


    await db.execute("ALTER INDEX test_config_pkey RENAME TO subtask_config_pkey;")
    await db.execute("ALTER INDEX test_pkey RENAME TO subtask_result_pkey;")
    await db.execute("ALTER INDEX test_idx_acct_id RENAME TO subtask_result_idx_acct_id;")
    await db.execute("ALTER TABLE test RENAME CONSTRAINT test_forkey_acct_id TO subtask_result_forkey_acct_id;")
    await db.execute("ALTER TABLE test RENAME CONSTRAINT test_forkey_chal_id TO subtask_result_forkey_chal_id;")
    await db.execute("ALTER TABLE test RENAME CONSTRAINT test_forkey_pro_id_test_idx TO subtask_forkey_pro_id_subtask_id;")

    await db.execute("DROP TRIGGER trigger_delete_challenge_state ON test;")
    await db.execute("ALTER TABLE challenge_state RENAME TO total_result;")
    await db.execute("ALTER TABLE test_config RENAME TO subtask_config;")
    await db.execute("ALTER TABLE test RENAME TO subtask_result;")

    await db.execute(
    '''
        CREATE OR REPLACE FUNCTION delete_total_result()
        RETURNS TRIGGER AS $$
        BEGIN
            DELETE FROM total_result WHERE chal_id = OLD.chal_id;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    await db.execute(
    '''
        CREATE TRIGGER trigger_delete_total_result
        AFTER DELETE ON subtask_result
        FOR EACH ROW
        EXECUTE FUNCTION delete_total_result();
    ''')

    await db.execute(
    '''
    CREATE OR REPLACE FUNCTION update_total_result(p_chal_id INTEGER)
    RETURNS VOID AS $$
    BEGIN
        WITH challenge_summary AS (
            SELECT
                t.chal_id,
                MAX(t.state) AS max_state,
                SUM(t.time) AS total_time,
                SUM(t.memory) AS total_memory,
                SUM(
                    CASE
                        WHEN (t.state = 1 OR t.state = 2) AND t.rate IS NOT NULL THEN t.rate -- special score
                        WHEN t.state = 1 AND t.rate IS NULL THEN tvr.rate -- default score
                        ELSE 0
                    END
                ) AS total_rate
            FROM subtask_result t
            LEFT JOIN test_valid_rate tvr ON t.pro_id = tvr.pro_id AND t.subtask_id = tvr.test_idx
            WHERE t.chal_id = p_chal_id
            GROUP BY t.chal_id
        )
        INSERT INTO total_result (chal_id, state, time, memory, rate)
        SELECT
            chal_id,
            max_state,
            total_time,
            total_memory,
            total_rate
        FROM challenge_summary
        ON CONFLICT (chal_id) DO UPDATE
        SET
            state = EXCLUDED.state,
            time = EXCLUDED.time,
            memory = EXCLUDED.memory,
            rate = EXCLUDED.rate
        WHERE
            total_result.state != EXCLUDED.state OR
            total_result.time != EXCLUDED.time OR
            total_result.memory != EXCLUDED.memory OR
            total_result.rate != EXCLUDED.rate;

        RETURN;
    END;
    $$ LANGUAGE plpgsql;
    '''
    )

    log_type = [
        ('manage.contest.remove', 'manage.board.remove'),
        ('manage.contest.set', 'manage.board.update'),
        ('manage.pro.update.tests.updateweight', 'manage.pro.update.tests.updaterate'),
        ('manage.pro.update.conf', 'manage.pro.update.pro'),
        ('manage.pro.update.tests.preview', 'manage.pro.update.testdata.preview'),
        ('manage.pro.update.tests.preview.failed', 'manage.pro.update.testdata.preview.failed'),
        ('manage.pro.update.tests.addsinglefile', 'manage.pro.update.testdata.addsinglefile'),
        ('manage.pro.update.tests.addsinglefile.failed', 'manage.pro.update.testdata.addsinglefile.failed'),
        ('manage.pro.update.tests.updatesinglefile', 'manage.pro.update.testdata.updatesinglefile'),
        ('manage.pro.update.tests.updatesinglefile.failed', 'manage.pro.update.testdata.updatesinglefile.failed'),
        ('manage.pro.update.tests.deletesinglefile', 'manage.pro.update.testdata.deletesinglefile'),
        ('manage.pro.update.tests.deletesinglefile.failed', 'manage.pro.update.testdata.deletesinglefile.failed'),
        ('manage.pro.update.tests.addtaskgroup', 'manage.pro.update.tests.addsubtask'),
        ('manage.pro.update.tests.addtaskgroup.failed', 'manage.pro.update.tests.addsubtask.failed'),
        ('manage.pro.update.tests.deletetaskgroup', 'manage.pro.update.tests.deletesubtask'),
        ('manage.pro.update.tests.addetetaskgroup.failed', 'manage.pro.update.tests.deletesubtask.failed'),
        ('contest.manage.chal.rechal', 'manage.chal.rechal'),
    ]

    for old_log_type, new_log_type in log_type:
        await db.execute('UPDATE log SET type=$1 WHERE type=$2;', new_log_type, old_log_type)

    await rs.delete("prolist")
