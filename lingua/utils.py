import itertools


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
