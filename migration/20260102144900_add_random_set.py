import json

async def dochange(db, rs):
    await db.execute("ALTER TABLE contest ADD COLUMN start_ip character varying(64) DEFAULT '0.0.0.0';")
    await db.execute("ALTER TABLE contest ADD COLUMN end_ip character varying(64) DEFAULT '0.0.0.0';")

    await db.execute(
    '''
        CREATE TABLE contest_ip_joints (
            contest_id integer NOT NULL,
            ip character varying(64) NOT NULL,
            pro_id integer NOT NULL
        );
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_ip_joints ADD CONSTRAINT contest_problem_joints_forkey_contest_id
            FOREIGN KEY (contest_id) REFERENCES contest(contest_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_ip_joints ADD CONSTRAINT contest_problem_joints_forkey_pro_id
            FOREIGN KEY (pro_id) REFERENCES problem(pro_id) ON DELETE CASCADE;
    '''
    )
