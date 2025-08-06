async def dochange(db, _):
    await db.execute('CREATE INDEX testdata_chal_id_testdata_id ON testdata_result USING btree (chal_id, id);')

