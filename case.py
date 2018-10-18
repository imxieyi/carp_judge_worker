import os
import json
import shutil
import random
import string
import docker
import asyncio
from io import BytesIO
from zipfile import ZipFile
from errors import *

IMAGE_NAME = 'carp_judge'
TMP_DIR = '/tmp/carp_judge'
SANDBOX_TMP_DIR = '/workspace'

if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR, exist_ok=True)

_docker_client = docker.from_env()


def id_generator(size=8, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class CARPCase:
    def __init__(self, zip_data):
        self._zipdata = zip_data
        self._tempdir = os.path.join(TMP_DIR, id_generator())
        self._container = None

    def __enter__(self):
        # Load data
        zipdata = BytesIO(self._zipdata)
        zipfile = ZipFile(zipdata)
        filelist = zipfile.namelist()
        # Load config.json
        if 'config.json' not in filelist:
            raise ArchiveError('No config.json in archive')
        with zipfile.open('config.json') as file:
            config = json.loads(file.read())
        self.entry = config['entry']
        self.data = config['data']
        self.parameters = config['parameters']
        self.time = config['time']
        self.memory = config['memory']
        self.cpu = config['cpu']
        # Find program and data
        program_files = []
        data_files = []
        for item in filelist:
            if item.startswith('program/') and item != 'program/':
                program_files.append(item)
            elif item.startswith('data/') and item != 'data/':
                data_files.append(item)
        if ('program/' + self.entry) not in program_files:
            raise ArchiveError('Entry file not found: ' + self.entry)
        if self.data != '' and ('data/' + self.data) not in data_files:
            raise ArchiveError('Data file not found: ' + self.data)
        # Prepare sandbox
        progdir = os.path.join(self._tempdir, 'program')
        if not os.path.exists(progdir):
            os.makedirs(progdir)
        datadir = os.path.join(self._tempdir, 'data')
        if not os.path.exists(datadir):
            os.makedirs(datadir)
        for item in (program_files + data_files):
            with open(os.path.join(self._tempdir, item), 'wb') as outfile:
                with zipfile.open(item) as file:
                    data = file.read()
                    data.replace(b'\r', b'')
                    outfile.write(data)
        # Prepare arguments
        self.parameters = self.parameters.replace('$data', os.path.join(SANDBOX_TMP_DIR, 'data', self.data))
        self.parameters = self.parameters.replace('$time', str(self.time))
        self.parameters = self.parameters.replace('$cpu', str(self.cpu))
        self.parameters = self.parameters.replace('$memory', str(self.memory))
        return self

    async def run(self):
        if self._container is not None:
            raise SandboxError('Container already exists!')
        # Build command
        command = 'python3 {program} {parameters}'.format(
            program=os.path.join(SANDBOX_TMP_DIR, 'program', self.entry),
            parameters=self.parameters
        )
        self._container = _docker_client.containers.run(
            image=IMAGE_NAME,
            command=command,
            auto_remove=True,
            detach=True,
            nano_cpus=self.cpu * 1000000000,
            mem_limit=str(self.memory) + 'm',
            memswap_limit=str(self.memory) + 'm',
            oom_kill_disable=False,
            pids_limit=64,
            network_mode='none',
            stop_signal='SIGKILL',
            volumes={self._tempdir: {'bind': SANDBOX_TMP_DIR, 'mode': 'rw'}},
            stdout=True,
            stderr=True
        )
        timeremains = float(self.time)
        while timeremains > 0. and self._container.status == 'running':
            await asyncio.sleep(0.5)
            timeremains -= 0.5
        if self._container.status == 'running':
            self._container.kill()
            timedout = True
        else:
            timedout = False
        logs = self._container.logs(
            stdout=True,
            stderr=True
        )
        return timedout, logs, self._container.wait()

    def close(self):
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
