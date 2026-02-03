async def dochange(db, rs):
    await db.execute(
    '''
        CREATE TABLE contest_acct_pro_joints (
            contest_id integer NOT NULL,
            acct_id integer NOT NULL,
            pro_id integer NOT NULL
        );
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_acct_pro_joints ADD CONSTRAINT contest_acct_pro_joints_forkey_contest_id
            FOREIGN KEY (contest_id) REFERENCES contest(contest_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_acct_pro_joints ADD CONSTRAINT contest_acct_pro_joints_forkey_acct_id
            FOREIGN KEY (acct_id) REFERENCES account(acct_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_acct_pro_joints ADD CONSTRAINT contest_acct_pro_joints_forkey_contest_user_acct_id
            FOREIGN KEY (contest_id, acct_id) REFERENCES contest_users(contest_id, acct_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_acct_pro_joints ADD CONSTRAINT contest_acct_pro_joints_forkey_pro_id
            FOREIGN KEY (pro_id) REFERENCES problem(pro_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        CREATE INDEX contest_acct_pro_joints_contest_acct_idx
        ON contest_acct_pro_joints(contest_id, acct_id);
    '''
    )
    await rs.delete('contest')

    await db.execute('DROP TABLE IF EXISTS contest_ip_joints;')
