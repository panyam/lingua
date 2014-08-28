import itertools
import graph
import collections


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

    def isTerminal(self):
        return len(self.productions) == 0

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

    def isTerminal(self):
        return self.symbol.isTerminal()

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

    def __repr__(self):
        return "%s -> %s" % (self.nonterm, " ".join(map(str, self.symbolUsages)))

    def setPredictSet(self, newset=None):
        newset = newset or set()
        self.predictSet = newset


class Reduction(object):
    def __init__(self, production, results):
        self.production = production
        self.results = results


class Grammar(object):
    EOF = Symbol("")

    def __init__(self):
        self.symbolsByName = {}
        self.symbolsByIndex = []
        self.eofToken = Grammar.EOF

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

    def allProductions(self):
        for nonterm in self.nonTerminals():
            for prod in nonterm.productions:
                yield nonterm, prod

    def nonTerminals(self):
        return itertools.ifilter(lambda x: x.isNonTerminal(), self.symbolsByIndex)

    def nullables(self):
        """
        Get the nullable non terminals in the grammar.
        """
        out = set()
        for nonterm in self.nonTerminals():
            # first find all non terms that already have a
            # production with only null
            for prod in nonterm.productions:
                if prod.symbolUsages is None or len(prod.symbolUsages) == 0:
                    out.add(nonterm)

        # Find productions now that are of the form:
        # Y -> X
        # where X is a nullable (as per step 1) or is optional
        for nonterm in self.nonTerminals():
            if nonterm not in out:
                for prod in nonterm.productions:
                    if len(prod.symbolUsages) == 1:
                        symbol = prod.symbolUsages[0].symbol
                        if prod.symbolUsages[0].isOptional or  \
                                (symbol.isNonTerminal() and symbol in out):
                            out.add(nonterm)
                            break

        # Finally for all productions of the form:
        # Y -> A B C ... N
        # add Y to the nullable list if all of A, B and C are nullable
        for nonterm in self.nonTerminals():
            if nonterm not in out:
                for prod in nonterm.productions:
                    if all([su.isOptional or su.symbol in
                            out for su in prod.symbolUsages]):
                        out.add(nonterm)
                        break
        return out

    def firstSets(self, nullables=None):
        nullables = nullables or self.nullables()
        out = {}

        # Now look at productions of the form:
        # A -> a B   (ie first symbol is a terminal)
        for symbol in self.symbolsByIndex:
            if symbol.isNonTerminal():
                nonterm = symbol
                fset = out[nonterm] = set()
                for prod in nonterm.productions:
                    if len(prod.symbolUsages) > 0:
                        symbol = prod.symbolUsages[0].symbol
                        if symbol.isTerminal():
                            fset.add(symbol)
            else:
                out[symbol] = set((symbol,))

        def dfs(nonterm, populated, fsets, nullables):
            fset = fsets[nonterm]
            if nonterm in populated:
                return fset
            populated.add(nonterm)
            for prod in nonterm.productions:
                for symUsage in prod.symbolUsages:
                    symbol = symUsage.symbol
                    if symbol.isTerminal():
                        fset.add(symbol)
                        if not symUsage.isOptional:
                            # no more FIRSTs in this production
                            break
                    else:
                        # add FIRST set to curr nonterm's first set
                        dfs(symbol, populated, fsets, nullables)
                        fset.update(fsets[symbol])
                        if symbol not in nullables:
                            break

        # Now go through all productions of the form:
        #   A -> X Y Z
        # First(A) would contain First(X Y Z)
        # First(X Y Z) would contain First(X) + First(Y Z) if X is nullable
        # and so on
        for nonterm in self.nonTerminals():
            dfs(nonterm, set(), out, nullables)
        return out

    def followSets(self, startnt, nullables=None, firstSets=None):
        startnt = startnt or self.symbolsByIndex[0]
        if type(startnt) is str:
            startnt = self.symbolsByName[startnt]

        nullables = nullables or self.nullables()
        firstSets = firstSets or self.firstSets(nullables)

        follow = collections.defaultdict(set)
        follow[startnt] = set((self.eofToken,))

        def visit(follow):
            queue = [startnt]
            visited = {}
            numAdded = 0
            while queue:
                nonterm = queue.pop(0)
                if nonterm not in visited:
                    visited[nonterm] = True
                    for prod in nonterm.productions:
                        nUsages = len(prod.symbolUsages)
                        nullableFrom = [False] * nUsages
                        firstFrom = [set() for i in xrange(0, nUsages)]
                        for i in xrange(nUsages - 1, -1, -1):
                            symUsage = prod.symbolUsages[i]
                            symbol = symUsage.symbol
                            if symbol.isNonTerminal() and symbol not in visited:
                                queue.append(symbol)

                            isNullable = symbol in nullables or symUsage.isOptional
                            firstFrom[i].update(firstSets[symbol])
                            if i == nUsages - 1:
                                nullableFrom[i] = isNullable
                                if nullableFrom[i] and symbol.isNonTerminal():
                                    # last symbol AND it is nullable so add
                                    # Follow[nonterm] to Folow[symbol]
                                    # since symUsage is nullable
                                    size = len(follow[symbol])
                                    follow[symbol].update(follow[nonterm])
                                    numAdded += len(follow[symbol]) - size
                            else:
                                nullableFrom[i] = isNullable and nullableFrom[i + 1]
                                if isNullable:
                                    firstFrom[i].update(firstFrom[i + 1])
                                if symbol.isNonTerminal():
                                    size = len(follow[symbol])
                                    follow[symbol].update(firstFrom[i + 1])
                                    numAdded += len(follow[symbol]) - size
                                if nullableFrom[i + 1]:
                                    size = len(follow[symbol])
                                    follow[symbol].update(follow[nonterm])
                                    numAdded += len(follow[symbol]) - size
            return numAdded
        while True:
            n = visit(follow)
            print "Num Added: ", n
            if n == 0:
                break
        return follow

    def evalPredictSets(self, nullables=None, firstSets=None, followSets=None):
        nullables = nullables or self.nullables()
        firstSets = firstSets or self.firstSets(nullables)
        followSets = followSets or self.followSets(None, nullables, firstSets)
        for nonterm, prod in self.allProductions():
            nUsages = len(prod.symbolUsages)
            nullableFrom = [False] * nUsages
            firstFrom = [set() for i in xrange(0, nUsages)]
            for i in xrange(nUsages - 1, -1, -1):
                symUsage = prod.symbolUsages[i]
                symbol = symUsage.symbol
                isNullable = symbol in nullables or symUsage.isOptional
                firstFrom[i].update(firstSets[symbol])
                nullableFrom[i] = isNullable
                if i < nUsages - 1 and isNullable:
                    nullableFrom[i] = isNullable and nullableFrom[i + 1]
                    firstFrom[i].update(firstFrom[i + 1])

            pset = set()
            if nUsages > 0:
                pset.update(firstFrom[0])
                if nullableFrom[0]:
                    pset.update(followSets[prod.nonterm])
            else:
                pset.update(followSets[prod.nonterm])
            prod.setPredictSet(pset)
            if pset:
                print "Prod: %s, predSet: [%s]" % (prod, " ".join(map(str, list(pset))))
            else:
                print "Prod: %s, predSet: []" % prod

    def predictAndFollowSets(self, startnt, firstSets=None, nullables=None):
        """
        Calcualtes the predict and follow sets.  These are mutually recursive
        functions.
        """
        def predict(nonterm, psets, fsets, nullables, pvisited, fvisited):
            if nonterm not in pvisited:
                pvisited[nonterm] = True
                # First look at productions of the form:
                # A -> a B   (ie first symbol is a terminal)
                # and add "a" to the predict sets of A
                pset = psets[nonterm] = set()
                for prod in nonterm.productions:
                    for symUsage in prod.symbolUsages:
                        symbol = symUsage.symbol
                        if symbol.isTerminal():
                            pset.add(symbol)
                        else:
                            predict(symbol, psets, fsets, nullables, pvisited, fvisited)
                            pset.update(psets[symbol])
                        if not symUsage.isOptional:
                            break

                if nonterm in nullables:
                    follow(nonterm, psets, fsets, nullables, pvisited, fvisited)
                    pset.update(fsets[nonterm])

        def follow(nonterm, psets, fsets, nullables, pvisited, fvisited):
            if nonterm not in fvisited:
                fvisited[nonterm] = True

                # For all productions such that:
                for prod in self.allProductions():
                    numSymbols = len(prod.symbolUsages)
                    for index, symUsage in enumerate(prod.symbolUsages):
                        if index == numSymbols - 1:
                            # we have:
                            # B -> ..... A
                            # So add every token in Follow(B) to Follow(A)
                            follow(prod.nonterm, psets, fsets, nullables,
                                   pvisited, fvisited)
                            fsets[nonterm].update(fsets[prod.nonterm])
                        else:
                            nextSymUsage = prod.symbolUsages[index + 1]
                            if nextSymUsage.isTerminal():
                                # if we have:
                                # X ->  ... A b ...
                                # Add the terminal b to the follow set of A
                                fsets[nonterm].add(nextSymUsage.symbol)
                            else:
                                # add Predict(B) to Follow(A)
                                predict(prod.nonterm, psets, fsets, nullables,
                                        pvisited, fvisited)
                                fsets[nonterm].update(psets[prod.nonterm])

        if type(startnt) is str:
            startnt = self.symbolsByName[startnt]
        nullables = nullables or self.nullables()
        fsets = {}
        psets = {}
        fsets[startnt] = set((self.eofToken,))
        predict(startnt, psets, fsets, nullables, {}, {})
        return psets, fsets

    def detectLeftRecursion(self):
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

    def eliminateLeftRecursion(self):
        pass

