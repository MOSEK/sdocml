# Parse the table format
#
# The table format expression is:
#  
#  Expr -> Es
#  Es   -> E1 Es
#  E1   -> E0 "*"
#       |  E0 "+"
#       |  E0 "{" Num "}"
#       |  E0
#  E0   -> "(" Es ")"
#       | "." | "|" | "l" | "r" | "c"
#  Num  -> [ 0-9 ]+






import re

def print_ret(f):
    def _(*args,**kwds):
        r = f(*args,**kwds)
        print '-- r =',r
        return r
    return _


class InvalidFormat(Exception): pass
class Lexer:
    EOF = 'EOF'
    NUM = 'NUM'
    SFX = 'SFX'
    GST = '(  '
    GND = '  )'
    TOK = 'TOK'
    
    tokenize_re = re.compile(r'[{](?P<num>[0-9]+)[}]|(?P<sfx>[*+])|(?P<grp>[()])|(?P<tok>[.lrc|])')
    def __init__(self,s):
        self._p   = 0
        self.data = s
    def next(self):
        if self._p == len(self.data):
            return self.EOF,None
        o = self.tokenize_re.match(self.data, self._p)
        if o is None:
            raise InvalidFormat("Unexpected char")
        else:
            self._p = o.end(0)

            if   o.group('num'): return self.NUM,int(o.group('num'))
            elif o.group('sfx'): return self.SFX,o.group('sfx')
            elif o.group('grp'): 
                if o.group('grp') == '(':
                    return self.GST,o.group('grp')
                else:
                    return self.GND,o.group('grp')
            elif o.group('tok'): return self.TOK,o.group('tok')
            
            
    def pos(self,p = None):
        if p is not None:        
            self._p = p
        return self._p
    def __str__(self):
        return "%s\n%*s" % (self.data,self._p+1,'^')
            
    def peek(self):
        p = self._p
        r = self.next()
        self._p = p
        return r


class E1:
    def __init__(self,l):
        if isinstance(l,tuple):
            self.expr,self.suffix = l
        else:            
            tt,tv = l.peek()
            #print 'token = ',tt,tv
            if tt is Lexer.TOK:
                l.next()
                z = tv
            elif tt is Lexer.GST:
                l.next()
                z = Es(l)
                tt,tv = l.next()
                if tt is not Lexer.GND:
                    raise InvalidFormat("Expected a ')'")                
            else:
                raise InvalidFormat('Unexpected token "%s"' % tv)

            tt,tv = l.peek()
            if z in ['.','l','r','c'] or isinstance(z,Es):
                if tt in [ Lexer.SFX, Lexer.NUM ]:
                    l.next()
                    r = z,tv
                else:
                    r = z,None
            else:
                r = z,None

            self.expr, self.suffix = r

            if (isinstance(self.expr, Es)) and not self.expr.const and (self.suffix in ['*','+']):
                raise InvalidFormat("Multipliers may only be used on fixed-length expressions")
                
        self.const = self.suffix not in ['*','+']

    def __repr__(self):
        if   self.suffix in ['*','+']: 
            sfx = self.suffix
        elif self.suffix:
            sfx = '{%d}' % self.suffix
        else:
            sfx = ''
                
        if isinstance(self.expr,Es):
            return '(%s)%s' % (repr(self.expr),sfx)
        else:
            return '%s%s' % (self.expr,sfx)        

    def __str__(self):
        sfx = ''
        if   self.suffix in ['*','+']: 
            sfx = self.suffix
        elif self.suffix:
            sfx = '{%d}' % self.suffix
        else:
            pass
                
        if isinstance(self.expr,Es):
            return '(%s)%s' % (str(self.expr),sfx)
        else:
            return '%s%s' % (self.expr,sfx)
    def __len__(self):
        if   self.suffix == '*':
            assert 0
        else:
            if self.expr == '|': 
                r = 0
            elif self.suffix:
                if isinstance(self.expr,Es):
                    r = len(self.expr) * self.suffix
                else:
                    r = self.suffix
            else:
                r = 1
        return r
    def gen(self,n=None):
        b = ''
        bl = len(self.expr)
        if isinstance(self.expr,Es):
            b = self.expr.gen()
        else:
            b = self.expr

        if   self.suffix == '*':
            assert n is not None
            assert n % bl == 0
            r = b * (n/bl)
        elif self.suffix:
            r = b * self.suffix
        else:
            r = b

        return r
        
        

        
class Es:
    def __init__(self,l):
        if isinstance(l,list):
            self.data = l
        else:
            r = []

            # parse first part
            while True:
                tt,tv = l.peek()
                if tt in [ Lexer.GST, Lexer.TOK ]:
                    e = E1(l)
                    if e.suffix == '+':
                        r.append(E1((e.expr,None)))
                        r.append(E1((e.expr,'+')))
                    else:
                        r.append(e)
                else:
                    break
            self.data = r
        self.const = any([ i.const for i in self.data ])

    def gen(self):
        return ''.join([ i.gen() for i in self ])
        
    def __repr__(self):
        return ''.join([ repr(i) for i in self ])
    def __str__(self):
        return '[%s]' % ' '.join([str(i) for i in self])
    def __iter__(self):
        return iter(self.data)
    def __len__(self):        
        return sum([ len(i) for i in self ])


class Et:
    def __init__(self,l):
        l1 = []
        i2 = None
        l3 = []

        it = iter(l)
        try: 
            while True:
                e = it.next()
                if e.const: l1.append(e)
                else:  
                    i2 = e
                    break
        except StopIteration:
            pass
                    
        try: 
            while True:
                e = it.next()
                if e.const:
                    l3.append(e)
                else:  
                    raise InvalidFormat('Top level expression may contain at most one variable-length expression')
        except StopIteration:
            pass

        self.l1 = Es(l1) if l1 else None
        self.i2 = i2
        self.l3 = Es(l3) if l3 else None

        #print '--- l1 = ',repr(self.l1)
        #print '--- i2 = ',repr(self.i2)
        #print '--- l3 = ',repr(self.l3)

    def __repr__(self):
        r1 = '' if self.l1 is None else repr(self.l1)
        r2 = '' if self.i2 is None else repr(self.i2)
        r3 = '' if self.l3 is None else repr(self.l3)
        
        return ''.join([ r1, r2, r3 ])

    def mkfmt(self,size):
        """
        Generate a fixed format string for a list of the given size.
        """
        sz1 = len(self.l1) if self.l1 is not None else 0
        sz3 = len(self.l3) if self.l3 is not None else 0


        if sz1 + sz3 > size:
            print repr(self.l1),sz1
            print repr(self.l3),sz3
            raise InvalidFormat("The the table is too small to accomodate the specified format")
        
        s1 = self.l1.gen() if self.l1 is not None else ''
        s2 = self.i2.gen(size - (sz1 + sz3)) if self.i2 is not None else ''
        s3 = self.l3.gen() if self.l3 is not None else ''
        
        return ''.join([s1, s2, s3])

            
def parse(s):
    try:
        lex = Lexer(s)
        
        exp = Et(Es(lex))
        
        tt,tv = lex.peek()
        if tt is not Lexer.EOF:
            raise InvalidFormat('Expected EOF')
    
        return exp
    except InvalidFormat,msg:
        print "%s\n\t%s\n\t%*s" % (msg,s,lex.pos()+1,'^')
    except InvalidFormat:
        print "Exception at\n\t%s\n\t%*s" % (s,lex.pos()+1,'^')    

if __name__ == '__main__':
    import sys

    s = sys.argv[1]
    r = parse(sys.argv[1])
    if r is not None:
        print repr(r)
        print r.mkfmt(int(sys.argv[2]))

    
