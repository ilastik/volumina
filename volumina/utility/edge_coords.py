import numpy as np
from collections import defaultdict

def edge_coords_along_axis( label_img, axis ):
    """
    Find the edges between label segments along a particular axis, e.g. if axis=-1
    Return all edges as keys in a dict, along with the list of coordinates that belong to the edge.
    
    Returns a dict of edges -> coordinate lists
    That is: { (id1, id2) : [coord, coord, coord, coord...] }
    
    Where:
        - id1 is always less than id2
        - for each 'coord', len(coord) == label_img.ndim
        - the edge lies just to the RIGHT (or down, or whatever) of the coordinate
    
    TODO: Speed this up with either C++ or pandas.
    """
    if axis < 0:
        axis += label_img.ndim
    assert label_img.ndim > axis
    if label_img.shape[axis] == 1:
        return {} # No edges
    
    up_slicing = ((slice(None),) * axis) + (np.s_[:-1],)
    down_slicing = ((slice(None),) * axis) + (np.s_[1:],)

    edge_mask = (label_img[up_slicing] != label_img[down_slicing])
    up_ids = label_img[up_slicing][edge_mask]
    down_ids = label_img[down_slicing][edge_mask]

    edge_coords = np.asarray( np.nonzero(edge_mask), dtype=np.uint32 )
    edge_coords = edge_coords.transpose()
    assert edge_coords.shape[1] == label_img.ndim
    
    id_pairs = np.concatenate((up_ids[None], down_ids[None]), axis=0)
    id_pairs = id_pairs.transpose()
    id_pairs = np.sort(id_pairs, axis=1)
    assert id_pairs.shape[1] == 2

    grouped_coords = defaultdict(list)
    for id_pair, coords in zip(id_pairs, edge_coords):
        grouped_coords[tuple(id_pair)].append(coords)
    
    return grouped_coords

def edge_coords_2d( label_img ):
    vertical_edge_coords = edge_coords_along_axis( label_img, 0 )
    horizontal_edge_coords = edge_coords_along_axis( label_img, 1 )
    return (vertical_edge_coords, horizontal_edge_coords)

def edge_coords_nd( label_img, axes=None ):
    if axes is None:
        axes = range(label_img.ndim)
    
    result = []    
    for axis in axes:
        result.append( edge_coords_along_axis(label_img, axis) )
    return result

if __name__ == "__main__":
    labels_img = np.load('/Users/bergs/workspace/ilastik-meta/ilastik/seg-slice-256.npy')
    assert labels_img.dtype == np.uint32
    
    vert_edges, horizontal_edges = edge_coords_nd(labels_img)
    for id_pair, coords_list in horizontal_edges.iteritems():
        print id_pair, ":", map(tuple, coords_list)

    import zlib
    import base64
    buffer = np.getbuffer(labels_img)
    compressed = zlib.compress(buffer)
    encoded = base64.b64encode(compressed)
    print len(encoded)
    print encoded
