# -*- coding: utf-8 -*-
import random
import types
import time
import sys
import io
import multiprocessing as mp
import math
import numpy
from itertools import chain

from concurrent.futures import ProcessPoolExecutor
import asyncio

class Sampler(mp.Process):
    def __init__(self, graph, type, inQ, outQ, random_seed):
        super(Sampler, self).__init__(target=self.start)
        self.graph = graph
        self.type = type
        self.inQ = inQ
        self.outQ = outQ
        self.types = {'IC': self.one_IC_sample, 'LT': self.one_LT_sample}
        self.func = self.types[self.type]
        self.random_seed = random_seed
        
    def run(self):
        random.seed(self.random_seed)
        while True:
            task = self.inQ.get()
            if task is None:
                break
            sample = self.single_sample(task[0], task[1])
            self.outQ.put(sample)
        
    def single_sample (self,seeds, r):
        sample = []
        activate(seeds, self.graph.status)
        for i in range(r):
            sample.append(self.func(seeds))
        inactivate(seeds, self.graph.status)
        return sample
        
    def one_IC_sample (self, seeds):
        neighbours = self.graph.neighbour
        status = list(self.graph.status)
        active_set = seeds
        influence_area = len(seeds)
        while active_set:
            new_active_set = []
            for vertex in active_set:
                for neighbour, weight in neighbours[vertex]:
                    if not status[neighbour] and random.random() <= weight:
                        status[neighbour] = True
                        new_active_set.append(neighbour)
            influence_area += len(new_active_set)
            active_set = new_active_set
        return influence_area

    def one_LT_sample (self, seeds):
        neighbours = self.graph.neighbour
        last_neighbours = self.graph.last_neighbour
        status = list(self.graph.status)
        active_set = seeds
        influence_area = len(seeds)
        gate = [random.random() for i in range(self.graph.vnum)]
        while active_set:
            new_active_set = []
            for vertex in active_set:
                for neighbour, p in neighbours[vertex]:
                    if not status[neighbour]:
                        impact = 0
                        for last_neighbour, weight in last_neighbours[neighbour]:
                            if status[last_neighbour]:
                                impact += weight
                        if impact >= gate[neighbour]:
                            status[neighbour] = True
                            new_active_set.append(neighbour)
            influence_area += len(new_active_set)
            active_set = new_active_set
        return influence_area
    
class ISE(object):
    def __init__(self, graph, type, mnum):
        self.graph = graph
        self.type = type
        self.mnum = mnum
        self.result = 0
        
    def start_simpler(self):
        self.workers = []
        for i in range(self.mnum):
            worker = Sampler(self.graph, self.type, mp.Queue(), mp.Queue(), random.random())
            self.workers.append(worker)
            worker.start()
            
    def finish(self):
        for w in self.workers:
            w.inQ.put(None)
        for w in self.workers:
            w.join()
        return self.result
        
    def multi_sample (self, seeds, r):
        result = []
        average_work = int(math.ceil(float(r) / (self.mnum)))
        for w in self.workers:
            w.inQ.put((seeds, average_work))
        for w in self.workers:
            result += w.outQ.get()
        return result

    def sample_mean (self, seeds, r):
        return numpy.mean(self.multi_sample(seeds, r))

    def Testing (self, seeds, r):
        starttime = time.time()
        icsum = self.sample_mean(seeds, r)
        parttime = time.time()
        self.result = icsum
        
class Graph(object):
    def __init__ (self, vnum, enum):
        self.vnum = vnum
        self.enum = enum
        self.num = 0
        self.map = {}
        self.anti_map = {}
        self.neighbour = [set() for i in range(vnum)]
        self.last_neighbour = [set() for i in range(vnum)]
        self.status = [False for i in range(vnum)]
        self.nonactive = set()
    
    def add_edge (self, vi, vj, weight):
        if vi in self.map:
            vi = self.map[vi]
        else:
            self.map[vi] = self.num
            self.anti_map[self.num] = vi
            vi = self.num
            self.num += 1
        if vj in self.map:
            vj = self.map[vj]
        else:
            self.map[vj] = self.num
            self.anti_map[self.num] = vj
            vj = self.num
            self.num += 1
            
        self.neighbour[vi].add((vj, weight))
        self.last_neighbour[vj].add((vi, weight))
        self.nonactive.add(vi)
        self.nonactive.add(vj)
    
    def pruning (self):
        delete = set()
        for vertex in self.nonactive:
            if not self.neighbour[vertex]:
                delete.add(vertex)
        self.nonactive = self.nonactive.difference(delete)

def read_network(fd):
    line = fd.readline().split()
    vnum = int(line[0])
    enum = int(line[1])
    graph = Graph(vnum, enum)
    lines = fd.readlines()
    for line in lines:
        if line:
            e = line.split()
            graph.add_edge(int(e[0]), int(e[1]), float(e[2]))
    graph.pruning()
    return graph

def read_seed (fd, seed_count, graph):
    seeds = []
    lines = fd.readlines()
    for line in lines:
        if line:
            try:
                seeds.append(graph.map[int(line)])
            except ValueError:
                err = SolutionError()
                err.set_reason("Vaule Error! Not int.")
                raise err
            except KeyError:
                err = SolutionError()
                err.set_reason("Node not in the network.")
                raise err
    if len(seeds) != seed_count:
        err = SolutionError()
        err.set_reason("Wrong number of seeds")
        raise err
    return seeds

def chunks(arr, m):
    n = int(math.ceil(len(arr) / float(m)))
    arr = list(arr)
    return [arr[i:i + n] for i in range(0, len(arr), n)]

def activate(verties, status):
    if isinstance(verties, int):
        status[verties] = True
    else:
        for vertex in verties:
            status[vertex] = True

def inactivate(verties, status):
    if isinstance(verties, int):
        status[verties] = False
    else:
        for vertex in verties:
            status[vertex] = False

async def estimate_async(network, seeds, seed_count, model='IC', multiprocess=8, random_seed='88010123'):
    # Can set executor to None if a default has been set for loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(ProcessPoolExecutor(), estimate, network, seeds, seed_count, model, multiprocess, random_seed)
    return result

def estimate(network, seeds, seed_count, model='IC', multiprocess=2, random_seed='sustech'):
    '''
    network: string
    seeds: string
    '''
    networkio = io.StringIO(network)
    seedsio = io.StringIO(seeds)
    random.seed(random_seed)
    graph = read_network(networkio)
    seeds = read_seed(seedsio, seed_count, graph)
    r = 10000
    workstation = ISE(graph, model, multiprocess)
    workstation.start_simpler()
    workstation.Testing(seeds, r)
    result = workstation.finish()
    return result

class SolutionError(Exception):
    def __init__(self):
        super(SolutionError, self).__init__()
        self.reason = ""

    def set_reason(self, reason):
        self.reason = reason

    def get_reason(self):
        return self.reason
    