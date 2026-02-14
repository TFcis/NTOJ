import json
import logging
import datetime

logger = logging.getLogger("tornado.application")

class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat(timespec="seconds")

        return super().default(o)

class LogService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        LogService.inst = self

    async def add_log(self, message, log_type=None, params=None):
        if isinstance(params, dict):
            params = json.dumps(params, ensure_ascii=False, cls=_Encoder)

        message = str(message)

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        INSERT INTO "log"
                        ("message", "type", "params")
                        VALUES ($1, $2, $3) RETURNING "log_id";
                    ''',
                    message,
                    log_type,
                    params,
                )
        except Exception as e:
            logger.error(f"Error adding log: {e}", exc_info=True)
            logger.error(f"Log details: message={message}, log_type={log_type}, params={params}")
            return ('Eunk', 'Unknown error'), None
        return None, result[0]['log_id']

    async def view_log(self, log_id: int):
        try:
            async with self.db.acquire() as con:
                res = await con.fetch('SELECT log_id, "type", message, "timestamp", params FROM log WHERE log_id = $1', int(log_id))
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
                    'params': params
                }
        except Exception as e:
            logger.error(f"Error viewing log {log_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None


    async def list_log(self, off, num, log_type=None):
        try:
            async with self.db.acquire() as con:
                if log_type is None:
                    result = await con.fetch(
                        '''
                            SELECT "log"."log_id", "log"."message", "log"."timestamp"
                            FROM "log"
                            ORDER BY "log"."timestamp" DESC OFFSET $1 LIMIT $2;
                        ''',
                        off,
                        num,
                    )

                    count = await con.fetch('SELECT COUNT(*) FROM "log"')
                    count = count[0]['count']

                else:
                    result = await con.fetch(
                        '''
                            SELECT "log"."log_id", "log"."message", "log"."timestamp"
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

                loglist = []
                for log_id, message, timestamp in result:
                    loglist.append(
                        {
                            'log_id': log_id,
                            'message': message,
                            'timestamp': timestamp,
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
