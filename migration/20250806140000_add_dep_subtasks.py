async def dochange(db, rs):
    await db.execute(f"ALTER TABLE subtask_config ADD COLUMN dep_subtasks integer[] DEFAULT '{{}}'::integer[] NOT NULL;")
