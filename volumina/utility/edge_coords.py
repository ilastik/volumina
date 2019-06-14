from __future__ import print_function
from builtins import range
import numpy as np
import warnings
from collections import defaultdict


try:
    _pandas_available = True
    import pandas as pd
except ImportError:
    _pandas_available = False
    warnings.warn("pandas not available. edge_coords functions will be slower.")


def edge_ids(label_img, axes=None):
    """
    Find all edges in the given label volume and return the edge ids
    (u,v) where u and v are segment ids.  For all ids (u,v), u < v.
    """
    if axes is None:
        axes = list(range(label_img.ndim))

    all_edge_ids = []

    for axis in axes:
        if axis < 0:
            axis += label_img.ndim
        assert label_img.ndim > axis
        if label_img.shape[axis] == 1:
            continue

        up_slicing = ((slice(None),) * axis) + (np.s_[:-1],)
        down_slicing = ((slice(None),) * axis) + (np.s_[1:],)

        edge_mask = label_img[up_slicing] != label_img[down_slicing]
        num_edges = np.count_nonzero(edge_mask)
        edge_ids = np.ndarray(shape=(num_edges, 2), dtype=np.uint32)
        edge_ids[:, 0] = label_img[up_slicing][edge_mask]
        edge_ids[:, 1] = label_img[down_slicing][edge_mask]
        edge_ids.sort(axis=1)
        all_edge_ids.append(edge_ids)

    if _pandas_available:
        all_dfs = []
        for edge_ids in all_edge_ids:
            df = pd.DataFrame({"id1": edge_ids[:, 0], "id2": edge_ids[:, 1]})
            df.drop_duplicates(inplace=True)
            all_dfs.append(df)

        combined_df = pd.concat(all_dfs)
        combined_df.drop_duplicates(inplace=True)
        return list(combined_df[["id1", "id2"]].itertuples(index=False))
    else:
        unique_edge_ids = set()
        for edge_ids in all_edge_ids:
            unique_edge_ids.update(list(map(tuple, edge_ids)))
        return set(map(tuple, unique_edge_ids))


def edge_coords_along_axis(label_img, axis):
    """
    Find the edges between label segments along a particular axis
    Return all edges as keys in a dict, along with the list of coordinates that belong to the edge.

    Returns a dict of edges -> coordinate lists
    That is: { (id1, id2) : [coord, coord, coord, coord...] }

    For all edge ids (id1, id2), id1 < id2.

    Where:
        - id1 is always less than id2
        - for each 'coord', len(coord) == label_img.ndim
        - the edge lies just to the RIGHT (or down, or whatever) of the coordinate
    """
    if axis < 0:
        axis += label_img.ndim
    assert label_img.ndim > axis
    if label_img.shape[axis] == 1:
        return {}  # No edges

    up_slicing = ((slice(None),) * axis) + (np.s_[:-1],)
    down_slicing = ((slice(None),) * axis) + (np.s_[1:],)

    edge_mask = label_img[up_slicing] != label_img[down_slicing]

    # Instead of using .transpose() here (which induces a copy),
    # we use use a clever little trick: The arrays in the index
    # tuple have a common base, and it's exactly what we want.
    # edge_coords = np.transpose(np.nonzero(edge_mask))
    edge_coords = np.nonzero(edge_mask)[0].base
    assert edge_coords.shape[1] == label_img.ndim

    edge_ids = np.ndarray(shape=(len(edge_coords), 2), dtype=np.uint32)
    edge_ids[:, 0] = label_img[up_slicing][edge_mask]
    edge_ids[:, 1] = label_img[down_slicing][edge_mask]
    edge_ids.sort(axis=1)

    # FIXME: This doesn't work any more...
    #     # pandas can do groupby 3x faster than pure-python,
    #     # but pure-python is faster on tiny data (e.g. a couple 256*256 tiles)
    #     if _pandas_available and len(edge_ids) > 10000:
    #         df = pd.DataFrame({ 'id1' : edge_ids[:,0],
    #                             'id2' : edge_ids[:,1],
    #                             'coords' : NpIter(edge_coords) }) # This is much faster than list(edge_coords)
    #         return df.groupby(['id1', 'id2'])['coords'].apply(np.asarray).to_dict()
    #     else:
    grouped_coords = defaultdict(list)
    for id_pair, coords in zip(edge_ids, edge_coords):
        grouped_coords[tuple(id_pair)].append(coords)
    return grouped_coords


class NpIter(object):
    # This class just exists because we don't want to copy edge_coords,
    # but iter() objects don't support __len__, which pandas needs.
    def __init__(self, a):
        self.iter = iter(a)
        self._len = len(a)

    def __next__(self):
        return self.iter.__next__()

    def __len__(self):
        return self._len


def edge_coords_2d(label_img):
    vertical_edge_coords = edge_coords_along_axis(label_img, 0)
    horizontal_edge_coords = edge_coords_along_axis(label_img, 1)
    return (vertical_edge_coords, horizontal_edge_coords)


def edge_coords_nd(label_img, axes=None):
    if axes is None:
        axes = list(range(label_img.ndim))
    result = []
    for axis in axes:
        result.append(edge_coords_along_axis(label_img, axis))
    return result


if __name__ == "__main__":
    import h5py

    # watershed_path = '/magnetic/data/flyem/chris-two-stage-ilps/volumes/subvol/256/watershed-256.h5'
    watershed_path = "/magnetic/data/flyem/chris-two-stage-ilps/volumes/subvol/512/watershed-512.h5"
    with h5py.File(watershed_path, "r") as f:
        watershed = f["watershed"][:256, :256, :256]

    n = NpIter(np.array([[10, 20], [20, 30], [30, 40]]))
    print(np.array(n))

    from lazyflow.utility import Timer

    with Timer() as timer:
        # ec = edge_coords_nd(watershed)
        ids = edge_ids(watershed)
    print("Python time was: {}".format(timer.seconds()))

    import vigra

    with Timer() as timer:
        gridGraph = vigra.graphs.gridGraph(watershed.shape)
        rag = vigra.graphs.regionAdjacencyGraph(gridGraph, watershed)
        ids = rag.uvIds()
    print("vigra time was: {}".format(timer.seconds()))

    # print len(set( ec[0].keys() + ec[1].keys() + ec[2].keys() ))
    print(len(ids))

#     labels_img = np.load('/Users/bergs/workspace/ilastik-meta/ilastik/seg-slice-256.npy')
#     assert labels_img.dtype == np.uint32
#
#     vert_edges, horizontal_edges = edge_coords_nd(labels_img)
#     for id_pair, coords_list in horizontal_edges.iteritems():
#         print id_pair, ":", coords_list
