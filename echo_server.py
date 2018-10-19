#!/usr/bin/env python

# WS server example

import asyncio
import websockets


async def hello(websocket, path):
    async for message in websocket:
        await websocket.send(message)

if __name__ == '__main__':
    start_server = websockets.serve(hello, 'localhost', 8765)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
