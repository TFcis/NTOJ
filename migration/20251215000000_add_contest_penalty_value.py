async def dochange(db, rs):
    # Add penalty_value column to contest table for ICPC scoring
    await db.execute(
        "ALTER TABLE public.contest ADD COLUMN penalty_value integer NOT NULL DEFAULT 20;"
    )
    await rs.delete("contest")
