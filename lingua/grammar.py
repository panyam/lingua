import graph
import collections
from utils import enumeratex, TrieNode


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
            return "%s(%s)" % (self.name, self.resultType)
        else:
            return "%s" % self.name

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

    def __cmp__(self, other):
        return cmp(self.symbol, other.symbol)

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


class SymbolString(list):
    """
    A symbol string.
    """
    def __init__(self, symbols=None):
        super(SymbolString, self).__init__()
        self.extend(symbols)

    def validate(self, symbol):
        if type(symbol) is str:
            return SymbolUsage(Symbol(symbol))
        elif type(symbol) is Symbol:
            return SymbolUsage(symbol)
        elif type(symbol) is SymbolUsage:
            return symbol
        else:
            raise Exception("Only strings or Symbol types are allowed")

    def revalOptionals(self):
        symbols = self
        self._numSymbols = len(symbols)
        # optionalTo[i] is True if symbols 0 to i (inclusive) are ALL optional
        # optionalFrom[i] is True if symbols i to end (inclusive) are ALL optional
        isOptional = [su.isOptional for su in symbols]
        optionalTo = isOptional[:]
        optionalFrom = isOptional[:]
        for index, _ in enumerate(optionalTo):
            optionalTo[index] = symbols[index].isOptional
            if index > 0:
                optionalTo[index] = optionalTo[index] and optionalTo[index - 1]
        for i in xrange(self.numSymbols - 1, -1, -1):
            optionalFrom[i] = symbols[i].isOptional
            if i < self.numSymbols - 1:
                optionalFrom[i] = optionalFrom[i] and optionalFrom[i + 1]
        self.optionalTo = optionalTo
        self.optionalFrom = optionalFrom

    def append(self, symbol):
        symbol = self.validate(symbol)
        super(SymbolString, self).append(symbol)
        self.revalOptionals()

    def insert(self, index, symbol):
        symbol = self.validate(symbol)
        super(SymbolString, self).insert(index, symbol)
        self.revalOptionals()

    def remove(self, symbol):
        super(SymbolString, self).remove(symbol)
        self.revalOptionals()

    def extend(self, symbols):
        symbols = symbols or []
        for index, symbol in enumerate(symbols):
            symbols[index] = self.validate(symbol)
        super(SymbolString, self).extend(symbols)
        self.revalOptionals()

    def copy(self, grammar=None):
        return SymbolString([s.copy(grammar) for s in self])

    def isOptionalTo(self, index):
        if index < 0:
            return True
        return self.optionalTo[index]

    def isOptionalFrom(self, index):
        if index >= len(self):
            return True
        return self.optionalFrom[index]

    @property
    def numSymbols(self):
        return self._numSymbols

    def __repr__(self):
        return " ".join(map(str, self))

    def __getslice__(self, start, end):
        return self.__getitem__(slice(start, end))

    def __getitem__(self, index):
        # result = self.symbols[index]
        result = super(SymbolString, self).__getitem__(index)
        if type(index) is slice:
            result = SymbolString(result)
        return result

    def __setitem__(self, index, symbol):
        if type(symbol) is str:
            symbol = SymbolUsage(symbol)
        elif type(symbol) is list:
            symbols = symbol
            for index, symbol in enumerate(symbols):
                if type(symbol) is str:
                    symbols[index] = SymbolUsage(symbol)
            symbol = symbols
        super(SymbolString, self).__setitem__(index, symbol)
        self.revalOptionals()
        # self.symbols[index] = symbol


class Production(object):
    def __init__(self, nonterm, rhs, handler=None):
        self.nonterm = nonterm
        if type(rhs) is list:
            rhs = SymbolString(rhs)
        self.rhs = rhs
        self.handler = handler

    def __repr__(self):
        return "%s -> %s" % (self.nonterm, repr(self.rhs))

    def copy(self, grammar=None):
        outsym = self.nonterm
        if grammar:
            outsym = grammar.symbolByName(self.nonterm.name)
        return Production(outsym, self.rhs.copy(grammar), self.handler)

    def setPredictSet(self, newset=None):
        newset = newset or set()
        self.predictSet = newset

    def removeNullInProduction(self, grammar, start=0):
        """
        Given a production of the form:
            A -> B C D

        returns productions which are same as the above ones but with the
        nullables removed.  If all of B C and D are nullable then the following
        productions are added and returned:

            A -> B | C | D | B C | B D | C D | B C D
        """
        nullables = grammar.nullables
        if start >= self.rhs.numSymbols:
            return []

        su = self.rhs[start]
        newsu = su.copy(grammar)
        newsu.isOptional = False
        rest = self.removeNullInProduction(grammar, start + 1)
        rest = rest or [[]]
        rest_with_sym = [[newsu] + r for r in rest]
        if not su.isOptional and su.symbol not in nullables:
            return rest_with_sym
        else:
            # clone rest
            return rest + rest_with_sym


class ProductionList(object):
    """
    ProductionLists are an easy way to maintain a group of productions instead
    of just storing them all in a list.

    The goals are:

    1. Provide easy ordered iteration as one would do with lists.
    2. Efficient searching of existing/duplicate productions
    3. Allow storage of duplicate productions
    """
    def __init__(self, nonterm, productions=None):
        self.nonterm = nonterm
        self.productions = productions or []
        self.prodsByPrefix = TrieNode()

    def copy(self, grammar=None):
        nonterm = self.nonterm
        if grammar:
            nonterm = grammar.symbolByName(self.nonterm.name)
        prodcopy = [p.copy(grammar) for p in self.productions]
        return ProductionList(nonterm, prodcopy)

    def __repr__(self):
        return " ; ".join(map(repr, self.productions))

    def addProduction(self, production):
        production.nonterm = self.nonterm
        # add production if not a duplicate
        for prod in self.productions:
            if prod.handler == production.handler and \
                    prod.rhs.numSymbols == production.rhs.numSymbols:
                # check if symbols are same:
                found = True
                for sym1, sym2 in zip(prod.rhs, production.rhs):
                    if cmp(sym1, sym2) != 0:
                        found = False
                        break
                if found:
                    return
        self.productions.append(production)

    def removeProduction(self, production):
        if type(production) is int:
            del self.productions[production]
        else:
            for index, prod in self.productions:
                if prod == production:
                    del self.productions[index]
                    break

    def removeNullProductions(self, grammar):
        for prod in self.productions:
            if prod.rhs.numSymbols > 0:
                newprods = prod.removeNullInProduction(grammar)
                for symbols in newprods:
                    newprod = Production(self.nonterm, symbols, prod.handler)
                    self.addProduction(newprod)

        # remove null productions now
        for index in xrange(len(self.productions) - 1, -1, -1):
            prod = self.productions[index]
            if prod.rhs.numSymbols == 0:
                del self.productions[index]

    def removeCycles(self, grammar, cycles=None):
        """
        Remove cycles from this set of productions.
        """
        cycles = cycles or grammar.cycles

    def __iter__(self):
        return iter(self.productions)

    def __len__(self):
        return len(self.productions)

    def __getitem__(self, index):
        return self.productions[index]

    def __setitem__(self, index, prod):
        self.productions[index] = prod

    def __delitem__(self, index):
        del self.productions[index]

    def findProduction(self, symbols):
        """
        Returns a production that has the same symbols in the given list
        """
        pass


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
        self.setModified()

    @property
    def modified(self):
        return self._modified

    def setModified(self):
        self._firstSets = None
        self._followSets = None
        self._nullables = None
        self._modified = True

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
            out.productions[name] = productions.copy(self)
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
        self.setModified()
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
        self.setModified()
        return symbol

    def addProduction(self, nonterm, production):
        production.nonterm = nonterm
        if nonterm not in self.productions:
            self.productions[nonterm] = ProductionList(nonterm)
        self.productions[nonterm].addProduction(production)
        self.setModified()

    def findProduction(self, nonterm, symbols):
        if nonterm in self.productions:
            productions = self.productions[nonterm]
            for prod in productions:
                if prod.matchesSymbols(symbols):
                    return prod
        return None

    def allProductions(self):
        for nonterm, productions in self.productions.iteritems():
            for prod in productions:
                yield nonterm, prod

    def productionsFor(self, nonterm, reverse=False, indexed=False):
        name = nonterm
        if hasattr(nonterm, "name"):
            name = nonterm.name
        if name in self.productions:
            return enumeratex(self.productions[name], reverse, indexed)
        else:
            return []

    @property
    def nullables(self):
        """
        Get the nullable non terminals in the grammar.
        """
        if self._nullables is not None:
            return self._nullables
        out = set()
        for name, nonterm in self.nonTerminalsByName.iteritems():
            # first find all non terms that already have a
            # production with only null
            for prod in self.productionsFor(nonterm):
                if prod.rhs is None or prod.rhs.numSymbols == 0:
                    out.add(nonterm)

        # Find productions now that are of the form:
        # Y -> X
        # where X is a nullable (as per step 1) or is optional
        for name, nonterm in self.nonTerminalsByName.iteritems():
            if nonterm not in out:
                for prod in self.productionsFor(nonterm):
                    if prod.rhs.numSymbols == 1:
                        symbol = prod.rhs[0].symbol
                        if prod.rhs[0].isOptional or  \
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
                            out for su in prod.rhs]):
                        out.add(nonterm)
                        break
        self._nullables = out
        return out

    @property
    def firstSets(self):
        if self._firstSets is not None:
            return self._firstSets

        nullables = self.nullables
        out = {}

        # Now look at productions of the form:
        # A -> a B   (ie first symbol is a terminal)
        for name, nonterm in self.nonTerminalsByName.iteritems():
            fset = out[nonterm] = set()
            for prod in self.productionsFor(nonterm):
                if prod.rhs.numSymbols > 0:
                    symbol = prod.rhs[0].symbol
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
                for symUsage in prod.rhs:
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
        self._firstSets = out
        return out

    def followSets(self, startnt=None):
        startnt = startnt or self.nonTerminalsByIndex[0]
        if type(startnt) is str:
            startnt = self.nonTerminalsByName[startnt]

        nullables = self.nullables
        firstSets = self.firstSets

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
                        nUsages = prod.rhs.numSymbols
                        nullableFrom = [False] * nUsages
                        firstFrom = [set() for i in xrange(0, nUsages)]
                        for i in xrange(nUsages - 1, -1, -1):
                            symUsage = prod.rhs[i]
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

    def evalPredictSets(self, startnt=None):
        nullables = self.nullables
        firstSets = self.firstSets
        followSets = self.followSets(startnt)
        for nonterm, prod in self.allProductions():
            nUsages = prod.rhs.numSymbols
            nullableFrom = [False] * nUsages
            firstFrom = [set() for i in xrange(0, nUsages)]
            for i in xrange(nUsages - 1, -1, -1):
                symUsage = prod.rhs[i]
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
                print "Prod: %s, predSet: [%s]" % (prod, " ".join(map(str, list(pset))))
            else:
                print "Prod: %s, predSet: []" % prod

    @property
    def cycles(self):
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
                for i, su in enumerate(prod.rhs):
                    rhs = prod.rhs
                    if rhs.isOptionalTo(i - 1) and rhs.isOptionalFrom(i + 1):
                        if su.isNonTerminal:
                            yield su.symbol, prod
                    else:
                        break

        return graph.all_minimal_cycles(self.nonTerminalsByIndex, edge_functor)

    @property
    def leftRecursion(self):
        """
        Returns a set of "Starting" non terminals which have atleast
        one production containing left recursion.
        """
        def edge_functor(node):
            for prod in self.productionsFor(node):
                for symUsage in prod.rhs:
                    if symUsage.isNonTerminal:
                        yield symUsage.symbol, prod
                    if not symUsage.isOptional:
                        break
        return graph.all_minimal_cycles(self.nonTerminalsByIndex, edge_functor)

    def removes(self, symbols, invert=False):
        """
        Removes all productions which contain symbols in the given symbol list.
        If invert is True then productions with symbols NOT in the production
        are removed.
        Null productions are not affected.
        """
        for index in xrange(len(self.nonTerminalsByIndex) - 1, -1, -1):
            nonterm = self.nonTerminalsByIndex[index]
            if (nonterm in symbols and not invert) or \
                    (invert and nonterm not in symbols):
                del self.nonTerminalsByIndex[index]
                del self.nonTerminalsByName[nonterm.name]
                del self.productions[nonterm.name]

        for nonterm in self.nonTerminalsByName:
            prodlist = self.productions[nonterm]
            for index, prod in enumeratex(prodlist, reverse=True, indexed=True):
                for su in prod.rhs:
                    if (su.symbol in symbols and not invert) or \
                            (invert and su.symbol not in symbols):
                        del prodlist[index]
                        break

    def terminalDerivingSymbols(self):
        derives_terminal = set()
        nadded = -1
        while nadded != 0:
            nadded = 0
            for nonterm, prod in self.allProductions():
                allDerive = True
                for su in prod.rhs:
                    if su.symbol not in derives_terminal:
                        if su.isTerminal:
                            derives_terminal.add(su.symbol)
                            nadded += 1
                        else:
                            allDerive = False
                if allDerive and nonterm not in derives_terminal:
                    derives_terminal.add(nonterm)
                    nadded += 1
        return derives_terminal

    def reachableSymbols(self, startnt=None):
        startnt = startnt or self.nonTerminalsByIndex[0]
        if type(startnt) is str:
            startnt = self.nonTerminalsByName[startnt]

        reachable = set((startnt,))
        queue = [startnt]
        while queue:
            curr = queue.pop(0)
            productions = self.productionsFor(curr)
            for prod in productions:
                for su in prod.rhs:
                    if su.isNonTerminal and su.symbol not in reachable:
                        queue.append(su.symbol)
                    reachable.add(su.symbol)
        return reachable

    def removeUselessSymbols(self, startnt=None):
        """
        Returns symbols that do not derive any terminal strings or symbols that
        cannot be reached from the Start symbol and a grammar with these symbols
        removed.
        """
        # First find symbols that do not derive any terminal strings and
        # remove them
        derives_terminal = self.terminalDerivingSymbols()
        print "Derives Terminals: ", derives_terminal
        self.removes(derives_terminal, invert=True)

        # Now find symbols that cannot be derived from the start symbol
        # and remove them
        reachable_symbols = self.reachableSymbols(startnt)
        print "Reachable Symbols: ", reachable_symbols
        self.removes(reachable_symbols, invert=True)

    def removeNullProductions(self):
        """
        Return a grammar with null productions removed.
        Also note that all "optional" indicators will also be removed, ie

        A -> ? B C

        will be replaced with:

        A -> C
        A -> B C
        """
        for nonterm in self.nonTerminalsByIndex:
            self.productions[nonterm].removeNullProductions(self)
        self.setModified()

    def removeLeftRecursionFor(self, nonterm, newnamefunc=None):
        """
        Removes direct left recursion for a particular non terminal if any.
        For the given terminal, A, replaces the productions of the form:

            A -> A a1 | A a2 ... | A an | b1 | b2 | b3 ... bm

        with:

            A -> b1 A' | b2 A' | ... bm A'
            A' -> a1 A' | a2 A' | ... an A' | epsilon
        """
        if type(nonterm) is str:
            nonterm = self.nonTerminalsByName[nonterm]
        # First check if this NT has left recursive productions
        isLeftRecursive = False
        for prod in self.productionsFor(nonterm):
            if prod.rhs[0].symbol == nonterm:
                isLeftRecursive = True
                break
        if not isLeftRecursive:
            return

        # Add a new nonterminal that will be right recursive
        def default_newnamefunc(ntname):
            count = 1
            newname = nonterm.name + str(count)
            while newname in self.nonTerminalsByName:
                count += 1
                newname = nonterm.name + str(count)
            return newname

        newnamefunc = newnamefunc or default_newnamefunc
        newname = newnamefunc(nonterm.name)
        newnonterm = Symbol(newname, nonterm.resultType)
        self.addNonTerminal(newnonterm)

        prodlist = self.productions[nonterm]
        for index, prod in enumeratex(prodlist, indexed=True, reverse=True):
            if prod.rhs[0].symbol == nonterm:
                # we have a left recursion:
                # A -> A ax
                # So change to:
                # remove rule and add following to A'
                # A' -> ax A'
                prodlist.removeProduction(index)
                prod.rhs.append(SymbolUsage(newnonterm, prod.rhs[0].varname))
                del prod.rhs[0]
                self.addProduction(newnonterm, prod)
            else:
                # We have non left recursive rule:
                # A -> bk
                # Replace rule with:
                # A -> bk A'
                prod.rhs.append(newnonterm)
        # finally add the epsilon production
        self.addProduction(newnonterm, Production(newnonterm, []))

    def removeCycles(self):
        """
        Returns an equivalent grammar with cycles removed.
        """
        if self.nullables:
            self.removeNullProductions()

        while True:
            cycles = self.cycles
            if not cycles:
                return
            for start_sym, cycle in cycles:
                # Find all non terminals in this cycle
                cycle_symbols = set([sym for rule, sym in cycle])

                # Find the union of all production of all
                # non terminals in cycle_symbols
                prod_union = []
                for sym in cycle_symbols:
                    for prod in self.productionsFor(sym):
                        if prod.rhs.numSymbols != 1 or prod.rhs[0].symbol not in cycle_symbols:
                            prod_union.append(prod)

                # For each non term in the cycle, add all productions in
                # prod_union and remove all productions of the form:
                # M -> N where M and N are BOTH in cycle_symbols
                for rule, sym in cycle:
                    prodlist = self.productions[sym]
                    for index, prod in self.productionsFor(sym, indexed=True, reverse=True):
                        if prod.rhs.numSymbols == 1 or prod.rhs[0].symbol in cycle_symbols:
                            prodlist.removeProduction(index)

                    for prod in prod_union:
                        prodlist.addProduction(prod.copy(self))

    def removeLeftRecursion(self, orderer=None):
        """
        Removes all left recursion.  If nullables or cycles exist,
        those are removed first.

        The removal of left recursion is based on Paull's algorithm and is
        affected by the ordering of symbols.  The function to order the
        symbols can be provided with the orderer parameter.  By default the
        existing order is used.
        """
        if self.nullables:
            self.removeNullProductions()

        if self.cycles:
            self.removeCycles()

        symbols = self.nonTerminalsByIndex[:]
        if orderer:
            symbols = orderer(symbols)

        for i, Ai in enumerate(symbols):
            print "Symbol Ai: ", i, Ai
            if Ai not in self.productions:
                continue
            for j in xrange(i):
                Aj = symbols[j]
                if j == 174:
                    import ipdb
                    ipdb.set_trace()
                if Aj not in self.productions:
                    continue
                print "Symbol Aj: ", j, Aj
                aiprods = self.productions[Ai]
                for ai, aiprod in enumeratex(aiprods, indexed=True, reverse=True):
                    if aiprod.rhs[0].symbol == Aj:
                        aiprods.removeProduction(ai)
                        ajprods = self.productions[Aj]
                        for ajprod in enumeratex(ajprods):
                            # replace this production:
                            # Ai -> Aj x
                            #
                            # with
                            # Ai -> b1 x | b2 x | ... | bn x
                            #
                            # where
                            # Aj -> b1 | b2 | ... | bn
                            newsyms = ajprod.rhs[:] + aiprod.rhs[1:]
                            newprod = Production(Ai, newsyms, aiprod.handler)
                            aiprods.addProduction(newprod)
            # Remove left recursion from Ai production if any
            self.removeLeftRecursionFor(Ai)
