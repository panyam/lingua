
# import ipdb
# import sys
import StringIO
import grammar
import graph

reload(grammar)
reload(graph)

TOKEN_ERROR = -1
TOKEN_EOF = 0
TOKEN_OPAREN = 1
TOKEN_CPAREN = 2
TOKEN_COLON = 3
TOKEN_SEMICOLON = 4
TOKEN_BLOCK = 5
TOKEN_OBRACE = 6
TOKEN_CBRACE = 7
TOKEN_ARROW = 8
TOKEN_IDENT = 9
TOKEN_STRING = 10
TOKEN_QMARK = 11
TOKEN_PIPE = 12

token_labels = {
    TOKEN_ERROR: "ERROR",
    TOKEN_EOF: "EOF",
    TOKEN_OPAREN: "OPAREN",
    TOKEN_CPAREN: "CPAREN",
    TOKEN_COLON: "COLON",
    TOKEN_SEMICOLON: "SEMICOLON",
    TOKEN_BLOCK: "BLOCK",
    TOKEN_OBRACE: "OBRACE",
    TOKEN_CBRACE: "CBRACE",
    TOKEN_ARROW: "ARROW",
    TOKEN_IDENT: "IDENT",
    TOKEN_STRING: "STRING",
    TOKEN_QMARK: "QMARK",
    TOKEN_PIPE: "PIPE",
}


def tokenize(input):
    """
    Scans a elk grammar like grammar file.
    """
    prevch = None

    instream = input
    if type(input) is str:
        instream = StringIO.StringIO(input)

    def reachedEof(ch): return ch == '' or ch is None

    def read_identifier(strsofar=''):
        prevch = None
        nextch = instream.read(1)
        while nextch.isalnum() or nextch == '_':
            strsofar += nextch
            nextch = instream.read(1)

        if not reachedEof(nextch):
            prevch = nextch
        return TOKEN_IDENT, strsofar, prevch

    def read_block():
        out = ''
        nextch = instream.read(1)
        while not reachedEof(nextch):
            if nextch == '%':
                nextch = instream.read(1)
                if nextch != '}':
                    out += '%'
                    out += nextch
                else:
                    return TOKEN_BLOCK, out
            else:
                out += nextch
            nextch = instream.read(1)
        return TOKEN_ERROR, "Unexpected end of file in block"

    finished = False
    while not finished:
        # skip spaces
        if prevch:
            nextch = prevch
            prevch = None
        else:
            nextch = instream.read(1)

        while nextch.isspace():
            nextch = instream.read(1)

        if nextch == '(':
            yield TOKEN_OPAREN, None
        elif nextch == ')':
            yield TOKEN_CPAREN, None
        elif nextch == ':':
            yield TOKEN_COLON, None
        elif nextch == ';':
            yield TOKEN_SEMICOLON, None
        elif nextch == '{':
            nextch = instream.read(1)
            if nextch == '%':
                yield read_block()
            else:
                prevch = nextch
                yield TOKEN_OBRACE, None
        elif nextch == '}':
            yield TOKEN_CBRACE, None
        elif nextch == '|':
            yield TOKEN_PIPE, None
        elif nextch == '?':
            yield TOKEN_QMARK, None
        elif nextch == '-':
            nextch = instream.read(1)
            if nextch != '>':
                yield TOKEN_ERROR, "Expected '>', Found: '%s'" % nextch
            else:
                yield TOKEN_ARROW, None
        elif nextch.isalpha() or nextch == '_':
            tok, value, prevch = read_identifier(nextch)
            yield tok, value
        # elif nextch == '"' or nextch == "'":
            # yield read_string_literal(nextch)
        else:
            if reachedEof(nextch):
                yield TOKEN_EOF, None
                finished = True
            else:
                print "Reached EOF: ", reachedEof(nextch)
                yield TOKEN_ERROR, "Invalid character: '%s'" % nextch


class Parser(object):
    """
    The grammar for the input file is:

    NonTerms ::= NonTerm NonTerm * ;
    NonTerms ::= NonTerm  ;

    NonTerm ::= NonTermName ? ( ":" NonTermType )  NonTermBody ;

    NonTermType ::= "(" IDENT ")" ;
    NonTermName ::= IDENT ;
    NonTermBody ::= "->" Production ( | Production ) *;
    NonTermBody ::= "{" ( "->" Production ) * "}" ;

    Production :: SymbolUsages ? ";" ? ProductionHandler ;
    ProductionHandler ::= BLOCK

    SymbolUsages ::= SymbolUsage SymbolUsages ;
    SymbolUsages ::= SymbolUsage ;

    SymbolUsage ::= Symbol
    SymbolUsage ::= Symbol ":" SymbolVar
    SymbolUsage ::= "?" Symbol ":" SymbolVar

    SymbolVar ::= IDENT
    Symbol ::= IDENT
    """
    def __init__(self, input):
        self.instream = input
        if type(input) is str:
            self.instream = StringIO.StringIO(input)

        # Create the "core" parser which will be used to parse other files
        self.tokenizer = tokenize(self.instream)
        self.peekedTokens = []

    def insertToken(self, ttype, tval=None):
        self.peekedTokens.insert(0, (ttype, tval))

    def peekToken(self, nth=0):
        while len(self.peekedTokens) <= nth:
            self.peekedTokens.append(self.tokenizer.next())
        return self.peekedTokens[nth][0]

    def advanceToken(self):
        self.peekToken()
        toktype, tokvalue = self.peekedTokens.pop(0)
        return tokvalue

    def expectAndAdvanceToken(self, token_type):
        pt = self.peekToken()
        if pt is None:
            raise Exception("Unexpected end of input")
        if pt != token_type:
            expected = token_labels[token_type]
            found = token_labels[pt]
            raise Exception("Expected token: %s, Found: %s" % (expected, found))
        return self.advanceToken()

    def hasToken(self):
        pt = self.peekToken()
        return pt not in (None, TOKEN_EOF)

    def parse(self):
        G = grammar.Grammar()
        self.getNonTerms(G)
        return G

    def getNonTerms(self, G):
        out = []
        nonterm = None
        while self.hasToken():
            if self.peekToken() == TOKEN_PIPE:
                # then insert a couple of tokens
                # to mimic A ->
                self.advanceToken()
                self.insertToken(TOKEN_ARROW)
                self.insertToken(TOKEN_IDENT, nonterm.name)
            nonterm = self.getNonTerm(G)
            out.append(nonterm)
        return out

    def getNonTerm(self, G):
        ntname = self.expectAndAdvanceToken(TOKEN_IDENT)
        nttype = self.getNonTermType()
        nonterm = G.addSymbol(ntname, nttype)

        # Get the productions
        if self.peekToken() == TOKEN_OBRACE:
            self.advanceToken(TOKEN_OBRACE)
            while self.peekToken() != TOKEN_CBRACE:
                production = self.getProduction(G, nonterm)
                nonterm.addProduction(production)
            self.expectAndAdvanceToken(TOKEN_CBRACE)
        elif self.peekToken() == TOKEN_ARROW:
            production = self.getProduction(G, nonterm, False)
            nonterm.addProduction(production)
        return nonterm

    def getNonTermType(self):
        if self.peekToken() != TOKEN_COLON:
            return None
        self.advanceToken()

        return self.expectAndAdvanceToken(TOKEN_IDENT)

    def getProduction(self, G, nonterm, insideBlock=True):
        self.expectAndAdvanceToken(TOKEN_ARROW)
        symbols = []
        symbolUsage = self.getSymbolUsage(G, insideBlock)
        handler = None
        while symbolUsage:
            symbols.append(symbolUsage)
            symbolUsage = self.getSymbolUsage(G, insideBlock)

        if self.peekToken() != TOKEN_IDENT or insideBlock:
            # next rule has started so push it back so the next prod can start
            if self.peekToken() == TOKEN_SEMICOLON:
                self.advanceToken()

            if self.peekToken() == TOKEN_BLOCK:
                handler = self.advanceToken()
        return grammar.Production(nonterm, symbols, handler)

    def getSymbolUsage(self, G, insideBlock=True):
        symbolName = None
        symbolVar = None
        isOptional = False
        if self.peekToken() == TOKEN_QMARK:
            isOptional = True
            self.advanceToken()

        if not isOptional and self.peekToken() != TOKEN_IDENT:
            return None

        if not insideBlock and self.peekToken(1) == TOKEN_ARROW:
            return None

        symbolName = self.expectAndAdvanceToken(TOKEN_IDENT)
        if self.peekToken() == TOKEN_COLON:
            self.advanceToken()
            symbolVar = self.expectAndAdvanceToken(TOKEN_IDENT)
        symbol = G.addSymbol(symbolName)
        return grammar.SymbolUsage(symbol, symbolVar, isOptional)


def tokenize_file(fname):
    for tok, value in tokenize(open(fname)):
        if value:
            print "Token: ", token_labels[tok], value
        else:
            print "Token: ", token_labels[tok]


def parse_file(filepath):
    return Parser(open(filepath).read()).parse()

# g = parse_file("./simple.pg") ; nts = list(g.nonTerminals()) ; g.predictAndFollowSets("S")
