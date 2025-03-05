async def dochange(db, rs):
    await db.execute(
    '''
    CREATE SEQUENCE IF NOT EXISTS contest_problem_joints_id_seq
        INCREMENT 1
        START 1
        MINVALUE 1
        MAXVALUE 9223372036854775807
        CACHE 1;
    '''
    )

    await db.execute(
    '''
        CREATE TABLE contest_problem_joints (
            id integer NOT NULL DEFAULT nextval('contest_problem_joints_id_seq'::regclass),
            contest_id integer NOT NULL,
            pro_id integer NOT NULL,
            score_type integer NOT NULL DEFAULT 0 -- IOI2017
        );
    '''
    )
    await db.execute('ALTER SEQUENCE IF EXISTS contest_problem_joints_id_seq OWNED BY contest_problem_joints.id;')

    await db.execute(
    '''
        ALTER TABLE ONLY contest_problem_joints ADD CONSTRAINT contest_problem_joints_forkey_contest_id
            FOREIGN KEY (contest_id) REFERENCES contest(contest_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_problem_joints ADD CONSTRAINT contest_problem_joints_forkey_pro_id
            FOREIGN KEY (pro_id) REFERENCES problem(pro_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_problem_joints ADD CONSTRAINT contest_problem_joints_unique_key
            UNIQUE(contest_id, pro_id);
    '''
    )

    res = await db.fetch('SELECT contest_id, pro_list FROM contest ORDER BY contest_id;')
    for contest_id, pro_list in res:
        for pro_id in pro_list:
            await db.execute('INSERT INTO contest_problem_joints (contest_id, pro_id) VALUES ($1, $2)', contest_id, pro_id)

    await db.execute('ALTER TABLE contest DROP COLUMN pro_list;')
    await rs.delete('contest')
