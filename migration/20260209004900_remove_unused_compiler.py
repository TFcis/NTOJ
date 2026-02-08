async def dochange(db, rs):
    compiler_type_convert_table = {
        'gcc': 1,
        'clang': 2,
        'g++': 3,
        'clang++': 4,
        'python3': 6,
    }
    default_allow_compilers = list(map(str, compiler_type_convert_table.values()))
    await db.execute(f'''ALTER TABLE problem ALTER COLUMN allow_compilers integer[] SET DEFAULT '{{ {','.join(default_allow_compilers)} }}'::integer[];''')
