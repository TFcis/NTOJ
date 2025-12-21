async def dochange(db, rs):
    """Add enable_system_test column to contest table (default False)."""

    print("Adding enable_system_test column to contest table...")
    await db.execute(
        "ALTER TABLE contest ADD COLUMN enable_system_test boolean DEFAULT FALSE NOT NULL;"
    )

    await rs.delete('contest')
    print("Contest enable_system_test column migration completed!")
