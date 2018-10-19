import json
import logging
import coloredlogs
import asyncio
import base64
import websockets
import config
import msg_types
import traceback
from case import CARPCase
from errors import *

coloredlogs.install(level=config.log_level)

send_queue = asyncio.Queue()
receive_queue = asyncio.Queue()
judge_queue = asyncio.Queue()


async def __message_handler():
    while True:
        message = await receive_queue.get()
        try:
            obj = json.loads(message)
            mtype = obj['type']
            logging.debug('Message type: ' + str(mtype))
            if mtype == msg_types.CASE_DATA:
                await judge_queue.put(obj['payload'])
        except Exception as e:
            logging.error(e)


async def __judge_worker():
    while True:
        obj = await judge_queue.get()
        try:
            jid = obj['id']
            data = base64.b85decode(obj['data'])
            logging.info('Enter judge for id: ' + str(jid))
            with CARPCase(data, jid) as case:
                logging.info('Start judge for id: ' + str(jid))
                timedout, stdout, stderr, exitcode = await case.run(stdout=True, stderr=False)
                logging.info('Judge finished: {}, {}'.format(timedout, exitcode))
                stdout_overflow = False
                stderr_overflow = False
                stdout = stdout.decode('utf8')
                stderr = stderr.decode('utf8')
                if len(stdout) > config.log_limit_bytes:
                    stdout = stdout[-config.log_limit_bytes:]
                    stdout_overflow = True
                if len(stderr) > config.log_limit_bytes:
                    stderr = stderr[-config.log_limit_bytes:]
                    stderr_overflow = True
                ret = {
                    'type': msg_types.CASE_RESULT,
                    'payload': {
                        'timedout': timedout,
                        'stdout': stdout,
                        'stdout_overflow': stdout_overflow,
                        'stderr': stderr,
                        'stderr_overflow': stderr_overflow,
                        'exitcode': exitcode
                    }
                }
                await send_queue.put(json.dumps(ret))
        except ArchiveError as e:
            logging.error(e)
        except Exception as e:
            logging.error(e)
            traceback.print_exc()


async def __message_dispatcher(ws):
    while True:
        message = await send_queue.get()
        await ws.send(message)


async def __message_receiver(ws):
    async for message in ws:
        await receive_queue.put(message)


async def __fake_server():
    await asyncio.sleep(1.0)
    with open('./examples/data_example.zip', 'rb') as zipfile:
        data = {
            'type': msg_types.CASE_DATA,
            'payload': {
                'id': 1000,
                'data': base64.b85encode(zipfile.read()).decode('ascii')
            }
        }
        await send_queue.put(json.dumps(data))


async def main():
    while True:
        try:
            logging.info('Connecting to ' + config.server_url)
            async with websockets.connect(config.server_url) as ws:
                logging.info('Connected')
                # TODO: Auth with server
                handler_task = asyncio.ensure_future(__message_handler())
                dispatcher_task = asyncio.ensure_future(__message_dispatcher(ws))
                receiver_task = asyncio.ensure_future(__message_receiver(ws))
                judge_task = asyncio.ensure_future(__judge_worker())
                asyncio.get_event_loop().create_task(__fake_server())
                done, pending = await asyncio.wait(
                    [handler_task, dispatcher_task, receiver_task, judge_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
        except Exception as e:
            logging.error(e)
        finally:
            logging.error('Disconnected, retry after 5 secs')
            await asyncio.sleep(5.0)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
