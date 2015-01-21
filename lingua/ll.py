
class Parser(object):
    """
    Generates the LL parser for a particular language.
    """
    def __init__(self):
        pass

    def generate(self, G, startnt):
        assert len(G.leftRecursion) == 0, "Grammar has left recursion.  Please remove it first"
        # the predict sets tell which productions should be descended
        # into at any point
        G.evalPredictSets()

        """
        The algorithm is:

        # This can be DFS or BFS
        stack = [ startnt ]
        visited = {}
        while stack:
            top = stack.pop()
            visited += [top]
            genCodeForNT(top)

        def genCodeForNT(nt, stack, visited):
            genFunctionSignature(nt, stack, visited)
            genFunctionBody(nt, stack, visited)

        class Parser(object):
            def parseA():
                p1
        """
