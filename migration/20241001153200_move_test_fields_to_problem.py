import json

async def dochange(db, rs):
    CHECK_TYPES = {
        "diff": 0,
        "diff-strict": 1,
        "diff-float": 2,
        "ioredir": 3,
        "cms": 4
    }

    await db.execute("ALTER TABLE problem ADD check_type integer DEFAULT 0")
    await db.execute("ALTER TABLE problem ADD is_makefile boolean DEFAULT false")
    await db.execute("""
        ALTER TABLE problem ADD "limit" jsonb DEFAULT '{"default": {"timelimit": 0, "memlimit":0}}'::jsonb
    """)
    await db.execute("ALTER TABLE problem ADD chalmeta jsonb DEFAULT '{}'::jsonb")

    res = await db.fetch("SELECT pro_id FROM problem;")
    for pro in res:
        pro_id = pro['pro_id']
        limit = {
            'default': {
                'timelimit': 0,
                'memlimit': 0,
            }
        }
        f_check_type = 0
        f_is_makefile = False
        f_chalmeta = {}

        res = await db.fetch('SELECT check_type, compile_type, chalmeta, timelimit, memlimit FROM test_config WHERE pro_id = $1', pro_id)
        for check_type, compile_type, chalmeta, timelimit, memlimit in res:
            f_check_type = CHECK_TYPES[check_type]
            f_is_makefile = compile_type == 'makefile'
            f_chalmeta = json.loads(chalmeta)
            limit['default']['timelimit'] = timelimit
            limit['default']['memlimit'] = memlimit

        await db.execute("UPDATE problem SET check_type = $1, is_makefile = $2, \"limit\" = $3, chalmeta = $4 WHERE pro_id = $5",
                         f_check_type, f_is_makefile, json.dumps(limit), json.dumps(f_chalmeta), pro_id)


    await db.execute('ALTER TABLE test_config DROP COLUMN check_type;')
    await db.execute('ALTER TABLE test_config DROP COLUMN score_type;')
    await db.execute('ALTER TABLE test_config DROP COLUMN compile_type;')
    await db.execute('ALTER TABLE test_config DROP COLUMN chalmeta;')
    await db.execute('ALTER TABLE test_config DROP COLUMN timelimit;')
    await db.execute('ALTER TABLE test_config DROP COLUMN memlimit;')
