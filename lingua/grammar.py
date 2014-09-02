# import itertools
import graph
import collections
import pudb


class Symbol(object):
    def __init__(self, name, resultType=None):
        self.index = -1
        self.name = name
        self._isTerminal = True
        self.resultType = resultType

    def copy(self):
        out = Symbol(self.name, self.resultType)
        out.isTerminal = self.isTerminal
        out.index = self.index
        return out

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

    @property
    def isTerminal(self):
        return self._isTerminal

    @isTerminal.setter
    def isTerminal(self, val):
        self._isTerminal = val

    @property
    def isNonTerminal(self):
        return not self._isTerminal


class SymbolUsage(object):
    def __init__(self, symbol, varname=None, isOptional=False):
        self.symbol = symbol
        self.varname = varname
        self.isOptional = isOptional

    def copy(self, grammar=None):
        outsym = self.symbol
        if grammar:
            outsym = grammar.symbolByName(self.symbol.name)
        return SymbolUsage(outsym, self.varname, self.isOptional)

    @property
    def isTerminal(self):
        return self.symbol.isTerminal

    @property
    def isNonTerminal(self):
        return self.symbol.isNonTerminal

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
        self._numSymbols = len(self.symbolUsages)

        # optionalTo[i] is True if symbols 0 to i (inclusive) are ALL optional
        # optionalFrom[i] is True if symbols i to end (inclusive) are ALL optional
        isOptional = [su.isOptional for su in self.symbolUsages]
        optionalTo = isOptional[:]
        optionalFrom = isOptional[:]
        for index, _ in enumerate(optionalTo):
            optionalTo[index] = self.symbolUsages[index].isOptional
            if index > 0:
                optionalTo[index] = optionalTo[index] and optionalTo[index - 1]
        for i in xrange(self.numSymbols - 1, -1, -1):
            optionalFrom[i] = self.symbolUsages[i].isOptional
            if i < self.numSymbols - 1:
                optionalFrom[i] = optionalFrom[i] and optionalFrom[i + 1]
        self.optionalTo = optionalTo
        self.optionalFrom = optionalFrom

    def __repr__(self):
        return "%s -> %s" % (self.nonterm, " ".join(map(str, self.symbolUsages)))

    def isOptionalTo(self, index):
        if index < 0:
            return True
        return self.optionalTo[index]

    def isOptionalFrom(self, index):
        if index >= len(self.symbolUsages):
            return True
        return self.optionalFrom[index]

    def copy(self, grammar=None):
        outsym = self.nonterm
        if grammar:
            outsym = grammar.symbolByName(self.nonterm.name)
        return Production(outsym, [s.copy(grammar) for s in self.symbolUsages], self.handler)

    def setPredictSet(self, newset=None):
        newset = newset or set()
        self.predictSet = newset

    @property
    def numSymbols(self):
        return self._numSymbols


class Reduction(object):
    def __init__(self, production, results):
        self.production = production
        self.results = results


class Grammar(object):
    EOF = Symbol("EOF")

    def __init__(self):
        self.terminalsByName = {}
        self.nonTerminalsByName = {}
        self.terminalsByIndex = []
        self.nonTerminalsByIndex = []
        self.productions = {}
        self.eofToken = Grammar.EOF

    def copy(self):
        out = Grammar()
        out.eofToken = self.eofToken.copy()

        # copy symbols first
        out.terminalsByIndex = [t.copy() for t in self.terminalsByIndex]
        out.nonTerminalsByIndex = [nt.copy() for nt in self.nonTerminalsByIndex]
        for term in out.terminalsByIndex:
            out.terminalsByName[term.name] = term
        for nonterm in out.nonTerminalsByIndex:
            out.nonTerminalsByName[nonterm.name] = nonterm

        # copy productions
        for name, productions in self.productions.iteritems():
            out.productions[name] = [p.copy(self) for p in productions]
        return out

    def symbolByName(self, name):
        if name in self.terminalsByName:
            return self.terminalsByName[name]
        else:
            return self.nonTerminalsByName[name]

    def isTerminal(self, symbol):
        return symbol in self.terminalsByName

    def isNonTerminal(self, symbol):
        return symbol in self.nonTerminalsByName

    def addTerminal(self, symbol, resultType=None):
        if type(symbol) is str:
            assert symbol not in self.nonTerminalsByName, "Symbol is already classified as a non terminal"
            if symbol in self.terminalsByName:
                symbol = self.terminalsByName[symbol]
            else:
                symbol = Symbol(symbol, resultType)
        else:
            assert symbol.name not in self.nonTerminalsByName, "Symbol is already classified as a non terminal"
        if symbol.name not in self.terminalsByName:
            self.terminalsByName[symbol.name] = symbol
            self.terminalsByIndex.append(symbol)
        symbol = self.terminalsByName[symbol]
        symbol.isTerminal = True
        return symbol

    def addNonTerminal(self, symbol, resultType=None):
        if type(symbol) is str:
            if symbol in self.nonTerminalsByName:
                symbol = self.nonTerminalsByName[symbol]
            elif symbol in self.terminalsByName:
                symbol = self.terminalsByName[symbol]
            else:
                symbol = Symbol(symbol, resultType)
        if symbol.name in self.terminalsByName:
            del self.terminalsByName[symbol.name]
            index = self.terminalsByIndex.index(symbol)
            del self.terminalsByIndex[index]
        if symbol.name not in self.nonTerminalsByName:
            self.nonTerminalsByIndex.append(symbol)
        self.nonTerminalsByName[symbol.name] = symbol
        symbol.isTerminal = False
        return symbol

    def addProduction(self, nonterm, production):
        production.nonterm = nonterm
        if nonterm not in self.productions:
            self.productions[nonterm] = []
        self.productions[nonterm].append(production)

    def allProductions(self):
        for nonterm, productions in self.productions.iteritems():
            for prod in productions:
                yield nonterm, prod

    def productionsFor(self, nonterm):
        name = nonterm
        if hasattr(nonterm, "name"):
            name = nonterm.name
        if name in self.productions:
            return self.productions[name]
        else:
            return []

    def nullables(self):
        """
        Get the nullable non terminals in the grammar.
        """
        out = set()
        for nonterm in self.nonTerminalsByName.iteritems():
            # first find all non terms that already have a
            # production with only null
            for prod in self.productionsFor(nonterm):
                if prod.symbolUsages is None or prod.numSymbols == 0:
                    out.add(nonterm)

        # Find productions now that are of the form:
        # Y -> X
        # where X is a nullable (as per step 1) or is optional
        for name, nonterm in self.nonTerminalsByName.iteritems():
            if nonterm not in out:
                for prod in self.productionsFor(nonterm):
                    if prod.numSymbols == 1:
                        symbol = prod.symbolUsages[0].symbol
                        if prod.symbolUsages[0].isOptional or  \
                                (symbol.isNonTerminal and symbol in out):
                            out.add(nonterm)
                            break

        # Finally for all productions of the form:
        # Y -> A B C ... N
        # add Y to the nullable list if all of A, B and C are nullable
        for name, nonterm in self.nonTerminalsByName.iteritems():
            if nonterm not in out:
                for prod in self.productionsFor(nonterm):
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
        for name, nonterm in self.nonTerminalsByName.iteritems():
            fset = out[nonterm] = set()
            for prod in self.productionsFor(nonterm):
                if prod.numSymbols > 0:
                    symbol = prod.symbolUsages[0].symbol
                    if symbol.isTerminal:
                        fset.add(symbol)

        # First set of terminals is the terminal itself
        for name, symbol in self.terminalsByName.iteritems():
            out[symbol] = set((symbol,))

        def dfs(nonterm, populated, fsets, nullables):
            fset = fsets[nonterm]
            if nonterm in populated:
                return fset
            populated.add(nonterm)
            for prod in self.productionsFor(nonterm):
                for symUsage in prod.symbolUsages:
                    symbol = symUsage.symbol
                    if symbol.isTerminal:
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
        for nonterm in self.nonTerminalsByName:
            dfs(nonterm, set(), out, nullables)
        return out

    def followSets(self, startnt, nullables=None, firstSets=None):
        startnt = startnt or self.nonTerminalsByIndex[0]
        if type(startnt) is str:
            startnt = self.nonTerminalsByName[startnt]

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
                    for prod in self.productionsFor(nonterm):
                        nUsages = prod.numSymbols
                        nullableFrom = [False] * nUsages
                        firstFrom = [set() for i in xrange(0, nUsages)]
                        for i in xrange(nUsages - 1, -1, -1):
                            symUsage = prod.symbolUsages[i]
                            symbol = symUsage.symbol
                            if symbol.isNonTerminal and symbol not in visited:
                                queue.append(symbol)

                            isNullable = symbol in nullables or symUsage.isOptional
                            firstFrom[i].update(firstSets[symbol])
                            if i == nUsages - 1:
                                nullableFrom[i] = isNullable
                                if nullableFrom[i] and symbol.isNonTerminal:
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
                                if symbol.isNonTerminal:
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

    def evalPredictSets(self, startnt, nullables=None, firstSets=None, followSets=None):
        nullables = nullables or self.nullables()
        firstSets = firstSets or self.firstSets(nullables)
        followSets = followSets or self.followSets(startnt, nullables, firstSets)
        for nonterm, prod in self.allProductions():
            nUsages = prod.numSymbols
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
                    pset.update(followSets[nonterm])
            else:
                pset.update(followSets[nonterm])
            prod.setPredictSet(pset)
            if pset:
                print "Prod: %s, predSet: [%s]" % (nonterm, prod, " ".join(map(str, list(pset))))
            else:
                print "Prod: %s, predSet: []" % (nonterm, prod)

    def detectCycles(self):
        """
        Returns all cycles.
        """
        def edge_functor(node):
            """
            Returns the edge of the given nonterm
            For a nt such that:

                S -> alpha1 X1 beta1 |
                     alpha2 X2 beta2 |
                     ...
                     alphaN XN betaN |

            S's neighbouring nodes would be Xk if all of alphak is optional
            AND all of betak is optional
            """
            for prod in self.productionsFor(node):
                for i, su in enumerate(prod.symbolUsages):
                    if prod.isOptionalTo(i - 1) and prod.isOptionalFrom(i + 1):
                        if su.isNonTerminal:
                            yield su.symbol, prod
                    else:
                        break

        return graph.all_minimal_cycles(self.nonTerminalsByIndex, edge_functor)

    def detectLeftRecursion(self):
        """
        Returns a set of "Starting" non terminals which have atleast
        one production containing left recursion.
        """
        def edge_functor(node):
            for prod in self.productionsFor(node):
                for symUsage in prod.symbolUsages:
                    if symUsage.isNonTerminal:
                        yield symUsage.symbol, prod
                    if not symUsage.isOptional:
                        break

        return graph.all_minimal_cycles(self.nonTerminalsByIndex, edge_functor)

    def removeCycles(self):
        """
        Returns an equivalent grammar with cycles removed.
        """
        if self.nullable():
            raise Exception("Grammar has null productions.  Cycle removal will not work")

        cycles = self.detectCycles()
        if not cycles:
            return None

        # make a copy to alter and return
        out = self.copy()

        non_cycle_prods = {}
        for cycle in cycles:
            # todo - see if we need to convert the cycle into a set
            # for fast lookups

            # For each nonterm in the cycle
            for nonterm in cycle:
                # get all productions for this nonterm which does *not* begin
                # with any other nonterms in the cycle
                for prod in self.productionsFor(nonterm):
                    if prod.numSymbols != 1 and prod.symbolUsages(0):
                        continue
                    if len(prod) > 1 or prod[0].isTerminal or prod not in cycle:
                        if nonterm not in non_cycle_prods:
                            non_cycle_prods[nonterm] = []
                        non_cycle_prods[nonterm].append(prod)

        # now for all nonterm prods
        pudb.set_trace()
        return out

    def eliminateLeftRecursion(self):
        pass

    def eliminateNullProductions(self, nullables=None):
        """
        Return a grammar with null productions removed
        """
        nullables = nullables or self.nullables()
