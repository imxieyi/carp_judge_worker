
'''
ISE
'''
import random
import logging
import numpy as np


class Estimater(object):
    '''
    Class to solve the problem 01
    '''

    def __init__(self, graph, seeds, model, solution_receiver, processid, random_s=None, sim_round=10000):
        model_map = {'IC': self.ic_simulate, 'LT': self.lt_simulate}
        if random_s:
            random.seed(random_s)
        self.graph = graph
        self.seeds = seeds
        self.nodes = self.graph.vertices()
        self.max_node = max(self.nodes)
        self.model = model_map[model]
        self.solution_receiver = solution_receiver
        self.processid = processid
        self.cur_avg = 0
        self.cur_round = 0
        self.sim_round = sim_round

    def get_result(self):
        '''
        get the influenece valuence
        '''
        # logging.debug("get result")
        
        sum_activated = 0
        for _ in range(self.sim_round):
            estimated_spread = self.model()
            sum_activated += estimated_spread
        self.cur_avg = (self.cur_round * self.cur_avg +
                        sum_activated / self.sim_round) / (self.cur_round + 1)
        self.cur_round += 1
        logging.debug("id %d, avg %f", self.processid, self.cur_avg)
        self.solution_receiver.put([self.processid, self.cur_avg])

    def estimate(self):
        '''
        see the termination type to decide
        '''
        self.get_result()


    def ic_simulate(self):
        '''
        use the independent Cascade model
        '''
        active_array = np.zeros((self.max_node + 1))
        logging.debug(self.seeds)
        next_layer = list(self.seeds)
        while next_layer:
            active_array[next_layer] = 1
            new_layer = list()
            for node in next_layer:
                for linked_node, value in self.graph[node].items():
                    if active_array[linked_node] == 0 and random.random() < value['weight']:
                        new_layer.append(linked_node)
            # print(activated)
            next_layer = new_layer
        return np.sum(active_array)

    def lt_simulate(self):
        '''
        use the independent Cascade model
        '''
        activated = set(self.seeds)
        threshold = dict()
        for node in self.graph.vertices():
            threshold[node] = random.random()

        def get_nextround(changed_vertices):
            '''
            get influenced vertices
            '''
            next_round = set()
            for vertex in changed_vertices:
                next_round = set.union(
                    next_round, set(self.graph[vertex].keys()))
            return next_round
        next_round = get_nextround(activated)
        while next_round:
            changed_vertices = set()
            for node in next_round:
                indicator = 0
                for linked_node, value in self.graph.inverse[node].items():
                    if linked_node in activated:
                        indicator += value['weight']
                if indicator > threshold[node]:
                    changed_vertices.add(node)
                    activated.add(node)
            next_round = get_nextround(changed_vertices)
        return len(activated)
