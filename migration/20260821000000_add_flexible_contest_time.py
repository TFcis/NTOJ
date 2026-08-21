async def dochange(db, rs):
    await db.execute(
        """
        ALTER TABLE contest
            ADD COLUMN contest_time_mode INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN contest_duration INTEGER NOT NULL DEFAULT 0;

        UPDATE contest
        SET contest_duration = GREATEST(
            EXTRACT(EPOCH FROM (contest_end - contest_start))::INTEGER,
            0
        );

        ALTER TABLE contest
            ADD CONSTRAINT contest_time_mode_valid
                CHECK (contest_time_mode IN (0, 1)),
            ADD CONSTRAINT contest_duration_valid
                CHECK (contest_duration >= 0);

        CREATE TABLE contest_sessions (
            session_id BIGSERIAL PRIMARY KEY,
            contest_id INTEGER NOT NULL,
            acct_id INTEGER NOT NULL,
            session_type INTEGER NOT NULL DEFAULT 0,
            start_time TIMESTAMP WITH TIME ZONE NOT NULL,
            end_time TIMESTAMP WITH TIME ZONE NOT NULL,

            CONSTRAINT contest_sessions_contest_fkey
                FOREIGN KEY (contest_id) REFERENCES contest(contest_id)
                ON DELETE CASCADE,
            CONSTRAINT contest_sessions_account_fkey
                FOREIGN KEY (acct_id) REFERENCES account(acct_id)
                ON DELETE CASCADE,
            CONSTRAINT contest_sessions_membership_fkey
                FOREIGN KEY (contest_id, acct_id)
                REFERENCES contest_users(contest_id, acct_id)
                ON DELETE CASCADE,
            CONSTRAINT contest_sessions_type_valid
                CHECK (session_type >= 0),
            CONSTRAINT contest_sessions_time_valid
                CHECK (end_time > start_time),
            CONSTRAINT contest_sessions_unique
                UNIQUE (contest_id, acct_id, session_type)
        );

        CREATE INDEX contest_sessions_contest_type_idx
            ON contest_sessions (contest_id, session_type);

        CREATE INDEX challenge_contest_scoreboard_idx
            ON challenge (contest_id, pro_id, acct_id, timestamp);
        """
    )

    await rs.delete("contest")
    async for key in rs.scan_iter(match="contest_*_scores"):
        await rs.delete(key)
