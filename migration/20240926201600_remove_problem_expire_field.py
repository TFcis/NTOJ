async def dochange(db, rs):
    await db.execute('DROP MATERIALIZED VIEW test_valid_rate;')
    await db.execute('ALTER TABLE problem DROP COLUMN expire;')
    await db.execute(
        '''
            CREATE MATERIALIZED VIEW public.test_valid_rate AS
            SELECT test_config.pro_id,
               test_config.test_idx,
               count(DISTINCT account.acct_id) AS count,
               test_config.weight AS rate
              FROM (((public.test
                JOIN public.account ON ((test.acct_id = account.acct_id)))
                JOIN public.problem ON (((((test.pro_id = problem.pro_id)) AND (test.state = 1)))))
                RIGHT JOIN public.test_config ON (((test.pro_id = test_config.pro_id) AND (test.test_idx = test_config.test_idx))))
            GROUP BY test_config.pro_id, test_config.test_idx, test_config.weight
            WITH NO DATA;
        ''')
    await db.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')
    await rs.delete('prolist')
