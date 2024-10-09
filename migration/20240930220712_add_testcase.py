import json

async def dochange(db, rs):
    test_configs = await db.fetch('SELECT pro_id, test_idx, metadata FROM test_config;')

    for pro_id, test_group_idx, metadata in test_configs:
        metadata = json.loads(metadata)
        for i in range(len(metadata["data"])):
            metadata["data"][i] = str(metadata["data"][i])

        await db.execute('UPDATE test_config SET metadata = $1 WHERE pro_id = $2 AND test_idx = $3',
                   json.dumps(metadata), pro_id, test_group_idx)
