async def dochange(db, rs):
    await db.execute('ALTER TABLE contest ADD COLUMN contest_creator INTEGER;')
    await db.execute(
    '''
        ALTER TABLE ONLY contest ADD CONSTRAINT contest_forkey_creator
            FOREIGN KEY (contest_creator) REFERENCES account(acct_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        CREATE TABLE contest_users (
            contest_id integer NOT NULL,
            acct_id integer NOT NULL,
            status integer NOT NULL
        );
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_users ADD CONSTRAINT contest_users_forkey_contest_id
            FOREIGN KEY (contest_id) REFERENCES contest(contest_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_users ADD CONSTRAINT contest_users_forkey_acct_id
            FOREIGN KEY (acct_id) REFERENCES account(acct_id) ON DELETE CASCADE;
    '''
    )

    await db.execute(
    '''
        ALTER TABLE ONLY contest_users ADD CONSTRAINT contest_users_unique_key
            UNIQUE(contest_id, acct_id);
    '''
    )

    res = await db.fetch('SELECT contest_id, admin_list, acct_list, reg_list FROM contest ORDER BY contest_id;')
    for contest_id, admin_list, acct_list, reg_list in res:
        creator = 2**31 - 1
        for acct_id in admin_list:
            await db.execute('INSERT INTO contest_users (contest_id, acct_id, status) VALUES ($1, $2, $3)', contest_id, acct_id, 3) # UserStatus.ADMIN.value)
            res = await db.fetch('SELECT acct_type FROM account WHERE acct_id = $1', acct_id)
            if int(res[0]) == 0: # UserConst.ACCTTYPE_KERNEL:
                creator = min(acct_id, creator)

        await db.execute('UPDATE contest SET contest_creator = $1 WHERE contest_id = $2', creator, contest_id)

        for acct_id in acct_list:
            await db.execute('INSERT INTO contest_users (contest_id, acct_id, status) VALUES ($1, $2, $3)', contest_id, acct_id, 2) # UserStatus.APPROVED.value)
        for acct_id in reg_list:
            await db.execute('INSERT INTO contest_users (contest_id, acct_id, status) VALUES ($1, $2, $3)', contest_id, acct_id, 1) # UserStatus.REQUESTED.value)

    await db.execute('ALTER TABLE contest ALTER COLUMN contest_creator SET NOT NULL;')

    await db.execute('ALTER TABLE contest DROP COLUMN acct_list;')
    await db.execute('ALTER TABLE contest DROP COLUMN admin_list;')
    await db.execute('ALTER TABLE contest DROP COLUMN reg_list;')

    await rs.delete('contest')
