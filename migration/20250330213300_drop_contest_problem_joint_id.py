async def dochange(db, _):
    await db.execute('ALTER TABLE contest_problem_joints ADD COLUMN "order" INTEGER;')
    await db.execute('''
    WITH ranked AS (
        SELECT
            contest_id,
            pro_id,
            ROW_NUMBER() OVER (PARTITION BY contest_id ORDER BY id) - 1 AS new_order
        FROM contest_problem_joints
    )
    UPDATE contest_problem_joints AS cpj
    SET "order" = ranked.new_order
    FROM ranked
    WHERE cpj.contest_id = ranked.contest_id
    AND cpj.pro_id = ranked.pro_id;
    ''')

    await db.execute('ALTER TABLE contest_problem_joints DROP COLUMN id;')
    await db.execute('DROP SEQUENCE contest_problem_joints_id_seq;')
    await db.execute('ALTER TABLE contest_problem_joints ALTER COLUMN "order" SET NOT NULL;')
