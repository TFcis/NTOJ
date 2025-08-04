import json

checker_type_convert_table = {
    0: 1, # NOTE: CHECKER_DIFF 2 CheckerType.DIFF
    1: 2, # NOTE: CHECKER_DIFF_STRICT 2 CheckerType.DIFF_STRICT
    2: 4, # NOTE: CHECKER_DIFF_FLOAT 2 CheckerType.DIFF_FLOAT6
    3: 8, # NOTE: CHECKER_IOREDIR 2 CheckerType.IOREDIR
    4: 6, # NOTE: CHECKER_CMS 2 CheckerType.CMS_TPS_TESTLIB
}

compiler_type_convert_table = {
    'gcc': 1,
    'clang': 2,
    'g++': 3,
    'clang++': 4,
    'rustc': 5,
    'python3': 6,
    'java': 7,
    'asmc': 8,
    'asmcpp': 9,
}

default_allow_compilers = list(map(str, compiler_type_convert_table.values()))
default_has_grader_allow_compilers = list(map(int, [compiler_type_convert_table['g++'], compiler_type_convert_table['clang++']]))

async def dochange(db, rs):
    await db.execute(
    '''
        ALTER TABLE ONLY testdata
            ADD CONSTRAINT testdata_unique_key UNIQUE(pro_id, id);
    ''')

    # NOTE: add testdata_result TABLE
    await db.execute(
    '''
        CREATE TABLE testdata_result (
            chal_id integer NOT NULL,
            pro_id integer NOT NULL,
            id integer NOT NULL,
            state integer NOT NULL DEFAULT 101, -- NotStart
            time bigint DEFAULT 0,
            memory bigint DEFAULT 0,
            rate NUMERIC(10, 3) NOT NULL DEFAULT 0,
            message character varying NOT NULL DEFAULT ''::character varying,
            message_type integer NOT NULL DEFAULT 1 -- MessageType.NONE
        );
    ''')

    await db.execute(
    '''
        ALTER TABLE ONLY testdata_result
            ADD CONSTRAINT testdata_result_forkey_pro_id FOREIGN KEY (pro_id) REFERENCES problem(pro_id) ON DELETE CASCADE;
    ''')
    await db.execute(
    '''
        ALTER TABLE ONLY testdata_result
            ADD CONSTRAINT testdata_result_forkey_chal_id FOREIGN KEY (chal_id) REFERENCES challenge(chal_id) ON DELETE CASCADE;
    ''')
    await db.execute(
    '''
        ALTER TABLE ONLY testdata_result
            ADD CONSTRAINT testdata_result_forkey_testdata FOREIGN KEY (pro_id, id) REFERENCES testdata(pro_id, id) ON DELETE CASCADE;
    ''')


    await db.execute('ALTER TABLE problem RENAME COLUMN is_makefile TO has_grader;')
    await db.execute("ALTER TABLE total_result ADD COLUMN message character varying DEFAULT ''::character varying NOT NULL;")
    await db.execute("ALTER TABLE total_result ADD COLUMN message_type integer DEFAULT 1 NOT NULL;") # NOTE: MessageType.NONE

    # NOTE: problem add allow_compilers column
    await db.execute(f'''ALTER TABLE problem ADD COLUMN allow_compilers integer[] DEFAULT '{{ {','.join(default_allow_compilers)} }}'::integer[] NOT NULL;''')
    await db.execute('UPDATE problem SET allow_compilers = $1 WHERE has_grader=true;', default_has_grader_allow_compilers)

    # NOTE: contest comvert allow_compilers from str to IntEnum
    contest_allow_compilers: dict[int, set[int]] = {}
    res = await db.fetch('SELECT contest_id, allow_compilers FROM contest;')
    for contest_id, allow_compilers in res:
        contest_allow_compilers[contest_id] = set()
        allow_compilers: list[str]

        for compiler in allow_compilers:
            contest_allow_compilers[contest_id].add(compiler_type_convert_table[compiler])

    await db.execute('ALTER TABLE contest ALTER COLUMN allow_compilers DROP NOT NULL;')
    await db.execute('UPDATE contest SET allow_compilers = NULL;')
    await db.execute('ALTER TABLE contest ALTER COLUMN allow_compilers DROP DEFAULT;')
    await db.execute('ALTER TABLE contest ALTER COLUMN allow_compilers TYPE integer[] using allow_compilers::integer[];')
    await db.execute(f'''ALTER TABLE contest ALTER COLUMN allow_compilers SET DEFAULT '{{ {','.join(default_allow_compilers)} }}'::integer[]''')

    for contest_id, allow_compilers in contest_allow_compilers.items():
        await db.execute('UPDATE contest SET allow_compilers = $1 WHERE contest_id = $2;', allow_compilers, contest_id)
    await db.execute('ALTER TABLE contest ALTER COLUMN allow_compilers SET NOT NULL;')

    # NOTE:
    problems_subtasks: dict[int, dict] = {}
    res = await db.fetch('SELECT pro_id FROM problem;')
    for pro_id in res:
        res2 = await db.fetch('SELECT id FROM testdata WHERE pro_id=$1 ORDER BY id;', pro_id['pro_id'])
        testdatas = [testdata_id['id'] for testdata_id in res2]
        res2 = await db.fetch('SELECT subtask_id FROM subtask_config WHERE pro_id=$1 ORDER BY subtask_id', pro_id['pro_id'])
        subtasks = [subtask_id['subtask_id'] for subtask_id in res2]
        problems_subtasks[pro_id['pro_id']] = {
            'testdatas': testdatas,
            'subtasks': subtasks
        }

    # NOTE: Move subtask_config.rate to subtask_result.rate when subtask_result.rate IS NULL AND subtask_result.state = STATE_AC
    await db.execute(
        '''
        UPDATE subtask_result SET rate = subtask_config.rate
        FROM subtask_config
        WHERE subtask_result.pro_id = subtask_config.pro_id
            AND subtask_result.subtask_id = subtask_config.subtask_id
            AND subtask_result.rate IS NULL AND subtask_result.state = 1; -- STATE_AC
        '''
    )
    # NOTE: Set subtask_result.rate to 0 when subtask_result.rate IS NULL AND subtask_result.state != STATE_AC
    await db.execute(
        '''
        UPDATE subtask_result SET rate = 0
        FROM subtask_config
        WHERE subtask_result.pro_id = subtask_config.pro_id
            AND subtask_result.subtask_id = subtask_config.subtask_id
            AND subtask_result.rate IS NULL AND subtask_result.state != 1; -- STATE_AC
        '''
    )
    # NOTE: Move ce message to total_result
    await db.execute(
        '''
        UPDATE total_result SET message = subtask_result.response
        FROM subtask_result
        WHERE total_result.chal_id = subtask_result.chal_id
            AND subtask_result.state IN (9, 10) AND subtask_result.subtask_id = 0; -- STATE_CE, STATE_CLE
        '''
    )
    # NOTE: In old TOJ, NotStart means there are no any row in subtask_result and total_result, it ONLY appear in challenge.
    # NOTE: Insert NotStart testdata_result
    res = await db.fetch('SELECT chal_id, pro_id FROM challenge;')
    for chal_id, pro_id in res:
        r = await db.fetch('SELECT chal_id FROM total_result WHERE chal_id = $1;', chal_id)
        insert = []
        for testdata_id in problems_subtasks[pro_id]['testdatas']:
            insert.append((chal_id, pro_id, testdata_id))
        await db.executemany('INSERT INTO testdata_result (chal_id, pro_id, id) VALUES ($1, $2, $3);', insert)
        if len(r) == 0:  # NOTE: NotStart
            insert = []
            for subtask_id in problems_subtasks[pro_id]['subtasks']:
                insert.append((chal_id, pro_id, subtask_id))
            await db.executemany('INSERT INTO subtask_result (chal_id, pro_id, id, acct_id) VALUES ($1, $2, $3, 0);', insert)
            await db.execute('INSERT INTO total_result (chal_id) VALUES ($1);', chal_id)

    await db.execute('ALTER TABLE subtask_result ALTER COLUMN rate SET DEFAULT 0;')
    await db.execute('ALTER TABLE subtask_result ALTER COLUMN rate SET NOT NULL;')
    await db.execute('ALTER TABLE subtask_result ALTER COLUMN state SET DEFAULT 101 -- NotStart;')
    await db.execute('ALTER TABLE subtask_result ALTER COLUMN state SET NOT NULL;')

    await db.execute('ALTER TABLE total_result ALTER COLUMN rate SET DEFAULT 0;')
    await db.execute('ALTER TABLE total_result ALTER COLUMN rate SET NOT NULL;')
    await db.execute('ALTER TABLE total_result ALTER COLUMN state SET DEFAULT 101 -- NotStart;')
    await db.execute('ALTER TABLE total_result ALTER COLUMN state SET NOT NULL;')

    # NOTE: convert problem limits compiler from str to IntEnum
    # NOTE: add output limit config
    # NOTE: memory limit unit from bytes to kib
    res = await db.fetch('SELECT pro_id, limits FROM problem;')
    for pro_id, limits in res:
        limits = json.loads(limits)
        new_limits = {}

        for compiler, lim in limits.items():
            lim['output'] = 65536
            lim['memory'] = lim['memory'] // 1024

            if compiler != "default":
                new_limits[compiler_type_convert_table[compiler]] = lim
            else:
                new_limits['default'] = lim

        await db.execute('UPDATE problem SET "limits" = $1 WHERE pro_id = $2;', json.dumps(new_limits), pro_id)
    await db.execute('''ALTER TABLE problem ALTER COLUMN limits SET DEFAULT '{"default":{"time":1000,"memory":65536,"output":65536}}'::jsonb;''')

    # NOTE: total_result and subtask_result memory unit from bytes to kib
    await db.execute('UPDATE total_result SET memory = memory / 1024;')
    await db.execute('UPDATE subtask_result SET memory = memory / 1024;')

    # NOTE: convert problem checker_type from old style to new style
    res = await db.fetch('SELECT pro_id, checker_type FROM problem;')
    for pro_id, checker_type in res:
        await db.execute('UPDATE problem SET checker_type = $1 WHERE pro_id=$2', checker_type_convert_table[checker_type], pro_id)
    await db.execute('ALTER TABLE problem ALTER COLUMN checker_type SET DEFAULT 1;') # NOTE: CheckerType.DIFF

    await db.execute("ALTER TABLE problem ADD COLUMN userprog_compile_args character varying DEFAULT ''::character varying;")
    await db.execute('ALTER TABLE problem ADD COLUMN summary_type integer DEFAULT 1 NOT NULL;') # NOTE: SummaryType.GROUP_MIN
    await db.execute('ALTER TABLE problem ADD COLUMN summary_compiler integer;')
    await db.execute("ALTER TABLE problem ADD COLUMN summary_compile_args character varying DEFAULT ''::character varying;")
    await db.execute('ALTER TABLE problem ADD COLUMN checker_compiler integer;')
    await db.execute("ALTER TABLE problem ADD COLUMN checker_compile_args character varying DEFAULT ''::character varying;")

    # NOTE: convert challenge compiler_type from str to IntEnum
    for old_compiler_type, new_compiler_type in compiler_type_convert_table.items():
        await db.execute('UPDATE challenge SET compiler_type = $1 WHERE compiler_type = $2', str(new_compiler_type), old_compiler_type)
    await db.execute('ALTER TABLE challenge ALTER COLUMN compiler_type TYPE integer USING compiler_type::integer;')

    # NOTE: convert account last_compiler from str to IntEnum
    for old_compiler_type, new_compiler_type in compiler_type_convert_table.items():
        await db.execute('UPDATE account SET last_compiler = $1 WHERE last_compiler = $2', str(new_compiler_type), old_compiler_type)
    await db.execute(f'''ALTER TABLE account ALTER COLUMN last_compiler SET DEFAULT {compiler_type_convert_table['g++']};''')
    await db.execute('ALTER TABLE account ALTER COLUMN last_compiler TYPE integer USING last_compiler::integer;')

    await db.execute('DROP MATERIALIZED VIEW test_valid_rate;')
    await db.execute('ALTER TABLE subtask_result DROP COLUMN response;')
    await db.execute('ALTER TABLE subtask_result DROP COLUMN "timestamp";')
    await db.execute('ALTER TABLE subtask_result DROP COLUMN acct_id;')
    await db.execute('DROP TRIGGER trigger_delete_total_result ON subtask_result;')
    await db.execute('DROP FUNCTION IF EXISTS delete_challenge_state();')
    await db.execute('DROP FUNCTION IF EXISTS update_total_result();')
    await db.execute('DROP FUNCTION IF EXISTS update_challenge_state();')
    await db.execute('DROP FUNCTION delete_total_result();')

    await rs.delete("rate")
    await rs.delete("pro_rate")
