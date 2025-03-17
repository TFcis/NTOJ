async def dochange(db, rs):
    await db.execute(
    '''
    CREATE SEQUENCE IF NOT EXISTS contest_announcement_announce_id_seq
        INCREMENT 1
        START 1
        MINVALUE 1
        MAXVALUE 9223372036854775807
        CACHE 1;
    '''
    )

    await db.execute(
    '''
        CREATE TABLE contest_announcement (
            contest_id integer NOT NULL,
            announce_id integer NOT NULL DEFAULT nextval('contest_announcement_announce_id_seq'::regclass),
            acct_id integer NOT NULL,
            subject character varying NOT NULL,
            content character varying NOT NULL,
            "timestamp" TIMESTAMP WITH TIME ZONE
        );
    ''')

    await db.execute(
    '''
        ALTER TABLE ONLY contest_announcement
            ADD CONSTRAINT contest_announcement_forkey_contest_id FOREIGN KEY (contest_id) REFERENCES contest(contest_id) ON DELETE CASCADE;
    ''')
    await db.execute(
    '''
        ALTER TABLE ONLY contest_announcement
            ADD CONSTRAINT contest_announcement_forkey_acct_id FOREIGN KEY (contest_id, acct_id) REFERENCES contest_users(contest_id, acct_id) ON DELETE CASCADE;
    ''')

    await db.execute(
    '''
    CREATE SEQUENCE IF NOT EXISTS contest_question_question_id_seq
        INCREMENT 1
        START 1
        MINVALUE 1
        MAXVALUE 9223372036854775807
        CACHE 1;
    '''
    )

    await db.execute(
    '''
        CREATE TABLE contest_question (
            contest_id integer NOT NULL,
            question_id integer NOT NULL DEFAULT nextval('contest_question_question_id_seq'::regclass),
            ask_acct_id integer NOT NULL,
            ask_subject character varying NOT NULL,
            ask_content character varying NOT NULL,
            ask_timestamp TIMESTAMP WITH TIME ZONE,

            reply_acct_id integer,
            reply_content character varying,
            reply_timestamp TIMESTAMP WITH TIME ZONE
        );
    ''')

    await db.execute(
    '''
        ALTER TABLE ONLY contest_question
            ADD CONSTRAINT contest_question_forkey_contest_id FOREIGN KEY (contest_id) REFERENCES contest(contest_id) ON DELETE CASCADE;
    ''')
    await db.execute(
    '''
        ALTER TABLE ONLY contest_question
            ADD CONSTRAINT contest_question_forkey_ask_acct_id FOREIGN KEY (contest_id, ask_acct_id) REFERENCES contest_users(contest_id, acct_id) ON DELETE CASCADE;
    ''')
    await db.execute(
    '''
        ALTER TABLE ONLY contest_question
            ADD CONSTRAINT contest_question_forkey_reply_acct_id FOREIGN KEY (contest_id, reply_acct_id) REFERENCES contest_users(contest_id, acct_id) ON DELETE CASCADE;
    ''')

    await db.execute('ALTER TABLE contest_users ADD COLUMN notification_read_count INTEGER DEFAULT 0;')
