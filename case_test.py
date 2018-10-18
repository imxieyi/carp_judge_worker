import asyncio
import unittest
from case import CARPCase


class TestAPlusBCase(unittest.TestCase):

    def setUp(self):
        with open('./examples/data_example.zip', 'rb') as zipfile:
            self.case = CARPCase(zipfile.read()).__enter__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def test_config(self):
        self.assertEqual('aplusb.py', self.case.entry)
        self.assertEqual('test.dat', self.case.data)
        self.assertEqual('/workspace/data/test.dat -t 10 -c 8 -m 256', self.case.parameters)
        self.assertEqual(10, self.case.time)
        self.assertEqual(256, self.case.memory)
        self.assertEqual(8, self.case.cpu)

    def test_run(self):
        async def run_main():
            timedout, logs, exitcode = await self.case.run()
            logs = logs.decode('utf8')
            print(logs)
            self.assertEqual(0, exitcode)
            self.assertEqual('35', logs.strip())
        self.loop.run_until_complete(asyncio.wait([run_main()]))

    def tearDown(self):
        self.case.close()
        self.loop.close()


class TestForkBombCase(unittest.TestCase):

    def setUp(self):
        with open('./examples/data_forkbomb.zip', 'rb') as zipfile:
            self.case = CARPCase(zipfile.read()).__enter__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def test_run(self):
        async def run_main():
            timedout, logs, exitcode = await self.case.run()
            logs = logs.decode('utf8')
            print(logs)
            self.assertTrue(timedout)
            self.assertEqual(-1, exitcode)
        self.loop.run_until_complete(asyncio.wait([run_main()]))

    def tearDown(self):
        self.case.close()
        self.loop.close()


class TestOOMCase(unittest.TestCase):

    def setUp(self):
        with open('./examples/data_oom.zip', 'rb') as zipfile:
            self.case = CARPCase(zipfile.read()).__enter__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def test_run(self):
        async def run_main():
            timedout, logs, exitcode = await self.case.run()
            logs = logs.decode('utf8')
            print(logs)
            self.assertTrue('MemoryError' in logs)
            self.assertFalse(timedout)
            self.assertEqual(1, exitcode)
        self.loop.run_until_complete(asyncio.wait([run_main()]))

    def tearDown(self):
        self.case.close()
        self.loop.close()


if __name__ == '__main__':
    unittest.main()
