async def dochange(db, _):
    await db.execute(
        "CREATE INDEX testdata_result_pro_id_testdata_id_foreign_key_index ON testdata_result(pro_id, id);"
    )
    await db.execute(
        "CREATE INDEX subtask_result_pro_id_subtask_id_foreign_key_index ON subtask_result(pro_id, subtask_id);"
    )
