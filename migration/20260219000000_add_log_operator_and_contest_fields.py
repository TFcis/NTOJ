import re
import json


async def dochange(db, _):
    """Add operator_acct_id, operator_ip, and contest_id fields to log table"""

    # Add operator_acct_id column (nullable, because system operations may not have an operator)
    await db.execute(
        'ALTER TABLE log ADD COLUMN operator_acct_id INTEGER DEFAULT NULL;'
    )

    await db.execute(
        '''
        ALTER TABLE log
            ADD CONSTRAINT log_forkey_operator_acct_id
            FOREIGN KEY (operator_acct_id)
            REFERENCES account(acct_id)
            ON DELETE SET NULL;
        '''
    )

    await db.execute(
        'ALTER TABLE log ADD COLUMN operator_ip VARCHAR(64) DEFAULT NULL;'
    )

    # Add contest_id column (NOT NULL, default 0 for non-contest operations)
    await db.execute(
        'ALTER TABLE log ADD COLUMN contest_id INTEGER NOT NULL DEFAULT 0;'
    )

    await db.execute(
        'CREATE INDEX IF NOT EXISTS log_idx_log_id ON log(log_id);'
    )

    # Try to fill operator_acct_id for existing logs
    print("Attempting to populate operator_acct_id for existing logs...")

    logs = await db.fetch('SELECT log_id, message, params, type FROM log;')

    accounts = await db.fetch('SELECT acct_id, name FROM account;')
    name_to_id = {account['name']: account['acct_id'] for account in accounts}
    # Sort names by length (longest first) to avoid partial matches
    sorted_names = sorted(name_to_id.keys(), key=len, reverse=True)

    updated_count = 0
    skipped_count = 0

    for log in logs:
        log_id = log['log_id']
        message = log['message']
        params = log['params']
        log_type = log['type']
        operator_acct_id = None

        # Skip system logs (no operator)
        if log_type in ('judge.offline', 'system.startup', 'system.shutdown'):
            skipped_count += 1
            continue

        # Strategy 1: Extract from message - pattern like "#{acct_id}"
        # Example: "username(#123) sign out"
        acct_id_match = re.search(r'\(#(\d+)\)', message)
        if acct_id_match:
            operator_acct_id = int(acct_id_match.group(1))

        # Strategy 2: For "Update acct {acct_id} lastip" - the acct_id IS the operator
        if not operator_acct_id and log_type == 'acct.updateip':
            update_acct_match = re.search(r'Update acct (\d+)', message)
            if update_acct_match:
                operator_acct_id = int(update_acct_match.group(1))

        # Strategy 3: For management operations, extract from "changing the password of user #X"
        # In this case, the operator is NOT the user mentioned, need to find from message start
        if not operator_acct_id and 'user #' in message:
            # First, try to get operator name from message start
            for name in sorted_names:
                if message.startswith(name + ' '):
                    operator_acct_id = name_to_id[name]
                    break

        # Strategy 4: Extract account name from message start
        # Messages usually start with "{name} did something"
        if not operator_acct_id:
            for name in sorted_names:
                # Check if message starts with the account name
                # Use word boundary to avoid partial matches
                if message.startswith(name + ' '):
                    operator_acct_id = name_to_id[name]
                    break

        # Strategy 5: Check params for acct_id
        if not operator_acct_id and params:
            try:
                params_dict = json.loads(params) if isinstance(params, str) else params
                if isinstance(params_dict, dict):
                    # Look for common acct_id keys in params
                    if 'operator_acct_id' in params_dict:
                        operator_acct_id = params_dict['operator_acct_id']
                    elif 'acct_id' in params_dict and 'name' in params_dict:
                        # If both acct_id and name are present, likely the operator
                        operator_acct_id = params_dict['acct_id']
            except (json.JSONDecodeError, TypeError):
                pass

        # Update the log if we found an operator_acct_id
        if operator_acct_id:
            # Verify the acct_id exists
            try:
                await db.execute(
                    'UPDATE log SET operator_acct_id = $1 WHERE log_id = $2;',
                    operator_acct_id,
                    log_id
                )
                updated_count += 1
            except Exception as e:
                print(f"Error updating log_id {log_id} with operator_acct_id {operator_acct_id}: {e}")
                skipped_count += 1
        else:
            skipped_count += 1

    await db.execute(
        'CREATE INDEX log_idx_operator_acct_id ON log(operator_acct_id);'
    )

    await db.execute(
        'CREATE INDEX log_idx_contest_id ON log(contest_id);'
    )

    print(f"Successfully populated operator_acct_id for {updated_count} out of {len(logs)} existing logs.")
    print(f"Skipped {skipped_count} logs (system operations or unable to determine operator).")
