import os
from typing import Optional
from app.settings import config


def read_pid_file() -> Optional[int]:
    if os.path.exists(config['pid_file']):
        with open(config['pid_file']) as file:
            return int(file.read())
    else:
        return None


def write_pid_file() -> int:
    pid = os.getpid()
    with open(config['pid_file'], 'w') as file:
        file.write(f'{pid}\n')
    return pid


def remove_pid_file() -> Optional[int]:
    pid = read_pid_file()
    if pid:
        os.remove(config['pid_file'])
    return pid
