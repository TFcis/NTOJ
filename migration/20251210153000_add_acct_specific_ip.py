import json

async def dochange(db, rs):
    # Add specific_ip column to account table
    await db.execute('ALTER TABLE public.account ADD COLUMN specific_ip character varying(64) DEFAULT \'\';')
