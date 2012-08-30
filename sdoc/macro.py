"""
This module defines functionality used for representing macros and
environments.
"""

from util import *
import logging
import re
from EvHandler import Pos

log = logging.getLogger("SDocML Macro")
log.setLevel(logging.ERROR)


class SAXEvent:
    def __init__(self,pos):
        self.trace = [ pos ]
        self.pos = pos
    def tr(self,pos):
        self.trace.append(pos)
        return self

class SAXEvTableItemStart(SAXEvent):
    name = '*table-item*'
    def __repr__(self):
        return '<%s>' % self.name
class SAXEvTableItemEnd(SAXEvent):
    name = '*table-item*'
    def __repr__(self):
        return '</%s>' % self.name

class SAXEvTableRowStart(SAXEvTableItemStart):
    name = '*table-row*'
class SAXEvTableRowEnd(SAXEvTableItemEnd): 
    name = '*table-row*'
class SAXEvTableCellStart(SAXEvTableItemStart):
    name = '*table-cell*'
class SAXEvTableCellEnd(SAXEvTableItemEnd): 
    name = '*table-cell*'

class SAXEvStartTag(SAXEvent):
    def __init__(self,name,attrs,pos):
        SAXEvent.__init__(self,pos)
        self.name = name
        self.attrs = attrs
    def __repr__(self):
        return '<%s>' % self.name
class SAXEvEndTag(SAXEvent):
    def __init__(self,name,pos):
        SAXEvent.__init__(self,pos)
        self.name = name
    def __repr__(self):
        return '</%s>' % self.name
class SAXEvText(SAXEvent):
    """
    Represents a piece of pure text that has either already been parsed or
    should not be parsed at all.

    This should be handed to the Node using handleRawText().
    """
    def __init__(self,data,pos):
        SAXEvent.__init__(self,pos)
        #assert data # No: some operations may evaluate to empty string (e.g. dict lookup)
        assert isinstance(data,basestring)
        self.data = data
    def __repr__(self):
        return 'TEXT{%s}' % repr(self.data)
class SAXEvUnexpandedText(SAXEvent):
    """
    Represents a piece of text that has not been parsed yet.

    This should be handed to a node using handleText().
    """
    def __init__(self,data,pos):
        SAXEvent.__init__(self,pos)
        assert data
        assert isinstance(data,basestring)
        self.data = data
    def __repr__(self):
        return 'TEXT{%s}' % repr(self.data)

class _DelayedItem:
    autoClose = False
    def __init__(self,pos):
        self.pos = pos
        assert isinstance(pos,Position)
    def __repr__(self):
        return self.__class__.__name__

class DelayedMacro(_DelayedItem):
    def __init__ (self, name, pos, args=None, subscr=None, superscr=None):
        _DelayedItem.__init__(self,pos)
        self.name = name        
        self.args = args
        self.subscr = None
        self.superscr = None
    def asDoc(self,r):
        r.append('\\%s' % self.name)
        for a in self.args:
            r.append('{')
            a.asDoc(r)
            r.append('}')
        if subscr is not None:
            r.append('_{')
            subscr.asDoc(r)
            r.append('}')
        if superscr is not None:
            r.append('_{')
            superscr.asDoc(r)
            r.append('}')
        return r
    def __repr__(self):
        return 'DelayedMacro(%s)' % self.name

class DelayedArgRef(_DelayedItem):
    def __init__(self,key,pos):
        _DelayedItem.__init__(self,pos)
        self.key = key
    def asDoc(self,r):
        r.append('{{%s}}' % self.key)
        return r
    def __repr__(self):
        return 'DelayedArgRef(%s)' % self.key

class DelayedLookup(_DelayedItem):
    def __init__(self,pos,content):
        _DelayedItem.__init__(self,pos)
        self.content = content
        #log.debug('DelayedLookup content = %s' % content)
    def asDoc(self,r):
        r.append('<lookup>')
        for item in self.content:
            item.asDoc(r)
        r.append('</lookup>')
        return r
    def append(self,item):
        self.content.append(item)

class DelayedText(_DelayedItem):
    def __init__(self,data,pos):
        _DelayedItem.__init__(self,pos)
        self.data = data
    def asDoc(self,r):
        r.append(self.data)
    def __repr__(self):
        return 'DelayedText{%s}' % repr(self.data)
class DelayedUnexpandedText(_DelayedItem):
    def __init__(self,data,pos):
        _DelayedItem.__init__(self,pos)
        self.data = data
    def asDoc(self,r):
        assert 0
    def __repr__(self):
        return 'DelayedUnexpandedText{%s}' % repr(self.data)

class DelayedEnvironment(_DelayedItem):
    def __init__(self,name,pos):
        _DelayedItem.__init__(self,pos)
        self.endpos = None
        self.name = name
        self.content = []
    def asDoc(self,r):
        r.append('\\begin{%s}' % self.name)
        for a in self.args:
            a.asDoc(r)
        r.append('\\end{%s}' % self.name)
    def append(self,item):
        self.content.append(item)
    def end(self,name,pos):
        if name != self.name:
            raise MacroError('%s: Environment "%s" at %s ended by "%s"' % (pos,self.name,self.pos,name))
        self.endpos = pos
        #print "DelayedEnvironment(%s). Content: %s" % (self.name,len(self.content))
    def __repr__(self):
        return 'DelayedEnvironment(%s){%s}' % (self.name, ','.join([ repr(i) for i in self.content ]))
    def __iter__(self):
        return iter(self.content)

class DelayedGroup(_DelayedItem):
    def __init__(self,pos,args=None):
        """
        A not-yet-expanded group.

        The group can be instantiated with arguments (args, subscr, superscr
        and body), in which case these define the relevant substitutions inside
        the group. Otherwise the substitutions from the context of the group
        apply. 

        (args) Either None, meaning that the default context should be used,
            otherwise a tuple (args,subscr,superscr,body)
        """
        _DelayedItem.__init__(self,pos)
        self.endpos = None
        self.content = []
        self.args = args
    def asDoc(self,r):
        for i in self.content:
            i.asDoc(r)
        return r

    def append(self,item):
        if isinstance(item,DelayedElement) and item._mark:
            assert 0
        item._mark = True

        self.content.append(item)
    def extend(self,items):
        self.content.extend(items)

    def __iter__(self): return iter(self.content)
    def __len__(self): return len(self.content)
    def end(self,pos,tok):
        if tok != '}':
            raise MacroError('%s: Group at %s ended by "%s"' % (pos,self.pos,tok))
        self.endpos = endpos
    def __repr__(self):
        return 'DelayedGroup@[%s]{%s}' % (self.pos,','.join([ repr(i) for i in self.content ]))

class DelayedSubScript(_DelayedItem): pass
class DelayedSuperScript(_DelayedItem): pass

class DelayedTableContent(_DelayedItem):
    autoClose = True
    def __init__(self,pos):
        _DelayedItem.__init__(self,pos)
        self.__data = [ [ [] ] ]
        self.__cstack = [ self.__data, self.__data[0], self.__data[0][0] ]
    def row(self,pos):
        assert len(self.__cstack) == 3
        self.__cstack.pop()
        self.__cstack.pop()
        r = []
        self.__cstack[-1].append(r)
        self.__cstack.append(r)
        c = []
        self.__cstack[-1].append(c)
        self.__cstack.append(c)

    def cell(self,pos):
        if len(self.__cstack) != 3:
            print "CSTACK:"
            for i in self.__cstack:
                print "\t%s" % i
        assert len(self.__cstack) == 3
        self.__cstack.pop()
        c = []
        self.__cstack[-1].append(c)
        self.__cstack.append(c)
       
    def append(self,item):
        assert len(self.__cstack) > 1
        self.__cstack[-1].append(item)
    def get(self):
        return self.__data

class DelayedElement(_DelayedItem):
    """
    An element encountered originating either inside a group or an environment, or from a macro or environment definition.
    """
    def __init__(self,name,attrs,pos):
        _DelayedItem.__init__(self,pos)
        if name in [ 'dictentry', 'def','defenv', 'section' ]:
            raise Exception("ABBASDFAB")
        self.name = name
        self._mark = False
        self.nodeName = name
        self.attrs = attrs

        for v in attrs.values():
            assert isinstance(v,list)
            for i in v:
                assert isinstance(i,_DelayedItem)
        self.pos = pos
        self.endpos = None
        self.body = []
    def asDoc(self,r):
        attrs = []
        for k,v in self.attrs.items():
            l = []
            for i in v: i.asDoc(l)
            attrs.append((k,''.join(l)))
        r.append('<%s%s>' % (self.name, u''.join([ u' %s="%s"' % attr for attr in attrs ])))
        for i in self.body:
            i.asDoc(r)
        r.append('</%s>' % self.name)
    def startChildElement(self,name,attrs,pos):
        attrd = {}
        for k,v in attrs.items():
            attrd[k] = [ DelayedText(v,pos) ]
        node = DelayedElement(name,attrd,pos)
        self.body.append(node)
        node._mark = False
        return node
    def endChildElement(self,name,pos):
        pass
    def endThisElement(self,name,pos):
        pass
    def __iter__(self):
        return iter(self.body)
    def extend(self,items):
        for i in items:
            #log.debug('Append to <%s> : %s' % (self.name,i))
            assert isinstance(i,_DelayedItem)
            if isinstance(i,DelayedElement) and i._mark:
                assert 0
            self.body.append(i)
        
    def end(self,pos):
        #if name != self.name:
        #    raise MacroError('%s: Element "%s" at %s ended by "%s"' % (pos,self.name,self.pos,name))
        self.endpos = pos
    def __repr__(self):
        return 'DelayedElement@[%s](%s){%s}' % (self.pos,self.name,','.join([ repr(i) for i in self.body ]))


class Element:
    def __init__(self,name,attrs,content):
        self.name = name
        self.attrs = attrs
        self.content = content
    def __iter__(self):
        return iter(content)

class Placeholder:
    def __init__(self,arg):
        self.arg = arg
    def __repr__(self):
        return "Placeholder for :"+self.arg

class MacroRef:
    def __init__(self,ref,sub,sup):
        self.ref = ref
        self.sub = sub
        self.sup = sup

class Group:
    def __init__(self,p):
        self.end = False
        self.start = p
        self.content = ''
        self.sub= True
        self.sup = True
        self.nArgs = 0
    def __repr__(self):
        return "{"+self.content+"}"

class SubSup:
    def __init__(self,sub,sup):
        self.sup = sup
        self.sub = sub
    def __repr__(self):
        return '_'+self.sub+'^'+self.sup


class Sup:
    def __init__(self):
        self.sup = None

    def sub(self,sub=None):
        return SubSup(self.base,sub=sub,sup=self.sup)
        
        
class Sub:
    def __init__(self):
        self.sub = None

    def sup(self):
        return SubSup(self.base,sub=self.sub,sup=none)

class Macro:
    def __init__(self,name,desc,nargs,body,tree,sub=True,sup=True,pos=0):
        self.name = name
        self.desc  = desc # text
        self.nargs = nargs # int        
        self.body  = body
        self.args = {}
        self.sub = sub
        self.sup = sup
        self.pos = pos
        self.recv = 0
        self.start = []
        self.end = []
        self.tree = []
        self.tree.extend(tree)
        for i in xrange(len(self.tree)):
            node = self.tree[i]
            if isinstance(node,Placeholder):
                if node.arg in self.args:
                    self.args[node.arg].append(i)
                else:
                    self.args[node.arg] = [i]
    def copy(self,pos):
        return Macro(self.name,self.desc,self.nargs,self.body,self.tree,pos=pos)
    def asDoc(self, r):
        for i in self.body:
            i.asDoc(r)
        return r
    def handleSubp(char):
        if char == '_':
            key = 'SUBSCRIPT'
        else:
            key = 'SUPERSCRIPT'
        returnee = None
        if(self.sub):
            if(self.args.has_key(key)):
                self.nargs += 1
                self.args[self.nargs] = self.args[key]
                del self.args[key]
            else:
                raise MacroError(('<%s>: %s recived a %s but has no %s'+
                'argument')%(self.pos,self.name,char,key))
        else:
            if(self.nargs ==0):
                returnee = ''.join(self.content)
            else:
                raise MacroError('<%s>: %s does not accept %s' %
                (self.pos,self.name,key.lower()))
    def addArgument(self,group,pos):
        try:
            argument = str(group)[1:-1]
            for n in self.args[str(self.recv)]:
                self.tree[n] = argument
            self.nargs = self.nargs -1
            self.recv +=1
        except IndexError:
            raise MacroError(('%s: Macro %s needs no more '+
                'arguments')%(self.pos,self.name))
    def end(self):
        if not self.nargs == 0:
            raise MacroError('%s: %s missing arguments'%(self.pos,self.name))
        return self.body
    def __repr__(self):
        return self.name
    def nArgs(self):
        return self.nargs

class Environment:
    def __init__(self,name,desc,localcmds,nargs,defines,body,tree,sub=None,sup=None,pos='0'):
        self.desc    = desc
        self.defines = defines
        self.nargs   = nargs
        self.body    = body
        self.localcmds = localcmds
        self.recv = 0
        self.name = name
        self.sub = sub
        self.sup = sup
        self.pos = pos
        self.args = {}
        self.tree = tree
        self.printed = False
        for i in xrange(len(self.tree)):
            node = self.tree[i]
            if isinstance(node,Placeholder):
                if self.args.has_key(node.arg):
                    self.args[node.arg].append(i)
                else:
                    self.args[node.arg] = [i]
    def nArgs(self):
        return self.nargs
    def printable(self):
        if not self.printed:
            try:
                returnee = ''.join([self.tree[x] for x in (range(self.args['BODY'][0]))])
                self.printed = True
                return returnee
            except IndexError:
                raise MacroError(('<%s>:Environment %s does not have a {{BODY}}')
                %(self.pos,self.name))
        else:
            return ''
    def printend(self):
        r = range(self.args['BODY'][0]+1,len(self.tree))
        try:
            return ''.join([self.tree[x] for x in r])
        except IndexError:
            #This cant happen
            raise MacroError(('<%s>:Environment %s does not have a {{BODY}}')
            %(self.pos,self.name))

    def __repr__(self):
        return self.name

    def asDoc(self, r):
        for i in self.body:
            i.asDoc(r)
        return r
    def copy(self):
        return Environment(self.name,self.desc,self.localcmds,self.nargs,self.defines,self.body,self.tree)

    def addArgument(self,group,pos):
        if self.nArgs()!=0:
            try:
                for place in self.args[self.recv]:
                    self.tree[place] = group
                self.recv +=1
                self.args -=1
            except: 
                #print group
                raise MacroError(('%s: <%s> to many arguments '+
                'recieved')%(pos,self.name))
        #We are adding to the body
        else:
            if len(self.tree) >2:
                start = ''.join(self.tree[:-1])+group
                self.tree = [start,self.tree[-1]]
            else:
                self.tree[0] +=group
    def end(self):
        returnee = ''
        try:
            returnee.join([self.tree[x] for x in
            range(self.args['BODY'][0],len(self.args))])
        except IndexError:
            raise MacroError('<%s>: Enviroment %s failed'%
            (self.pos,self.name))
        return returnee
        
class EnvDict:
    def __init__(self,parent,d):
        self.__parent = parent
        self.__d = d
    def __getitem__(self,key):
        try:
            return self.__d[key]
        except KeyError:
            return self.__parent[key]
    def has_key(self,key):
        return self.__d.has_key(key) or self.__parent.has_key(key)
    
    # NOTE: This is read-only, so no need to implement all the set functions
    def dictLookup(self,key):
        try:
            return self.__d.dictLookup(key)
        except KeyError:
            return self.__parent.dictLookup(key)

class ResolvedSubSuperScript:
    def __init__(self,pos,base,subscr=None,superscr=None):
        self.pos      = pos
        self.base     = base
        self.subscr   = subscr
        self.superscr = superscr

class ResolvedMacro:
    def __init__(self,macro,pos):
        self.pos      = pos
        self.macro    = macro
        self.args     = []
        self.subscr   = None
        self.superscr = None
    def requireArgs(self):
        return self.macro.nArgs() - len(self.args)
    def append(self,arg):
        "Append argument"
        self.args.append(arg)

    def requireMoreArgs(self):
        return len(self.args) < self.macro.nArgs()

    def end(self):
        if self.macro.nArgs() < len(self.args):
            raise MacroError('%s: Missing macro argument for \\%s' % (self.pos,self.name))


def eval(lst,cmddict,args=None,subscr=None,superscr=None,body=None,keymode=False,fixpos=None):
    """
    Given a list consisting of unresolved items (DelayedText, DelayedMacro,
    DelayedEnvironment, DelayedGroup, etc), perform recursive evaluation. 

    The function evaluates to an iterator returning a list of SAXEvents.

    (lst)       List of delayed items.
    (cmddict)   Current macro dictionary
    (args)      List of macro arguments or None of none is available.
    (subscr)    Subscript group or None, if not defined.
    (superscr)  Superscript group or None, if not defined.
    (body)      List of delayed items defining the body of an environment, or None if unedfined.
    (keymode)   (True|False) True means that we try to evaluate to a string, so '_' and '^' are ignored except when they are arguments for a macro.
    """
    
    pit = PushIterator(lst)
    #log.debug('----i------- BEG iter(%s)\n\t%s' % (id(pit),lst))

    prev = None
    item = None
    try:
        while pit:
            prev = item
            item = pit.next()
            ic = item.__class__
            #log.debug("iter = %s" % id(pit))
            #log.debug("eval %s" % repr(item))
            if keymode and ic in [DelayedSubScript, DelayedSuperScript]:
                if ic is DelayedSubScript:
                    yield SAXEvText('_',item.pos)
                else:
                    yield SAXEvText('^',item.pos)
            elif   ic is DelayedUnexpandedText:
                if item.data:
                    yield SAXEvUnexpandedText(item.data,item.pos)
            elif   ic is DelayedText:
                if (not keymode) and pit and pit.peek().__class__ in [DelayedSubScript, DelayedSuperScript]:
                    next = pit.peek()
                    nc = next.__class__
                    # encapsulate one char in a group and push it back
                    if len(item.data) > 1:
                        yield SAXEvText(item.data[:-1],item.pos)
                    item = DelayedText(item.data[-1],item.pos)
                    g = DelayedGroup(item.pos)
                    g.append(item)
                    #print "Create ResolvedSubSuperScript with base = %s" % item.data[-1]
                    pit.pushback(ResolvedSubSuperScript(item.pos,g))
                else:
                    yield SAXEvText(item.data,item.pos)
            elif ic is DelayedGroup:
                if (not keymode) and pit and pit.peek().__class__ in [DelayedSubScript, DelayedSuperScript]:
                    pit.pushback(ResolvedSubSuperScript(item.pos,item))
                else:
                    if item.args is not None:
                        exargs = item.args
                    else:
                        exargs = (args,subscr,superscr,body)
                    for i in eval(item,cmddict,*exargs,keymode=keymode):
                        yield i.tr(item.pos)
            elif ic is ResolvedSubSuperScript:
                if pit and pit.peek().__class__ in [DelayedSubScript, DelayedSuperScript]:
                    op = pit.next()
                    opc = op.__class__
                        
                    if not pit:
                        raise MacroError("%s: Missing argument for sub-/superscript" % (item.pos,))
                    rhs = pit.next()
                    rc = rhs.__class__
                    if rc is DelayedText:
                        if len(rhs.data) > 1:
                            pit.pushback(DelayedText(rhs.data[1:],rhs.pos))
                            rhs = DelayedText(rhs.data[0],rhs.pos)
                        g = DelayedGroup(rhs.pos)
                        #print "Sub-/superscript (%s) = '%s'" % (ic,rhs.data)
                        g.append(rhs)
                    elif rc is DelayedGroup:
                        g = rhs
                    else:
                        raise MacroError("%s: Invalid argument for sub-/superscript" % rhs.pos)

                    if   opc is DelayedSubScript:
                        if item.subscr is not None:
                            raise MacroError("%s: Duplicate subscript for group" % rhs.pos)
                        item.subscr = rhs
                    else:
                        if item.superscr is not None:
                            raise MacroError("%s: Duplicate superscript for group" % rhs.pos)
                        item.superscr = rhs
                    pit.pushback(item)
                else:
                    # ugly, ugly! Assume that we're in math mode! Sorry, that's just how it works for now.
                    if item.subscr and item.superscr:
                        tag = 'msubsup'
                    elif item.subscr:
                        tag = 'msub'
                    elif item.superscr:
                        tag = 'msup'
                    else:
                        assert 0

                    assert not keymode
                    yield SAXEvStartTag(tag,{},item.pos)
                    yield SAXEvStartTag('mrow',{},item.pos)
                    for i in eval([item.base],cmddict,args,subscr,superscr,body):
                        yield i.tr(item.pos)
                    yield SAXEvEndTag('mrow',item.pos)

                    if item.subscr:
                        yield SAXEvStartTag('mrow',{},item.pos)
                        for i in eval([item.subscr],cmddict,args,subscr,superscr,body):
                            yield i.tr(item.pos)
                        yield SAXEvEndTag('mrow',item.pos)
                    if item.superscr:
                        yield(SAXEvStartTag('mrow',{},item.pos))
                        for i in eval([item.superscr],cmddict,args,subscr,superscr,body):
                            yield i.tr(item.pos)
                        yield(SAXEvEndTag('mrow',item.pos))

                    yield(SAXEvEndTag(tag,item.pos))
            elif ic is DelayedMacro:
                #if   item.name == ':':
                #    assert not keymode
                #    yield(SAXEvSpecialTableRowBegin(item.pos))
                #elif item.name == '!':
                #    assert not keymode
                #    yield(SAXEvSpecialTableCellBegin(item.pos))
                #else:
                if True:
                    macroitem = item
                    try:
                        macronode = cmddict[item.name]
                    except KeyError:
                        #print "Known macros:"
                        #print cmddict
                        raise MacroError('%s: Unknown macro "%s"' % (item.pos,item.name))
                    
                    if not macronode.nodeName == 'def':
                        raise MacroError('%s: Environment "%s" used as a macro' % (item.pos,item.name))
                    macrodef = macronode.macro
                   
                    macro = ResolvedMacro(macronode,item.pos)
                    class _MakeGroupException(Exception): pass
                    try:
                        if item.args is not None:
                            if len(item.args) != macronode.nArgs():
                                raise MacroError('%s: Too few arguments for macro "%s"; expected %d, got %d' % (item.pos,item.name,macronode.nArgs(),len(item.args)))
                            for a in item.args:
                                g = DelayedGroup(item.pos,args=(args,subscr,superscr,body))
                                g.extend(a)
                                macro.append(g)
                            if item.subscr is not None:
                                if not macronode.acceptsSubscript():
                                    raise MacroError('%s: Macro "%s" does not accept subscript' % (item.pos,item.name))
                                else:
                                    g = DelayedGroup(item.pos,args=(args,subscr,superscr,body))
                                    g.extend(items.subscr)
                                    macro.subscr = g
                            if item.superscr is not None:
                                if not macronode.acceptsSubscript():
                                    raise MacroError('%s: Macro "%s" does not accept superscript' % (item.pos,item.name))
                                else:
                                    g = DelayedGroup(item.pos,args=(args,subscr,superscr,body))
                                    g.extend(items.superscr)
                                    macro.superscr = g
                        else:
                            while pit:
                                # collect arguments for macro
                                nxt = pit.peek()
                                nc = nxt.__class__
                                # we skip whitespace between macro and group
                                # arguments, bit if we do not find an argument
                                # we put back the whitespace.
                                skipped_ws = []
                                #log.debug("DelayedMacro \\%s. Next: %s" % (item.name,nxt))
                                if nc is DelayedGroup:
                                    if macro.requireArgs() > 0:
                                        macro.append(pit.next())
                                    else:
                                        break
                                elif nc is DelayedText:
                                    if not nxt.data.strip():
                                        skipped_ws.append(pit.next()) # ignore whitespace between arguments
                                    else:
                                        break
                                elif nc in [DelayedSubScript,DelayedSuperScript]:
                                    opc = nc
                                    if   nc is DelayedSubScript and not macronode.acceptsSubscript():
                                        if macro.requireArgs() > 0:
                                            raise MacroError("%s: Macro '%s' does not accept subscript" % (item.pos,item.name))
                                        else:
                                            raise _MakeGroupException()
                                    elif nc is DelayedSuperScript and not macronode.acceptsSuperscript():
                                        if macro.requireArgs() > 0:
                                            raise MacroError("%s: Macro '%s' does not accept superscript" % (item.pos,item.name))
                                        else:
                                            raise _MakeGroupException()
                                    pit.next()
                                    if not pit:
                                        raise MacroError("%s: Missing argument for sub-/superscript" % item.pos)
                                    
                                    rhs = pit.next()
                                    rc = rhs.__class__

                                    if rc is DelayedText:
                                        if len(rhs.data) > 1:
                                            pit.pushback(DelayedText(rhs.data[1:],rhs.pos))
                                            rhs = DelayedText(rhs.data[1], rhs.pos)
                                        g = DelayedGroup(item.pos)
                                        g.append(rhs)
                                        rhs = g
                                    elif rc is DelayedGroup:
                                        g = rhs
                                    else:
                                        raise MacroError("%s: Invalid argument for sub-/superscript" % item.pos)

                                    if opc is DelayedSubScript:
                                        if item.subscr is not None:
                                            raise MacroError("%s: Duplicate subscript" % rhs.pos)
                                        macro.subscr = rhs
                                    else:
                                        if item.superscr is not None:
                                            raise MacroError("%s: Duplicate superscript" % rhs.pos)
                                        macro.superscr = rhs
                                else:
                                    while skipped_ws:
                                        pit.pushback(skipped_ws.pop())
                                    break
                    except _MakeGroupException:                    
                        g = DelayedGroup(item.pos)
                        g.append(macroitem)
                        for a in macro.args:
                            g.append(a)
                        if macro.subscr:
                            g.append(DelayedSubScript(item.pos))
                            g.append(macro.subscr)
                        if macro.superscr:
                            g.append(DelayedSuperScript(item.pos))
                            g.append(macro.superscr)
                        pit.pushback(g)
                    else:
                        #print "  Macro args: %s" % macro.args
                        if macro.requireArgs() > 0:
                            raise MacroError("%s: Missing arguments for macro '%s'" % (item.pos,item.name))

                        subscr   = (macro.subscr   or DelayedGroup(item.pos)) if macronode.acceptsSubscript()   else None
                        superscr = (macro.superscr or DelayedGroup(item.pos)) if macronode.acceptsSuperscript() else None
                        #if macronode.acceptsSubscript() and macro.subscr is None:
                        #    raise MacroError("%s: Missing subscript arguments for macro '%s'" % (item.pos,item.name))
                        #if macronode.acceptsSuperscript() and macro.superscr is None:
                        #    raise MacroError("%s: Missing superscript arguments for macro '%s'" % (item.pos,item.name))

                        #log.debug('DelayedMacro: \\%s, args = %s' % (item.name,macro.args))
                        #print macrodef.body
                        try:
                            for i in eval(macrodef.body,cmddict,macro.args,subscr,superscr):
                                yield i.tr(item.pos)
                        except MacroError,e:
                            e.trace.append(item.pos)
                            raise
                        
            elif ic is DelayedEnvironment:
                try:
                    envnode = cmddict[item.name]
                except KeyError:
                    raise MacroError('%s: Unknown macro "%s"' % (item.pos,item.name))
                
                if envnode.nodeName != 'defenv':
                    raise MacroError('%s: Macro "%s" used as an environment' % (item.pos,item.name))
                
                #env = ResolvedEnvironment(envnode,item.pos)

                content = item.content
                envargs = []
            
                idx = 0
                while idx < len(content) and len(envargs) < envnode.nArgs():
                    # collect arguments for macro
                    nxt = content[idx]
                    nc = nxt.__class__

                    if nc is DelayedGroup:
                        envargs.append(nxt)
                    elif nc is DelayedText:
                        if not nxt.data.strip():
                            pass
                        else:
                            break
                    else:
                        break
                    idx += 1
                if len(envargs) < envnode.nArgs():
                    raise MacroError("%s: Missing arguments for environment '%s't" % (item.pos,item.name))
                envbody = DelayedGroup(item.pos)
                envbody.extend(content[idx:])


                # TODO: Add defines from the env node to the dict
                d = EnvDict(cmddict,envnode.env.localcmds)

                try:
                    for i in eval(envnode.env.body,d,envargs,None,None,envbody):
                        yield i.tr(item.pos)
                except MacroError,e:
                    e.trace.append(item.pos)
                    raise
            elif ic is DelayedArgRef:
                #log.debug('DelayedArgRef : {{%s}}' % item.key )
                key = item.key
                if isinstance(key,int):
                    if args is None:
                        raise MacroError("%s: Invalid argument reference" % item.pos)
                    elif len(args) <= key:
                        raise MacroError("%s: Referred to argument %d, but only %d are defined" % (item.pos,key,len(args)))
                    
                    for i in eval([args[key]],cmddict,keymode=keymode):
                        yield i.tr(item.pos)
                else:
                    if key == 'BODY':
                        if body is None:
                            raise MacroError("%s: Invalid {{BODY}} reference" % item.pos)
                        r = body
                        assert r.__class__ is not list
                    elif key == 'SUBSCRIPT':
                        if subscr is None:
                            raise MacroError("%s: Invalid {{SUBSCRIPT}} reference" % item.pos)
                        r = subscr
                        assert r.__class__ is not list
                    elif key == 'SUPERSCRIPT':
                        if superscr is None:
                            raise MacroError("%s: Invalid {{SUPERSCRIPT}} reference" % item.pos)
                        r = superscr
                        assert r.__class__ is not list
                    else:
                        raise MacroError("%s: Invalid {{%s}} reference" % (item.pos,key))
                    
                    #log.debug('  items = %s' % r) 
                    
                    assert r is not None
                    for i in eval([r],cmddict,keymode=keymode):
                        #log.debug('  > %s' % i)
                        yield i.tr(item.pos)
            elif ic is DelayedLookup:
                r = []
                #log.debug('DelayedLookup: %s' % item.content)
                #log.debug('               args = %s' % args)
                for i in eval(item.content,cmddict,args,subscr,superscr,body,keymode=True):
                    if i.__class__ is SAXEvText:
                        r.append(i.data)
                    else:                    
                        raise MacroError('%s: Only text is allowed in dictionary lookup' % i.pos)
                key = ''.join(r)
                try:
                    #log.debug("Dictionary key = '%s'" % key)
                    yield SAXEvText(cmddict.dictLookup(key).value,item.pos)
                except KeyError:
                    raise MacroError("%s: No dictionary entry for '%s'" % (item.pos,key))
            elif ic is DelayedElement:
                if keymode:
                    raise MacroError('%s: Element may not be used in text-only context' % item.pos)
               
                #log.debug('DelayedElement <%s>' % item.name)
                #log.debug('  Body : %d' % len(item.body))
                #log.debug('  Body = %s' % item.body)
                d = {}
                for k,v in item.attrs.items():
                    r = []
                    for i in eval(v,cmddict,args,subscr,superscr,body,keymode=True):
                        if i.__class__ is SAXEvText:
                            r.append(i.data)
                        else:
                            raise MacroError('%s: Only text is allowed in element attributes' % i.pos)
                    d[k] = ''.join(r)

                yield SAXEvStartTag(item.name,d,item.pos)
                
                #log.debug('Eval <%s> content...' % item.name)
                #log.debug(' content = %s' % item.body)
                for i in eval(item.body, cmddict, args,subscr,superscr,body,keymode=False):
                    yield i.tr(item.pos)
                #log.debug('End <%s> content.' % item.name)
                
                yield SAXEvEndTag(item.name,item.pos)
            elif ic is DelayedTableContent:
                data = item.get()
                pos = item.pos
                for row in data:
                    yield SAXEvTableRowStart(pos)
                    for cell in row:
                        yield SAXEvTableCellStart(pos)
                        for i in eval(cell,cmddict,args,subscr,superscr,body,keymode=False):
                            yield i
                        yield SAXEvTableCellEnd(pos)
                    yield SAXEvTableRowEnd(pos)
            elif ic in [ DelayedSubScript, DelayedSuperScript ]:
                raise MacroError('%s: Missing left-hand operand for sub-/superscript' % item.pos)
            else:
                print '---------',ic
                assert False
        #log.debug('-----------<<< END iter(%s)'  % id(pit))
    except AssertionError:
        if prev:
            print "  trace : prev @ %s" % prev.pos
        raise

def closeStack(macrostack,stopClass,pos,name):
    text = ''
    while(macrostack):
        top = macrostack.pop()
        if(isinstance(top,stopClass)):
            break
        else:
            try:
                if top.nArgs()==0:
                    text = text + ''.join(top.tree)
                else:
                    raise MacroError('%s:<%s> was closed preemptivly' %(pos,top.name))
            except AttributeError:
                raise MacroError('%s:while closing <%s> a unclosed group was'+
                'encountered'%(pos,name))
    return (text,macrostack)

class MacroParser:
    def ___init__(self):
        self.__macrostack = []
        self.__cmdstack = []

    def handleText(cmddict,data,pos,table=False):
        text = ''
        macro_re = re.compile('|'.join([
            r'\\(?P<env>begin|end)\s*\{(?P<envname>[a-zA-Z][a-zA-Z0-9@]*)\}',
            r'\\(?P<macro>[a-zA-Z@][a-zA-Z0-9@]*|[:!\\_\^\{\}| ]|[~\'"`,.\-%#][a-zA-Z]?)',
            r'(?P<group>[{}])',
            r'(?P<subsuperscr>[_^])',
            r'(?P<longdash>---*)', 
            r'(?P<leftdquote>``)', 
            r"(?P<rightdquote>'')", 
            r'(?P<nbspace>~)',
            r'(?P<newline>\n)'
            ]))
        p = 0
        for o in macro_re.finditer(data):
            #close the top element if the next isnt a ^ or _
            print macrostack
            if(not o.group('subsuperscr') and macrostack):
                while(macrostack and isinstance(macrostack[-1],Group) and
                macrostack[-1].end):
                    top = macrostack.pop()
                    if(macrostack):
                        macrostack[-1].addArgument(top,pos)
                    else:
                        text += top.content
                if(isinstance(macrostack[-1],Environment) and
                    macrostack[-1].nArgs()==0):
                    text += macrostack[-1].printable()
                if(isinstance(macrostack[-1],Macro) and macrostack[-1].nArgs()==0):
                    top = macrostack.pop()
                    text += ''.join(top.tree)
            #Slight misuse of try, this is meant to check if the text is inside a
            #group
            try:
                if macrostack[-1].end:
                    if p < o.start(0):
                        text += data[p:o.start(0)]
            except IndexError:
                if p < o.start(0):
                    text += data[p:o.start(0)]
            except AttributeError:
                pass
            p= o.end(0)
            print macrostack
            print cmddict
            #should check if the macro is in the __cmddict
            if o.group('macro'):
                name = o.group('macro')
                try:
                    i = macrostack[-1] 
                    if isinstance(i,unicode):
                        if i=="_" or i == "^":
                            raise MacroError("%s:%s can't have macro on"+\
                            "left hand side"%(pos,i))
                except IndexError:
                    pass
                assert name not in ['begin','']
                if name == ':':
                    if table:
                        #dgb("%s: New table row" % pos)
                        try:
                            self.started
                        except AttributeError:
                            self.started = True
                    else:
                        raise MacroError('%s: Row syntax used outside a Table'%pos)
                elif name == '!':
                    if table:
                        try:
                            if self.started:
                                #dgb("%s: New table cell" % pos)
                                pass
                        except AttributeError:
                            #dgb('%s: cstack = %s' % (pos,self.__cstack))
                            raise MacroError('%s: Table syntax must start with a row \\:' % pos)
                    else:
                        raise MacroError('%s: \! syntax used outside a Table'%pos)
                else:
                    try:
                        macronode = cmddict[name].macro
                        macronode = macronode.copy(pos)
                        macrostack.append(macronode)
                    except KeyError:
                        raise MacroError('%s: Unknown macro "%s"' % (pos,name))
                        
            elif o.group('env'):
                name = o.group('envname')
                if o.group('env') == 'begin':
                    #emitOpen(DelayedEnvironment(name,pos))
                    try:
                        envnode = cmddict[name]
                        d = envnode.getDefs()
                        envnode = envnode.env.copy()
                        cmdstack.append(cmddict)
                        cmddict = CommandDict(cmddict) 
                        cmddict.update(d.getCmdDict())
                        macrostack.append(envnode)
                    except KeyError:
                        raise MacroError('%s: Unknown environment\
                        "%s"'%(pos,name))
                else:
                    if (macrostack and macrostack[-1].name ==
                        name):
                        cmddict = cmdstack.pop()
                        envdone = macrostack.pop()
                        if envdone.nArgs()==0:
                            text = text + ''.join(envdone.printend())
                        else:
                            raise MacroError(('%s: <%s> ended '+
                                'before getting enough arguments')
                                %(self.pos,name))
                    else:
                        raise MacroError(('%s: <%s> end environment'+
                        'mismatch')%(pos,name))
            elif o.group('group'):
                #Either a start or an end or a group
                tok = o.group('group')
                if tok == '{': 
                    #self.__emitOpen(DelayedGroup(pos))
                    macrostack.append(Group(p))
                else:
                    top = macrostack[-1]
                    if(isinstance(top,Group)):
                        top.end = True
                        content = data[top.start:p-1]
                        top.content = content
                    else:
                        raise MacroError("%s: Umatched group close"%pos)
            elif o.group('subsuperscr'):
                char = o.group('subsuperscr')
                if len(macrostack)>0:
                    macrostack[-1].handleSubp(char)
                    if(data[p+1]!='{'):
                        p +=1
                        macrostack[-1].addArgument(data[p],pos)
                else:
                    raise MacroError("<%s-%s>:Trying to apply %s to an"\
                    +"empty argument"%(start,pos,char))
            elif   o.group('longdash') is not None:
                if   o.group('longdash') == '--':
                    text += u'\u2013'
                    #self.__emitItem(DelayedText(u'\u2013',pos)) # &ndash;
                elif o.group('longdash') == '---':
                    text += u'\u2014'
                    #self.__emitItem(DelayedText(u'\u2014',pos)) # &ndash;
                    pass
                else:
                    text += o.group('longdash')
                    #self.__emitItem(DelayedText(o.group('longdash'),pos)) # &ndash;
            elif o.group('leftdquote') is not None:
                #self.__emitItem(DelayedText(u'\u201c',pos)) # &ldquote
                text += u'\u201c'
                pass
            elif o.group('rightdquote') is not None:
                #self.__emitItem(DelayedText(u'\u201d',pos)) # &rdquote
                text += u'\u201d'
            elif o.group('nbspace'):
                #self.__emitItem(DelayedText(u'\xa0',pos)) # &nbsp;
                text += u'\xa0'
            elif o.group('newline'):
                #self.__emitItem(DelayedText(u' \n',pos))
                text += u' \n '
                pos = Pos(pos.filename,pos.line + 1)
            else:
                #print 'GOT: "%s"' % o.group(0)
                assert 0
        if macrostack:
            while(macrostack and isinstance(macrostack[-1],Group) and
            macrostack[-1].end):
                top = macrostack.pop()
                if(macrostack):
                    macrostack[-1].addArgument(top,pos)
                else:
                    text += top.content
            if(isinstance(macrostack[-1],Environment) and
                macrostack[-1].nArgs()==0):
                text += macrostack[-1].printable()
            if(isinstance(macrostack[-1],Macro) and macrostack[-1].nArgs()==0):
                top = macrostack.pop()
                text += ''.join(top.tree)
        if p < len(data):
            #print "NODE : <%s>" % self.nodeName
            #print len(self.__cstack),self.__cstack[-1].data
            #print repr(self.__cstack[-1])
            #self.__cstack[-1].append(DelayedText(data[p:],pos))
            text += data[p:]
        return (text,pos,macrostack)
