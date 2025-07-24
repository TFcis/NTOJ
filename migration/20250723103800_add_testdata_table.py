import re
import json
import collections

def natsort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]

async def dochange(db, rs):
    await db.execute(
    '''
        CREATE TABLE testdata (
            pro_id integer NOT NULL,
            id integer NOT NULL,
            inputfile character varying NOT NULL,
            outputfile character varying NOT NULL
        );
    ''')
    await db.execute(
    '''
        ALTER TABLE ONLY testdata
            ADD CONSTRAINT testdata_forkey_pro_id FOREIGN KEY (pro_id) REFERENCES problem(pro_id) ON DELETE CASCADE;
    ''')

    await db.execute('ALTER TABLE test_config ADD COLUMN testdatas INTEGER[] NOT NULL DEFAULT \'{}\'::integer[];')

    test_configs = await db.fetch('SELECT pro_id, test_idx, metadata FROM test_config;')

    m = collections.defaultdict(set)
    m3: dict[int, dict[str, int]] = {}
    for pro_id, test_group_idx, metadata in test_configs:
        testdatas = set()
        metadata = json.loads(metadata)
        for testdata in metadata["data"]:
            m[pro_id].add(testdata)

    for pro_id, testdatas in m.items():
        m2 = {}
        for id, testdata in enumerate(sorted(testdatas, key=natsort_key)):
            m2[testdata] = id
            await db.execute('INSERT INTO testdata ("pro_id", "id", "inputfile", "outputfile") VALUES ($1, $2, $3, $4);',
                             pro_id, id, f"{testdata}.in", f"{testdata}.out")

        m3[pro_id] = m2

    for pro_id, test_group_idx, metadata in test_configs:
        testdatas = []
        metadata = json.loads(metadata)
        for testdata in metadata["data"]:
            testdatas.append(m3[pro_id][testdata])
        await db.execute("UPDATE test_config SET testdatas=$1 WHERE pro_id=$2 AND test_idx=$3", testdatas, pro_id, test_group_idx)

    await db.execute('ALTER TABLE test_config DROP COLUMN metadata;')
