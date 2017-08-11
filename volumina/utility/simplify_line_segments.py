from __future__ import print_function
import numpy as np

try:
    import shapely.ops
    from shapely.geometry import LineString, MultiLineString
    _missing_shapely = False
except ImportError:
    _missing_shapely = True

def simplify_line_segments(lines, tolerance=0.707):
    """
    Given a list of line segments (in any order) of the form
        [((x1, y1), (x2, y2)), 
         ((x1, y1), (x2, y2)),
         ...]

    do the following:
    
    - Aggregate all of the line segments into a shapely MultiLineString
    - 'Merge' connected line segments
    - 'Simplify' each contiguous LineString, constrained to the given tolerancea
    
    Returns a list of the segment point arrays (one array per segment),
    where each point array is already in order, ready to be drawn on screen.
    """
    assert not _missing_shapely, "This function requires shapely to be installed."

    # shapely calls repr() on these items many times,
    # which is slow for numpy integer types like numpy.int64, etc.
    # To avoid a ~2x slowdown, force everything to be plain python.
    lines = np.asarray(lines).tolist()
    lines = MultiLineString(lines)
    
    merged_lines = shapely.ops.linemerge(lines).simplify(tolerance, False)
    if isinstance(merged_lines, LineString):
        # Annoyingly, the output type of linemerge() depends
        # on how many segments were found
        return [ np.array(merged_lines) ]
    return list(map( np.array, merged_lines ))


##
##
## OLD IMPLEMENTATION: All functions below this line aren't needed any more,
##                     but might be useful in the future...
## 
## This version implements the merge step using networkx.
## (I implemented this before I discovered the shapely.ops.linemerge() function...)
##
##

try:
    import networkx as nx
    _missing_nx = False
except ImportError:
    _missing_nx = True

def simplify_line_segments_OLD(lines, tolerance=0.707):
    """
    Given a list of line segments (in any order) of the form
        [((x1, y1), (x2, y2)), 
         ((x1, y1), (x2, y2)),
         ...]

    do the following:
    
    - Join all line segments into a graph
    - Separate the graph into 'segments' that can be independently "simplified"
    - Simplify each segment, constrained to the given tolerance
    
    Returns a list of the segment point arrays (one array per segment),
    where each point array is already in order, ready to be drawn on screen.
    """
    assert not _missing_shapely and not _missing_nx, \
        "This function requires networkx and shapely to be installed."

    lines = [tuple(map(tuple, l)) for l in lines]
    merged_lines = merge_line_segments(lines)

    # Convert to LineString
    merged_lines = list(map(LineString, merged_lines))

    # Simplify
    simplified_line_strings = [ls.simplify(tolerance, preserve_topology=False) for ls in merged_lines]

    # Return as numpy
    point_arrays = list(map(np.array, simplified_line_strings))
    return point_arrays

def merge_line_segments(lines):
    """
    Given a list of line segments (in any order) of the form
        [((x1, y1), (x2, y2)), 
         ((x1, y1), (x2, y2)),
         ...]

    do the following:
    
    - Join all line segments into a graph
    - Split the graph into segments that do not contain internal branch points
    
    Returns a list of the segment point arrays (one array per segment),
    where each point array is already in order, ready to be drawn on screen.
    """
    # Construct a graph of the given line segments
    # Line segments that touch at their beginning/ending points are neighbors in the graph.
    g = nx.Graph()
    g.add_edges_from(lines)

    # Extract segments
    cycle_segments = pop_cycle_segments(g)
    branch_segments = split_into_branchless_segments(g)
    return cycle_segments + branch_segments

def pop_cycle_segments(graph):
    """
    Find all cycles in the given nx.Graph (each cycle becomes a 'segment'),
    and remove the cycle nodes from the graph after they are found.
    """
    segments = []
    try:
        while True:
            cycle_edges = nx.find_cycle(graph)
            graph.remove_edges_from(cycle_edges)
            cycle_nodes = [node[0] for node in cycle_edges]
            cycle_nodes.append( cycle_edges[-1][1] )

            # Drop nodes without neighbors                
            for node in cycle_nodes[:-1]:
                if not graph.neighbors(node):
                    graph.remove_node(node)                
            segments.append(cycle_nodes)
    except nx.NetworkXNoCycle:
        pass
 
    return segments
        
def split_into_branchless_segments(undirected_graph):
    """
    Break the (possibly disjoint) nx.Graph into 'segments'.
    Here, a 'segment' is a string of connected nodes that don't
    include branch points of the original graph, except for the
    first/last node of the segment.

    Note: The graph must not contain cycles.
    
    For example:
    
        a - b - c - d
                 \
                  e - f - g
    
        h - i - j
    
    The above graph would be split into four segments:
    
        ['a', 'b', 'c'],
        ['c', 'd'],
        ['c', 'e', 'f', 'g']
        ['h', i', 'j']
    """
    # Choose an arbitrary tip to use as the tree root
    degrees = list(undirected_graph.degree_iter())
    tip_degrees = [node_degree for node_degree in degrees if node_degree[1] == 1]
    tip_nodes = [node_degree1[0] for node_degree1 in tip_degrees]

    tips_already_processed = set()
    segments = []
    for tip_node in tip_nodes:
        if tip_node in tips_already_processed:
            continue
        tips_already_processed.add(tip_node)

        # Construct a tree (DiGraph) from the tip
        tree = nx.dfs_tree(undirected_graph, tip_node)

        def grow_segments(current_node, current_segments):
            """
            Helper function.
            Add the current node to the current segment (the last item in 'current_segments'),
            and if the current node is a branch point, start two new segments.
            Continue recursively until the leaf nodes are found.
            """
            # Append the current node to the current segment
            current_segments[-1].append(current_node)

            children = tree.neighbors(current_node)
            if len(children) == 0:
                tips_already_processed.add(current_node)
            elif len(children) == 1:
                grow_segments(children[0], current_segments)
            else:
                # We've found a branch point; the current segment is complete.
                # Start a new segment for each child branch.
                for child in children:
                    current_segments.append([current_node])
                    grow_segments(child, current_segments)

        segments.append([])
        grow_segments(tip_node, segments)
    
    return segments

if __name__ == "__main__":
    import networkx as nx
    g = nx.Graph()
    g.add_path('abcdefg')
    g.add_path('chijk')
    g.add_path('ilmnop')

    g.add_path('12345')
    g.add_path('3678')
    g.add_path('790')
    
    segments = split_into_branchless_segments(g)
    #print segments
    
    # Start with an edge taken from real-world data.    
    lines = [((56, 111), (57, 111)), ((56, 126), (57, 126)), ((57, 110), (58, 110)), ((58, 109), (59, 109)), ((59, 108), (60, 108)), ((60, 107), (61, 107)), ((61, 106), (62, 106)), ((62, 106), (63, 106)), ((63, 106), (64, 106)), ((64, 108), (65, 108)), ((65, 106), (66, 106)), ((65, 107), (66, 107)), ((65, 108), (66, 108)), ((66, 109), (67, 109)), ((67, 110), (68, 110)), ((56, 111), (56, 112)), ((56, 112), (56, 113)), ((56, 113), (56, 114)), ((56, 114), (56, 115)), ((56, 115), (56, 116)), ((56, 116), (56, 117)), ((56, 117), (56, 118)), ((56, 118), (56, 119)), ((56, 119), (56, 120)), ((56, 120), (56, 121)), ((56, 121), (56, 122)), ((56, 122), (56, 123)), ((56, 123), (56, 124)), ((56, 124), (56, 125)), ((56, 125), (56, 126)), ((57, 110), (57, 111)), ((57, 126), (57, 127)), ((57, 127), (57, 128)), ((58, 109), (58, 110)), ((59, 108), (59, 109)), ((60, 107), (60, 108)), ((61, 106), (61, 107)), ((64, 106), (64, 107)), ((64, 107), (64, 108)), ((65, 106), (65, 107)), ((66, 106), (66, 107)), ((66, 108), (66, 109)), ((67, 109), (67, 110)), ((68, 110), (68, 111))]
    
    # Add a branch point
    lines += [((62, 106), (62, 105))]
    
    # Add a tangent cycle
    lines += [((64, 108), (64, 109)), ((64, 109), (63, 109)), ((63, 109), (63, 108)), ((63, 108), (64, 108))]

    # randomize the order, to prove this really works
    import random
    random.shuffle(lines)
    #print lines

    simplified_lines = simplify_line_segments(lines, 0.0)
    simplified_lines_OLD = simplify_line_segments_OLD(lines, 0.0)

    print("showing plot...")
    import matplotlib.pyplot as plt
    fig = plt.figure()
    ax = fig.add_subplot(111)
    for ls in simplified_lines_OLD:
        ax.plot(*np.array(ls).T, color='blue', linewidth=3, solid_capstyle='round')

    for ls in simplified_lines:
        ax.plot(*np.array(ls).T, color='green', linewidth=3, solid_capstyle='round')

    plt.show()

