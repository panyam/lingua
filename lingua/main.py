
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


class Tokenizer(object):
    def __init__(self, input):
        self.instream = input
        if type(input) is str:
            self.instream = StringIO.StringIO(input)

        # Create the "core" parser which will be used to parse other files
        self.prevch = None
        self.line = 0
        self.column = 0
        self.finished = False

    def reachedEof(self, ch):
        return ch == '' or ch is None

    def nextChar(self):
        if self.prevch:
            nextch = self.prevch
            self.prevch = None
        else:
            nextch = self.instream.read(1)
            if nextch in "\n\r":
                self.line += 1
                self.column = 0
        return nextch

    def nextToken(self):
        """
        Scans a elk grammar like grammar file.
        """
        if self.finished:
            return TOKEN_EOF, None

        # skip spaces
        nextch = self.nextChar()
        while nextch.isspace():
            nextch = self.nextChar()

        if nextch == '(':
            return TOKEN_OPAREN, None
        elif nextch == ')':
            return TOKEN_CPAREN, None
        elif nextch == ':':
            return TOKEN_COLON, None
        elif nextch == ';':
            return TOKEN_SEMICOLON, None
        elif nextch == '{':
            nextch = self.nextChar()
            if nextch == '%':
                return self.read_block()
            else:
                self.prevch = nextch
                return TOKEN_OBRACE, None
        elif nextch == '}':
            return TOKEN_CBRACE, None
        elif nextch == '|':
            return TOKEN_PIPE, None
        elif nextch == '?':
            return TOKEN_QMARK, None
        elif nextch == '-':
            nextch = self.nextChar()
            if nextch != '>':
                return TOKEN_ERROR, "Expected '>', Found: '%s'" % nextch
            else:
                return TOKEN_ARROW, None
        elif nextch.isalpha() or nextch.isdigit() or nextch == '_':
            tok, value, self.prevch = self.read_identifier(nextch)
            return tok, value
        # elif nextch == '"' or nextch == "'":
            # return read_string_literal(nextch)
        else:
            if self.reachedEof(nextch):
                return TOKEN_EOF, None
                self.finished = True
            else:
                print "Reached EOF: ", self.reachedEof(nextch)
                return TOKEN_ERROR, "Invalid character: '%s'" % nextch

    def read_identifier(self, strsofar=''):
        self.prevch = None
        nextch = self.nextChar()
        while nextch.isalnum() or nextch.isdigit() or nextch == '_':
            strsofar += nextch
            nextch = self.nextChar()

        if not self.reachedEof(nextch):
            self.prevch = nextch
        return TOKEN_IDENT, strsofar, self.prevch

    def read_block(self):
        out = ''
        nextch = self.nextChar()
        while not self.reachedEof(nextch):
            if nextch == '%':
                nextch = self.nextChar()
                if nextch != '}':
                    out += '%'
                    out += nextch
                else:
                    return TOKEN_BLOCK, out
            else:
                out += nextch
            nextch = self.nextChar()
        return TOKEN_ERROR, "Unexpected end of file in block"


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
        self.tokenizer = Tokenizer(self.instream)
        self.peekedTokens = []

    def insertToken(self, ttype, tval=None):
        self.peekedTokens.insert(0, (ttype, tval))

    def peekToken(self, nth=0):
        while len(self.peekedTokens) <= nth:
            self.peekedTokens.append(self.tokenizer.nextToken())
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
        nonterm = G.addNonTerminal(ntname, nttype)

        # Get the productions
        if self.peekToken() == TOKEN_OBRACE:
            self.advanceToken()
            while self.peekToken() != TOKEN_CBRACE:
                self.getProduction(G, nonterm)
            self.expectAndAdvanceToken(TOKEN_CBRACE)
        elif self.peekToken() == TOKEN_ARROW:
            self.getProduction(G, nonterm, False)
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
        production = grammar.Production(nonterm, grammar.SymbolString(symbols), handler)
        G.addProduction(nonterm, production)

    def getSymbolUsage(self, G, insideBlock=True):
        symbolName = None
        symbolVar = None
        isOptional = False
        if self.peekToken() == TOKEN_QMARK:
            isOptional = True
            self.advanceToken()

        if not isOptional and self.peekToken() != TOKEN_IDENT:
            return None

        if not insideBlock:
            if self.peekToken(1) in (TOKEN_ARROW, TOKEN_OBRACE):
                return None

        symbolName = self.expectAndAdvanceToken(TOKEN_IDENT)
        if self.peekToken() == TOKEN_COLON:
            self.advanceToken()
            symbolVar = self.expectAndAdvanceToken(TOKEN_IDENT)
        if G.isNonTerminal(symbolName):
            symbol = G.addNonTerminal(symbolName)
        else:
            symbol = G.addTerminal(symbolName)
        return grammar.SymbolUsage(symbol, symbolVar, isOptional)


def tokenize_file(fname):
    for tok, value in Tokenizer(open(fname)).tokenize():
        if value:
            print "Token: ", token_labels[tok], value
        else:
            print "Token: ", token_labels[tok]


def parse_file(filepath):
    return Parser(open(filepath).read()).parse()

# g = parse_file("./simple.pg") ; nts = list(g.nonTerminals()) ; g.predictAndFollowSets("S")
