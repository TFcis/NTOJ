async def dochange(db, rs):
    await db.execute(
    '''
        CREATE OR REPLACE FUNCTION delete_challenge_state()
        RETURNS TRIGGER AS $$
        BEGIN
            DELETE FROM challenge_state WHERE chal_id = OLD.chal_id;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    await db.execute(
    '''
        CREATE TRIGGER trigger_delete_challenge_state
        AFTER DELETE ON test
        FOR EACH ROW
        EXECUTE FUNCTION delete_challenge_state();
    ''')
