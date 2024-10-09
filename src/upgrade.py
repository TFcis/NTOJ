#!/bin/python3

import os
import shutil
import datetime
import tempfile
import subprocess

import config

working_directory = tempfile.TemporaryDirectory()
working_path = working_directory.name
subprocess.run(['git', 'clone', 'https://github.com/TFcis/NTOJ', f'{working_path}/NTOJ'])

cur_dir = os.getcwd()

if not os.path.exists('service-bak'):
    os.mkdir('service-bak')

bak_dir = f'service-bak/{datetime.datetime.now().isoformat()}'
if not os.path.exists(bak_dir):
    os.mkdir(bak_dir)

# backup
shutil.copy('config.py', f'{bak_dir}/config.py')
shutil.copy('fixnoeol.sh', f'{bak_dir}/fixnoeol.sh')
shutil.copy('newline.sh', f'{bak_dir}/newline.sh')
shutil.copy('server.py', f'{bak_dir}/server.py')
shutil.copy('url.py', f'{bak_dir}/url.py')
shutil.copytree('services', f'{bak_dir}/services')
shutil.copytree('handlers', f'{bak_dir}/handlers')
shutil.copytree('static', f'{bak_dir}/static')
shutil.copytree('utils', f'{bak_dir}/utils')

os.mkdir(f'{bak_dir}/web')
web_dir = config.WEB_PROBLEM_STATIC_FILE_DIRECTORY[0:-8]  # /srv/oj_web/oj/problem, remove `/problem`
shutil.copy(f'{web_dir}/index.js', f'{bak_dir}/web/index.js')
shutil.copy(f'{web_dir}/pack.js', f'{bak_dir}/web/pack.js')
shutil.copy(f'{web_dir}/index.css', f'{bak_dir}/web/index.css')
shutil.copy(f'{web_dir}/blk.css', f'{bak_dir}/web/blk.css')
shutil.copy(f'{web_dir}/challist.css', f'{bak_dir}/web/challist.css')
shutil.copy(f'{web_dir}/manage-pro.css', f'{bak_dir}/web/manage-pro.css')
shutil.copy(f'{web_dir}/pro.css', f'{bak_dir}/web/pro.css')
shutil.copy(f'{web_dir}/submit.css', f'{bak_dir}/web/submit.css')

# copy
shutil.copy(f'{working_path}/NTOJ/src/static/index.js', f'{web_dir}/index.js')
shutil.copy(f'{working_path}/NTOJ/src/static/pack.js', f'{web_dir}/pack.js')
shutil.copy(f'{working_path}/NTOJ/src/static/index.css', f'{web_dir}/index.css')
shutil.copy(f'{working_path}/NTOJ/src/static/blk.css', f'{web_dir}/blk.css')
shutil.copy(f'{working_path}/NTOJ/src/static/challist.css', f'{web_dir}/challist.css')
shutil.copy(f'{working_path}/NTOJ/src/static/manage-pro.css', f'{web_dir}/manage-pro.css')
shutil.copy(f'{working_path}/NTOJ/src/static/pro.css', f'{web_dir}/pro.css')
shutil.copy(f'{working_path}/NTOJ/src/static/submit.css', f'{web_dir}/submit.css')

shutil.copy(f'{working_path}/NTOJ/src/fixnoeol.sh', 'fixnoeol.sh')
shutil.copy(f'{working_path}/NTOJ/src/newline.sh', 'newline.sh')
shutil.copy(f'{working_path}/NTOJ/src/server.py', 'server.py')
shutil.copy(f'{working_path}/NTOJ/src/url.py', 'url.py')
# shutil.copy(f'{working_path}/NTOJ/src/config.py.example', 'config.py.example')
shutil.copytree(f'{working_path}/NTOJ/src/services', 'services', dirs_exist_ok=True)
shutil.copytree(f'{working_path}/NTOJ/src/handlers', 'handlers', dirs_exist_ok=True)
shutil.copytree(f'{working_path}/NTOJ/src/static', 'static', dirs_exist_ok=True)
shutil.copytree(f'{working_path}/NTOJ/src/utils', 'utils', dirs_exist_ok=True)

# shutil.copy(f'{working_path}/NTOJ/pyproject.toml', 'pyproject.toml')
#
# subprocess.run(['$HOME/.local/bin/poetry update'], shell=True)

# run migration
shutil.copy('config.py', f'{working_path}/NTOJ/migration/config.py')
subprocess.run([f'$HOME/.local/bin/poetry -C {os.getcwd()} run python3 {working_path}/NTOJ/migration/migration.py'],
               cwd=f'{working_path}/NTOJ/migration',
               shell=True)

working_directory.cleanup()
