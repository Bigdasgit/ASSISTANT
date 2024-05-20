import networkx as nx


import torch_geometric.utils.convert as cv
from torch_geometric.data import NeighborSampler as RawNeighborSampler

import pandas as pd
from utils import *
import warnings
import argparse
warnings.filterwarnings('ignore')
import collections
import networkx as nx
import copy 
from sklearn.metrics import roc_auc_score
import os
from models import *
import numpy as np
import random
import torch

'''
Please note that some function codes are apopted and revised from
https://github.com/vinhsuhi/GAlign
https://github.com/deepopo/CENALP
'''

def na_dataloader(args):
    G1, G2= loadG(args.data_folder, args.graphname)          
    if args.graphname == 'am-td': # will be revised later 
    
        source_dataset = Dataset('dataset\\DataProcessing\\allmv_tmdb\\allmv')
        target_dataset = Dataset('dataset\\DataProcessing\\allmv_tmdb\\tmdb')
        gt_dr = 'dataset\\DataProcessing\\allmv_tmdb\\dictionaries\\groundtruth'
        gt_dict = graph_utils.load_gt(gt_dr, source_dataset.id2idx, target_dataset.id2idx, 'dict')
        gt_dict = DeleteDuplicatedElement(gt_dict)
        G2, alignment_dict, alignment_dict_reversed = preprocessing(G1, G2, gt_dict)
        idx1_dict, idx2_dict = create_idx_dict_pair(G1,G2,alignment_dict)
        
        return G1, G2, alignment_dict, alignment_dict_reversed, idx1_dict, idx2_dict
    
    elif args.graphname == 'fl-my': # will be revised later 
    
        source_dataset = Dataset('dataset\\DataProcessing\\fl-my\\flickr')
        target_dataset = Dataset('dataset\\DataProcessing\\fl-my\\myspace')
        gt_dr = 'dataset\\DataProcessing\\fl-my\\dictionaries\\groundtruth'
        gt_dict = graph_utils.load_gt(gt_dr, source_dataset.id2idx, target_dataset.id2idx, 'dict')
        G2, alignment_dict, alignment_dict_reversed = preprocessing(G1, G2, gt_dict)
        idx1_dict, idx2_dict = create_idx_dict_pair(G1,G2,alignment_dict)
        
        return G1, G2, alignment_dict, alignment_dict_reversed, idx1_dict, idx2_dict
    
    elif args.graphname == 'synthetic': # will be revised later 

        alignment_dict, alignment_dict_reversed = read_alignment(args.alignment_folder, args.graphname)
        idx1_dict, idx2_dict = create_idx_dict_pair(G1,G2,alignment_dict)
        
        return G1, G2, alignment_dict, alignment_dict_reversed, idx1_dict, idx2_dict
            
    else:        
        
        alignment_dict, alignment_dict_reversed = read_alignment(args.alignment_folder, args.graphname)
        attr1, attr2, attribute_sim = AttributeProcessing(args, G1, G2, alignment_dict)
        G2, alignment_dict, alignment_dict_reversed = preprocessing(G1, G2, alignment_dict)
        idx1_dict, idx2_dict = create_idx_dict_pair(G1,G2,alignment_dict)
        return G1, G2, alignment_dict, alignment_dict_reversed, idx1_dict, idx2_dict
    
'''Data preprocessing'''

def Reordering(G1,G2):
    G1 = nx.convert_node_labels_to_integers(G1, first_label=1, ordering='default', label_attribute=None)
    G2 = nx.convert_node_labels_to_integers(G2, first_label=G1.number_of_nodes()+1, ordering='default', label_attribute=None)
    return G1,G2

def ReorderingSame(G1,G2):
    G1 = nx.convert_node_labels_to_integers(G1, first_label=1, ordering='default', label_attribute=None)
    G2 = nx.convert_node_labels_to_integers(G2, first_label=1, ordering='default', label_attribute=None)
    return G1,G2
    
def AttributeProcessing(args,G1,G2, alignment_dict):

    attribute_sim, attr1, attr2, attr1_pd, attr2_pd = read_attribute(args.attribute_folder, args.graphname, G1, G2, alignment_dict)

    featpd1 = pd.DataFrame(attr1)
    featpd2 = pd.DataFrame(attr2)
    featnpy1 = featpd1.to_numpy() 
    featnpy2 = featpd2.to_numpy() 
    print(featpd1)
    np.save("feats1.npy",featnpy1)
    np.save("feats2.npy",featnpy2)
    print("feats exporting complete")
    
    return attr1, attr2, attribute_sim



def DeleteDuplicatedElement(gt_dict):
    for key in dellist:
        del gt_dict[key]
    return gt_dict

class Dataset:
    """
    this class are copied from the repo: https://github.com/vinhsuhi/GAlign
    this class receives input from graphsage format with predefined folder structure, the data folder must contains these files:
    G.json, id2idx.json, features.npy (optional)

    Arguments:
    - data_dir: Data directory which contains files mentioned above.
    """

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self._load_id2idx()
        self._load_G()
        self._load_features()
        graph_utils.construct_adjacency(self.G, self.id2idx, sparse=False, file_path=self.data_dir + "/edges.edgelist")
        # self.load_edge_features()
        print("Dataset info:")
        print("- Nodes: ", len(self.G.nodes()))
        print("- Edges: ", len(self.G.edges()))

    def _load_G(self):
        G_data = json.load(open(os.path.join(self.data_dir, "G.json")))
        G_data['links'] = [{'source': self.idx2id[G_data['links'][i]['source']], 'target': self.idx2id[G_data['links'][i]['target']]} for i in range(len(G_data['links']))]
        self.G = json_graph.node_link_graph(G_data)


    def _load_id2idx(self):
        id2idx_file = os.path.join(self.data_dir, 'id2idx.json')
        self.id2idx = json.load(open(id2idx_file))
        self.idx2id = {v:k for k,v in self.id2idx.items()}


    def _load_features(self):
        self.features = None
        feats_path = os.path.join(self.data_dir, 'feats.npy')
        if os.path.isfile(feats_path):
            self.features = np.load(feats_path)
        else:
            self.features = None
        return self.features

    def load_edge_features(self):
        self.edge_features= None
        feats_path = os.path.join(self.data_dir, 'edge_feats.mat')
        if os.path.isfile(feats_path):
            edge_feats = loadmat(feats_path)['edge_feats']
            self.edge_features = np.zeros((len(edge_feats[0]),
                                           len(self.G.nodes()),
                                           len(self.G.nodes())))
            for idx, matrix in enumerate(edge_feats[0]):
                self.edge_features[idx] = matrix.toarray()
        else:
            self.edge_features = None
        return self.edge_features

    def get_adjacency_matrix(self, sparse=False):
        return graph_utils.construct_adjacency(self.G, self.id2idx, sparse=False, file_path=self.data_dir + "/edges.edgelist")

    def get_nodes_degrees(self):
        return graph_utils.build_degrees(self.G, self.id2idx)

    def get_nodes_clustering(self):
        return graph_utils.build_clustering(self.G, self.id2idx)

    def get_edges(self):
        return graph_utils.get_edges(self.G, self.id2idx)

    def check_id2idx(self):
        # print("Checking format of dataset")
        for i, node in enumerate(self.G.nodes()):
            if (self.id2idx[node] != i):
                print("Failed at node %s" % str(node))
                return False
        # print("Pass")
        return True
''' file loading '''
def read_alignment(alignment_folder, filename):
    alignment = pd.read_csv(alignment_folder + filename + '.csv', header = None)
    alignment_dict = {}
    alignment_dict_reversed = {}
    for i in range(len(alignment)):
        alignment_dict[alignment.iloc[i, 0]] = alignment.iloc[i, 1]
        alignment_dict_reversed[alignment.iloc[i, 1]] = alignment.iloc[i, 0]
    return alignment_dict, alignment_dict_reversed

def get_reversed(alignment_dict):
    alignment_dict_reversed = {}
    reversed_dictionary = {value : key for (key, value) in alignment_dict.items()}
    return alignment_dict, reversed_dictionary

def read_attribute(attribute_folder, filename, G1, G2, alignment_dict):
    try:
        attribute, attr1, attr2, attr1_pd, attr2_pd = load_attribute(attribute_folder, filename, G1, G2, alignment_dict)
        attribute = attribute.transpose()
        
    except:
        attr1 = []
        attr2 = []
        attr1_pd = []
        attr2_pd = []
        attribute = []
        print('Attribute files not found.')
    return attribute, attr1, attr2, attr1_pd, attr2_pd

def load_gt(path, id2idx_src=None, id2idx_trg=None, format='matrix'):    
    if id2idx_src:
        conversion_src = type(list(id2idx_src.keys())[0])
        conversion_trg = type(list(id2idx_trg.keys())[0])
    if format == 'matrix':
        # Dense
        """
        gt = np.zeros((len(id2idx_src.keys()), len(id2idx_trg.keys())))
        with open(path) as file:
            for line in file:
                src, trg = line.strip().split()                
                gt[id2idx_src[conversion_src(src)], id2idx_trg[conversion_trg(trg)]] = 1
        return gt
        """
        # Sparse
        row = []
        col = []
        val = []
        with open(path) as file:
            for line in file:
                src, trg = line.strip().split()
                row.append(id2idx_src[conversion_src(src)])
                col.append(id2idx_trg[conversion_trg(trg)])
                val.append(1)
        gt = csr_matrix((val, (row, col)), shape=(len(id2idx_src), len(id2idx_trg)))
    else:
        gt = {}
        with open(path) as file:
            for line in file:
                src, trg = line.strip().split()
                # print(src, trg)
                if id2idx_src:
                    gt[id2idx_src[conversion_src(src)]] = id2idx_trg[conversion_trg(trg)]
                else:
                    gt[str(src)] = str(trg)
    return gt


def loadG(data_folder, filename):

    G1 = nx.Graph()
    G2 = nx.Graph()
    G1_edges = pd.read_csv(data_folder + filename + '1.edges', names = ['0', '1'])
    G1.add_edges_from(np.array(G1_edges))
    G2_edges = pd.read_csv(data_folder + filename + '2.edges', names = ['0', '1'])
    G2.add_edges_from(np.array(G2_edges))
    
    return G1, G2

def loadG_link(data_folder, test_frac, filename):
    G1 = nx.Graph()
    G2 = nx.Graph()
    G1_edges = pd.read_csv(data_folder + filename + '1.edges', names = ['0', '1'])
    G1.add_edges_from(np.array(G1_edges))
    G2_edges = pd.read_csv(data_folder + filename + '2_' + str(test_frac) + '.edges', names = ['0', '1'])
    G2.add_edges_from(np.array(G2_edges))
    test_edges = pd.read_csv(data_folder + filename + '2_' + str(test_frac) + '_test.edges', names = ['0', '1'])
    return G1, G2, test_edges

def load_attribute(attribute_folder, filename, G1, G2, alignment_dict):

    G1_nodes = list(G1.nodes()) 
    G2_nodes = list(G2.nodes())
    
    attribute1_pd = pd.read_csv(attribute_folder + filename + 'attr1.csv', header = None, index_col = 0)
    attribute2_pd = pd.read_csv(attribute_folder + filename + 'attr2.csv', header = None, index_col = 0)

    attribute1 = np.array(attribute1_pd.loc[G1_nodes, :])
    attribute2 = np.array(attribute2_pd.loc[G2_nodes, :])   

    attr_cos = cosine_similarity(attribute1, attribute2)
    
    return attr_cos, attribute1, attribute2, attribute1_pd, attribute2_pd

def preprocessing(G1, G2, alignment_dict):
    '''
    Parameters
    ----------
    G1 : source graph
    G2 : target graph
    alignment_dict : grth dict

    '''
    # shift index for constructing union
    # construct shifted dict
    shift = G1.number_of_nodes()
    G2_list = list(G2.nodes())
    G2_shiftlist = list(idx + shift for idx in list(G2.nodes()))
    shifted_dict = dict(zip(G2_list,G2_shiftlist))
    
    #relable idx for G2
    G2 = nx.relabel_nodes(G2, shifted_dict)
    
    #update alignment dict
    align1list = list(alignment_dict.keys())
    align2list = list(alignment_dict.values())   
    shifted_align2list = [a+shift for a in align2list]
    
    groundtruth_dict = dict(zip(align1list, shifted_align2list))
    groundtruth_dict, groundtruth_dict_reversed = get_reversed(groundtruth_dict)
    
    return G2, groundtruth_dict, groundtruth_dict_reversed


def create_idx_dict_pair(G1,G2,alignment_dict):
    '''
    Make sure that this function is followed after preprocessing dict.

    '''
    G1list = list(G1.nodes())
    #G1list.sort()
    idx1_list = list(range(G1.number_of_nodes()))
    #make dict for G1
    idx1_dict = {a : b for b, a in zip(idx1_list,G1list)}

    
    G2list = list(G2.nodes())
    #G2list.sort()
    idx2_list = list(range(G2.number_of_nodes()))
    #make dict for G2
    idx2_dict = {c : d for d, c in zip(idx2_list,G2list)}
    
    return idx1_dict, idx2_dict


def create_idx_dict_pair_backup(G1,G2,alignment_dict):
    '''
    Make sure that this function is followed after preprocessing dict.

    '''
    
    G1list = list(G1.nodes())
    #G1list.sort()
    idx1_list = list(range(G1.number_of_nodes()))
    #make dict for G1
    idx1_dict = {a : b for b, a in zip(idx1_list,G1list)}
    
    G2list = list(G2.nodes())
    #G2list.sort()
    idx2_list = list(range(G2.number_of_nodes()))
    #make dict for G2
    idx2_dict = {c : d for d, c in zip(idx2_list,G2list)}
    
    return idx1_dict, idx2_dict

def augment_attr(Gs, Gt, attr_s, attr_t, interval):
    # attribute index의 순서는 G*.nodes()를 출력했을때 나오는 순서와 같음 !!

    # Gs, Gt 중 max deg를 측정
    max_deg = max(max(Gs.degree, key=lambda x: x[1])[1], max(Gt.degree, key=lambda x: x[1])[1])
    print(f"max degree is {max_deg}")
    # interval을 기준으로 했을 때, 늘어나는 속성 개수를 계산
    num_attr = math.ceil(max_deg / interval)
    # n_s * num_attr 의 속성 벡터를 0 value로 초기화
    init_np_s = np.zeros((Gs.number_of_nodes(), num_attr))
    init_np_t = np.zeros((Gt.number_of_nodes(), num_attr))

    # 각 노드마다 deg를 측정하여 attr를 init_np에 assign
    for idx_s, node_s in enumerate(Gs.nodes()):
        deg_node = Gs.degree(node_s)
        init_np_s[idx_s, int(deg_node / interval) - 1] = 1

    for idx_t, node_t in enumerate(Gt.nodes()):
        deg_node = Gt.degree(node_t)
        init_np_t[idx_t, int(deg_node / interval) - 1] = 1

    # assign이 완료된 매트릭스를 기존 attr에 attach (np.append(a,b, axis =1))
    new_attr_s = np.append(attr_s, init_np_s, axis=1)
    new_attr_t = np.append(attr_t, init_np_t, axis=1)
    new_attr_s = init_np_s
    new_attr_t = init_np_t
    # 만약 len(attr_s) == 1 (plain network) 의 경우, 그냥 attr을 대체하면 된다.
    if len(attr_s) == 1:
        new_attr_s = new_attr_s[:, 1:]
        new_attr_t = new_attr_t[:, 1:]

    return new_attr_s, new_attr_t

def augment_attr_khop(Gs, Gt, attr_s, attr_t, interval, k):
    # attribute index의 순서는 G*.nodes()를 출력했을때 나오는 순서와 같음 !!
    Gs_nodes = list(Gs.nodes())
    Gt_nodes = list(Gt.nodes())
    # node: khop nbr의 구성을 갖는 dict 생성
    khopdict_source = {key : len(nx.single_source_shortest_path_length(Gs, source = key, cutoff=k)) for key in Gs_nodes}
    khopdict_target = {key : len(nx.single_source_shortest_path_length(Gt, source = key, cutoff=k)) for key in Gt_nodes}
    # Gs, Gt 중 max deg를 측정
    max_deg = max(max(khopdict_source.values()), max(khopdict_target.values()))
    print(f"max k-hop degree is {max_deg}")
    # interval을 기준으로 했을 때, 늘어나는 속성 개수를 계산
    num_attr = math.ceil(max_deg / interval)
    # n_s * num_attr 의 속성 벡터를 0 value로 초기화
    init_np_s = np.zeros((Gs.number_of_nodes(), num_attr))
    init_np_t = np.zeros((Gt.number_of_nodes(), num_attr))

    # 각 노드마다 deg를 측정하여 attr를 init_np에 assign
    for idx_s, node_s in enumerate(Gs.nodes()):
        deg_node = Gs.degree(node_s)
        init_np_s[idx_s, int(deg_node / interval) - 1] = 1

    for idx_t, node_t in enumerate(Gt.nodes()):
        deg_node = Gt.degree(node_t)
        init_np_t[idx_t, int(deg_node / interval) - 1] = 1

    # assign이 완료된 매트릭스를 기존 attr에 attach (np.append(a,b, axis =1))
    # new_attr_s = np.append(attr_s, init_np_s, axis=1)
    # new_attr_t = np.append(attr_t, init_np_t, axis=1)
    new_attr_s = init_np_s
    new_attr_t = init_np_t
    # 만약 len(attr_s) == 1 (plain network) 의 경우, 그냥 attr을 대체하면 된다.
    if len(attr_s) == 1:
        new_attr_s = new_attr_s[:, 1:]
        new_attr_t = new_attr_t[:, 1:]

    return new_attr_s, new_attr_t



def augment_attr_Katz(Gs, Gt, attr_s, attr_t, interval,mul):
    # attribute index의 순서는 G*.nodes()를 출력했을때 나오는 순서와 같음 !!
    
    # Katz dictionary
    katzdict_s = nx.katz_centrality_numpy(Gs, alpha = 0.05, beta = 1, normalized = False)
    katzdict_t = nx.katz_centrality_numpy(Gt, alpha = 0.05, beta = 1, normalized = False)
    
    katzdict_s.update((x, y*mul) for x, y in katzdict_s.items())
    katzdict_t.update((x, y*mul) for x, y in katzdict_t.items())
    
    # Gs, Gt 중 max length를 측정
    max_len = max((max(katzdict_s.values())), (max(katzdict_t.values())))
    print(f"len of attr is {max_len}")

    # interval을 기준으로 했을 때, 늘어나는 속성 개수를 계산
    num_attr = math.ceil(max_len / interval)
    # n_s * num_attr 의 속성 벡터를 0 value로 초기화
    init_np_s = np.zeros((Gs.number_of_nodes(), num_attr))
    init_np_t = np.zeros((Gt.number_of_nodes(), num_attr))

    # 각 노드마다 deg를 측정하여 attr를 init_np에 assign
    for idx_s, node_s in enumerate(Gs.nodes()):
        katz_node = katzdict_s[node_s]
        init_np_s[idx_s, int(katz_node / interval) - 1] = 1

    for idx_t, node_t in enumerate(Gt.nodes()):
        katz_node = katzdict_t[node_t]
        init_np_t[idx_t, int(katz_node / interval) - 1] = 1

    # assign이 완료된 매트릭스를 기존 attr에 attach (np.append(a,b, axis =1))
    new_attr_s = np.append(attr_s, init_np_s, axis=1)
    new_attr_t = np.append(attr_t, init_np_t, axis=1)
    new_attr_s = init_np_s
    new_attr_t = init_np_t
    # 만약 len(attr_s) == 1 (plain network) 의 경우, 그냥 attr을 대체하면 된다.
    if len(attr_s) == 1:
        new_attr_s = new_attr_s[:, 1:]
        new_attr_t = new_attr_t[:, 1:]

    return new_attr_s, new_attr_t


def augment_attr_bin(Gs, Gt, attr_s, attr_t):
    # attribute index의 순서는 G*.nodes()를 출력했을때 나오는 순서와 같음 !!

    # Gs, Gt 중 max deg를 측정
    max_deg = max(max(Gs.degree, key=lambda x: x[1])[1], max(Gt.degree, key=lambda x: x[1])[1])
    bin_max = bin(max_deg)
    print(f"max degree is {max_deg}")
    # max_deg를 기준으로, 늘어나는 속성 개수를 계산 (앞 0b 제외)
    num_attr = len(bin_max) - 2
    # node * num_attr 의 속성 벡터를 0 value로 초기화
    init_np_s = np.zeros((Gs.number_of_nodes(), num_attr))
    init_np_t = np.zeros((Gt.number_of_nodes(), num_attr))

    # 각 노드마다 deg를 측정하여 attr를 init_np에 assign
    for idx_s, node_s in enumerate(Gs.nodes()):
        deg_node = Gs.degree(node_s)
        bin_vec_deg = [int(i) for i in bin(deg_node)[2:]]
        init_np_s[idx_s][:len(bin_vec_deg)] = bin_vec_deg

    for idx_t, node_t in enumerate(Gt.nodes()):
        deg_node = Gt.degree(node_t)
        bin_vec_deg = [int(i) for i in bin(deg_node)[2:]]
        init_np_t[idx_t][:len(bin_vec_deg)] = bin_vec_deg

    # assign이 완료된 매트릭스를 기존 attr에 attach (np.append(a,b, axis =1))
    # new_attr_s = np.append(attr_s, init_np_s, axis = 1)
    # new_attr_t = np.append(attr_t, init_np_t, axis = 1)
    new_attr_s = init_np_s
    new_attr_t = init_np_t
    # 만약 len(attr_s) == 1 (plain network) 의 경우, 그냥 attr을 대체하면 된다.
    if len(attr_s) == 1:
        new_attr_s = new_attr_s[:, 1:]
        new_attr_t = new_attr_t[:, 1:]

    return new_attr_s, new_attr_t





def struct_consist_checker(G1, G2, alignment_dict):
    
    G1_nodes = list(G1.nodes()) 
    G2_nodes = list(G2.nodes())    
    # load nodes:deg dict
    degdict_G1 = {key : len(nx.single_source_shortest_path_length(G1, source = key, cutoff=1)) for key in G1_nodes}
    degdict_G2 = {key : len(nx.single_source_shortest_path_length(G2, source = key, cutoff=1)) for key in G2_nodes}
    # compare with alignment_dict
    
    score = 0
    for key in degdict_G1:
        try:            
            if degdict_G1[key] == degdict_G2[alignment_dict[key]]:
                score += 1
        except:
            continue
    str_consist = score/len(alignment_dict)
    print(f"same degree portion is {str_consist:.2f}")
    
    return str_consist
        
def att_consist_checker(G1, G2, attr1, attr2, idx1_dict, idx2_dict, alignment_dict):
    
    G1_nodes = list(G1.nodes()) 
    # load nodes:deg dict

    # compare with alignment_dict
    
    score = 0
    for node in G1_nodes:
        try:            
            if (attr1[idx1_dict[node]] == attr2[idx2_dict[alignment_dict[node]]]).all():
                score += 1
        except:
            continue
    att_consist = score/len(alignment_dict)
    print(f"same attr portion is {att_consist:.2f}")
    
    return att_consist
        
