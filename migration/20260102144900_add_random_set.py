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
