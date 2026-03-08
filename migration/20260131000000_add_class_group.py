async def dochange(db, rs):
    await db.execute('''
        CREATE SEQUENCE class_group_group_id_seq
            INCREMENT 1
            START 1
            MINVALUE 1
            MAXVALUE 9223372036854775807
            CACHE 1;
    ''')

    await db.execute('''
        CREATE TABLE class_group (
            group_id INTEGER NOT NULL DEFAULT nextval('class_group_group_id_seq'::regclass),
            year INTEGER NOT NULL,
            semester SMALLINT NOT NULL,
            class_number SMALLINT,
            custom_name VARCHAR(128) DEFAULT '',
            ip_range_start VARCHAR(64) DEFAULT '',
            ip_range_end VARCHAR(64) DEFAULT '',
            ip_login_enabled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (group_id)
        );
    ''')

    await db.execute('ALTER SEQUENCE class_group_group_id_seq OWNED BY class_group.group_id;')

    await db.execute('''
        CREATE TABLE class_group_member (
            group_id INTEGER NOT NULL,
            acct_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (group_id, acct_id),
            FOREIGN KEY (group_id) REFERENCES class_group(group_id) ON DELETE CASCADE,
            FOREIGN KEY (acct_id) REFERENCES account(acct_id) ON DELETE CASCADE
        );
    ''')

    await db.execute('CREATE INDEX idx_class_group_year_semester ON class_group(year, semester);')
    await db.execute('CREATE INDEX idx_class_group_class_number ON class_group(class_number);')
    await db.execute('CREATE INDEX idx_class_group_member_acct ON class_group_member(acct_id);')
    await db.execute('CREATE INDEX idx_class_group_member_group ON class_group_member(group_id);')
