from termcolor import colored
import datetime


def dbg_print(file='', line=0, **kwargs):
    print(colored(f'time: {datetime.datetime.now()} {file}: {line} dbg: ', 'blue'), end='')

    for key, val in kwargs.items():
        print(f'{key}: {val}', end=' ')
    print('')
