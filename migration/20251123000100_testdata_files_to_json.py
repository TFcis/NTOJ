import json

async def dochange(db, rs):
    # Step 1: Add new files column
    print("Adding files column to testdata table...")
    await db.execute("ALTER TABLE testdata ADD COLUMN files jsonb DEFAULT '{}'::jsonb NOT NULL;")

    # Step 2: Migrate existing data
    print("Migrating testdata files to JSON format...")
    testdatas = await db.fetch('SELECT pro_id, id, inputfile, outputfile FROM testdata;')

    for testdata in testdatas:
        pro_id = testdata['pro_id']
        testdata_id = testdata['id']

        # Build files JSON for Batch type
        files = {
            'input': testdata['inputfile'],
            'output': testdata['outputfile'],
        }

        await db.execute(
            'UPDATE testdata SET files = $1 WHERE pro_id = $2 AND id = $3;',
            json.dumps(files),
            pro_id,
            testdata_id
        )

        print(f"Migrated testdata pro_id={pro_id}, id={testdata_id}")

    # Step 3: Drop old columns
    print("Dropping old columns...")
    await db.execute('ALTER TABLE testdata DROP COLUMN inputfile;')
    await db.execute('ALTER TABLE testdata DROP COLUMN outputfile;')

    print("Testdata table migration completed!")
