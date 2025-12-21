async def dochange(db, rs):
    """Add metadata column to testdata and subtask_config tables for system test support."""

    # Add metadata column to testdata table
    print("Adding metadata column to testdata table...")
    await db.execute(
        "ALTER TABLE testdata ADD COLUMN metadata jsonb DEFAULT '{}'::jsonb NOT NULL;"
    )

    # Add metadata column to subtask_config table
    print("Adding metadata column to subtask_config table...")
    await db.execute(
        "ALTER TABLE subtask_config ADD COLUMN metadata jsonb DEFAULT '{}'::jsonb NOT NULL;"
    )

    print("System test metadata columns migration completed!")
