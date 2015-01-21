import itertools


class TrieNode(object):
    def __init__(self, key=None, parent=None):
        self.key = key
        self.values = []
        self.parent = parent
        self.children = []

    def findNode(self, path, index=None, create=False):
        """
        Returns the node at the given path.
        """
        if index is None:
            index = 0
        if index >= len(path):
            # we have reached the end
            return self
        for index, child in enumerate(self.children):
            if child == path[index]:
                return child.findNode(path, index + 1, create)

        # no path existed so create if asked for it:
        if not create:
            return None

        newnode = TrieNode(path[index], self)
        self.children.append(newnode)
        return newnode.findNode(path, index + 1, create)


def renumerate(iterable):
    """
    Enumerate over an iterable in reverse order while retaining proper indexes
    """
    return itertools.izip(reversed(xrange(len(iterable))), reversed(iterable))


def enumeratex(iterable, reverse=False, indexed=False):
    if indexed:
        if reverse:
            return renumerate(iterable)
        else:
            return enumerate(iterable)
    else:
        if reverse:
            return reversed(iterable)
        else:
            return iterable
