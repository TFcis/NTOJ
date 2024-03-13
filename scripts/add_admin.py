import argparse
import asyncio
import base64
import logging
import os
import shutil

import asyncpg
import bcrypt
from redis import asyncio as aioredis


class UserConst:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 8
    NAME_MAX = 27  # 3227
    NAME_MIN = 1

    ACCTTYPE_KERNEL = 0


class GroupConst:
    KERNEL_GROUP = 'kernel'


async def sign_up(mail, pw, name, db, rs):
    tmp_len = len(mail)
    if tmp_len < UserConst.MAIL_MIN:
        return 'Emailmin', None
    if tmp_len > UserConst.MAIL_MAX:
        return 'Emailmax', None

    tmp_len = len(pw)
    if tmp_len < UserConst.PW_MIN:
        return 'Epwmin', None
    if tmp_len > UserConst.PW_MAX:
        return 'Epwmax', None

    if not (any(char.islower() for char in pw) or any(char.isupper() for char in pw)):
        return 'Epwcomplex', None

    if not any(char.isdigit() for char in pw):
        return 'Epwcomplex', None

    tmp_len = len(name)
    if tmp_len < UserConst.NAME_MIN:
        return 'Enamemin', None
    if tmp_len > UserConst.NAME_MAX:
        return 'Enamemax', None
    del tmp_len

    # hash password
    hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))

    try:
        async with db.acquire() as con:
            result = await con.fetch(
                '''
                    INSERT INTO "account"
                    ("mail", "password", "name", "acct_type", "class", "group")
                    VALUES ($1, $2, $3, $4, $5, $6) RETURNING "acct_id";
                ''',
                mail,
                base64.b64encode(hpw).decode('utf-8'),
                name,
                UserConst.ACCTTYPE_KERNEL,
                [1],
                GroupConst.KERNEL_GROUP,
            )

    except asyncpg.IntegrityConstraintViolationError:
        return 'Eexist', None

    if result.__len__() != 1:
        return 'Eexist', None

    # refresh redis cache
    await rs.delete('acctlist')
    return None, result[0]['acct_id']


def copyfile(source, target):
    source = os.path.join(*source)
    target = os.path.join(*target)
    if not os.path.exists(target):
        shutil.copyfile(source, target)


"""
mail
username
password
DBNAME_OJ
DBUSER_OJ
DBPW_OJ
"""

args_parser = argparse.ArgumentParser(description='add_admin')
args_parser.add_argument('username', type=str, help='admin username')
args_parser.add_argument('password', type=str, help='admin password')
args_parser.add_argument('mail', type=str, help='admin mail')
args_parser.add_argument('config_path', type=str, help='ntoj config path')
args_parser.add_argument('-d', '--debug', action='store_const', dest='loglevel', const=logging.DEBUG)
args_parser.set_defaults(loglevel=logging.INFO)

args = args_parser.parse_args()
copyfile((args.config_path,), ('./config.py',))

logging.basicConfig(level=args.loglevel, format='%(asctime)s %(levelname)s %(message)s')

import config

db = asyncio.get_event_loop().run_until_complete(
    asyncpg.create_pool(database=config.DBNAME_OJ, user=config.DBUSER_OJ, password=config.DBPW_OJ, host='localhost')
)
rs = aioredis.Redis(host='localhost', port=6379, db=1)
err, acct_id = asyncio.get_event_loop().run_until_complete(sign_up(args.mail, args.password, args.username, db, rs))

os.remove('./config.py')

if err == 'Eexist':
    logging.error("Mail: {args.mail} already existed!!!")

elif err in ['Emailmin', 'Emailmax']:
    logging.error("Mail is too long or too short. The range is from 1 to 1024.")

elif err in ['Epwmin', 'Epwmax']:
    logging.error("Password is too long or too short. The range is from 8 to 1024.")

elif err == 'Epwcomplex':
    logging.error("Password is too simple. Please use more complex password!!!")
    logging.error("Password must contain digit and english alphabat")

elif err in ['Enamemin', 'Enamemax']:
    logging.error("Name is too long or too short. The range is from 1 to 27.")

else:
    logging.info(f"Your admin account id is {acct_id}")
    logging.info("Add admin account successfully")
