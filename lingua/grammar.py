
import itertools
import graph


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
        return itertools.ifilter(lambda x: x.isNonTerminal(), self.symbolsByIndex)

    def detectAllLRCycles(self, startingFrom=None):
        """
        Returns a set of "Starting" non terminals which have atleast
        one production containing left recursion.
        """
        def edge_functor(node):
            for prod in node.productions:
                if len(prod.symbolUsages) > 0:
                    if prod.symbolUsages[0].symbol.isNonTerminal():
                        yield prod.symbolUsages[0].symbol

        # return graph.tarjan(self.nonTerminals(), edge_functor)
        return graph.all_minimal_cycles(self.nonTerminals(), edge_functor)
