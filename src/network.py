import numpy as np

from random import random

from sklearn.metrics.pairwise import pairwise_distances

from classification import get_basis, LinearClassifier
from utils import compute_adjacencies, partition

class Node():

    def __init__(self, k, sample, labels, test_sample=None, test_labels=None):
        self.id = k
        self.d = sample.shape[1] 
        self.sample = sample
        self.labels = labels
        self.test_sample = test_sample
        self.test_labels = test_labels
        self.confidence = 1
        self.sum_similarities = 1
        self.clf = None
        self.alpha = None

    def predict(self, sample):
        if self.clf is None:
            p = np.sign(np.dot(self.get_predictions(sample), self.alpha + self.alpha0))
            p[p==0] = 1
            return p
        return self.clf.predict(sample) 

    def init_matrices(self, base_clfs, alpha=None, alpha0=None):
        # set weak classifiers
        self.n = len(base_clfs)
        self.base_clfs = base_clfs

        # set alpha and A
        if alpha is None:
            alpha = np.zeros((self.n, 1))

        if alpha0 is None:
            alpha0 = np.zeros((self.n, 1))
        
        self.set_margin_matrix()
        self.set_alpha(alpha, alpha0)

    def compute_weights(self, temp=1, distr=True):

        w = np.exp(-np.dot(self.margin, self.alpha + self.alpha0) / temp)

        if distr:
            w = np.nan_to_num(w / np.sum(w))
        return w

    def get_neighbors_alphas(self):
        nei_alpha = np.vstack([n.alpha for n in self.neighbors])
        return nei_alpha

    def get_predictions(self, sample):
        """ get a prediction per weak classifier """
        return np.hstack([c.predict(sample)[:, None] for c in self.base_clfs])

    def set_neighbors(self, neighbors, sim=None):
        self.neighbors = neighbors
        self.sim = sim

    def reset_neighbors(self, nodes, adj_matrix):

        self.neighbors = []
        self.sim = []

        for j, a in enumerate(adj_matrix[self.id]):
            if a != 0:
                self.neignbors.append(nodes[j])
                self.sim.append(similarities[self.id][j])

        n.sum_similarities = sum(self.sim)

    def set_margin_matrix(self):
        # set margin matrix A
        self.margin = self.get_predictions(self.sample) * self.labels[:, np.newaxis]
        assert self.margin.shape == (len(self.sample), len(self.base_clfs)), self.margin.shape

    def set_alpha(self, alpha=None, alpha0=None):

        if alpha is not None:
            self.alpha = alpha
        if alpha0 is not None:
            self.alpha0 = alpha0

    def set_test_set(self, x, y):
        self.test_sample = x
        self.test_labels = y

def get_alphas(nodes):

    alphas = [n.alpha for n in nodes]

    return alphas

def compute_alpha_diff(nodes):
    return pairwise_distances(np.hstack(get_alphas(nodes)).T)**2

def set_edges(nodes, similarities, adj_matrix, max_nb_instances=1):

    for i, n in enumerate(nodes):

        neis, sims = [], []
        for j, a in enumerate(adj_matrix[i]):

            if a != 0:
                
                s = similarities[i][j]

                if i == j:
                    s *= 2

                neis.append(nodes[j])
                sims.append(s)

        n.set_neighbors(neis, sims) 
        n.sum_similarities = sum(sims)

def centralize_data(nodes):

    if len(nodes) == 1:
        return nodes[0]

    # centralize data
    x, y, x_test, y_test = [], [], [], []
    for n in nodes:
        x.append(n.sample)
        y.append(n.labels)
        x_test.append(n.test_sample)
        y_test.append(n.test_labels)

    try:
        node = Node(len(nodes), np.vstack(x), np.concatenate(y), np.vstack(x_test), np.concatenate(y_test))
    except:
        node = Node(len(nodes), np.vstack(x), np.concatenate(y))

    return node

# --------------------------------------------------------------- NETWORK CONSTRUCTORS

# line network
def line_network(x, y, nb_nodes=3, cluster_data=False):
    M, _ = x.shape
    # add offset dim
    x_copy = np.c_[x, np.ones(M)]

    # clustering
    groups = partition(x_copy, y, nb_nodes, cluster_data)

    nodes = list()
    nei_ids = list()
    for i in range(nb_nodes):

        n = Node(i, *groups[i])
        nei_ids.append([j for j in [i-1, i, i+1] if j >= 0 and j < nb_nodes])
        nodes.append(n)

    for ids, n in zip(nei_ids, nodes):
        n.set_neighbors([nodes[i] for i in ids])

    return nodes

def complete_graph(x, y, nb_nodes=3, cluster_data=False, rnd_state=None):
    M, _ = x.shape
    # add offset dim
    x_copy = np.c_[x, np.ones(M)]

    # clustering
    groups = partition(x_copy, y, nb_nodes, cluster_data, random_state=None)

    nodes = list()
    for i in range(nb_nodes):

        n = Node(i, *groups[i])
        nodes.append(n)

    for i, n in enumerate(nodes):
        neis = [n] + [nodes[j] for j in range(nb_nodes) if i!=j]
        n.set_neighbors(neis, [1/len(neis)]*len(neis))

    return nodes

def random_graph(x, y, nb_nodes=3, prob_edge=1, cluster_data=False, rnd_state=None):
    M, _ = x.shape
    # add offset dim
    x_copy = np.c_[x, np.ones(M)]

    # clustering
    groups = partition(x_copy, y, nb_nodes, cluster_data, random_state=None)

    nodes = list()
    for i in range(nb_nodes):

        n = Node(i, *groups[i])
        nodes.append(n)

    for i, n in enumerate(nodes):
        neis = [n] + [nodes[j] for j in range(nb_nodes) if i!=j and random() < prob_edge]
        n.set_neighbors(neis, [1/len(neis)]*len(neis))

    return nodes

def exponential_graph(x, y, x_test, y_test, nb_nodes, theta_true, max_nb_instances):

    adj_matrix, similarities = compute_adjacencies(theta_true, nb_nodes)

    nodes = graph(x, y, x_test, y_test, nb_nodes, adj_matrix, similarities, max_nb_instances)

    return nodes, adj_matrix, similarities

def graph(x, y, x_test, y_test, nb_nodes, adj_matrix, similarities, max_nb_instances):

    nodes = list()
    nei_ids = list()
    nei_sim = list()

    for i in range(nb_nodes):

        # add offset
        M, _ = x[i].shape
        x_copy = np.c_[x[i], np.ones(M)]
        M, _ = x_test[i].shape
        x_test_copy = np.c_[x_test[i], np.ones(M)]

        n = Node(i, x_copy, y[i], x_test_copy, y_test[i])
        nb_instances = len(x[i])
        n.confidence = nb_instances / max_nb_instances

        nei_ids.append([])
        nei_sim.append([])
        for j, a in enumerate(adj_matrix[i]):
            if a != 0:
                nei_ids[i].append(j)
                nei_sim[i].append(similarities[i][j])
        nodes.append(n)

    for ids, sims, n in zip(nei_ids, nei_sim, nodes):
        n.set_neighbors([nodes[i] for i in ids], sims)
        n.sum_similarities = sum(sims)

    return nodes


def null_graph(x, y, x_test, y_test, nb_nodes, max_nb_instances):

    nodes = list()

    for i in range(nb_nodes):

        n = Node(i, x[i], y[i], x_test[i], y_test[i])
        nb_instances = len(x[i])
        n.confidence = nb_instances / max_nb_instances

        nodes.append(n)

    return nodes

def true_theta_graph(nodes, theta_true):

    new_graph = list()

    for i, n in enumerate(nodes):

        m = Node(i, n.sample, n.labels, n.test_sample, n.test_labels)
        m.clf = LinearClassifier(n.n, np.append(theta_true[i], np.zeros((1, n.d - 2))))
        new_graph.append(m)

    return new_graph
