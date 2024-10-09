class ProClassConst:
    OFFICIAL_PUBLIC = 0
    OFFICIAL_HIDDEN = 1
    USER_PUBLIC = 2
    USER_HIDDEN = 3


async def dochange(db, rs):
    # NOTE: rename
    await db.execute("ALTER TABLE pubclass RENAME TO proclass")
    await db.execute("ALTER SEQUENCE pubclass_pubclass_id_seq RENAME TO proclass_proclass_id_seq")
    await db.execute("ALTER TABLE proclass RENAME COLUMN pubclass_id TO proclass_id")
    await db.execute("ALTER TABLE proclass RENAME CONSTRAINT pubclass_pkey TO proclass_pkey")

    await db.execute('''ALTER TABLE proclass ADD "desc" text DEFAULT \'\'''')
    await db.execute("ALTER TABLE proclass ADD acct_id integer")
    await db.execute('ALTER TABLE proclass ADD "type" integer')
    await db.execute(
        "ALTER TABLE proclass ADD CONSTRAINT proclass_forkey_acct_id FOREIGN KEY (acct_id) REFERENCES account(acct_id) ON DELETE CASCADE"
    )
    await db.execute('UPDATE proclass SET "type" = $1', ProClassConst.OFFICIAL_PUBLIC)
    await db.execute('ALTER TABLE proclass ALTER COLUMN "type" SET NOT NULL')
