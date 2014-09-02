
def tarjan(nodes, edge_functor):
    """
    Returns a set of "Starting" non terminals which have atleast
    one production containing left recursion.
    """
    def strongconnect(currNode, index, indexes, lowlink, stack):
        indexes[currNode] = index
        lowlink[currNode] = index
        index = index + 1
        stack.insert(0, currNode)

        # consider all rules of currNode which start with a non term
        for nextNode in edge_functor(currNode):
            if nextNode not in indexes:
                # not yet been visited so recurse on it
                index, _ = strongconnect(nextNode, index, indexes, lowlink, stack)
                lowlink[currNode] = min(lowlink[currNode], lowlink[nextNode])
            elif nextNode in stack:
                # success is in the stack so we are good
                lowlink[currNode] = min(lowlink[currNode], lowlink[nextNode])

        scc = []
        if lowlink[currNode] == indexes[currNode]:
            # start a new strongly connected component
            while True:
                nextNT = stack.pop(0)
                scc.append(nextNT)
                if nextNT == currNode:
                    break
        return index, scc

    out = []
    index = 0
    indexes = {}
    lowlink = {}
    stack = []

    for currNode in nodes:
        if currNode not in indexes:
            index, scc = strongconnect(currNode, index, indexes, lowlink, stack)
            out.append(scc)
    return out


def all_minimal_cycles(nodes, edge_functor):
    # Tells which cycle a node is assigned to if any
    cycles = []
    in_a_cycle = set()
    cycle_count = 0
    for node in nodes:
        # start from node and do a BFS to see what cycle a node appears in
        if node not in in_a_cycle:
            start_node = node
            visited = {}
            queue = [(node, [])]
            while queue:
                node, cycle = queue.pop(0)
                assert node is not None
                for nextNode in set(edge_functor(node)):
                    edgeData = None
                    if type(nextNode) is tuple:
                        nextNode, edgeData = nextNode
                    if nextNode == start_node:
                        # we have a cycle
                        cycle.append((edgeData, nextNode))
                        in_a_cycle.update([n for e, n in cycle])
                        cycles.append((start_node, cycle))
                        cycle_count += 1
                        cycle = cycle[:-1]
                    elif nextNode not in visited:
                        visited[nextNode] = True
                        queue.append((nextNode, cycle[:] + [(edgeData, nextNode)]))
    return cycles
