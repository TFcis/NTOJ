"""Add challenge_style column to contest_problem_joints table"""

async def dochange(db, rs):
    # Add challenge_style column with default value 1 (FULL)
    await db.execute('ALTER TABLE contest_problem_joints ADD COLUMN challenge_style INTEGER NOT NULL DEFAULT 1;')
