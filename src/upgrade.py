#!/bin/python3

import os
import shutil
import datetime
import tempfile
import subprocess

with tempfile.TemporaryDirectory() as working_path:
    subprocess.run(['git', 'clone', 'https://github.com/TFcis/NTOJ', f'{working_path}/NTOJ'])

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
    # TODO: We should run database backup
    shutil.copy('config.py', f'{working_path}/NTOJ/migration/config.py')
    subprocess.run([f'$HOME/.local/bin/poetry -P {os.getcwd()} run python3 {working_path}/NTOJ/migration/migration.py'],
                cwd=f'{working_path}/NTOJ/migration',
                shell=True)
