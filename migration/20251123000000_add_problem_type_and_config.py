import json

async def dochange(db, rs):
    # Step 1: Add new columns
    print("Adding problem_type and config columns...")
    await db.execute('ALTER TABLE problem ADD COLUMN problem_type integer DEFAULT 1 NOT NULL;')  # Default to BATCH = 1
    await db.execute("ALTER TABLE problem ADD COLUMN config jsonb DEFAULT '{}'::jsonb NOT NULL;")

    # Step 2: Migrate existing data to config json
    print("Migrating existing problem data to config json...")
    problems = await db.fetch('SELECT pro_id, allow_compilers, userprog_compile_args, checker_type, checker_compiler, checker_compile_args, summary_type, summary_compiler, summary_compile_args, has_grader, chalmeta FROM problem;')

    for pro in problems:
        pro_id = pro['pro_id']

        # Build config JSON for Batch type
        config = {
            'chalmeta': json.loads(pro['chalmeta']) if pro['chalmeta'] else '',
            'userprog_compile_args': pro['userprog_compile_args'] if pro['userprog_compile_args'] else '',
            'checker_type': pro['checker_type'],
            'checker_compiler': pro['checker_compiler'],
            'checker_compile_args': pro['checker_compile_args'] if pro['checker_compile_args'] else '',
            'summary_type': pro['summary_type'],
            'summary_compiler': pro['summary_compiler'],
            'summary_compile_args': pro['summary_compile_args'] if pro['summary_compile_args'] else '',
            'has_grader': pro['has_grader'],
            'allow_compilers': pro['allow_compilers'] if pro['allow_compilers'] else [],
        }

        await db.execute(
            'UPDATE problem SET config = $1 WHERE pro_id = $2;',
            json.dumps(config),
            pro_id
        )

        print(f"Migrated problem #{pro_id}")

    # Step 3: Drop old columns
    print("Dropping old columns...")
    await db.execute('ALTER TABLE problem DROP COLUMN allow_compilers;')
    await db.execute('ALTER TABLE problem DROP COLUMN userprog_compile_args;')
    await db.execute('ALTER TABLE problem DROP COLUMN checker_type;')
    await db.execute('ALTER TABLE problem DROP COLUMN checker_compiler;')
    await db.execute('ALTER TABLE problem DROP COLUMN checker_compile_args;')
    await db.execute('ALTER TABLE problem DROP COLUMN summary_type;')
    await db.execute('ALTER TABLE problem DROP COLUMN summary_compiler;')
    await db.execute('ALTER TABLE problem DROP COLUMN summary_compile_args;')
    await db.execute('ALTER TABLE problem DROP COLUMN has_grader;')
    await db.execute('ALTER TABLE problem DROP COLUMN chalmeta;')

    # Step 4: Clear cache
    await rs.delete('prolist')

    print("Problem table migration completed!")
