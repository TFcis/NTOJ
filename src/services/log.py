import json
import logging
import datetime
import decimal
from dataclasses import is_dataclass, asdict

logger = logging.getLogger("tornado.application")

class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat(timespec="seconds")

        if is_dataclass(o):
            logger.warning(f"Serializing dataclass {o} using asdict()")
            return asdict(o)

        if isinstance(o, decimal.Decimal):
            logger.warning(f"Serializing Decimal {o} as string")
            return str(o)

        return super().default(o)

class LogService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        LogService.inst = self

    async def add_log(self, message, log_type=None, params=None, handler=None):
        if isinstance(params, dict):
            params = json.dumps(params, ensure_ascii=False, cls=_Encoder)

        message = str(message)

        # Extract context from handler if provided
        operator_acct_id = None
        operator_ip = None
        contest_id = 0

        if handler is not None:
            if hasattr(handler, 'acct') and handler.acct and handler.acct.acct_id != 0:
                operator_acct_id = handler.acct.acct_id
            if hasattr(handler, 'request'):
                operator_ip = handler.request.remote_ip
            if hasattr(handler, 'contest') and handler.contest:
                contest_id = handler.contest.contest_id

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        INSERT INTO "log"
                        ("message", "type", "params", "operator_acct_id", "operator_ip", "contest_id")
                        VALUES ($1, $2, $3, $4, $5, $6) RETURNING "log_id";
                    ''',
                    message,
                    log_type,
                    params,
                    operator_acct_id,
                    operator_ip,
                    contest_id,
                )
        except Exception as e:
            logger.error(f"Error adding log: {e}", exc_info=True)
            logger.error(f"Log details: message={message}, log_type={log_type}, params={params}")
            return ('Eunk', 'Unknown error'), None
        return None, result[0]['log_id']

    async def view_log(self, log_id: int):
        try:
            async with self.db.acquire() as con:
                res = await con.fetch(
                    'SELECT log_id, "type", message, "timestamp", params, operator_acct_id, operator_ip, contest_id FROM log WHERE log_id = $1',
                    int(log_id)
                )
                if len(res) == 0:
                    return ('Enoext', 'Log not found'), None
                res = res[0]

                params = '{}'
                if res['params']:
                    params = json.dumps(json.loads(res['params']), indent=4)

                return None, {
                    'log_id': res['log_id'],
                    'log_type': res['type'],
                    'message': res['message'],
                    'timestamp': res['timestamp'],
                    'params': params,
                    'operator_acct_id': res['operator_acct_id'],
                    'operator_ip': res['operator_ip'],
                    'contest_id': res['contest_id'],
                }
        except Exception as e:
            logger.error(f"Error viewing log {log_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None


    async def list_log(self, off, num, log_type=None, contest_id=None):
        try:
            async with self.db.acquire() as con:
                if log_type is None and contest_id is None:
                    result = await con.fetch(
                        '''
                            SELECT "log"."log_id", "log"."message", "log"."timestamp", "log"."operator_acct_id", "log"."contest_id"
                            FROM "log"
                            ORDER BY "log"."timestamp" DESC OFFSET $1 LIMIT $2;
                        ''',
                        off,
                        num,
                    )

                    count = await con.fetch('SELECT COUNT(*) FROM "log"')
                    count = count[0]['count']

                elif log_type is not None and contest_id is None:
                    result = await con.fetch(
                        '''
                            SELECT "log"."log_id", "log"."message", "log"."timestamp", "log"."operator_acct_id", "log"."contest_id"
                            FROM "log"
                            WHERE "log"."type" = $1
                            ORDER BY "log"."timestamp" DESC OFFSET $2 LIMIT $3;
                        ''',
                        log_type,
                        off,
                        num,
                    )

                    count = await con.fetch('SELECT COUNT(*) FROM "log" WHERE "log"."type" = $1', log_type)
                    count = count[0]['count']

                elif log_type is None and contest_id is not None:
                    result = await con.fetch(
                        '''
                            SELECT "log"."log_id", "log"."message", "log"."timestamp", "log"."operator_acct_id", "log"."contest_id"
                            FROM "log"
                            WHERE "log"."contest_id" = $1
                            ORDER BY "log"."timestamp" DESC OFFSET $2 LIMIT $3;
                        ''',
                        contest_id,
                        off,
                        num,
                    )

                    count = await con.fetch('SELECT COUNT(*) FROM "log" WHERE "log"."contest_id" = $1', contest_id)
                    count = count[0]['count']

                else:  # Both log_type and contest_id are provided
                    result = await con.fetch(
                        '''
                            SELECT "log"."log_id", "log"."message", "log"."timestamp", "log"."operator_acct_id", "log"."contest_id"
                            FROM "log"
                            WHERE "log"."type" = $1 AND "log"."contest_id" = $2
                            ORDER BY "log"."timestamp" DESC OFFSET $3 LIMIT $4;
                        ''',
                        log_type,
                        contest_id,
                        off,
                        num,
                    )

                    count = await con.fetch(
                        'SELECT COUNT(*) FROM "log" WHERE "log"."type" = $1 AND "log"."contest_id" = $2',
                        log_type,
                        contest_id
                    )
                    count = count[0]['count']

                loglist = []
                for log_id, message, timestamp, operator_acct_id, contest_id_val in result:
                    loglist.append(
                        {
                            'log_id': log_id,
                            'message': message,
                            'timestamp': timestamp,
                            'operator_acct_id': operator_acct_id,
                            'contest_id': contest_id_val,
                        }
                    )
        except Exception as e:
            logger.error(f"Error listing logs: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        return None, {'loglist': loglist, 'lognum': count}

    async def get_log_type(self):
        try:
            async with self.db.acquire() as con:
                result = await con.fetch('SELECT DISTINCT "type" FROM "log" ORDER BY "type"')

                log_type = [type['type'] for type in result]
        except Exception as e:
            logger.error(f"Error fetching log types: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        return None, log_type
