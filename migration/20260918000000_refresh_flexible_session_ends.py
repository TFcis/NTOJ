async def dochange(db, rs):
    async with db.transaction():
        await db.execute(
            """
            ALTER TABLE contest_sessions
                DROP CONSTRAINT contest_sessions_time_valid,
                ADD CONSTRAINT contest_sessions_time_valid
                    CHECK (session_type = 0 OR end_time > start_time);

            UPDATE contest_sessions AS cs
            SET end_time = LEAST(
                cs.start_time + c.contest_duration * INTERVAL '1 second',
                c.contest_end
            )
            FROM contest AS c
            WHERE cs.contest_id = c.contest_id
              AND cs.session_type = 0 AND c.contest_time_mode = 1;
            """
        )
    await rs.delete("contest")
    async for key in rs.scan_iter(match="contest_*_scores"):
        await rs.delete(key)
