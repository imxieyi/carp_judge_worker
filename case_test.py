import asyncio
import unittest
import msg_types
from case import CARPCase
from ie import estimate, estimate_async, SolutionError


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
            timedout, stdout, stderr, exitcode = await self.case.run()
            stdout = stdout.decode('utf8')
            stderr = stderr.decode('utf8')
            print(stdout)
            print(stderr)
            self.assertEqual(0, exitcode)
            self.assertEqual('35', stdout.strip())
            self.assertEqual('', stderr.strip())
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
            timedout, stdout, stderr, exitcode = await self.case.run()
            stderr = stderr.decode('utf8')
            print(stderr)
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
            timedout, stdout, stderr, exitcode = await self.case.run()
            stderr = stderr.decode('utf8')
            print(stderr)
            self.assertTrue('MemoryError' in stderr)
            self.assertFalse(timedout)
            self.assertEqual(1, exitcode)
        self.loop.run_until_complete(asyncio.wait([run_main()]))

    def tearDown(self):
        self.case.close()
        self.loop.close()


class TestLogFloodCase(unittest.TestCase):

    def setUp(self):
        with open('./examples/data_outflood.zip', 'rb') as zipfile:
            self.case = CARPCase(zipfile.read()).__enter__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def test_run(self):
        async def run_main():
            timedout, stdout, stderr, exitcode = await self.case.run()
            print(len(stdout))
            print(len(stderr))
            self.assertTrue(len(stdout) + len(stderr) < 2 * 1024 * 1024)
            self.assertTrue(timedout)
        self.loop.run_until_complete(asyncio.wait([run_main()]))

    def tearDown(self):
        self.case.close()
        self.loop.close()


class TestJunkFileCase(unittest.TestCase):

    def setUp(self):
        with open('./examples/data_junkfile.zip', 'rb') as zipfile:
            self.case = CARPCase(zipfile.read()).__enter__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def test_run(self):
        async def run_main():
            timedout, stdout, stderr, exitcode = await self.case.run()
            print(len(stdout))
            print(len(stderr))
        self.loop.run_until_complete(asyncio.wait([run_main()]))

    def tearDown(self):
        self.case.close()
        self.loop.close()


class TestIMPCase(unittest.TestCase):

    def setUp(self):
        with open('./examples/data_imp.zip', 'rb') as zipfile:
            self.case = CARPCase(zipfile.read(), ctype=msg_types.IMP).__enter__()
        with open('./examples/network.txt', 'r') as network:
            self.case._dataset = {
                'network': network.read(),
                'seedCount': 5
            }
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def test_run(self):
        async def run_main():
            timedout, stdout, stderr, exitcode = await self.case.run()
            print(len(stdout))
            print(len(stderr))
            valid, influence, reason = await self.case.check_imp_result()
            print(influence)
            self.assertTrue(valid)
            self.assertEquals('Solution accepted', reason)
        self.loop.run_until_complete(asyncio.wait([run_main()]))

    def tearDown(self):
        self.case.close()
        self.loop.close()


class TestISE(unittest.TestCase):
    def test_run(self):
        with open('./examples/network.txt', 'r') as network:
            dataset = network.read()
        with open('./examples/seeds.txt', 'r') as seeds:
            seedset = seeds.read()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        async def run_main():
            result = 0
            try:
                result = await estimate_async(dataset, seedset, 2)
            except Exception as err:
                print(err)
            self.assertAlmostEqual(result, 19.21, places=1)
        self.loop.run_until_complete(asyncio.wait([run_main()]))
           

class TestISESync(unittest.TestCase):
    def test_run(self):
        with open('./examples/network.txt', 'r') as network:
            dataset = network.read()
        with open('./examples/seeds.txt', 'r') as seeds:
            seedset = seeds.read()

        try:
            result = estimate(dataset, seedset, seed_count=2, multiprocess=2)
        except SolutionError as err:
            print(err.get_reason())
            result = 0
            
        self.assertAlmostEqual(result, 19.2, places=1)

if __name__ == '__main__':
    unittest.main()
