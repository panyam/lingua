
class Symbol(object):
    def __init__(self, name, resultType=None):
        self.index = -1
        self.name = name
        self.resultType = resultType
        self.productions = []

    def __cmp__(self, other):
        if type(other) is str:
            other = Symbol(other)
        return cmp(self.name, other.name)

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        if self.resultType:
            return "<%s(%s)>" % (self.name, self.resultType)
        else:
            return "<%s>" % self.name

    def isNonTerminal(self):
        return len(self.productions) > 0

    def addProduction(self, production):
        production.nonterm = self
        self.productions.append(production)


class SymbolUsage(object):
    def __init__(self, symbol, varname=None, isOptional=False):
        self.symbol = symbol
        self.varname = varname
        self.isOptional = isOptional

    def isNonTerminal(self):
        return self.symbol.isNonTerminal()

    def __repr__(self):
        return "%s%s%s" % (("? " if self.isOptional else ""),
                           (self.varname + ":" if self.varname else ""),
                           self.symbol)


class Production(object):
    def __init__(self, nonterm, symbols, handler=None):
        self.nonterm = nonterm
        for index, symbol in enumerate(symbols):
            if type(symbol) is str:
                symbols[index] = SymbolUsage(symbol)
        self.symbolUsages = symbols
        self.handler = handler


class Reduction(object):
    def __init__(self, production, results):
        self.production = production
        self.results = results


class Grammar(object):
    def __init__(self):
        self.symbolsByName = {}
        self.symbolsByIndex = []

    def isSymbolATerminalinal(self, symbolname):
        return symbolname in self.symbolsByName

    def addSymbol(self, symbol, resultType=None):
        if type(symbol) is str:
            if symbol in self.symbolsByName:
                symbol = self.symbolsByName[symbol]
            else:
                symbol = Symbol(symbol, resultType)
        if symbol.name not in self.symbolsByName:
            self.symbolsByName[symbol.name] = symbol
            self.symbolsByIndex.append(symbol)
        return self.symbolsByName[symbol.name]

    def removeSymbol(self, symbolname):
        del self.symbolsByName[symbolname]
        for index, value in enumerate(self.symbolsByIndex):
            if value.name == symbolname:
                del self.symbolsByIndex[index]
                break

    def reindexSymbols(self):
        ntCount = 0
        tCount = 0
        for value in self.symbolsByIndex:
            if value.isNonTerminal():
                value.index = ntCount
                ntCount += 1
            else:
                value.index = tCount
                tCount += 1

    def nonTerminals(self):
        return filter(lambda x: x.isNonTerminal(), self.symbolsByIndex)

    def detectAllLRCycles(self, startingFrom=None):
        """
        Returns a set of "Starting" non terminals which have atleast
        one production containing left recursion.
        """
        def strongconnect(currNT, index, indexes, lowlink, stack):
            indexes[currNT] = index
            lowlink[currNT] = index
            index = index + 1
            stack.insert(0, currNT)

            # consider all rules of currNT which start with a non term
            for prod in currNT.productions:
                if prod.symbolUsages[0].symbol.isNonTerminal():
                    nextNT = prod.symbolUsages[0].symbol
                    if nextNT not in indexes:
                        # not yet been visited so recurse on it
                        index, _ = strongconnect(nextNT, index, indexes, lowlink, stack)
                        lowlink[currNT] = min(lowlink[currNT], lowlink[nextNT])
                    elif nextNT in stack:
                        # success is in the stack so we are good
                        lowlink[currNT] = min(lowlink[currNT], lowlink[nextNT])

            scc = []
            if lowlink[currNT] == indexes[currNT]:
                # start a new strongly connected component
                while True:
                    nextNT = stack.pop(0)
                    scc.append(nextNT)
                    if nextNT == currNT:
                        break
            return index, scc

        out = []
        index = 0
        indexes = {}
        lowlink = {}
        stack = []

        for currNT in self.nonTerminals():
            if currNT not in indexes:
                index, scc = strongconnect(currNT, index, indexes, lowlink, stack)
                out.append(scc)
        return out
