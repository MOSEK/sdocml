import re

def counter(start):
    i = int(start)
    while True:
        yield i
        i += 1


condregex = re.compile('|'.join([r'\?(?P<isdef>[a-zA-Z0-9@:_\.\-\*]+)',
                                 r'(?P<not>!)',
                                 r'(?P<and>\+)',
                                 r'(?P<or>\|)',
                                 r'(?P<xor>/)',
                                 r'(?P<lpar>\()',
                                 r'(?P<rpar>\))',
                                 r'(?P<term>[a-zA-Z0-9@:_\.\-\*]+)',
                                 r'(?P<space>\s+)',
                                 r'(?P<error>.)']))
class CondError(Exception): pass


class Token:
    ISDEF,NOT,AND,OR,XOR,LPAR,RPAR,TERM = xrange(8)

    def __init__(self,o): 
        if   o.group('isdef'): t,d = self.ISDEF,o.group('isdef')
        elif o.group('not'):   t,d = self.NOT,o.group('not')
        elif o.group('and'):   t,d = self.AND,o.group('and')
        elif o.group('or'):    t,d = self.OR,o.group('or')
        elif o.group('xor'):   t,d = self.XOR,o.group('xor')
        elif o.group('lpar'):  t,d = self.LPAR,o.group('lpar')
        elif o.group('rpar'):  t,d = self.RPAR,o.group('rpar')
        elif o.group('term'):  t,d = self.TERM,o.group('term')
        else: assert 0

        self.type = t
        self.data = d
        self.pos  = o.start(0)
    def __repr__(self):
        return 'Token(%d:%s)' % (self.type,self.data)
    def __str__(self):
        return self.data

def tokenize(s):
    it = condregex.finditer(s)    
    while True:
        tok = it.next()
        if tok.group('error') is not None:
            raise CondError('Invalid condition syntax "%s" at %d' % (tok.group('error'),tok.pos))
        elif tok.group('space') is None:
            yield Token(tok)

def rev(l):
    r = [i for i in l ]
    r.reverse()
    return r

def eval(s,d):
    T = [ t for t in tokenize(s) ]
    T.reverse()

    def evalcond(skip): # eval a single condition expr
        #print "eval cond:",rev(T)
        t = T[-1]
        neg = False
        if t.type == t.NOT:
            T.pop()
            r = not evalcond(skip)
        elif t.type == t.TERM:
            if not d.has_key(t.data):
                raise CondError('Undefined conditional variable "%s"' % t.data)
            r = skip or d[t.data]
            T.pop()
        elif t.type == t.ISDEF:
            r = skip or d.has_key(t.data)
            T.pop()
        elif t.type == t.LPAR:
            r = evalsubcond(skip)
        else:
            raise CondError('Expected a logical term in position %d' % t.pos)

        return skip or r
    def evalsubcond(skip):
        #print "eval parexpr:",rev(T)
        t = T.pop()
        assert t.type == t.LPAR
        r = evallist(skip)
        t = T.pop()
        if t.type != t.RPAR:
            raise CondError('Expected a ")" in position %d' % t.pos)
        return r

    def evalandlist(skip):
        #print "eval andlist:",rev(T)
        r = True
        if T:
            t = T[-1]
            if t.type == t.AND:
                T.pop()
                r1 = evalcond(skip)
                r = evalandlist(skip or not r1) and r1
        return r

    def evalorlist(skip):
        #print "eval orlist:",rev(T)
        r = False
        if T:
            t = T[-1]
            if t.type == t.OR:
                T.pop()
                r1 = evalcond(skip or r)
                r = evalorlist(skip or r1) or r1
        return r
    
    def evalxorlist(skip,r0):
        #print "eval xorlist:",rev(T)
        r = False
        if T:
            t = T[-1]
            if t.type == t.XOR:
                T.pop()
                r1 = evalcond(skip)
                r2 = evalxorlist(skip or (r and r1), r or r1)
                r = (r1 and not r2) or (r2 and not r1)
        return r

    def evallist(skip):
        r0 = evalcond(skip)
        if not T: return r0
        t = T[-1]
        if   t.type == t.AND:
            r = evalandlist(skip or not r0) and r0
        elif t.type == t.OR:
            r = evalorlist(skip or r0) or r0
        elif t.type == t.XOR:
            r1 = evalxorlist(skip,r0)
            r = (r0 and not r1) or (r1 and not r0)
        elif t.type == t.RPAR:
            r = r0 
        else:
            raise CondError('Invalid condition syntax at %d' % t.pos)
        return r

    try:
        r = evallist(False)
        if T: raise CondError('Invalid condition syntax at %d' % T[-1].pos)
        return r
    except IndexError:
        raise
        raise CondError('Invalid condition syntax at %d' % len(s))


if __name__ == '__main__':
    d = { 'A' : True, 
          'B' : False, 
          'C' : True, 
          'D' : False,
          'T' : True,
          'F' : False } 

    ok = True
    for c,res in [ 
        ('T + T',True),
        ('T + F',False),
        ('F + T',False),
        ('F + F',False),
        ('(T + T)',True),
        
        ('F | F',False),
        ('T | F',True),
        ('F | T',True),
        ('T | T',True),
        ('(F | F)',False),
        
        ('F / F / F',False),
        ('T / F / F',True),
        ('F / T / F',True),
        ('F / F / T',True),
        ('T / F / T',False),
        ('F / T / T',False),

        ('T',True),
        ('(T)',True),
        ('F',False),
        ('(F)',False),

        ('(A | B | C)',None),
        ('A | B | C',None),
        ('(A/B)',None),
        ('A/B',None),
        ('A/B/C',None),
        ('B/D/A',None),
        ('A+B',None),
        ('A|B',None),
        ('A|B|(A+B+C)|D',None),
        ('?X+X',None),
        ]:
        r = eval(c,d)
        if res is not None:
            if res is not r:
                ok = False

        print '\t%s -> %s%s' % (c,r,'' if res is None else ' (expected %s)' % res)
    print "Failed!!" if not ok else "Succeeded."

