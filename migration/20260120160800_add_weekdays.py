
async def dochange(db, rs):
    await db.execute(
    '''
        CREATE TABLE weekdays (
            "start" bigint NOT NULL unique,
            "end" bigint NOT NULL unique,
            "priority" integer NOT NULL,
            "is_weekday" boolean NOT NULL
        );
    ''')

    await db.execute(
    '''
        CREATE TABLE weekdays_fetch_status (
            "offset" integer NOT NULL
        );
    '''
    )

    # _id=1556 is 2026-01-01
    await db.execute(
    '''
        INSERT INTO weekdays_fetch_status ("offset") VALUES (1555); 
    '''
    )
