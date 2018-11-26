import os
import json
import shutil
import random
import string
import docker
import asyncio
import aiohttp
from io import BytesIO
from zipfile import ZipFile
import msg_types

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
    def __init__(self, zip_data, cid=0, ctype=msg_types.CARP, dataset=json.loads('{}')):
        self.cid = cid
        self.ctype = ctype
        self._zipdata = zip_data
        self._dataset = dataset
        self._tempdir = os.path.join(TMP_DIR, id_generator())
        self._container = None
        self._stdout = b''
        self._stderr = b''
        self._timedout = False
        self._statuscode = -1

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
        if 'data' in config:
            self.data = config['data']
        else:
            self.data = ''
        if 'network' in config:
            self.network = config['network']
        else:
            self.network = ''
        if 'seeds' in config:
            self.seeds = config['seeds']
        else:
            self.seeds = ''
        if 'seedCount' in config:
            self.seedCount = config['seedCount']
            if self.seedCount <= 0:
                raise ArchiveError('Invalid seedCount')
        else:
            self.seedCount = 0
        if 'model' in config:
            self.model = config['model']
        else:
            self.model = ''
        self.parameters = config['parameters']
        self.time = config['time']
        self.memory = config['memory']
        self.cpu = config['cpu']
        if 'seed' in config:
            self.seed = config['seed']
        if self.entry == '':
            raise ArchiveError('No entry point')
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
        if self.network != '' and ('data/' + self.network) not in data_files:
            raise ArchiveError('Network file not found: ' + self.network)
        if self.seeds != '' and ('data/' + self.seeds) not in data_files:
            raise ArchiveError('Seeds file not found: ' + self.seeds)
        # Prepare sandbox
        progdir = os.path.join(self._tempdir, 'program')
        if not os.path.exists(progdir):
            os.makedirs(progdir)
        datadir = os.path.join(self._tempdir, 'data')
        if not os.path.exists(datadir):
            os.makedirs(datadir)
        for item in (program_files + data_files):
            new_path = os.path.join(self._tempdir, item)
            # check dir or not
            if item[-1] == '/':
                os.makedirs(new_path)
                continue
            outpath = os.path.join(self._tempdir, item)
            os.makedirs(os.path.dirname(outpath), exist_ok=True)
            with open(outpath, 'wb') as outfile:
                with zipfile.open(item) as file:
                    data = file.read()
                    data.replace(b'\r', b'')
                    if item.endswith('.py'):
                        data.replace('sys.exit(0)', 'print(\'sys.exit(0) removed\')')
                        data.replace('exit(0)', 'print(\'exit(0) removed\')')
                    if item.endswith(self.entry):
                        data += b'\nprint(\'Fast exit injected by judge_worker\')' \
                                b'\nimport sys' \
                                b'\nsys.stdout.flush()' \
                                b'\nsys.stderr.flush()' \
                                b'\nimport os' \
                                b'\nos._exit(0)\n'
                    outfile.write(data)
        # Prepare arguments
        if self.data:
            self.parameters = self.parameters.replace('$data', os.path.join(SANDBOX_TMP_DIR, 'data', self.data))
        if self.network:
            self.parameters = self.parameters.replace('$network', os.path.join(SANDBOX_TMP_DIR, 'data', self.network))
        if self.seeds:
            self.parameters = self.parameters.replace('$seeds', os.path.join(SANDBOX_TMP_DIR, 'data', self.seeds))
        if self.seedCount:
            self.parameters = self.parameters.replace('$seedCount', str(self.seedCount))
        if self.model:
            self.parameters = self.parameters.replace('$model', self.model)
        self.parameters = self.parameters.replace('$time', str(self.time))
        self.parameters = self.parameters.replace('$cpu', str(self.cpu))
        self.parameters = self.parameters.replace('$memory', str(self.memory))
        if 'seed' in config:
            self.parameters = self.parameters.replace('$seed', str(self.seed))
        return self

    async def _wait_container(self):
        with aiohttp.UnixConnector('/var/run/docker.sock') as conn:
            timeout = aiohttp.ClientTimeout(total=self.time)
            async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
                async with session.post('http://localhost/containers/{}/wait'.format(self._container.id)) as resp:
                    try:
                        return False, await resp.json()
                    except asyncio.TimeoutError:
                        return True, None

    async def run(self, stdout=True, stderr=True):
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
            auto_remove=False,
            detach=True,
            read_only=True,
            nano_cpus=self.cpu * 1000000000,
            mem_limit=str(self.memory) + 'm',
            memswap_limit=str(self.memory) + 'm',
            oom_kill_disable=False,
            pids_limit=64,
            network_mode='none',
            stop_signal='SIGKILL',
            volumes={self._tempdir: {'bind': SANDBOX_TMP_DIR, 'mode': 'ro'}},
            working_dir=os.path.join(SANDBOX_TMP_DIR, 'program'),
            tmpfs={
                '/tmp': 'rw,size=1g',
                '/run': 'rw,size=1g'
            },
            stdout=stdout,
            stderr=stderr,
            log_config={
                'config': {
                    'mode': 'non-blocking',
                    'max-size': '1m',
                    'max-file': '2'
                }
            }
        )
        try:
            timedout, response = await self._wait_container()
            statuscode = -1
            if timedout:
                try:
                    self._container.kill()
                except:
                    pass
            else:
                statuscode = response['StatusCode']
            if stdout:
                _stdout = self._container.logs(
                    stdout=True,
                    stderr=False
                )
            else:
                _stdout = b''
            if stderr:
                _stderr = self._container.logs(
                    stdout=False,
                    stderr=True
                )
            else:
                _stderr = b''
        finally:
            self._container.remove(force=True)
        self._stdout = _stdout
        self._stderr = _stderr
        self._timedout = timedout
        self._statuscode = statuscode
        return timedout, _stdout, _stderr, statuscode

    async def check_imp_result(self):
        if self._timedout:
            return False, 0., 'Timed out'
        if self._statuscode != 0:
            return False, 0., 'Exit code is not zero'
        if not self._stdout:
            return False, 0., 'No output'
        stdout = self._stdout.decode('utf8')
        network = self._dataset['network']
        # TODO: check imp result
        return True, 0., 'Solution accepted'

    def close(self):
        try:
            self._container.remove(force=True)
        except:
            pass
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
