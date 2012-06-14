import re,os.path

T_TEXT = 0
T_EXPR = 1
T_VAL  = 2
T_IDEN = 3
T_NUM  = 4
T_STR  = 5
exprre = re.compile('|'.join([r'\s*(?P<par>[()])',
                              r'\s*(?P<id>[a-zA-Z_][a-zA-Z0-9@_:.#]*)',
                              r'\s*"(?P<dqstr>[^"]*)"',
                              r"\s*'(?P<sqstr>[^']*)'",
                              r'\s*(?P<num>[0-9]+)',
                              ]))
class TemplateError(Exception):
    pass

def parsepar(text,pos):
    stack = [[]]
    
    if text[pos] == '(':
        pos += 1

    while True:
        o = exprre.match(text,pos)
        if o is not None:
            if   o.group('par') == '(':
                pos = o.end(0)
                t = []
                stack[-1].append((T_EXPR,t))
                stack.append(t)
            elif o.group('par') == ')':
                if len(stack) == 1:
                    break
                else:
                    pos = o.end(0)
                    stack.pop()
            elif o.group('id'):
                pos = o.end(0)
                stack[-1].append((T_IDEN,o.group('id')))
            elif o.group('dqstr') is not None:
                pos = o.end(0)
                stack[-1].append((T_STR,o.group('dqstr')))
            elif o.group('sqstr') is not None:
                pos = o.end(0)
                stack[-1].append((T_STR,o.group('sqstr')))
            elif o.group('num'):
                pos = o.end(0)
                stack[-1].append((T_NUM,int(o.group('num'))))
            else:
                print o.group(0)
                assert 0
        else:
            errend = text.find('\n',pos)
            if errend < 0: errend = len(text)
            errstart = max(0,text.rfind('\n',0,pos))
            print text[errstart:errend]            
            print ' '*(pos-errstart)+'^'
            assert 0
    o = exprre.match(text,pos)
    if o.group('par') == ')':
        return o.end(0),stack[0]
    else:
        assert 0

def mkparser(text):
    pos = 0

    while pos < len(text):
        p = text.find('$',pos)
        if p < 0 or p == len(text)-1:
            yield T_TEXT, text[pos:]
            break
        elif text[p+1] == '{':
            p2 = text.find('}',p)
            if p > pos:
                yield T_TEXT, text[pos:p]
            yield T_VAL, text[p+2:p2]
            pos = p2+1
        elif text[p+1] == '(':
            if p > pos:
                yield T_TEXT, text[pos:p]

            pos, expr = parsepar(text,p+1)
            yield T_EXPR,expr
        elif text[p+1] == '$':
            yield T_TEXT, text[pos:p+1]
            pos = p+2
        else:
            yield T_TEXT, text[pos:p]
            pos = p+1

numargs = { 'has' : 1,
            'not' : 1,
            'or'  : -1,
            'and' : -1,
            'lookup' : 1,
            'resource' : 1,
            'if'  : 3}

def evalfunc(expr,d,ev):
    oprt = expr[0]
    if oprt[0] == T_IDEN and oprt[1] in numargs:
        opr = oprt[1]
        if opr == 'has':
            k = evalexpr(expr[1],d,ev)
            assert isinstance(k,str)
            return d.has_key(k)
        elif opr == 'not':
            return not evalexpr(expr[1],d,ev)
        elif opr == 'and':
            return all([ evalexpr(i,d,ev) for i in expr[1:] ])
        elif opr == 'or':
            return not all( [ not evalexpr(i,d,ev) for i in expr[1:] ])
        elif opr == 'if':
            assert len(expr) == 4
            cond = evalexpr(expr[1],d,ev)
            if cond: 
                return evalexpr(expr[2],d,ev)
            else:
                return evalexpr(expr[3],d,ev)
        elif opr == 'lookup':
            k = evalexpr(expr[1],d,ev)
            assert isinstance(k,str)
            return d[k]
        elif opr == 'resource':
            return ev['resource'](evalexpr(expr[1],d,ev))
        else:
            assert 0
    else:
        print "unknown function: %s" % str(oprt[1])
        assert 0    
    
builtin_idents = { 'true' : True, 'false' : False }
def evalexpr(expr,d,ev):
    tt,tv = expr
    if   tt is T_EXPR:
        return evalfunc(tv,d,ev)
    elif tt is T_IDEN:
        return builtin_idents[tv]
    elif tt is T_STR:
        return tv
    elif tt is T_NUM:
        return tv
    else:
        assert 0

ST_TOP  = 0
ST_IF   = 1
ST_ELSE = 2

class Template:
    def __init__(self,filename=None,text=None):
        self.__filename = filename
        self.__base = os.path.dirname(filename)
        self.__text = text or open(filename,'rb').read()
        self.__tmpl = [ i for i in mkparser(self.__text) ]

    def base(self):
        return self.__base

    def expand(self,d,ev):
        cond_stack = [ (True,ST_TOP) ]
        it = iter(self.__tmpl)
        res = []
        
        try:
            while True:
                tt,tv = it.next()
                if   tt is T_TEXT:
                    if cond_stack[-1][0]:
                        res.append(tv)
                elif tt is T_VAL:
                    if cond_stack[-1][0]:
                        val = d[tv]
                        if isinstance(val,str):
                            res.append(val)
                        else:
                            res.extend(val)
                elif tt is T_EXPR:                
                    oprtt,opr = tv[0]
                    if oprtt is T_IDEN:
                        if opr == 'if' and len(tv) == 2:
                            if cond_stack[-1][0]:                    
                                ee = evalexpr(tv[1],d,ev)
                                cond_stack.append((isinstance(ee,bool) and ee,ST_IF))
                            else:
                                cond_stack.append((False,ST_IF))
                        elif opr == 'else':
                            assert len(tv) == 1 and cond_stack[-1][1] is ST_IF
                            top = cond_stack.pop()
                            cond_stack.append((cond_stack[-1][0] and not top[0],ST_ELSE))
                        elif opr == 'endif':
                            assert len(tv) == 1 and cond_stack[-1][1] in [ST_IF,ST_ELSE]
                            cond_stack.pop()
                        else:
                            r = evalfunc(tv,d,ev)
                            if isinstance(r,str):
                                res.append(r)
                            else:
                                try:
                                    res.extend(r)
                                except:
                                    print "Did not evaluate to a string: ", ev
                                    print "\tresult =",type(r),r
                                    assert 0
                    else:
                        print tv
                        assert 0
                else:
                    assert 0
        except StopIteration:
            pass

        return res

