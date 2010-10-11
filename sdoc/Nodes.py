"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/

    
    Copyright (c) 2009 Mosek ApS 
"""

from   UserDict import UserDict
from   UserList import UserList

from   EvHandler import handler, dtdhandler, entityhandler
from   bibtexml import BibDB

import urlparse
import xml.sax
import sys,os,operator
import Iters
import syntax
import cond

import re
import logging


msglog = logging.getLogger("SDocML Expander")
msg = msglog.info
err = msglog.error

#def msg(m):
#    m = unicode(m)
#    sys.stderr.write('SDocML Expander: ')
#    sys.stderr.write(m.encode('utf-8'))
#    sys.stderr.write('\n')

def debug(*args):
    if 0:
        sys.stderr.write('[D]')
        sys.stderr.write((' '.join([ unicode(s) for s in args ])).encode('utf8'))
        sys.stderr.write('\n')

simpleTextNodeList = [ 'em','tt','bf','sc','font','nx','span','br', 'note' ]
structTextNodeList = [ 'ilist','dlist','div','table','float','img','noexpand','pre','center','flushleft','flushright' ]
linkNodeList       = [ 'a','ref','href' ]
mathEnvNodeList    = [ 'math','m','eqnarray' ]
textNodeList       = [ 'ilist','dlist','table','a','ref','href','float', 'img' ] + simpleTextNodeList + mathEnvNodeList

mathNodeList       = [ 'mrow','msup','msub','msubsup','mfenced', 'mi','mo','mn','mtable', 'mvector', 'mfont', 'mtext', 'mfrac', 'mroot','msqrt' ]

mathFonts          = [ 'mathbb','mathcal','mathtt','mathrm','mathfrac' ]
textFonts          = [ 'tt','rm','sc','sans','serif' ]

_simpleTextNodes = ' '.join([ '<%s>' % i for i in simpleTextNodeList ])
_structTextNodes = ' '.join([ '<%s>' % i for i in structTextNodeList ])
_linkNodes       = ' '.join([ '<%s>' % i for i in linkNodeList ])
_mathEnvNodes    = ' '.join([ '<%s>' % i for i in mathEnvNodeList ])
_mathNodes       = ' '.join([ '<%s>' % i for i in mathNodeList ])



######################################################################
#  ERRORS
######################################################################
class GenericNode:
    pass
def dummy(name):
    class _dummy(GenericNode):
        def __init__(self,*args):
            assert 0
    return _dummy


class MotexException(Exception):
    pass

class MathError(MotexException):
    pass

class MacroError(MotexException):
    pass

class MacroArgErrorX(MotexException):
    def __init__(self,msg):
        Exception.__init__(self,msg)
        self.msg = msg

class MacroArgError(MotexException):
    pass
class NodeError(MotexException):
    pass

class XMLIdError(MotexException):
    pass
class XMLIdRefError(MotexException):
    pass

class XMLError(MotexException):
    pass

class DocumentAssert(MotexException):
    pass

class CondError(MotexException):
    pass

class NodeIncludeError(MotexException):
    pass
    

######################################################################
#  Helper functionality
######################################################################

class CondOpr(str):
    pass

class Cond:
    And = CondOpr('+')
    Or  = CondOpr('|')
    Xor = CondOpr('/')
    Not = CondOpr('!')

class CondTerm(unicode):
    pass

class CondIsDef(unicode):
    pass


class CondExp(list):
    pass


def escape(s):
    def repl(o):
        if   o.group(0) == '<': return '&lt;'
        elif o.group(0) == '>': return '&gt;'
        elif o.group(0) == '&': return '&amp;'
    return re.sub(r'<|>|&',repl,s)

def xescape(s):
    def repl(o):
        if   o.group(0) == '<': return '&lt;'
        elif o.group(0) == '>': return '&gt;'
        elif o.group(0) == '&': return '&amp;'
        else:                   return '&#%d;' % ord(o.group(0))
    return re.sub(u'<|>|&|[\u0080-\u8000]',repl,s)

class Attr:
    defaultDescr = {
        'cond' : '\n'.join(['Conditional statement. The values of this attribute',
                            'is a space-separated list of keys referring to global',
                            'conditional values. If at least one of the keys evaluated to "True"',
                            'the condition is met and the tag is expanded.'
                            ''
                            'The special conditions "true" and "false" always evaluates to "True"',
                            'and "False" respectively. All others are defined globally either on',
                            'the command line or in an options file.',
                            ''
                            'The syntax for conditional expressions is:',
                            '<pre>',
                            'exp    -> subexp | "!" subexp',
                            'subexp -> TERM | "(" explst ")" | isdef',
                            'explst -> andlst | orlst | xorlst',
                            'orlst  -> exp | exp "|" orlst',
                            'andlst -> exp | exp "+" andlst',
                            'xorlst -> exp | exp "/" xorlst',
                            'isdef  -> ? TERM',
                            '</pre>',
                            'For example:',
                            '<pre>',
                            '(c1 | c2 | !c3)',
                            '( (c1 / c2) + c3 )',
                            '((?c1 + c1) | (?c2 + c2))',
                            '</pre>',
                            'Note: The exact meanings of',
                            '<dlist>',
                            '  <dt><tt>a|b|c</tt></dt>',
                            '  <dd>At least one of <tt>a</tt>, <tt>b</tt> and <tt>a</tt> must be true</dd>',
                            '  <dt><tt>a+b+c</tt></dt>',
                            '  <dd>All of one of <tt>a</tt>, <tt>b</tt> and <tt>a</tt> must be true</dd>',
                            '  <dt><tt>a/b/c</tt></dt>',
                            '  <dd>Exactly one of <tt>a</tt>, <tt>b</tt> and <tt>a</tt> must be true</dd>',
                            '</dlist>',
                            'Evaluaten is the normal lazy logic evaluation. This means that while referring to',
                            'a variable <tt>a</tt> which is not defined causes an error, but an expression ',
                            '<tt>?a+a</tt> (meaning: If <tt>a</tt> is defined and <tt>a</tt> is true) is valid.'
                            ]),
        'id'          : 'A globally unique ID that may be used to refer to this element.',
        'class'       : 'A space-separated list of class names that will be passed on to the backend as is.',
        'macroexpand' : '(yes|no) Tells the front end to either expand or ignore macros.',
        'url'         : 'An address of an external resource.',
        'type'        : 'A MIME type definition',
        'cellhalign'  : 'A space-separated list of (left|center|right) defining horizontal alignment for the cells.',
        'cellvalign'  : 'A space-separated list of (top|middle|bottom) defining vertical alignment for the cells.',
    }

    def __init__(self,name,default=None,descr=None,required=False):
        self.name = name
        self.default = default
        if descr is None:
            if self.defaultDescr.has_key(name):
                self.descr = self.defaultDescr[name]
            else:
                self.descr = None
        else:
            self.descr = descr

class DfltDict(UserDict):
    def __init__(self,cons=lambda: None):
        UserDict.__init__(self)
        self.__cons = cons
    def __ensurekey(self,k):
        if not self.data.has_key(k):
            self.data[k] = self.__cons()
    def __getitem__(self,k):
        self.__ensurekey(k)
        return self.data[k]


class Attrs(UserDict):
    def __init__(self,items={}):
        UserDict.__init__(self,[ (item.name, item) for item in items])
    def defaultValues(self):
        return dict([ (item.name, item.default) for item in self.values()])


class CommandDict(UserDict):
    def __init__(self,parent=None):
        UserDict.__init__(self)

        assert parent is None or isinstance(parent,CommandDict)
        self.__parent = parent

        self.__lookuptable = {}

    def __getitem__(self,key):
        try:
            return self.data[key]
        except KeyError:
            if self.__parent is not None:
                return self.__parent[key]
            else:
                raise

    def has_key(self,key):
        return self.data.has_key(key) or self.__parent.has_key(key)

    def __setitem__(self,key,value):
        if not self.data.has_key(key):
            self.data[key] = value
        else:
            raise KeyError('Macro "%s" already defined' % key)

    def dictLookup(self,key):
        if self.__lookuptable.has_key(key):
            return self.__lookuptable[key]
        elif self.__parent is not None:
            return self.__parent.dictLookup(key)
        else:
            raise KeyError('No Dictionary entry for %s' % key)
    def _dictKeys(self):
        if self.__parent is not None:
            s = self.__parent._dictKeys()
        else:
            s = set()
        return s | set(self.__lookuptable.keys())
    def dictSet(self,key,value):
        if not self.__lookuptable.has_key(key):
            self.__lookuptable[key] = value
        else:
            raise KeyError('Dictionary entry for %s already defined' % key)

    def dump(self,depth=0):
        for k,v in self.data.items():
            print '%*s = %s' % (depth*2,k,v)
        if isinstance(self.__parent,CommandDict):
            self.__parent.dump(depth+1)
        else:
            print '%*s' % (depth*2,str(self.__parent))

    def __collect(self,d):
        if self.__parent is not None:
            self.__parent.__collect(d)
        d.update(self.data)
        return d
        
    def items(self):
        return self.__collect({}).items()
        
######################################################################
# Macro expansion helper functionality
######################################################################

class MacroEvent_StartTag:
    def __init__(self,name,attrs,filename,line):
        assert name is not None
        self.name = name
        self.attrs = attrs
        self.filename = filename 
        self.line = line
    def __str__(self): return '<%s>' % self.name
    def __repr__(self): return '<%s>' % self.name
class MacroEvent_EndTag:
    def __init__(self,name,filename,line):
        self.name = name
        self.filename = filename
        self.line = line
    def __str__(self): return '</%s>' % self.name
    def __repr__(self): return '</%s>' % self.name

class MacroEvent_Text:
    def __init__(self,data,filename,line):
        self.data = data
        self.filename = filename
        self.line = line
    def __str__(self): return '"%s"' % self.data
    def __repr__(self): return '"%s"' % self.data

class MacroEvent_ExpandText(MacroEvent_Text):
    pass

class MacroEvent_NoExpandText(MacroEvent_Text):
    pass

class UnexpandedItem:
    def acceptsSubscript(self):
        return False
    def acceptsSuperscript(self):
        return False

class LazyElement(UnexpandedItem,UserList):
    def __init__(self,name,attrs,filename,line,ev_close=None):
        UserList.__init__(self)
        self.__name     = name
        self.__attrs    = attrs
        self.__filename = filename
        self.__line     = line

        self.pos = filename,line

        self.__ev_close = ev_close

        self.nodeName = name

    def newChild(self,name,attrs,filename,line):
        debug('LazyElement %s: Add node %s' % (self.__name,name))

        node = LazyElement(name,attrs,filename,line)
        self.append(node)
        return node

    def handleText(self,data,filename,line):
        debug('\tLazyElement.handleText @ %s:%d (%s): ' % (filename,line,repr(data)))
        node = MacroEvent_ExpandText(data,filename,line)
        self.data.append(node)
    
    def linearize(self,res,args,kwds):
        res.append(MacroEvent_StartTag(self.__name,self.__attrs,self.__filename,self.__line))
        debug('LazyElement %s: Linearize' % (self.__name))

        for i in self:
            if isinstance(i,MacroEvent_ExpandText):
                res.append(i)
            else:
                i.linearize(res,args,kwds)
        
        res.append(MacroEvent_EndTag(self.__name,self.__filename, self.__line))
        return res
    def endOfElement(self,filename,line):
        if self.__ev_close:
            self.__ev_close()
        
    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,self.__name)
    def __repr__(self):
        return str(self)


    

class Group(UserList,UnexpandedItem):
    def __init__(self,filename,line):
        UserList.__init__(self)
        self.pos = filename,line
        self.__closed = False
    def linearize(self,res,args,kwds):
        try:
            for i in self:
                if isinstance(i,unicode):
                    res.append(MacroEvent_NoExpandText(i,self.pos[0],self.pos[1]))
                else:
                    i.linearize(res,args,kwds)
            return res
        except MacroArgErrorX, e:
            raise MacroArgError('%s at %s:%d' % (e.msg,self.pos[0],self.pos[1]))
    def append(self,value):
        debug("%s.append %s" % (self.__class__.__name__,repr(value)))
        assert not self.__closed
        UserList.append(self,value)
    def end(self):
        assert not self.__closed
        self.__closed = True
    def __repr__(self):
        return "%s{%s}" % (self.__class__.__name__,repr([repr(s) for s in self]))
    def __str__(self):
        return repr(self)

class BraceGroup(Group):
    pass

class LazyTableItem(Group):
    def __init__(self,name,filename,line):
        Group.__init__(self,filename,line)
        assert name is not None
        self.name       = name
    def linearize(self,res,args,kwds):
        #print "LINEARIZE TABLE ITEM %s" % self.__class__.__name__
        res.append(MacroEvent_StartTag(self.name,{},self.pos[0],self.pos[1]))
        Group.linearize(self,res,args,kwds)
        res.append(MacroEvent_EndTag(self.name,self.pos[0],self.pos[1]))
        return res
    
class LazyTableRow(LazyTableItem):
    pass
class LazyTableCell(LazyTableItem):
    pass
class SubSuperBraceGroup(BraceGroup):
    pass

class SubBraceGroup(SubSuperBraceGroup):
    pass
class SuperBraceGroup(SubSuperBraceGroup):
    pass

class UnexpandedEnvironment(UnexpandedItem):
    def __init__(self,env,pos):
        self.pos       = pos
        self.__macro   = env
        
        self.__args     = [] # actual arguments
        self.__data     = [] # the environment content
    
    def append(self,value):
        debug("Env argument for %s: (%d) '%s'" % (self.__macro.macroName(),id(value),repr(value)))
        assert not isinstance(value,ContentManager)
        
        if len(self.__args) < self.nArgs():
            if isinstance(value,BraceGroup):
                self.__args.append(value)
            elif isinstance(value,unicode) and valule.strip():
                raise MacroError('Expected an argument for environment at %s:%d' % self.pos)
            else:
                pass
        else:
            self.__data.append(value)

    def isFinished(self):
        return len(self.__args) == self.__macro.nArgs()
    
    def nArgs(self):
        return self.__macro.nArgs()

    def linearize(self,res,args,kwds): # args is a dummy - we will never use it
        if len(self.__args) < self.__macro.nArgs():
            raise MacroError("Too few arguments for environment '%s' at %s:%d" % (self.__macro.macroName(),self.pos[0],self.pos[1]))
        args = []
        for a in self.__args:
            debug("  Expand arg: ",repr(a))
            args.append(a.linearize([],[],{}))
        
        cont = []
        kwds['BODY'] = cont
        for a in self.__data:
            if isinstance(a,unicode):
                cont.append(MacroEvent_NoExpandText(a,self.pos[0],self.pos[1]))
            else:
                a.linearize(cont,[],{})
        debug('UnexpandedMacro.linearize. Before: ',repr(res))
        self.__macro.linearize(res,args,kwds,self.pos[0],self.pos[1])
    
        return res
    def envName(self):
        return self.__macro.macroName()

    def end(self):
        if not self.isFinished():
            raise MacroError("Too few arguments for environment '%s' at %s:%d" % (self.__macro.macroName(),self.pos[0],self.pos[1]))
            

    def __repr__(self):
        return 'unexpanded env %s' % self.__macro

class UnexpandedMacro(UnexpandedItem):
    def __init__(self,macro,pos,onclose_action=None):
        self.pos     = pos
        self.__macro   = macro
        self.__onclose = onclose_action
        self.__args = []
        self.__subscript   = None
        self.__superscript = None

    def acceptsSubscript(self):
        return self.__macro.acceptsSubscript() and self.__subscript is None
    def acceptsSuperscript(self):
        return self.__macro.acceptsSuperscript() and self.__superscript is None
    def putSubscript(self,a):
        if not self.acceptsSubscript():
            raise MacroError('Subscript not accepted by macro at %s:%d' % self.pos)
        self.__subscript = a
    def putSuperscript(self,a):
        if not self.acceptsSuperscript():
            raise MacroError('Superscript not accepted by macro at %s:%d' % self.pos)
        self.__superscript = a
    
    def append(self,value):
        debug("Macro argument for %s: (%d) '%s'" % (self.__macro.macroName(),id(value),repr(value)))
        assert not isinstance(value,ContentManager)

        if (isinstance(value,unicode) or isinstance(value,str)) and not value.strip():
            pass
        else:
            if not isinstance(value,BraceGroup):
                raise MacroError('Expected an argument for macro at %s:%d' % self.pos)
            elif  len(self.__args) < self.__macro.nArgs():
                self.__args.append(value)
                
                if len(self.__args) == self.__macro.nArgs() and self.__onclose is not None:
                    self.__onclose()
            else:
                raise MacroError('too many arguments for macro at %s:%d' % self.pos)
        if False and self.__macro.macroName() == 'frac':
            print "nargs = ",self.nArgs()
            print 'got = ',len(self.__args)


    def isFinished(self):
        return len(self.__args) == self.__macro.nArgs()
    
    def nArgs(self):
        return self.__macro.nArgs()

    def linearize(self,res,args_,kwds_): # args_ and kwds_ are dummies - we will never use them
        if len(self.__args) < self.__macro.nArgs():
            raise MacroError("Too few arguments for macro '%s' at %s:%d" % (self.__macro.macroName(),self.pos[0],self.pos[1]))
        args = []
        for a in self.__args:
            debug("  Expand arg: ",a)
            try:
                args.append(a.linearize([],[],{}))
            except MacroArgErrorX,e:
                raise MacroArgError(e.msg + ' in \\%s at %s:%d' % (self.__macroName,self.pos[0],self.pos[1]))
        kwds = { }
        if self.__subscript is not None:
            kwds['SUBSCRIPT'] = self.__subscript.linearize([],[],{})
        if self.__superscript is not None:
            kwds['SUPERSCRIPT'] = self.__superscript.linearize([],[],{})
        debug('UnexpandedMacro.linearize. Before: ',res)
        
        try:
            self.__macro.linearize(res,args,kwds,self.pos[0],self.pos[1])
        except MacroArgErrorX,e:
            raise MacroArgError(e.msg + ' in \\%s at %s:%d' % (self.__macro.macroName(),self.pos[0],self.pos[1]))
    
        #print "Linearize %s" % self.__macro.macroName()
        #for i in res:
        #    print "  %s" % repr(i)

        return res
    
    def __repr__(self):
        return 'unexpanded %s' % self.__macro

class InorderOp:
    def __init__(self,op,file,line):
        self.op = op
        self.pos = file,line
    def __repr__(self):
        return "InorderOp(%s)" % self.op


class UnexpandedInorderop(UnexpandedItem):
    def __init__(self,base,pos):
        self.pos            = pos
        self.__base         = base
        self.__subscr       = None
        self.__superscr     = None

    def append(self,item):
        if isinstance(item,SubBraceGroup):
            if self.__subscr is not None:
                raise MathError('Only one subscript per element is allowed')
            self.__subscr = item
        elif isinstance(item,SuperBraceGroup):
            if self.__superscr is not None:
                raise MathError('Only one superscript per element is allowed')
            self.__superscr = item
        else:
            assert 0 

    def linearize(self,res, args,kwds): # args is a dummy
        if self.__subscr is not None and self.__superscr is not None:
            # Expand as <msubsup> 
            res.append(MacroEvent_StartTag('msubsup',{},self.pos[0],self.pos[1]))
            
            res.append(MacroEvent_StartTag('mrow',{},self.pos[0],self.pos[1]))
            if isinstance(self.__base,unicode):
                res.append(MacroEvent_NoExpandText(self.__base,self.pos[0],self.pos[1]))
            else:
                self.__base.linearize(res,[],{})
            res.append(MacroEvent_EndTag('mrow',self.pos[0],self.pos[1]))
            
            res.append(MacroEvent_StartTag('mrow',{},self.pos[0],self.pos[1]))
            if isinstance(self.__subscr,unicode):
                res.append(MacroEvent_NoExpandText(self.__subscr,self.pos[0],self.pos[1]))
            else:
                self.__subscr.linearize(res,[],{})

            res.append(MacroEvent_EndTag('mrow',self.pos[0],self.pos[1]))

            res.append(MacroEvent_StartTag('mrow',{},self.pos[0],self.pos[1]))
            if isinstance(self.__superscr,unicode):
                res.append(MacroEvent_NoExpandText(self.__superscr,self.pos[0],self.pos[1]))
            else:
                self.__superscr.linearize(res,[],{})
            res.append(MacroEvent_EndTag('mrow',self.pos[0],self.pos[1]))

            res.append(MacroEvent_EndTag('msubsup',self.pos[0],self.pos[1]))
        elif self.__subscr is not None:
            # Expand as <msub> 
            res.append(MacroEvent_StartTag('msub',{},self.pos[0],self.pos[1]))
            
            res.append(MacroEvent_StartTag('mrow',{},self.pos[0],self.pos[1]))
            if isinstance(self.__base,unicode):
                res.append(MacroEvent_NoExpandText(self.__base,self.pos[0],self.pos[1]))
            else:
                self.__base.linearize(res,[],{})
            res.append(MacroEvent_EndTag('mrow',self.pos[0],self.pos[1]))
            
            res.append(MacroEvent_StartTag('mrow',{},self.pos[0],self.pos[1]))
            if isinstance(self.__subscr,unicode):
                res.append(MacroEvent_NoExpandText(self.__subscr,self.pos[0],self.pos[1]))
            else:
                self.__subscr.linearize(res,[],{})
            res.append(MacroEvent_EndTag('mrow',self.pos[0],self.pos[1]))

            res.append(MacroEvent_EndTag('msub',self.pos[0],self.pos[1]))
        elif self.__superscr is not None:
            # Expand as <msuper> 
            res.append(MacroEvent_StartTag('msup',{},self.pos[0],self.pos[1]))
            
            res.append(MacroEvent_StartTag('mrow',{},self.pos[0],self.pos[1]))
            if isinstance(self.__base,unicode):
                res.append(MacroEvent_NoExpandText(self.__base,self.pos[0],self.pos[1]))
            else:
                self.__base.linearize(res,[],{})
            res.append(MacroEvent_EndTag('mrow',self.pos[0],self.pos[1]))
            
            res.append(MacroEvent_StartTag('mrow',{},self.pos[0],self.pos[1]))
            if isinstance(self.__superscr,unicode):
                res.append(MacroEvent_NoExpandText(self.__superscr,self.pos[0],self.pos[1]))
            else:
                self.__superscr.linearize(res,[],{})
            res.append(MacroEvent_EndTag('mrow',self.pos[0],self.pos[1]))

            res.append(MacroEvent_EndTag('msup',self.pos[0],self.pos[1]))
        else:
            self.__base.linearize(res,[],{},self.pos[0],self.pos[1])

        return res

class MacroMode:
    Invalid        = 0 # Neither text or macros are not allowed
    NoExpand       = 1 # Text is allowed, but macros are not expanded and space is preserved
    Text           = 2 # Text is allowed and macros are expanded 
    Math           = 3 # Text is parsed as math with _ and ^ as special operators, and numbers, identifiers etc are converted to suitable elements.
    SimpleMath     = 4 # Text is parsed as math, ^ and _ are recognized, but numbers etc are not modified.

    Inherit        = 5 # Inherit from parent
    InheritContent = 6 # Inherit content and macro expansion

    @staticmethod
    def toStr(mode):
        if mode is None:
            return 'None'
        else:
            return ['invalid','noexpand','text','math','simplemath','inherit'][mode]

######################################################################
# Node base class
######################################################################
##\brief This class wraps a scope inside an XML element class to handle items
#        that are contained in the scope.
#
# Specificly, the one relevant thing that this class does is to make sure that
# "^" and "_" constructions in math mode are correctly expanded.
class ContentManager:
    def __init__(self,managed,mode=None):
        self.__managed = managed
        self.__inorder_op = None
        self.__last = None
        self.__mode = mode

        assert not isinstance(managed,str)
        assert not isinstance(managed,unicode)

    def Managed(self):
        return self.__managed

    def append(self,item):
        debug("ContentManager (mode=%s) got (%s): %s" % (MacroMode.toStr(self.__mode),repr(type(item)),repr(item)))
        if isinstance(item,SubSuperBraceGroup):
            debug('\tlast = %s' % str(self.__last))
            if self.__last is None:
                raise MacroError('Invalid use of inorder operation %s at %s:%d' % (item.op,item.pos[0],item.pos[1]))
            elif isinstance(self.__last,UnexpandedInorderop):
                self.__last.append(item)
            elif isinstance(self.__last,unicode):
                last = self.__last
                self.__last = None
                c = last[-1]
                if not c.strip(): 
                    raise MacroError('Invalid use of inorder operation %s at %s:%d' % (item.op,item.pos[0],item.pos[1]))
                
                self.__managed.append(last[:-1])
                self.__last = UnexpandedInorderop(c,item.pos)
                self.__last.append(item)
            elif isinstance(self.__last,UnexpandedItem):
                debug("Accepts subscript ? %s" % self.__last.acceptsSubscript())
                debug("Accepts superscript ? %s" % self.__last.acceptsSuperscript())
                if isinstance(item,SubBraceGroup) and self.__last.acceptsSubscript():
                    debug("Put subscript.")
                    self.__last.putSubscript(item)      
                elif isinstance(item,SuperBraceGroup) and self.__last.acceptsSuperscript():
                    debug("Put superscript.")
                    self.__last.putSuperscript(item)
                else:
                    self.__last = UnexpandedInorderop(self.__last,item.pos)
                    self.__last.append(item)
            else:
                print('Unexpected type: ',self.__last) 
                assert 0
        else:
            debug("ContentManager. Add:",repr(item))
            debug("ContentManager. last =",repr(self.__last))

            if isinstance(item,Node):
                if self.__last is not None:
                  debug("__last =",self.__last)
                  last = self.__last
                  assert last is not self
                  self.__last = None
                  self.__managed.append(last)
                self.__managed.append(item)
            else:
                assert not isinstance(item,ContentManager)
                if self.__last is not None:
                    last = self.__last
                    self.__last = None
                    
                    self.__managed.append(last)
                self.__last = item
    
    def flush(self):
        debug('ContentManager.end. last = %s' % repr(self.__last))
        if self.__last is not None:
            last = self.__last
            self.__last = None
            self.__managed.append(last)

    def __repr__(self):
        return "ContentManager(%s)" % repr(self.__managed)

class DontAcceptNoneList(UserList):
    def append(self,item):
        assert item is not None
        assert not isinstance(item,UnexpandedItem)
        UserList.append(self,item)
     


class Node:
    nodeName     = "<none>"
    acceptAttrs  = Attrs()
    contIter     = None
    macroMode    = MacroMode.Invalid
    traceInfo    = False
    comment      = None
    examples     = []
    allowTableSyntax = False 
    tablerowelement = None # The name of row elements for specual Table syntax
    tablecellelement = None # The name of cell elements for special  Table syntax
    metaElement  = False # The element should be read and processed but not added to the internal tree.
    expandElement = True # The node should be read, processed and added to the internal tree, but should not be added to the output.
    paragraphElement = True # The element starts its own paragraph (like <center>, <div> etc.)
    structuralElement = False # Don't break up the content (remove spaces, make paragraphs etc.)
    mathElement       = False

    
    ################################################################################  
    ##
    __progress = 0
    __lineprogress = 0
    __maxlline = 20
    @classmethod
    def pgs_SAX_element(self,item):
        if isinstance(item,Node):
            sys.stdout.write('.')
            self.__progress += 1
            if self.__lineprogress > 20:
                self.__lineprogress = 0
                sys.stdout.write('\n')
    ##
    ################################################################################  

    mathmodemacro_regex = re.compile('|'.join([r'\\(?P<env>begin|end)\s*\{\s*(?P<envname>[a-zA-Z][a-zA-Z0-9@]*)\s*\}',
                                               r'\\(?P<macro>[a-zA-Z@][a-zA-Z0-9@:]*|[^\\:!])',
                                               #r'\\(?P<bkslash>\\)',
                                               # Special table macros (horrible hack!)
                                               r'\\(?P<tr>:)',
                                               r'\\(?P<td>!)',
                                               # General math stuff
                                               r'(?P<brace>[{}])',
                                               r'(?P<subsupgrp>[\^\_]{)',
                                               r'(?P<subsupc>[\^\_][^\\])',
                                               r'(?P<nbspace>~)',
                                               ]))
    textmodemacro_regex = re.compile('|'.join([r'\\(?P<env>begin|end)\s*\{\s*(?P<envname>[a-zA-Z][a-zA-Z0-9@]*)\s*\}',
                                               r'\\(?P<bkslash>\\)',
                                               # Special table macros (horrible hack!)
                                               r'\\(?P<tr>:)',
                                               r'\\(?P<td>!)',
                                               # A few special abbrewations
                                               r'(?P<longdash>---?)', 
                                               r'(?P<leftdquote>``)', 
                                               r"(?P<rightdquote>'')", 
                                               # General math stuff
                                               r'\\(?P<macro>[a-zA-Z][a-zA-Z0-9@]*|["~\'`^\\][a-zA-Z]|[^\\:!])',
                                               r'(?P<brace>[\{\}])',
                                               r'(?P<nbspace>~)']))
    def __init__(self,
                 manager,
                 parent,
                 macroDict, # dictionary of available macros
                 nodeDict, # dictionary of all known element names
                 attrs, # None or a dictionary of attributes
                 filename,
                 line):
        assert filename is not None
        self.pos = filename,line
        self.__manager = manager

        self.__sealed = False # disallow any more content
        self.__closed = False
        if attrs.has_key('macroexpand'):
            if attrs['macroexpand'].lower() == 'yes':
                self.macroMode = MacroMode.Text
            else:
                self.macroMode = MacroMode.NoExpand
        elif self.macroMode == MacroMode.InheritContent:
            print "NODE <%s> inherits content iterator from <%s>" % (self.nodeName,parent.nodeName)
            assert 0
            self.macroMode = parent.macroMode
            self.contIter = parent.contIter
        elif self.contIter is None:
            raise NodeError('Undefined contents iterator in %s' % self.nodeName)
        
        try:
            self.__citer = Iters.parsedef(self.contIter)()
        except Iters.SyntaxDefError,e:
            raise Iters.SyntaxDefError(unicode(e) + ' in %s' % self.nodeName)
        
        if self.macroMode == MacroMode.Inherit:
            self.macroMode = parent.macroMode

        if attrs.has_key('id'):
            manager.saveId(attrs['id'],self)
        if attrs.has_key('ref'):
            manager.refId(attrs['ref'],self)

        # __fakeopen: Counts the number of times newChild returned the same
        # node instead of a new one. This is used by <condition>: When newChild
        # receives a condition it will do one of two things: 
        #  - If the condition requirement is met, the content of the
        #    <condition> element isincluded directly in the node wherein
        #    <condition> appeared (i.e. the generated node tree will contain no
        #    node representing <condition>). This is achieved by returning the
        #    currently opened node and increasing __fakeopen by one. When the
        #    .endOfElement method is called it must mean thet either a
        #    </condition> or a </...> matching the opening tag was encountered:
        #    If __fakeopen is 0, we have hit a </...>, otherwise it must be a
        #    </condition> in which case we decrease __fakeopen by one.
        #  - If the condition requirement is not met, the content is ignored.
        #    In this case a Dummy node is returned and ignored (excluded from the
        #    generated node tree). 
        self.__fakeopen = 0

        self.__cmddict  = macroDict
        self.__id       = None
        self.__ns       = None
        self.__parent   = parent
        self.__nodeDict = nodeDict
        self.__attrs    = {}
        
        self.__attrs.update(self.acceptAttrs.defaultValues())
        if attrs is not  None:
            for k,v in attrs.items():
                if self.__attrs.has_key(k):
                    self.__attrs[k] = v
                elif k == 'xmlns':
                    pass
                else:
                    raise NodeError('Invalid attribute "%s" in <%s> at %s:%d' % (k,self.nodeName,filename,line))

        self.__content = DontAcceptNoneList([])
        self.__cstack  = [ ContentManager(self) ] # used for scopes opened by expanded macros
    
    def seal(self):
        self.__sealed = True
    def __iter__(self):
        return iter(self.__content)
    def __len__(self):
        return len(self.__content)
   
    ##\brief Append a new child, append it and return it. This is called by the
    #        SAX parser when an tag-open event occurs.
    # \note We create the node using the dictionary from _this_ Node, not from
    # the node that actually will contain it. We assume that the dictionary is
    # static so it's should be correct.

    def getMacroDefs(self):
        return self.__cmddict.items()
    def newChild(self,name,attrs,filename,line):
        assert filename is not None
        if name == 'sdocml:conditional':
            #print "sdocml:conditional @ %s:%d. cond = %s -> %s" % (filename,line,attrs['cond'],self.__manager.evalCond(attrs['cond'],filename,line))
            try:
                if attrs.has_key('cond') and attrs['cond'].strip() and self.__manager.evalCond(attrs['cond'],filename,line):
                    self.__fakeopen += 1
                    return self
                else:
                    node = DummyNode(name,self.__manager,self,self.__cmddict,self.__nodeDict,attrs,filename,line)
            except KeyError,e:
                raise NodeError('%s at %s:%d' % (e,filename,line))
        elif len(self.__cstack) > 1:
            cstack = self.__cstack
            def on_close():
                item = cstack.pop()
                debug('Onstack close %s' % item)
                if isinstance(item,LazyElement):
                    cstack[-1].append(item)
                else:
                    raise NodeError('Tag <%s> starting at %s:%d is not correctly closed' % (name,self.nodeName, filename,line))

            node = LazyElement(name,attrs,filename,line,on_close)
            self.__cstack.append(node)
        else:
            debug('Node.newChild: <%s>' % name)
            try:
                nodecon = self.__nodeDict[name]
            except KeyError:
                debug(self.__nodeDict)
                #print repr(self),self.__class__.__name__,self.nodeName
                raise NodeError('Unknown element <%s> in <%s> at %s:%d' % (name,self.nodeName, filename,line))
            cond = True
            if attrs.has_key('cond') and \
               attrs['cond'] is not None and \
               attrs['cond'].strip():
                cond = self.__manager.evalCond(attrs['cond'],filename,line)
            if cond:
                node = nodecon(self.__manager,self,self.__cmddict,self.__nodeDict,attrs,filename,line)
                debug('Node(%s).newChild : ' % self,node)
                self.__cstack[-1].append(node)
            else:
                node = DummyNode(name,self.__manager,self,self.__cmddict,self.__nodeDict,attrs,filename,line)
                debug("Ignored node %s" % node.nodeName) 

        return node

        

    ##\brief Append an item to the current inner-most scope.
    # \param item A Node or a Unicode string.
    def appendItem(self,item,filename,line):
        if not isinstance(item,Node) and not isinstance(item,unicode):
            #if isinstance(item,UnexpandedMacro):
            print repr(item)
            assert 0
            for i in item.expand():
                self.appendItem(i)
        else:
            try:
                if self.__citer(item):
                    self.append(item)
                else:
                    if isinstance(item,unicode):
                        raise NodeError('1Text not allowed in <%s> at %s:%d' % (self.nodeName,filename,line))
                    else: 
                        raise NodeError('Element <%s> not allowed in <%s> at %s:%d' % (item.nodeName,self.nodeName,filename,line))
            except Iters.ContentIteratorError:
                if isinstance(item,unicode):
                    raise NodeError('Does not accept text in <%s> at %s:%d' % (self.nodeName,filename,line))
                else:
                    raise NodeError('Does not accept <%s> in <%s> at %s:%d' % (item.nodeName,self.nodeName,filename,line))
                

    ##\brief Append an item to the root scope, and expand it if necessary.
    # 
    #   - If item is a Node or a string, the function will check that the Node or that text in general is allowed in the current context.
    #   - If item is an UnexpandedItem, it will be expanded and the resulting nodes and text will be appended using this function.
    # \param item A Node or a unicode string.
    def append(self,item):
        assert len(self.__cstack) == 1
        debug("Node.append :",repr(item))
        assert not self.__closed
        if   self.__sealed:
            raise NodeError("Content not allowed in <%s> at %s:%d" % (self.nodeName, self.pos[0],self.pos[1]))
        elif isinstance(item,Node) or isinstance(item,unicode):
            if isinstance(item,Node) and item.metaElement:
                pass # Allowed everywhere, ignored
            else:
                try:
                    if self.__citer(item):
                        self.__content.append(item)
                    else:
                        if isinstance(item,unicode):
                            filename,line = self.pos
                            raise NodeError('2Text not allowed in <%s> at %s:%d' % (self.nodeName,filename,line))
                        else: 
                            filename,line = item.pos
                            debug('In element <%s>' % self.nodeName)
                            raise NodeError('Element <%s> not allowed in <%s> at %s:%d' % (item.nodeName,self.nodeName,filename,line))
                except Iters.ContentIteratorError:
                    if isinstance(item,unicode):
                        filename,line = self.pos
                        raise NodeError('Does not accept text in <%s> at %s:%d' % (self.nodeName,filename,line))
                    else:
                        filename,line = item.pos
                        raise NodeError('Does not accept <%s> in <%s> at %s:%d' % (item.nodeName,self.nodeName,filename,line))
                except:
                    raise
        elif isinstance(item,UnexpandedItem):
            res = item.linearize([],[],{})
            debug('Node.append: handlig events',res)
            self.__handleSAXEvents(res,item.pos[0],item.pos[1])
        else:
            print item,repr(item)
            assert 0

    def __handleSAXEvents(self,events,filename,line):
        cstack = [ self ]
        #debug("EVENTS:\n",'\n'.join([repr(e) for e in events]))
        for e in events:
            if isinstance(e,MacroEvent_NoExpandText):
                cstack[-1].handleRawText(e.data,e.filename,e.line)
            elif isinstance(e,MacroEvent_ExpandText):
                #debug('Delayed SAX event: TEXT @ %s:%s' % (e.filename,e.line),e)
                cstack[-1].handleText(e.data,e.filename,e.line)
            elif isinstance(e,MacroEvent_StartTag):
                #debug('Delayed SAX event: TAGOPEN %s @ %s:%s:' % (e,e.filename,e.line),e)
                cstack.append(cstack[-1].newChild(e.name,e.attrs,e.filename,e.line))
            elif isinstance(e,MacroEvent_EndTag):
                if not (cstack and cstack[-1].nodeName == e.name):
                    debug('CStack =',cstack)
                    debug('Top name = %s' % cstack[-1].nodeName)
                    debug('End name = %s' % e.name)
                    debug('At %s:%d' % (filename,line))
                assert cstack and cstack[-1].nodeName == e.name
                cstack[-1].endOfElement(filename,line)
                cstack.pop()
            else:
                print e
                assert 0
                

    def handleRawText(self,data,filename,line):
        """
        Handle text without expansion.
        """
        if self.macroMode == MacroMode.Invalid:
            if data.strip():
                raise NodeError('3Text not allowed in <%s> at %s:%d' % (self.nodeName,filename,line))
            else:
                # Just ignore.
                pass
        else:
            self.appendItem(data,filename,line)

    def __handleText_Math(self,data,filename,line):
        pos = 0
        for o in self.mathmodemacro_regex.finditer(data):
            if (o.group('tr') or o.group('td')):
                if not self.allowTableSyntax:
                    continue

            if pos < o.start(0):
                self.__cstack[-1].append(data[pos:o.start(0)])
                debug('Added math data: ',data[pos:o.start(0)])
            pos = o.end(0)

            debug('Got math item: ',repr(o.group(0)))
            if   o.group('macro'):
                macroname = o.group('macro')
                try: macro = self.__cmddict[macroname]
                except KeyError: 
                    raise NodeError('Undefined macro "%s" at %s:%d' % (macroname,filename, line))

                if macro.nArgs() > 0:
                    def popMacro():
                        g = self.__cstack.pop()
                        assert self.__cstack
                        self.__cstack[-1].append(g)

                    self.__cstack.append(UnexpandedMacro(macro, (filename,line), popMacro))
                else:
                    self.__cstack[-1].append(UnexpandedMacro(macro, (filename,line)))

            elif o.group('brace'):
                if o.group('brace') == '{':
                    self.__cstack.append(ContentManager(BraceGroup(filename,line)))
                else: # '}'
                    if not isinstance(self.__cstack[-1],ContentManager) or not isinstance(self.__cstack[-1].Managed(),BraceGroup):
                        raise NodeError('Unmatched end-group } at %s:%d' % (filename,line))
                    g = self.__cstack.pop()
                    g.flush()
                    assert self.__cstack
                    self.__cstack[-1].append(g.Managed())
            elif o.group('subsupgrp'):
                op = o.group('subsupgrp')
                if op == '_{':
                    g = SubBraceGroup(filename,line)
                else:
                    g = SuperBraceGroup(filename,line)
                self.__cstack.append(ContentManager(g))
            elif o.group('subsupc'):
                op = o.group('subsupc')[0]
                c  = o.group('subsupc')[1]

                if op == '_':
                    g = SubBraceGroup(filename,line)
                else:
                    g = SuperBraceGroup(filename,line)

                g.append(c) 
                g.end()
                self.__cstack[-1].append(g)

            elif o.group('tr'):
                # if special table syntax is used, this must be used
                # for _all_ rows and cells. This means that table
                # syntax elements must appear _only_ at the top-level
                # of a table and not be preceded by anything.
              
                if   len(self.__cstack) == 1: # we are at top-level, must be the first row.
                    self.__cstack.append(ContentManager(LazyTableRow(self.tablerowelement,filename,line)))
                    self.__cstack.append(ContentManager(LazyTableCell(self.tablecellelement,filename,line)))
                elif len(self.__cstack) == 3 and \
                     isinstance(self.__cstack[-1],ContentManager):
                    topcell = self.__cstack[-1].Managed()
                    if isinstance(topcell,LazyTableCell):
                        # end the current cell
                        item = self.__cstack.pop()
                        item.flush()
                        self.__cstack[-1].append(item.Managed())
                        # Then end the current row
                        top = self.__cstack[-1]
                        if isinstance(top,ContentManager) and \
                           isinstance(top.Managed(), LazyTableRow):
                            item = self.__cstack.pop()
                            item.flush()
                            self.__cstack[-1].append(item.Managed())
                            # Finally start a new row and a new cell 
                            self.__cstack.append(ContentManager(LazyTableRow(self.tablerowelement,filename,line)))
                            self.__cstack.append(ContentManager(LazyTableCell(self.tablecellelement,filename,line)))
                        else:
                            raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                    else:
                        raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                else:
                    raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
            elif o.group('td'):
                if len(self.__cstack) == 3 and \
                     isinstance(self.__cstack[-1],ContentManager):
                    topcell = self.__cstack[-1].Managed()
                    if isinstance(topcell,LazyTableCell):
                        # end the current cell
                        item = self.__cstack.pop()
                        item.flush()
                        self.__cstack[-1].append(item.Managed())
                        self.__cstack.append(ContentManager(LazyTableCell(self.tablecellelement,filename,line)))
                    else:
                        print "len cstack:",len(self.__cstack)
                        print 'cstack top:',self.__cstack[-1]
                        print 'topcell:',topcell
                        raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                else:
                    print "len cstack:",len(self.__cstack)
                    print 'cstack top:',self.__cstack[-1]
                    raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
            elif o.group('env'):
                macroname = o.group('envname')
                try: macro = self.__cmddict[macroname]
                except KeyError: 
                    raise NodeError('Undefined environment "%s" at %s:%d' % (macroname,filename, line))
                if not isinstance(macro,DefEnvNode):
                    raise NodeError('Tried to use "%s" as environment at %s:%d' % (macroname,filename, line))

                if o.group('env') == 'begin' :
                    self.__cstack.append(UnexpandedEnvironment(macro, (filename,line)))
                else: # o.group('env') == 'end'
                    top = self.__cstack.pop() 
                    if not isinstance(top,UnexpandedEnvironment):
                        raise NodeError('Unmatched %s at %s:%d' % (o.group(0),filename, line))
                    elif top.envName() != macroname:
                        raise NodeError('Unmatched %s at %s:%d' % (o.group(0),filename, line))
                    else:
                        top.end()
                        self.__cstack[-1].append(top)
            elif o.group('nbspace'):
                self.__cstack[-1].append(u'\u00a0') # &nbsp;
            else:
                print "GOT: ",o.group(0)
                assert 0
        if pos < len(data):
            self.__cstack[-1].append(data[pos:])
            debug('Added math data: ',data[pos:])


    ##\brief Handle text. Called by the SAX parser to pass a text string.
    #  
    # This function handles expansion of macros in both text and math mode (and no-expand mode).
    def handleText(self,data,filename,line):
        debug('\tNode.handleText @ %s:%d (%s): ' % (filename,line,MacroMode.toStr(self.macroMode)), repr(data))
        if  self.macroMode in [ MacroMode.Invalid, MacroMode.NoExpand ]:
            self.handleRawText(data,filename,line)
        elif self.macroMode == MacroMode.Text:
            pos = 0
            for o in self.textmodemacro_regex.finditer(data):
                if (o.group('tr') or o.group('td')):
                    if not self.allowTableSyntax:
                        assert 0
                        continue
                if pos < o.start(0):
                    debug('Node.handleText (remaining) append :',repr(data[pos:o.start(0)]))
                    debug('  Top element :',repr(self.__cstack[-1]))
                    self.__cstack[-1].append(data[pos:o.start(0)])
                pos = o.end(0)

                if   o.group('longdash') is not None:
                    if o.group('longdash') == '--':
                        self.__cstack[-1].append(u'\u2013') # &ndash;
                    else:
                        self.__cstack[-1].append(u'\u2014') # &ndash;
                elif o.group('leftdquote') is not None:
                    self.__cstack[-1].append(u'\u201c') # &ldquote
                elif o.group('rightdquote') is not None:
                    self.__cstack[-1].append(u'\u201d') # &rdquote
                elif o.group('bkslash'):
                    self.__cstack[-1].append(u'\\')
                elif o.group('tr'):
                    # if special table syntax is used, this must be used
                    # for _all_ rows and cells. This means that table
                    # syntax elements must appear _only_ at the top-level
                    # of a table and not be preceded by anything.
                  
                    if   len(self.__cstack) == 1: # we are at top-level, must be the first row.
                        self.__cstack.append(ContentManager(LazyTableRow(self.tablerowelement,filename,line)))
                        self.__cstack.append(ContentManager(LazyTableCell(self.tablecellelement,filename,line)))
                    elif len(self.__cstack) == 3 and \
                         isinstance(self.__cstack[-1],ContentManager):
                        topcell = self.__cstack[-1].Managed()
                        if isinstance(topcell,LazyTableCell):
                            # end the current cell
                            item = self.__cstack.pop()
                            item.flush()
                            self.__cstack[-1].append(item.Managed())
                            # Then end the current row
                            top = self.__cstack[-1]
                            if isinstance(top,ContentManager) and \
                               isinstance(top.Managed(), LazyTableRow):
                                item = self.__cstack.pop()
                                item.flush()
                                self.__cstack[-1].append(item.Managed())
                                # Finally start a new row and a new cell 
                                self.__cstack.append(ContentManager(LazyTableRow(self.tablerowelement,filename,line)))
                                self.__cstack.append(ContentManager(LazyTableCell(self.tablecellelement,filename,line)))
                            else:
                                raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                        else:
                            raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                    else:
                        raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                elif o.group('td'):
                    if len(self.__cstack) == 3 and \
                         isinstance(self.__cstack[-1],ContentManager):
                        topcell = self.__cstack[-1].Managed()
                        if isinstance(topcell,LazyTableCell):
                            # end the current cell
                            item = self.__cstack.pop()
                            item.flush()
                            self.__cstack[-1].append(item.Managed())
                            self.__cstack.append(ContentManager(LazyTableCell(self.tablecellelement,filename,line)))
                        else:
                            raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                    else:
                        raise NodeError('Table syntax not allowed at %s:%d' % self.pos)
                elif o.group('macro'):
                    macroname = o.group('macro')
                    try: macro = self.__cmddict[macroname]
                    except KeyError: 
                        print "Match = %s" % o.group(0)
                        print "Text = '%s'" % data[o.start(0):o.start(0)+20]
                        print "Data size = %d" % len(data)
                        print "data =\n",data
                        raise NodeError('Undefined macro "%s" at %s:%d' % (macroname,filename, line))
                    if not isinstance(macro,DefNode):
                        raise NodeError('Tried to use "%s" as macro at %s:%d' % (macroname,filename, line))
                    if macro.nArgs() > 0:
                        def popMacro():
                            g = self.__cstack.pop()
                            assert self.__cstack
                            assert isinstance(g,UnexpandedMacro)
                            self.__cstack[-1].append(g)

                        self.__cstack.append(UnexpandedMacro(macro, (filename,line), popMacro))
                    else:
                        self.__cstack[-1].append(UnexpandedMacro(macro, (filename,line)))

                elif o.group('brace'):
                    if o.group('brace') == '{':
                        self.__cstack.append(ContentManager(BraceGroup(filename,line)))
                    else: # '}'
                        if not isinstance(self.__cstack[-1],ContentManager) or not isinstance(self.__cstack[-1].Managed(),BraceGroup):
                            raise NodeError('Unmatched end-group } at %s:%d' % (filename,line))
                        g = self.__cstack.pop()
                        g.flush()
                        assert self.__cstack
                        #debug("Popped brace group from cstack. Adding to:",self.__cstack[-1])
                        #debug('  Group =',g.Managed())
                        self.__cstack[-1].append(g.Managed())
                elif o.group('env'):
                    macroname = o.group('envname')
                    try: macro = self.__cmddict[macroname]
                    except KeyError: 
                        raise NodeError('Undefined environment "%s" at %s:%d' % (macroname,filename, line))
                    if not isinstance(macro,DefEnvNode):
                        raise NodeError('Tried to use "%s" as environment at %s:%d' % (macroname,filename, line))

                    if o.group('env') == 'begin' :
                        self.__cstack.append(UnexpandedEnvironment(macro, (filename,line)))
                    else: # o.group('env') == 'end'
                        top = self.__cstack.pop() 
                        if not isinstance(top,UnexpandedEnvironment):
                            raise NodeError('Unmatched %s at %s:%d' % (o.group(0),filename, line))
                        elif top.envName() != macroname:
                            raise NodeError('Unmatched %s at %s:%d' % (o.group(0),filename, line))
                        else:
                            top.end()
                            self.__cstack[-1].append(top)
                elif o.group('nbspace'):
                    self.__cstack[-1].append(u'\xa0') # &nbsp;
                else:
                    print "ERROR: got '%s'" % o.group(0)
                    assert 0
            if pos < len(data):
                debug('Node.handleText (remaining) append :',repr(data[pos:]))
                self.__cstack[-1].append(data[pos:])
        elif self.macroMode in [ MacroMode.Math, MacroMode.SimpleMath ]:
            self.__handleText_Math(data,filename,line)

    def getID(self):
        return self.__id
    def getNS(self):
        return self.__ns

    def hasAttr(self,key):
        return self.__attrs.has_key(key) and self.__attrs[key] is not None
    def getAttr(self,key):
        return self.__attrs[key]

    def setXMLattrs(self,node):
        for k,v in self.__attrs.items():
            if v is not None:
                node.setAttribute(k,v)
    def end(self,filename,line):
        pass

    def endOfElement(self,filename,line):
        """
        Called at the end of the scope.
        """
        if not self.__closed:
            if self.__fakeopen > 0:
                self.__fakeopen -= 1
            else:
                if len(self.__cstack) == 3 and\
                   isinstance(self.__cstack[-1],ContentManager) and \
                   isinstance(self.__cstack[-1].Managed(),LazyTableCell):
                   item = self.__cstack.pop()
                   item.flush()
                   self.__cstack[-1].append(item.Managed())
                   
                   item = self.__cstack.pop()
                   item.flush()
                   self.__cstack[-1].append(item.Managed())

                maybeid = '[no]'
                if self.hasAttr ('id'):
                    maybeid = self.getAttr('id')

                debug('#### Close node <%s id="%s"> %d' % (self.nodeName,maybeid,id(self)))
                if 0:
                    import traceback
                    traceback.print_stack()
                
                if len(self.__cstack) != 1:
                    debug('SCOPE STACK:',self.__cstack)
                    raise NodeError('Unended scope or macro at %s:%d' % (filename,line))
                elif isinstance(self.__cstack[-1],ContentManager):
                    self.__cstack[-1].flush()
                    self.__cstack.pop()
                self.__closed = True

                self.end(filename,line)

    def paragraphifyXML(self,lst,doc,node):
        # generate paragraphs 
        pars = []
        par = []

        def cleanpar(p):
            while p and p[0].nodeType == p[0].TEXT_NODE and not p[0].data.strip(): p.pop(0)
            while p and p[-1].nodeType == p[-1].TEXT_NODE and not p[-1].data.strip(): p.pop()
            return p
          
        prevWasNode = False
        for item in lst:
            if isinstance(item,Node):
                n = item.toXML(doc)
                if n is not None:
                    if item.paragraphElement:
                        par = cleanpar(par)
                        if par:
                            pars.append(par)
                        par = []
                        pars.append(n)
                        prevWasNode = False
                    else:
                        par.append(n)
                        prevWasNode = True
            else:
                lines = ''.join(item).split('\n')
                for l in lines[:-1]: 
                    if l.strip():
                        par.append(doc.createTextNode(re.sub(r'\s+',' ',l)))
                        prevWasNode = False
                    elif par and not prevWasNode: # blank line not at the beginning of a paragraph starts a new paragraph
                        prevWasNode = False
                        par = cleanpar(par)
                        if par:
                          pars.append(par)
                        par = []
                if lines:
                    l = lines[-1] 
                    if l.strip():
                        par.append(doc.createTextNode(re.sub(r'\s+',' ',l)))
                    else:
                        par.append(doc.createTextNode(' '))
        par = cleanpar(par)
        if par:
            pars.append(par)

        for p in pars:
            if not isinstance(p,list):
                node.appendChild(p)
            else:
                par = doc.createElement('p')
                node.appendChild(par)
                for item in p:
                    par.appendChild(item)
        
    def toXML(self,doc,node=None):
        '''
        Convert the node to XML. Return either the generated node or None.
        '''
        if self.expandElement:
            if node is None:
                node = doc.createElement(self.nodeName)

            if self.structuralElement or self.mathElement:
                for item in self:
                    if isinstance(item,unicode):
                        node.appendChild(doc.createTextNode(item))
                    else:
                        n = item.toXML(doc)
                        if n is not None:
                            node.appendChild(n)
            else:
                lst = []
                for item in self:
                    if isinstance(item,unicode):
                        if not lst or isinstance(lst[-1],Node):
                            lst.append([item])
                        else:
                            lst[-1].append(item)
                    else:
                        lst.append(item)
                if self.paragraphElement:
                    # generate paragraphs 
                    self.paragraphifyXML(lst,doc,node)
                else: # not paragraph element. Eliminate all newlines.
                    for item in lst:
                        if not isinstance(item,list):
                            n = item.toXML(doc)
                            if n is not None:
                                node.appendChild(n)
                        else:
                            text = re.sub(r'\s+',' ',''.join(item))
                            node.appendChild(doc.createTextNode(text))

            for k,v in self.__attrs.items():
                if v is not None and k not in [ 'cond','macroexpand' ]:
                    node.setAttribute(k,v)
            if self.traceInfo:
                assert self.pos[0] is not None
                assert self.pos[1] is not None
                node.setAttribute("xmlns:trace","http://odense.mosek.com/emotek.dtd")
                node.setAttribute('trace:file',str(self.pos[0]))
                node.setAttribute('trace:line',str(self.pos[1]))
            return node

    def __str__(self):
        if self.hasAttr('id'):
            return '<%s id="%s">' % (self.nodeName,self.getAttr('id') )
        else:
            return "<%s>" % self.nodeName

    __repr__ = __str__

class _MathNode(Node):
    macroMode = MacroMode.Math
    contIter = ' [ T %s ]* ' % _mathNodes
    mathElement = True
  
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__cmddict  = cmddict
        self.__nodeDict = nodeDict
        self.__manager  = manager
        self.__filename = filename
        self.__line     = line


class NullNode(Node):
    def __init__(self,
                 name,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
    def newChild(self,name,attrs,filename,line):
        return DummyNode(name,self.__manager,self,self.__cmddict,self.__nodeDict,attrs,filename,line)
    def handleText(self,data,filename,line):
        pass
    def endOfElement(self,filename,line):
        pass
        

class DummyNode:
    nodeName = '*dummy*'
    def __init__(self,
                 name,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        self.nodeName = name
        self.__manager  = manager
        self.__parent   = parent
        self.__cmddict  = cmddict
        self.__nodeDict = nodeDict
        self.__filename = filename
        self.__line     = line
    def newChild(self,name,attrs,filename,line):
        return DummyNode(name,self.__manager,self,self.__cmddict,self.__nodeDict,attrs,filename,line)
    def handleText(self,data,filename,line):
        pass
    def handleRawText(self,data,filename,line):
        pass
    def endOfElement(self,filename,line):
        pass


######################################################################
#  Document node classes
######################################################################
class DescriptionNode(Node):
    comment  = 'A human readable text description.'
    nodeName = 'desc'
    macroMode   = MacroMode.NoExpand
    contIter = ' T '



class DictEntryNode(Node):
    comment  = '''
                 The \\tagref{dictentry} element can be used in the
                 \\tagref{defines} section to define a dictionary entry. A
                 dictionary entry is simply a string value mapping to another
                 string value much the same way as a macro is. 
                 
                 The key can be any string, containing spaces or non-ASCII
                 chars. The value is the content of the element.
                 
                 \\tagref{dictentry} mappings have the same scope as macros,
                 i.e. the current section and all child sections until
                 overridden. Redefining an entry is valid, and has the same
                 meaning as redefining a macro.
                 
                 A mapping created with \\tagref{dictentry} can be fetched with
                 a \\tagref{lookup}.
               '''
    nodeName = 'dictentry'
    metaElement = True
    acceptAttrs = Attrs([Attr('key',required=True,descr="The key under which the text is saved."),
                         Attr('cond')])
    macroMode   = MacroMode.NoExpand
    contIter = ' T '
    structuralElement = True

    def __init__(self, manager, parent, cmddict, nodeDict, attrs, filename, line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__cmddict = cmddict
    def end(self,filename,line):
        key = self.getAttr('key')
        self.value = u''.join(self)
        self.__cmddict.dictSet(key,self)

        
    

class IncDefNode(Node):
    comment     = '''
                    Include an external file containing macro definitions. This
                    file must be a valid XML file having the TeXML
                    \\tagref{defines} as the document element.
                  '''
    nodeName    = 'incdef'
    acceptAttrs = Attrs([Attr('url',descr='The address of the definition file to incude.'),
                         Attr('type',default='text/xml-defines'), 
                         Attr('cond')])
    contIter    = ''
    structuralElement = True
    
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__cmddict = cmddict

        #self.__url = urlparse.urlparse(attrs['url'])
        self.__url = attrs['url']

        fullname = manager.findFile(self.__url,filename)
        if 0:
            proto,server,path,r0,r1,r2 = self.__url
            if proto and proto != 'file':
                log(self.__url)
                raise NodeError('Only local includes allowed, got "%s"' % attrs['url'])

            basepath = os.path.dirname(filename)
            fullname = os.path.join(basepath,path) # currently only relative paths allowed. No checking done

        P = xml.sax.make_parser()
        N = ExternalDefineRoot(manager,self,self.__cmddict,nodeDict,fullname,1)
        h = handler(fullname,N) 
        P.setContentHandler(h)
        P.setEntityResolver(manager.getEntityResolver())

        try:
            msg("Parse external definitions %s (%s)" % (self.__url,fullname))
            P.parse(fullname)
        except Exception,e:
            import traceback
            traceback.print_exc()
            raise NodeError('Failed to parse file "%s" included at %s:%d' % (fullname,self.pos[0],self.pos[1]))

class DefElementNode(Node):
    comment     = """
                    This node denotes a specific element in a macro definition. The content of the 
                    tag will end up as the content of the expanded tag in the expanded macro.

                    Examples:
                    <ilist>
                        <li><tt>\\emptytaga{e}{n="texttt"}</tt> will be expanded to <tt>\\emptytag{texttt}</tt></li>
                        <li><tt>\\taga{e}{n="texttt"}ABC\\endtag{e}</tt> will be expanded to <tt>\\tag{texttt}ABC\\endtag{texttt}</tt></li>
                        <li><tt>\\taga{e}{n="texttt"}\\taga{attr}{n="class"}myclass\\endtag{attr}ABC\\endtag{e}</tt> will be expanded to <tt>\\taga{texttt}{class="myclass"}ABC\\endtag{texttt}</tt></li>
                    </ilist>
                  """

    nodeName    = 'e'
    acceptAttrs = Attrs([ Attr('n',descr='The name of the element')])
    macroMode   = MacroMode.Invalid
    contIter    = ' <attr>* [ <e> <d> <c> <lookup> ]*'
    structuralElement = True
    
    def linearize(self,res,args,kwds,filename,line,dolookup):
        attrs = {}
        content = []
        for i in self:
            if isinstance(i,DefElementAttrNode):
                r = i.linearize([],args,kwds,filename,line,dolookup)
                try:
                    attrs[i.getName()] = ''.join([ d.data for d in r ])
                except:
                    print r
                    raise

            else:
                content.append(i)

        elmname = self.getAttr('n')
        res.append(MacroEvent_StartTag(elmname, attrs,filename,line ))
        for i in content:
            i.linearize(res,args,kwds,filename,line,dolookup)
        res.append(MacroEvent_EndTag(elmname,filename,line))
    
    def __repr__(self):
        return '<e n="%s"><\e>' % (self.getAttr('n'))

    

    
class _DefDataNode(Node):
    macroMode   = MacroMode.NoExpand
    contIter    = ' [ T <lookup> ]* '

    argre = re.compile(r'{{(?:([0-9]+)|(BODY|SUBSCRIPT|SUPERSCRIPT))}}')
    structuralElement = True

    def linearize(self,res,args,kwds,filename,line,dolookup):
        debug("%s: %s" % (self.__class__.__name__,repr([repr(s) for s in self])))
        for data in self:
            if isinstance(data,LookupNode):
                data.linearize(res,args,kwds,filename,line,dolookup)
            else:
                pos = 0
                for o in self.argre.finditer(data):
                    if pos < o.start(0):
                        res.append(MacroEvent_NoExpandText(data[pos:o.start(0)],filename,line))
                    pos = o.end(0)

                    try:
                        if o.group(1) is not None:
                            res.extend(args[int(o.group(1))])
                        else:
                            k = o.group(2)
                            if kwds.has_key(k):
                                res.extend(kwds[k])
                    except IndexError:
                        raise MacroArgErrorX('Tried to refer to non-existant macro argument %s' % o.group(1))
                if pos < len(data):
                    res.append(MacroEvent_NoExpandText(data[pos:],filename,line))
        return res

class DefDataNode(_DefDataNode):
    comment     = '''
                    Text entry in a macro definition. The content is pure text,
                    but the placeholders {{n}} where "n" is a number, and
                    {{BODY}} are expanded to the corresponding argument and the
                    environment content (for \\tagref{defenv} only).
                  '''
    nodeName    = 'd'

class LookupNode(_DefDataNode):
    comment =   '''
                    The \\tag{lookup} looks up the dictionary entry made with \\tagref{dictentry}.
                '''

    examples = [("Define a macro performing lookup of the key ``XYZ'':",
                 '<def m="lookupXYZ"><d>The Value of XYZ is "<lookup>XYZ</lookup>"</d></def>'),
                ("Define a macro performing lookup of a key given as a macro argument:",
                 '<def m="lookup" n="1"><lookup>{{0}}</lookup></def>')]
    nodeName = 'lookup'
    acceptAttrs = Attrs([Attr('cond')])
    macroMode   = MacroMode.NoExpand
    contIter    = ' T '
   
    def __init__(self, manager, parent, cmddict, nodeDict, attrs, filename, line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__cmddict = cmddict
    def linearize(self,res,args,kwds,filename,line,dolookup):
        r = []
        _DefDataNode.linearize(self,r,args,kwds,filename,line,dolookup)
        for i in r:
            if not isinstance(i,MacroEvent_NoExpandText):
                raiseMacroArgError('Invalid use of <lookup> at %s:%d' % (filename,line))

        if dolookup:
            key = ''.join([ i.data for i in r ])
            try:
                node = self.__cmddict.dictLookup(key)
                res.append(MacroEvent_NoExpandText(node.value,filename,line))
            except KeyError:
                raise KeyError('Undefined dictionary entry "%s" at %s:%d' % (key,filename,line))
        else:
            res.append(MacroEvent_NoExpandText('{{DICT[',filename,line))
            res.extend(r)
            res.append(MacroEvent_NoExpandText(']}}',filename,line))
        return res

class DefElementAttrNode(_DefDataNode):
    comment     = """
                  Defines an attribute value for an element specification in a macro.
                  The content must be pure text, and the placeholders "{{0}}", "{{1}}"...  
                  can be used to refer to arguments 0, 1, ...
                  """
    nodeName    = 'attr'
    acceptAttrs = Attrs([Attr('n',descr='Name of the attribute.')])
    macroMode   = MacroMode.NoExpand
#    contIter    = ' T '

#    argre = re.compile(r'{{([0-9]+)}}')
    
    def getName(self):
        return self.getAttr('n')

    @staticmethod
    def __checkarg(arg):
        for i in arg:
            if not isinstance(i,MacroEvent_NoExpandText):
                print "Invalid item: %s" % repr(i)
                raise MacroArgError('Elements are not allowed in attributes')
    
    
#    def linearize(self,res,args,filename,line):
#        r = res
#        for data in self:
#            pos = 0
#            for o in self.argre.finditer(data):
#                if pos < o.start(0):
#                    r.append(MacroEvent_NoExpandText(data[pos:o.start(0)],filename,line))
#                pos = o.end(0)
#
#                argidx = int(o.group(1))
#                self.__checkarg(args[argidx])
#                r.extend(args[argidx])
#            if pos < len(data):
#                r.append(MacroEvent_NoExpandText(data[pos:],filename,line))
#        return r


class DefMacroRefNode(Node):
    comment     = """
                  This can be used inside a macro definition to refer to a
                  previously defined macro.

                  Note that the macro referred must be defined: For example,
                  suppose that a macro \\tt{\\\\one}, refers to another macro
                  \\tt{\\\\two}. When \\tt{\\\\one} is expanded, it will expand
                  \\tt{\\\\two} as it was defined at the point where
                  \\tt{\\\\one} was defined.
                  """
    nodeName    = 'c'
    acceptAttrs = Attrs([ Attr('n',descr='Name of the macro (without preceding backslash) that is referred.')])
    macroMode   = MacroMode.NoExpand
    contIter    = ' <arg>* '
    structuralElement = True

    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__macro = cmddict[self.getAttr('n')]
    
    def linearize(self,res,args,kwds,filename,line,dolookup):    
        largs = []
        for i in self:
            largs.append(i.linearize([],args,kwds,filename,line,dolookup))
        self.__macro.linearize(res,largs,filename,line,dolookup)
        debug("DefMacroRefNode: ", repr(res))
        return res
        

class DefMacroArgNode(Node):
    comment     = "Defines an argument for a macro reference."
    nodeName    = 'arg'
    macroMode   = MacroMode.NoExpand
    contIter    = ' [ <d> <e> <c> <lookup> ]* '
    structuralElement = True

    def linearize(self,res,args,kwds,filename,line,dolookup):
        for i in self:
            i.linearize(res,args,kwds,filename,line,dolookup)
        return res

class DefNode(Node):
    comment     = """
                  Define a new macro.

                  The placeholders "\\{\\{0\\}\\}", "\\{\\{1\\}\\}"... can be used in the body of the macro to
                  refer to argument 0, 1...
                  
                  In math mode subscript and superscript can be referred to
                  using "\\{\\{SUBSCRIPT\\}\\}" and "\\{\\{SUBSCRIPT\\}\\}".
                  """
    nodeName    = 'def'
    acceptAttrs = Attrs([Attr('m',descr="Name of the macro."),
                         Attr('n',default='0', descr='Number of arguments required by the macro.'),
                         Attr('subscript-arg',   default='no', descr='(yes|no) The macro accepts subscript. Only relevant in math mode.'),
                         Attr('superscript-arg', default='no', descr='(yes|no) The macro accepts superscript. Only relevant in math mode.'),
                         Attr('cond')])
    macroMode   = MacroMode.Invalid
    contIter    = ' <desc>? [ <d> <e> <c> <lookup>]* '
    structuralElement = True

    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__cmddict = cmddict
        self.__name = attrs['m']
        self.__accept_subscr = attrs.has_key('subscript-arg')   and attrs['subscript-arg'].lower()   == 'yes'
        self.__accept_supscr = attrs.has_key('superscript-arg') and attrs['superscript-arg'].lower() == 'yes'
        self.__descr = None
    
    def acceptsSubscript(self):
        return self.__accept_subscr
    def acceptsSuperscript(self):
        return self.__accept_supscr

    def getDescr(self):
        return self.__descr and ''.join(self.__descr)

    def macroName(self):
        return self.getAttr('m')

    def linearize(self,res,args,kwds,filename,line,dolookup=True):
        for i in self:
            if not isinstance(i,DescriptionNode):
                i.linearize(res,args,kwds,filename,line,dolookup)
        return res

    def docExpandMacro(self):
        events = self.linearize([],[ [MacroEvent_NoExpandText('{{%d}}' % i,'??',0) ] for i in range(self.nArgs()) ],{},'??',0,False)
        r = []
        for e in events:
            if isinstance(e,MacroEvent_Text):
                r.append(escape(e.data))
            elif isinstance(e,MacroEvent_StartTag):
                if e.attrs:
                    attrstr = ' ' + ' '.join([ '%s="%s"' % item for item in e.attrs.items() ])
                else:
                    attrstr = ''
                r.append('<%s%s>' % (e.name,attrstr))
            elif isinstance(e,MacroEvent_EndTag):
                r.append('</%s>' % e.name)
            else:
                print repr(e)
                assert 0
        return ''.join(r)
 
    def nArgs(self):
        return int(self.getAttr('n'))

    def end(self,filename,line):
        try:
            self.__cmddict[self.__name] = self
        except KeyError:
            m = self.__cmddict[self.__name]
            raise MacroError('Macro "\\%s" at %s:%d  already defined at %s:%d' % (self.__name,filename,line,m.pos[0],m.pos[1]))
        for d in self:
            if isinstance(d,DescriptionNode):
                self.__descr = d

    def __repr__(self):
        return 'macro(%s)' % self.__name
    def __str__(self):
        return 'macro(%s)' % self.__name

class DefEnvNode(Node):
    comment = """
    The defenv element defines an element that n requires arguments and contains a body text.
    In the body of the definition the placeholders "{{0}}", "{{1}}" ... refer to argument 0, 1 etc, and
    "{{BODY}}" refers to the content of the environment.

    For example:
    <pre>
\\begin{myenv}{HELLO!}
blabla
\\end{myenv}
    </pre>
    Will pass "HELLO!" as argument 0 and "... blabla ..." as BODY to the macro expansion.
    """
    examples    = [ ('Define a list which expands to an \\tagref{ilist} with the attribute class="my:list":', 
                     '''
<defenv m="mylist" n="1"><e n="ilist"><attr n="class">{{0}}</attr><d>{{BODY}}</d></e></defenv>

\\begin{mylist}{my:list}
  <li> Item1 </li>
  <li> Item2 </li>
\\end{mylist}
->
    <ilist class="my:list">
        <li> Item1 </li>
        <li> Item2 </li>
    </ilist>
''')
                  ]
    nodeName    = 'defenv'
    acceptAttrs = Attrs([Attr('m',descr='Name of the environment.'),
                         Attr('n',default='0',descr='Number of arguments required by the environment.')]) 
    macroMode   = MacroMode.Invalid
    contIter    = ' <desc>? [ <d> <e> <c> <lookup> ]* '
    structuralElement = True

    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__cmddict = cmddict
        self.__name = attrs['m']

        self.__descr = None

    def getDescr(self):
        return self.__descr and ''.join(self.__descr)

    def macroName(self):
        return self.getAttr('m')

    def linearize(self,res,args,kwds,filename,line,dolookup=True):
        for i in self:
            if not isinstance(i,DescriptionNode):
                i.linearize(res,args,kwds,filename,line,dolookup)
        return res

    def docExpandMacro(self):
        args = [ [MacroEvent_NoExpandText(u'{{%d}}' % i,'??',0) ] for i in range(self.nArgs()) ]
        kwds = { 'BODY' : [MacroEvent_NoExpandText(u'{{BODY}}','??',0)] }
        events = self.linearize([],args,kwds,'??',0,False)
        r = []
        for e in events:
            if isinstance(e,MacroEvent_Text):
                r.append(escape(e.data))
            elif isinstance(e,MacroEvent_StartTag):
                if e.attrs:
                    attrstr = ' ' + ' '.join([ '%s="%s"' % item for item in e.attrs.items() ])
                else:
                    attrstr = ''
                r.append('<%s%s>' % (e.name,attrstr))
            elif isinstance(e,MacroEvent_EndTag):
                r.append('</%s>' % e.name)
            elif isinstance(e,unicode):
                r.append(escape(e))
            else:
                print e
                assert 0
        return ''.join(r)

    def nArgs(self):
        return int(self.getAttr('n'))

    def end(self,filename,line):
        try:
            self.__cmddict[self.__name] = self
        except KeyError:
            m = self.__cmddict[self.__name]
            raise MacroError('Macro "\\%s" at %s:%d  already defined at %s:%d' % (self.__name,filename,line,m.pos[0],m.pos[1]))
        for d in self:
            if isinstance(d,DescriptionNode):
                self.__descr = d

    def __repr__(self):
        return 'macro(%s)' % self.__name
    def __str__(self):
        return 'macro(%s)' % self.__name

class DefinesNode(Node):
    comment     = '''
                    Contains definitions of macros and environments that will
                    be available in the current section and all descendants.            
                  '''
    nodeName    = 'defines'
    contIter    = ' [ <def> <incdef> <defenv> <dictentry> ]* '
    
    macronamere = re.compile(r'[a-zA-Z][a-zA-Z0-9@]*|.[a-zA-Z]$')
    expandElement = False
    structuralElement = True
        
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__cmddict = cmddict
    def end(self,file,line):
        pass


def SectionNode(manager,parent,cmddict,nodedict,attrs,filename,line):
    if attrs.has_key('url'):
        url = urlparse.urlparse(attrs['url'])
        fullpath = manager.findFile(attrs['url'],filename)

        P = xml.sax.make_parser()
        N = ExternalSectionRoot(manager,parent, cmddict,nodedict,attrs,filename,line)
        h = handler(fullpath,N) 
        P.setContentHandler(h)
        P.setEntityResolver(manager.getEntityResolver())
      
        if 1: # try:
            msg("Parse external section %s (%s)" % (attrs['url'],fullpath))
            P.parse(fullpath)
        else: # except Exception,e:
            import traceback
            traceback.print_exc()
            raise NodeError('Failed to parse file "%s" included at %s:%d' % (path,filename,line))

        return N.documentElement
    else:
        return _SectionNode(manager,parent,cmddict,nodedict,attrs,filename,line) 

class _SectionBaseElement(Node):
  # Base class for all elements that may produce a section
  pass

class BibliographyNode(_SectionBaseElement):
    comment     = '''
                    Defines the bibliography section.

                    This is either built automatically from an external bibliography database or explicitly written.

                    If an external URL is <em>not</em> given, the section will
                    be rendered containing ALL entries listed, ordered as they
                    appear.
                    If an external URL <em>is</em> given, the content of the
                    section is ignored, and a list of bibliography entries is
                    automatically generated from the database.
                  '''
    traceInfo   = True
    nodeName    = 'bibliography'
    macroMode   = MacroMode.Invalid
    acceptAttrs = Attrs([Attr('id'), 
                         Attr('url',descr='Adderess of the external bibliography database to use.'),
                         #Attr('xmlns:bib',default="http://bibtexml.sf.net/",descr="For convenience, define namespace of BibTeXML."),
                         Attr('cond')])
    #contIter    = ' <head>  <bibitem> * '
    contIter    = ' <bibitem> * '

    def __init__(self, manager, parent, cmddict, nodeDict, attrs, filename, line):
        _SectionBaseElement.__init__(self,manager,parent,CommandDict(cmddict),nodeDict,attrs,filename,line)
        self.__bibdb = None
        self.__cmddict = cmddict
        self.__nodedict = nodeDict
        self.__manager = manager

        if self.hasAttr('url'):
            biburl = manager.findFile(self.getAttr('url'),filename)
            self.__bibdb = BibDB(biburl)
        else:
            self.__bibdb = None
        
        self.__genitems = []
        self.__pp = False # postprocessed
        self.__endpos = None
    
    def end(self,filename,line):
        self.__endpos = filename,line

    def createTextNode(self,*args):
        assert 0

    def postprocess(self): 
        print "PostProcess Bibliograpy Node"
        if not self.__pp:
            self.__pp = True
            if self.__bibdb:
                bibkeys = [ i.getAttr('key') for i in self if i.nodeName == 'bibitem' and i.hasAttr('key') ]
                cites = []
                citedb = DfltDict(list) 
                for k,n in self.__manager.getCiteRefs():
                    #print "-- Lookup cite key '%s'" % k
                    if k not in bibkeys:
                        #print "-- Cite key %s must be externally resolved" % k

                        if not citedb.has_key(k):
                            cites.append(k)
                        citedb[k].append(n)
                    else:
                        #print "-- Cite key %s found in local definitions" % k
                        pass

                for k in cites:
                    if not self.__bibdb.has_key(k):
                        Warning('No bib item found for "%s". Referenced at: \n\t%s' % (k, '\n\t'.join([ '%s:%d' % n.pos for n in citedb[k]])))
                    else:
                        item = self.__bibdb[k]
                        
                        #print "-- Adding bibitem node for cite key %s" % k
                        node = BibItemNode(self.__manager,
                                           self,
                                           self.__cmddict,
                                           self.__nodedict,
                                           { 'key' : k },
                                           self.__endpos[0],
                                           self.__endpos[1])

                        node.formatBibEntry(item)
                        self.__genitems.append(node)
            else:
                Warning('No bibliography database found')


    def toXML(self,doc):
        node = doc.createElement(self.nodeName)
        if 1:
            n = doc.createElement('head')
            cn = doc.createElement('title')

            cn.appendChild(doc.createTextNode('Bibliography'))
            n.appendChild(cn)
            node.appendChild(n)

        
        self.postprocess() 
        num = 0
        for i in self:
            if i.nodeName == 'bibitem':
                n = i.toXML(doc)
                if n is not None:
                    node.appendChild(n)
                num += 1
                    
        for i in self.__genitems:
            n = i.toXML(doc)
            if n is not None:
                node.appendChild(n)

        return node

class BibItemNode(Node):
    nodeName = 'bibitem'
    contIter = ' [ T %s <href> <m> ] * ' % _simpleTextNodes
    acceptAttrs = Attrs([Attr('key',descr="The cite key.") ])
    macroMode = MacroMode.Text
    paragraphElement = False 

    # These need a serious hand, possibly more features.
    bibtemplate = { 'article'       : '${author}. ${title}. ${journal}$[month]{ ${month}}$[(number|volume)]{ ${number|volume}$[pages]{:${pages}}{}}{$[pages]{p. ${pages}}{}}.$[note]{ ${note}}}',
                    'book'          : '$[author]{${author}}{${editor}, editor}. ${title}$[series&(volume|number)]{, ${series} ${volume|number}}$[edition]{, ${edition} edition}, ${year}. ${publisher}$[address]{, ${address}}.$[note]{ ${note}}}',
                    'booklet'       : '$[author]{${author}. }${title}. $[howpublished]{${howpublished}$[year]{, ${year}.}}{$[year]{$year}.$[note]{ ${note}}}',
                    'conference'    : '${author}. ${title}, ${booktitle}, $[volume]{vol. ${volume}}{no. ${number}}$[organization]{, ${organization}}, ${year}.$[publisher]{ ${publisher}$[address]{, ${address}}.}',
                    'inbook'        : '$[author]{${author}}{${editor}, editor}. ${title}$[series&(volume|number)]{, ${series} ${volume|number}}$[edition]{, ${edition} edition}, ${year}, $[chapter]{chapter ${chapter}}{p. ${pages}}. ${publisher}$[address]{, ${address}}.$[note]{ ${note}}}',
                    'incollection'  : '${author}. ${title}, ${booktitle}$[series]{, ${series}}, $[volume]{vol. ${volume}}{no. ${number}}$[chapter|pages]{ $[chapter]{chapter ${chapter}}{p. ${pages}}}, ${year}. ${publisher}$[address]{, ${address}}.',
                    'inproceedings' : '${author}. ${title}, ${booktitle}$[series]{, ${series}}, $[volume]{vol. ${volume}}{no. ${number}}$[organization]{, ${organization}}, ${year}. ${publisher}$[address]{, ${address}}.',
                    'manual'        : '$[author]{${author}. }${title}$[edition]{, ${edition} edition}$[year]{, ${year}}.$[organization]{ ${organization}$[address]{, ${address}}.}$[note]{ ${note}',
                    'mastersthesis' : '${author}. $[type]{${type}}{Masters thesis}: ${title}, ${year}. ${school}$[address]{, ${address}}.$[note]{ ${note}.}',
                    'misc'          : '$[author]{${author}. }$[title]{${title}. }$[howpublished]{${howpublished}. }$[note]{${note}.}',
                    'phdthesis'     : '${author}. $[type]{${type}}{PhD thesis}: ${title}, ${year}. ${school}$[address]{, ${address}}.$[note]{ ${note}.}',
                    'proceedings'   : '$[author]{${author}. }{$[editor]{${editor}, editor. }}${title}, ${booktitle}, $[volume]{vol. ${volume}}{no. ${number}}$[organization]{, ${organization}}, ${year}.$[publisher]{ ${publisher}$[address]{, ${address}}.}',
                    'techreport'    : '${author}. $[type]{${type}: }${title}$[number]{ no. ${number}}, ${year}. ${institution}$[address]{, ${address}}.$[note]{ ${note}',
                    'unpublished'   : '${author}. ${title}$[year]{, ${year}}. ${note}.',
                    }  

    fmtre = re.compile(r'\$\{(?P<ref>[a-z\|]+)\}|\$\[(?P<cond>[a-z\|&\(\)]+)\]|(?P<endbrace>\})|(?P<beginbrace>\{)')
    bracere = re.compile(r'(?P<endbrace>})|(?P<beginbrace>{)')
    condre = re.compile(r'([()&|])|([^()&|]+)')
    def __init__(self, manager, parent, cmddict, nodeDict, attrs, filename, line):
        Node.__init__(self,manager,parent,CommandDict(cmddict),nodeDict,attrs,filename,line)
        self.__manager = manager

    def handleText(self,text,filename,line):
        #print '-- handleText: "%s"' % text
        Node.handleText(self,unicode(text),filename,line)
    def __handleText(self,text):
        self.handleText(text,self.pos[0],self.pos[1])
    def formatBibEntry(self,node):
        #
        #!!TODO!! Bib entry formatting should be handled in a more flexible way.
        #
        d = node
        #print node
        #for n in node.childNodes:
        #    if n.nodeType == n.ELEMENT_NODE:
        #        cn = n.firstChild
        #        if cn:
        #            d[n.nodeName].append(cn.data)
        filename,line = self.pos
        
        def formatentry(k):
            #print "-- formatentry: %s" % k
            
            items = d[k]
            if isinstance(items,str) or isinstance(items,unicode):
                n = self.newChild('span',{ 'class' : 'bib-item-%s' % k},filename,line)
                n.handleText(items,filename,line)
                n.endOfElement(filename,line)
            else:
                
                assert len(items) > 0
                #print "-- formatentry. items = %s" % str(items)
                    
                n = self.newChild('span',{ 'class' : 'bib-item-%s' % k},filename,line)
                n.handleText(items[0],filename,line)
                n.endOfElement(filename,line)
                if   len(items) > 1:
                    for sep,i in zip([ ', '] * (len(items)-2) + [' and '],items[1:]):
                        self.handleText(sep,filename,line)
                        n = self.newChild('span',{ 'class' : 'bib-item-%s' % k},filename,line)
                        n.handleText(i,filename,line)
                        n.endOfElement(filename,line)

        def formatref(ref):
            refs = [ r for r in ref.split('|') if d.has_key(r) ]
            assert refs
            formatentry(refs[0])


        def ignoregroup(s,p):
            #print "-- ignoregroup: |%s" % s[p:]
            if not s[p] == '{':
                # syntax error
                assert 0
            p += 1
            lvl = 1
            while lvl > 0:
                o = self.bracere.search(s,p)  
                if o is not None:
                    p = o.end(0)
                    if o.group('beginbrace'):
                        lvl += 1
                    else:
                        lvl -= 1
                else:
                    # format string syntax error - unbalanced parens
                    assert 0
            return p

        def parsecond(s):
            """
            I've been cutting some corners in this function. It should work,
            but it might not catch all errors, and all errors are reported with
            assert. Not very elegant.

            parse a condition of the form:
              cond     = "(" subcond ")"
                       |  subcond
              subcond  = conditem "+" and_cond
                       | conditem "|" or_cond
              conditem = TERM
                       | "(" subcond ")"
              and_cond = conditem
                       | conditem "&" and_cond
              or_cond  = conditem
                       | conditem "|" or_cond
            """
            #print "-- parsecond: %s" % s
            
            def parseandlist(cl):
                #print "-- parseandlist: %s" % cl
                assert cl
                if cl and cl[0][0] == '&':
                    cl.pop(0)
                    assert cl and cl[0][1] # syntax error
                    v = cl.pop(0)
                    return parseolist(cl) and d.has_key(v[1])
                else:
                    return True
            def parseorlist(cl):
                #print "-- parseorlist: %s" % cl
                assert cl
                if cl and cl[0][0] == '|':
                    cl.pop(0)
                    assert cl and cl[0][1] # syntax error
                    v = cl.pop(0)
                    return parseolist(cl) or d.has_key(v[1])
                else:
                    return False
            def parsesubcond(cl):
                #print "-- parsesubcond: %s" % cl
                assert cl
                if cl[0][0] == '(':
                    r = parsepargroup(cl)
                else:
                    r = d.has_key(cl.pop(0)[1])
                
                if cl:
                    if cl[0][0] == '|':
                        r = parseorlist(cl) or r
                    elif cl[0][0] == '&':
                        r = parseandlist(cl) and r
                    elif cl[0][0] in [ '(',')']:
                        assert 0 # syntax error
                else:
                    pass
                #print "--  parsesubcond res = %s" % r
                return r
                    
            def parsepargroup(cl):
                print "-- parsepargroup: %s" % cl
                assert cl and cl.pop(0)[0] == '('
                r = parsesubcond(cl)
                assert cl and cl.pop(0)[0] == ')'
                return r
                
            cl = self.condre.findall(s)
            r = parsesubcond(cl)
            assert not cl
            return r
           
        def parsegroup(s,p):
            #print "-- parsegroup: |%s" % s[p:]
            assert s[p] == '{'

            p += 1
            lvl = 1
            while lvl > 0:
                o = self.fmtre.search(s,p)  
                if p < o.start(0):
                    self.__handleText(s[p:o.start(0)])
                if o is not None:
                    #print "-- parsegroup: ...%s" % str(o.groups())
                    #print "               ...%s" % str(s[p:])
                    if o.group('ref'):
                        formatref(o.group('ref'))
                        p = o.end(0)
                    elif o.group('cond'):
                        r = parsecond(o.group('cond'))
                        #print "-- parsegroup: %s" % s[o.end(0):]
                        if r:
                            p = parsegroup(s,o.end(0))
                            p = ignoregroup(s,p)
                        else:
                            p = ignoregroup(s,o.end(0))
                            p = parsegroup(s,p)
                    elif o.group('beginbrace'):
                        p = o.end(0)
                        lvl += 1
                        self.__handleText('{')
                    elif o.group('endbrace'):
                        p = o.end(0)
                        lvl -= 1
                        if lvl > 0:
                            self.__handleText('}')
                    else:
                        # format string syntax error
                        assert 0 
                else:
                    # format string syntax error - unbalanced parens
                    assert 0
            #if p < len(s):
            #    self.__handleText(s[p:])
            return p
               
        def parsefmtstr(s,p):
            while True and p < len(s):
                #print "-- parsefmtstr: |%s" % s[p:]
                o = self.fmtre.search(s,p)  
                if o is not None:
                    if p < o.start(0):
                        self.__handleText(s[p:o.start(0)])
                    #print o.groups()
                    if o.group('ref'):
                        refs = [ r for r in o.group('ref').split('|') if d.has_key(r) ]
                        assert refs
                        formatentry(refs[0])
                        p = o.end(0)
                    elif o.group('cond'):
                        r = parsecond(o.group('cond'))
                        #print "-- parsegroup: %s" % s[o.end(0):]
                        if r:
                            p = parsegroup(s,o.end(0))
                            if len(s) > p and s[p] == '{':
                                p = ignoregroup(s,p)
                        else:
                            #print "STR: '%s'" % s
                            #print "   : '%s'" % s[p:]
                            #print "   : '%s'" % s[o.end(0):]
                            p = ignoregroup(s,o.end(0))
                            if len(s) > p and s[p] == '{':
                                p = parsegroup(s,p)
                    else:
                        # format string syntax error
                        print "STR = '%s', at: '%s'" % (s,s[p:])
                        assert 0 
                else:
                    break
            if p < len(s):
                #print "-- rest of s = |%s" % s[p:]
                self.handleText(s[p:])

        if node.name in [  'article', 'book', 'inbook', 'incollection', 'inproceedings', 'manual', 'mastersthesis', 'misc', 'phdthesis', 'techreport', 'unpublished',]:
            parsefmtstr(self.bibtemplate[node.name], 0)
        else:
            assert 0
            
    

        self.handleText('BIB:UNIMPLEMENTED',self.pos[0],self.pos[1])

        


class _SectionNode(_SectionBaseElement):
    comment     = '''
                    Defines a section in the document.

                    The "id" attribute can be used to refer to the section
                    using the \\tagref{ref} element. Sections should provide a
                    default link text for references, e.g. the section number
                    or the title.
                  '''
    traceInfo   = True
    nodeName    = 'section'
    macroMode   = MacroMode.Text
    acceptAttrs = Attrs([Attr('id'),
                         Attr('class'),
                         Attr('url',descr='Read the section content from an external source. If this is given, the section element must be empty.'),
                         Attr('cond')])
    contIter    = ' <head> [ T %s %s %s %s ]* <section>* ' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)
    
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        assert isinstance(nodeDict, dict)
        _SectionBaseElement.__init__(self,manager,parent,CommandDict(cmddict),nodeDict,attrs,filename,line)

        self.__head = None
        if parent is not None:
            self.__depth = parent.getDepth()+1
        else:
            self.__depth = 1
        self.__parent = parent
        if not manager.checkSectionDepth(self.__depth):
            raise NodeError('Section nested too deep:\n\t' + '\n\t'.join(self.makeSectionTrace([])))
   
    def makeSectionTrace(self,res):
        res.append('Section at %s:%d' % self.pos)
        if self.__parent is not None:
            self.__parent.makeSectionTrace(res)
        return res
        

    def getDepth(self):
        return self.__depth
    def end(self,filename,line):
        for n in self:
            if isinstance(n,Node) and n.nodeName == 'head':
                self.__head = n
    
    def getHeadNode(self):
        return self.__head

    def toXML(self,doc,node=None):
        if node is None:
            node = doc.createElement(self.nodeName)
            if self.hasAttr('class'):
                node.setAttribute('class', self.getAttr('class'))
            if self.hasAttr('id'):
                node.setAttribute('id', self.getAttr('id'))

        nodes = [ n for n in self  ]
        while not isinstance(nodes[0],HeadNode):
            nodes.pop(0)
        node.appendChild(nodes.pop(0).toXML(doc))
        node.appendChild(doc.createTextNode('\n'))

        body = doc.createElement('body')
        node.appendChild(body)
       
        lst = [] 
        while nodes and not isinstance(nodes[0],_SectionNode):
            item = nodes.pop(0)
            if isinstance(item,unicode):
                if not lst or isinstance(lst[-1],Node):
                    lst.append([item])
                else:
                    lst[-1].append(item)
            else:
                lst.append(item)

        if self.paragraphElement:
            # generate paragraphs 
            self.paragraphifyXML(lst,doc,body)
        for item in nodes:
            if isinstance(item,_SectionBaseElement):
                node.appendChild(item.toXML(doc))
                node.appendChild(doc.createTextNode('\n'))
            else:
                assert not item.strip()
        return node

class HeadNode(Node):
    comment = 'Contains the header definitions for a \\tagref{section} in the document.'
    nodeName = 'head'
    
    contIter = ' [ <title> <authors> <date> <defines> <abstract> ]/ '
    structuralElement = True
        
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        
        self.__date     = None
        self.__title    = None
        self.__authors  = None
        self.__abstract = None
        self.__defines  = None

    def getTitleNode(self):
        return self.__title
    def getDefinesNode(self):
        return self.__defines

    def end(self,filename,line):
        for n in self:
            if   n.nodeName == 'defines':
                self.__defines = n
            elif n.nodeName == 'date':
                self.__date = n
            elif n.nodeName == 'title':
                self.__title = n
            elif n.nodeName == 'authors':
                self.__authors = n
            elif n.nodeName == 'abstract':
                self.__abstract = n
            else:
                assert 0
        

class DateNode(Node):
    comment = 'Defines a date for a section or document'
    nodeName   = 'date'
    macroMode  = MacroMode.NoExpand
    contIter   = ' [ T ]* ' 
    
    paragraphElement = False

class TitleNode(Node):
    comment = 'Defines a \\tagref{section} title.'
    nodeName   = 'title'
    macroMode  = MacroMode.Text
    contIter   = ' [ T %s ]* ' % _simpleTextNodes
    
    paragraphElement = False

class AuthorsNode(Node):
    comment   = 'Defines a list of authors for the document or for a specific section.'
    nodeName  = 'authors'
    macroMode = MacroMode.Text
    contIter  = ' <author>+ '
    structuralElement = True

class AuthorNode(Node):
    comment   = 'Defines the information for a specific author.'
    nodeName  = 'author'
    macroMode = MacroMode.Text
    contIter = ' [ <firstname> <lastname> <email> <institution> ]* '
    paragraphElement = False

class AuthorFirstNameNode(Node):
    nodeName  = 'firstname'
    macroMode = MacroMode.Text
    contIter  = ' [ T ]* '
    paragraphElement = False
class AuthorLastNameNode(Node):
    nodeName  = 'lastname'
    macroMode = MacroMode.Text
    contIter  = ' [ T ]* '
    paragraphElement = False
class AuthorEmailNode(Node):
    nodeName  = 'email'
    macroMode = MacroMode.Text
    contIter  = ' [ T ]* '
    paragraphElement = False
class AuthorInstitutionNode(Node):
    nodeName  = 'institution'
    macroMode = MacroMode.Text
    contIter  = ' [ <name> <address> ]* '
    structuralElement = True
class AuthorInstitutionNameNode(Node):
    nodeName = 'name'
    macroMode = MacroMode.Text
    contIter = ' [ T ]*'
    paragraphElement = False
class AuthorInstitutionAddressNode(Node):
    nodeName = 'address'
    macroMode = MacroMode.Text
    contIter  = ' [ T ]* '
    allowParagraphs = False

class AbstractNode(Node):
    comment = """ Defines an abstract for a section or a whole document. """
    nodeName = 'abstract'
    macroMode = MacroMode.Text
    contIter   = ' [ T <href> <ref> %s %s %s ]* ' % (_simpleTextNodes,_structTextNodes,_mathEnvNodes)

######################################################################
#  Text content classes
######################################################################

class _SimpleTextElement(Node):
    macroMode = MacroMode.Inherit
    contIter = ' [ T %s %s ]* ' % (_simpleTextNodes,_linkNodes)
    paragraphElement = False

class TypedTextNode(_SimpleTextElement):
    comment = 'Typed Text. A fixed width font.'
    nodeName  = 'tt'

class BoldFaceNode(_SimpleTextElement):
    comment = 'Bold face.'
    nodeName  = 'bf'

class EmphasizeNode(_SimpleTextElement):
    comment = 'Emphasize.'
    nodeName  = 'em'

class SmallCapsNode(_SimpleTextElement):
    comment = 'Small caps.'
    nodeName  = 'sc'

class SpanNode(_SimpleTextElement):
    nodeName  = 'span'
    acceptAttrs = Attrs([ Attr('id'), 
                          Attr('class'),
                          Attr('cond'), 
                          Attr('macroexpand',default='yes') ])
    contIter    = ' [ T %s %s ]* ' % (_simpleTextNodes,_linkNodes)

class DivNode(Node):
    comment = 'A logical division element that creates a new paragraph.'
    nodeName  = 'div'
    acceptAttrs = Attrs([ Attr('id'),
                          Attr('class'), 
                          Attr('cond'), 
                          Attr('macroexpand',default='yes') ])
    contIter    = ' [ T %s %s %s %s ]* ' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)
    macroMode   = MacroMode.Text
    paragraphElement = True

class NoteNode(Node):
    comment = '''
                Meta comments. This is meant to be used as notes for
                proof-reading and comments on parts of the text. This is not a
                feature meant for internal use only.
              '''
    nodeName  = 'note'
    acceptAttrs = Attrs([ Attr('cond',default="true") ])
    contIter    = ' [ T %s %s %s %s ]* ' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)
    macroMode   = MacroMode.Text
    paragraphElement = True
    traceInfo    = True


class SDocMLConditionalNode(Node):
    # This class exists only for documentation purposes.
    comment = '''
                Preprocessor element. This element is handled as a special case.

                The element may appear anywhere in the document structure
                except at top-level. If the condition is met the content will
                be processed as had it appeared directly in the document
                instead of inside a \\tagref{sdocml:conditional} element, otherwise
                the content is ignored and thrown away.
              '''
    nodeName  = 'sdocml:conditional'
    acceptAttrs = Attrs([ Attr('cond') ])
    contIter = ''

class _AlignParagraphNode(Node):
    acceptAttrs = Attrs([ Attr('id'),
                          Attr('class'),
                          Attr('macroexpand',default='yes') ])
    macroMode = MacroMode.Text
    contIter    = ' [ T %s %s %s %s ]* ' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)
    paragraphElement = True

class CenterNode(_AlignParagraphNode):
    comment   = 'Centered text paragraph.'
    nodeName  = 'center'
class FlushLeftNode(_AlignParagraphNode):
    comment   = 'Left aligned text paragraph.'
    nodeName  = 'flushleft'
class FlushRightNode(_AlignParagraphNode):
    comment   = 'Right aligned text paragraph.'
    nodeName  = 'flushright'


class BreakNode(Node):
    comment   = 'Forced line-break.'
    nodeName  = 'br'
    macroMode = MacroMode.Invalid
    contIter = ''
    paragraphElement = False

#class InlineNoexpandNode(_SimpleTextElement):
#    macroMode = MacroMode.NoExpand
#    nodeName  = 'nx'

class ItemListNode(Node):
    comment     = 'Unordered list.'
    nodeName    = 'ilist'
    macroMode   = MacroMode.Text
    acceptAttrs = Attrs([ Attr('id'), 
                         Attr('class') ])
    contIter    = ' <li>* '
    structuralElement = True

class DefinitionListNode(Node):
    comment     = 'Definition list.'
    nodeName    = 'dlist'
    macroMode   = MacroMode.Text
    acceptAttrs = Attrs([ Attr('id'), Attr('class') ])
    contIter    = ' [ <dt> <dd> ]* '
    structuralElement = True

class _ListElementNode(Node):
    macroMode = MacroMode.Text
    contIter  = ' [ T %s %s %s %s ]* ' % (_simpleTextNodes, _structTextNodes, _linkNodes, _mathEnvNodes)

class ListItemNode(_ListElementNode):
    comment     = 'Unordered list item.'
    nodeName = 'li'
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), Attr('cond') ])

class DefinitionTitleNode(_ListElementNode):
    comment     = 'Definition list label node.'
    nodeName = 'dt'
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), Attr('cond') ])

class DefinitionDataNode(_ListElementNode):
    comment     = 'Definition list data node.'
    nodeName = 'dd'
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), Attr('cond') ])

class FloatCaptionNode(Node):
    comment     = 'Caption for a floating element.'
    nodeName = 'caption'
    macroMode = MacroMode.Text
    contIter = ' [ T <m> %s %s %s ]* ' % (_simpleTextNodes, _structTextNodes, _linkNodes)
    acceptAttrs = Attrs([ Attr('id'), Attr('class') ])
    paragraphElement = False

class FloatBodyNode(Node):
    comment     = 'Floating element body.'
    nodeName = 'floatbody'
    macroMode = MacroMode.Text
    contIter  = ' [ T %s %s %s %s ]* ' % (_simpleTextNodes, _structTextNodes, _linkNodes, _mathEnvNodes)

class FloatNode(Node):
    comment     = 'Floating element.'
    nodeName = 'float'
    macroMode = MacroMode.Text
    contIter = ' <floatbody> <caption>?'
    acceptAttrs = Attrs([ Attr('id'), 
                          Attr('class'),
                          Attr('float',default='right', descr="(left|right|no) Defines where the figure should float. The backend may choose to ignore this.") ])
    structuralElement = True

class TableNode(Node):
    comment     = '''
                    A table. The table element allows special table syntax:
                    <ilist>
                        <li> "\\\\:" for starting a new \\tagref{tr} element, and</li>
                        <li> "\\\\!" for starting a new \\tagref{td} element.</li>
                    </ilist>
                  
                    Please note that tables may not behave identically in TeX and HTML.
                  '''
    examples = [ ('Create a table using special table syntax:',
                  '\n'.join(['<table>',       
                             '  \\: Cell(1,1) \\! Cell(1,2) \\! Cell(1,3)',
                             '  \\: Cell(2,1) \\! Cell(2,2) \\! Cell(2,3)',
                             '</table>']))      ,
                 ('Create a table using tags',
                  '\n'.join(['<table>',       
                             '  <tr><td> Cell(1,1) </td><td> Cell(1,2) </td><td> Cell(1,3) </td></tr>',
                             '  <tr><td> Cell(2,1) </td><td> Cell(2,2) </td><td> Cell(2,3) </td></tr>',
                             '</table>'])) ]
    allowTableSyntax = True
    macroMode = MacroMode.Text
    nodeName = 'table'
    contIter = ' <tr>+ '
    tablerowelement = 'tr'
    tablecellelement = 'td'
    acceptAttrs = Attrs([ Attr('id'), 
                    Attr('class'),
                    Attr('orientation',default='rows'), # DEPRECATED!!
                    Attr('cellvalign',descr='Vertical alignment of cells. This is a space-separated list of (top|middle|bottom) defining the alignment of cells in the individual columns.'),
                    Attr('cellhalign',descr='Horizontal alignment of cells. This is a space-separated list of (left|right|center) defining the alignment of cells in the individual columns.'), ])
    structuralElement = True

    def __init__(self, manager, parent, cmddict, nodedict, attrs, filename, line):
        Node.__init__(self,manager,parent,cmddict,nodedict,attrs,filename,line)

        self.__halign = None
        self.__valign = None

    def end(self,filename,line):
        halign = None
        valign = None

        ncells = max([ len(r) for r in self ])

        if  self.hasAttr('cellhalign'):
            halign = re.split(r'\s+', self.getAttr('cellhalign'))
            for i in halign:
                if i not in [ 'left','right','center' ]:
                    raise NodeError('Invalid cellhalign attribute value in %s:%d' % self.pos)

        if  self.hasAttr('cellvalign'):
            valign = re.split(r'\s+', self.getAttr('cellvalign'))
            for i in valign:
                if i not in [ 'top','bottom','middle' ]:
                    raise NodeError('Invalid cellvalign attribute value in %s:%d' % self.pos)

        if halign is not None and valign is not None:
            if   len(halign) != len(valign):
                raise NodeError('Vertical and horizontal alignment definitions do not match at %s:%d' % pos)
        elif halign is not None:
            valign = [ 'top' ] * len(halign)
        elif valign is not None:
            halign = [ 'left' ] * len(valign)
        else: 
            valign = [ 'top' ] * ncells
            halign = [ 'left' ] * ncells

        lenr = len([i for i in r if isinstance(i,TableCellNode) ])
        for r in self:
            if lenr > len(halign) or lenr > len(valign):
                print "row: ",lenr,len(halign),len(valign)
                raise NodeError('Alignment definitions do not match row width at %s:%d' % self.pos)

        self.__halign = halign
        self.__valign = valign

    def toXML(self,doc):
        node = doc.createElement('table')

        if self.hasAttr('class'):
            node.setAttribute('class',self.getAttr('class'))
        node.setAttribute('cellhalign',' '.join(self.__halign))
        node.setAttribute('cellvalign',' '.join(self.__valign))

        rowlen = len(self.__halign)

        for r in self:
            if isinstance(r,basestring):
                if r.strip():
                    raise NodeError('Non-whitespace text not allowed in table at %s:%d' % self.pos)
            else:
                n = r.toXML(doc,rowlen)            
                if n is not None:
                    node.appendChild(n)
        
        return node

class TableColumnNode(Node):
    comment = 'Table column entries can be used to label a column of cells or define the format of a table.'
    nodeName = 'col'
    contIter = ''
    acceptAttrs = Attrs([ Attr('class'),Attr('valign'), Attr('halign')])
    allowTableSyntax = True
    structuralElement = True

class TableRowNode(Node):
    comment = '''
                Table row entries define the cells of each row in the table.
                The number of cells in each row must exactly match the format
                defined in \\tagref{table} or in the \\tagref{col}s.
              '''
    nodeName = 'tr'
    contIter = ' <td>* '
    acceptAttrs = Attrs([ Attr('id'), Attr('class') ])
    structuralElement = True

    def __len__(self):
        return len([ i for i in self if isinstance(i,TableCellNode)])
    
    def toXML(self,doc,rowlen):
        node = doc.createElement('tr')

        cells = list(self)
        cells.extend([ None ] * (rowlen - len(cells)))

        for cell in cells:
            if cell is not None:
                node.appendChild(cell.toXML(doc))
            else:
                node.appendChild(doc.createElement('td'))
        return node

class TableCellNode(Node):
    comment = 'Table can be used to label a column of cells or define the format of a table.'
    nodeName = 'td'
    macroMode = MacroMode.Text
    contIter  = ' [ T %s %s %s %s ]* ' % (_simpleTextNodes, _structTextNodes, _linkNodes, _mathEnvNodes)
    acceptAttrs = Attrs([ Attr('id'), Attr('class') ])
    paragraphElement = True

class DocumentNode(_SectionNode):
    nodeName   = 'sdocmlx'
#NOTE: we should support appendixes too at some point...
    contIter    = ' <head> [ T %s %s %s %s ]* <section>* <bibliography>?' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)

    def __init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line):
        _SectionNode.__init__(self,manager,None,cmddict,globalNodeDict,attrs,filename,line)


class FontNode(_SimpleTextElement):
    nodeName = 'font'
    acceptAttrs = Attrs([ Attr('id'), 
                          Attr('class'), 
                          Attr('family',descr='Font family name.'), 
                          Attr('style',descr='The font style; bold, italic, overlined etc.') ])



######################################################################
#  Non-expanding Text environments
######################################################################
class _NoExpandAnyNode(_SimpleTextElement):
    macroMode = MacroMode.NoExpand

class NoExpandInlineNode(_NoExpandAnyNode):
    nodeName  = 'nx'
    paragraphElement = False

    def toXML(self,doc):
        n = doc.createElement('span')
        _NoExpandAnyNode.toXML(self,doc,n)
        return n


class NoExpandNode(_NoExpandAnyNode):
    nodeName  = 'noexpand'

class PreformattedNode(Node):
    comment = '''
                The \\tagref{pre} element serves two different purposes: First
                of all it can be used to include performatted text as a
                separate paragraph. Secondly it allows inclusion of external
                files or snippets (a range of lines) from external files.
                Code snippets can be processed to add syntax hilighting by
                specifying a suitable mime type. The code for syntax analysis
                is located in the \\tt{syntax.py} module.

                In the former case the <tt>url</tt> attribute is not defined,
                and the element contains text. If <tt>macroexpand="yes"</tt> is
                given, macros will be expanded inside the element, otherwise
                they will not. The values of <tt>firstline</tt>,
                <tt>lastline</tt> and <tt>encoding</tt> are ignored.

                In the latter case <tt>url</tt> is defined. This points to a
                file or a link that is fetched and included. If
                <tt>firstline</tt> and/or <tt>lastline</tt> are given, only the
                corresponding range of lines (both bounds inclusive) is
                included. The value of the <tt>encoding</tt> attribute is used
                to termine the text encoding of the external file (which is
                conterted to UTF-8 when included).
                
                Please note that blank lines at the beginning and end of a
                external inclusion are removed (but the <tt>frstline</tt>
                value is adjusted accordingly). Blank space at the beginning of
                lines is kept.
                
                If <tt>url</tt> was given, the \emph{full name} of the url is
                included in the expansion (i.e. for local files, the absolute
                path will be used, for ecternal URLs, just the value of
                <tt>url</tt> will be used).
                
                If present, the value of <tt>firstline</tt> is included in the
                expansion (for generating line numbers etc).
                The <tt>type</tt> attribute is included unmodified in the
                expansion.

                
              ''' 
    nodeName  = 'pre'
    macroMode = MacroMode.NoExpand
    acceptAttrs = Attrs([
                    Attr('id'), 
                    Attr('class'), 
                    Attr('url',descr="Location of a text file to include."),
                    Attr('firstline',descr="Index of the first line to use from the url (1-based)."),
                    Attr('lastline',descr="Index of the last line+1 to use from the url (1-based)."),
                    Attr('xml:space',default='preserve'),
                    Attr('type',default='text/plain',descr="MIME type of the text element content or of the URL target."),
                    Attr('encoding',default='ascii'), # (ascii|utf-8)
                    Attr('macroexpand',default='no',descr="Tells if macros should be processed in the content of the element. For external sources this is ignored."), # (yes|no)
                    Attr('cond')])
    macroMode = MacroMode.NoExpand
    contIter  = ' [ T %s <a> ]* ' % (_simpleTextNodes )
    structuralElement = True
    paragraphElement = True

    def __init__(self, manager, parent, cmddict, nodeDict, attrs, filename, line):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)

        self.__realurl = None

        if self.hasAttr('url'):
            url = self.getAttr('url')
            self.__realurl = manager.findFile(url,filename) 
            lines = manager.readFrom(self.__realurl,self.getAttr('encoding')).split('\n')
            firstline = 0
            if self.hasAttr('firstline'):
                firstline = max(int(self.getAttr('firstline'))-1,0)
            lastline = len(lines)
            if self.hasAttr('lastline'):
                lastline = min(int(self.getAttr('lastline'))-1,lastline)

            if firstline >= lastline:
                raise NodeError('Empty inclusion from "%s" in <pre> at %s:%d' % (url,self.pos[0],self.pos[1]))
            
            while firstline < lastline and not lines[firstline].strip():
                firstline += 1
            while firstline < lastline and not lines[lastline-1].strip():
                lastline -= 1
            if firstline == lastline:
                raise NodeError('Only blank lines in inclusion in <pre> at %s:%d' % self.pos)
            inclines = lines[firstline:lastline]

            for l in inclines[:-1]:
                self.handleRawText(l,filename,line)
                self.handleRawText(u'\n',filename,line)
            self.handleRawText(inclines[-1],filename,line)

            self.__firstline = firstline
            self.seal()
    def toXML(self,doc,node=None):
        items = list(self)
        
        # If the first line is blank, we kill it.
        if not self.hasAttr('url'):
            if items and isinstance(items[0],basestring):
                v = items[0].lstrip(' \t')
                if v and v[0] == '\n':
                    items[0] = v[1:]
            
            # If the last line is blank, we kill that too.
            if items and isinstance(items[-1],basestring):
                item = items.pop().rstrip(' \t')
                if item:
                    if item[-1] == '\n':
                        items.append(item[:-1])
                    else:
                        items.append(item)
                else:# last line was spaces only, so delete the trailing newline in the second last line
                    if items and isinstance(items[-1],basestring):
                        item = items.pop()
                        if item and item[-1] == '\n':
                            items.append(item[:-1])
                        else:
                            items.append(item)
        if node is None:
            node = doc.createElement(self.nodeName)
            
        codelight = syntax.CodeHilighter(self.getAttr('type'))
        # special case: If first line is blank in a <pre>, we throw it away.
                        
        for item in items:
            if isinstance(item,unicode):
                for itm in codelight.process(item):
                    if isinstance(itm,basestring):
                        n = doc.createTextNode(itm)
                    else:
                        t,val = itm
                        n = doc.createElement('span')
                        n.setAttribute('class','language-syntax-%s' % t)
                        n.appendChild(doc.createTextNode(val))
                    node.appendChild(n)
            else:
                n = item.toXML(doc)
                if n is not None:
                    node.appendChild(n)

        for k in [ 'id', 'class', 'xml:space','type' ]:
            if self.hasAttr(k):
                node.setAttribute(k,self.getAttr(k))
    
        if self.__realurl is not None:    
            node.setAttribute('url',self.__realurl)
            node.setAttribute('firstline',str(self.__firstline+1))
            
        if self.traceInfo:
            assert self.pos[0] is not None
            assert self.pos[1] is not None
            node.setAttribute("xmlns:trace","http://odense.mosek.com/emotek.dtd")
            node.setAttribute('trace:file',self.pos[0])
            node.setAttribute('trace:line',str(self.pos[1]))
        return node

######################################################################
#  Link and reference elements
######################################################################
class ReferenceNode(Node):
    """
    -- Create a reference/hyperlink to an ID --
    <!ELEMENT ref (%textelements;)>
    <!ATTLIST ref
              class CDATA #IMPLIED
              ref   IDREF #REQUIRED -- The ID if the target --
              type  (cite|default) "default" 
                                    -- Reference type. 
              exuri CDATA #IMPLIED  -- If not given, the ref must be resolved within the document,
                                       otherwise it defines a resource containing the ID. In this case it is
                                       up to the output backend to interpret the reference. 
                                       NOTE: This should have the form of either an URI or a relative path. 
                                       In neither case will the frontend attempt to resolve it. 
                                    -- 
              >
    This element should be interpreted as follows:
      If 'exuri' is not given, the ID must be resolved within the finished document; this is checked by the frontend. 
      If 'exuri' is given, the frontend ignores the reference, even if it is defined within the document: It is up
        to the backend to resolve it.

      If the the element is non-empty, the contents must be used to produce the link text, e.g. for
        <ref ref="my:id">MyLink</ref> 
      the HTML backend might produce something like
        <a href="mynode.html#my:id">MyLink</a>
      If the element is empty, the linked node must provide a meaningful link
      text that can be used (again, this is up to the backend to determine).
      For example, if a link target was defined as
        <a id="my:id">My Target</a>
      then for the reference
        <ref ref="my:id"/> 
      the HTML backend might produce something like
        <a href="mynode.html#my:id">My Target</a>
      Alternatively, some nodes, like <math> or <eqn> might generate a linktext
      automatically as an equation counter, <section> might produce a section
      counter or a title text.
    """
    nodeName    = 'ref'
    macroMode   = MacroMode.Text
    acceptAttrs = Attrs([ Attr('class'), 
                          Attr('ref'),
                          Attr('type'),
                          Attr('exuri'),
                  ]) 
    traceInfo   = True
    contIter    = ' [ T %s ]* ' % (_simpleTextNodes)
    paragraphElement = False

class LinkTextNode(Node):
    nodeName    = 'linktext'
    macroMode   = MacroMode.Text
    acceptAttrs = Attrs([ Attr('id'), 
                          Attr('class') ])
    contIter    = ' [ T %s <m> ]* ' % (_simpleTextNodes)
    paragraphElement = False

class HyperRefNode(Node):
    nodeName    = 'href'
    macroMode   = MacroMode.Text
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), Attr('url') ])
    contIter    = ' [ T %s ]* ' % (_simpleTextNodes)
    paragraphElement = False

class AnchorNode(Node):
    comment     = """
                    Defines a target for links. The element's id can be used to
                    refer to it. If the element contains anything this will be
                    used as link text, otherwise no link text is provided. 
                    
                    The id is not mandatory. If it is left out, it is not
                    possible to refer to the point using a \\tagref{ref}
                    element --- instead the target can be used to mark e.g. an
                    index entry.
                  """
    nodeName    = 'a'
    macroMode   = MacroMode.Text
    acceptAttrs = Attrs([ Attr('id'), Attr('class') ])
    contIter    = ' [ T %s <m> ]* ' % (_simpleTextNodes)
    paragraphElement = False

class ImageNode(Node):
    comment     = '''
                    The image Node defines an image object to be inserted. It
                    specifies one or more image sources that are "logically
                    identical" (i.e. the same image in different formats). The
                    backend is then free to choose the image source having a
                    suitable format or, failing that, convert one of the images
                    to a suitable format.
                  '''
    nodeName    = 'img'
    macroMode   = MacroMode.Invalid
    contIter    = ' <imgitem>+ '
    acceptAttrs = Attrs([ Attr('id'),
                          Attr('class'), 
                          Attr('scale',default="1.0",descr="A value strictly greater than 0 defining the scaling factor."), 
                          Attr('width',default="1.0",descr="A fractional value defining the horizontal scaling factor, a 'X%' value defining the fraction of the available width, or a 'Xpt' defining an absolute size in points."), 
                          Attr('height',default="1.0",descr="A fractional value defining the horizontal scaling factor, a 'X%' value defining the fraction of the available height, or a 'Xpt' defining an absolute size in points.") ])
    structuralElement = True
    traceInfo    = True

class ImageItemNode(Node):
    comment     = 'Defines an instance of an image object to be inserted. '
    nodeName    = 'imgitem'
    macroMode   = MacroMode.Invalid
    acceptAttrs = Attrs([ Attr('cond'),
                          Attr('type'),
                          Attr('url',descr='Source of the image file.')])
    contIter    = ''



######################################################################
#  Some administrative Node classes
######################################################################

class _ExceptionNode(Node):
    macroMode   = MacroMode.NoExpand
    acceptAttrs = Attrs([ Attr('cond') ])
    contIter    = ' T  '
    structuralElement = True


    def __init__(self,
                 manager,
                 parent,
                 cmddict, # dictionary of available macros
                 nodedict, # dictionary of all known element names
                 attrs, # None or a dictionary of attributes
                 filename,
                 line):
        Node.__init__(self,manager,parent,cmddict,nodedict,attrs,filename,line)
    
    def onCreate(self):
        pass

    def toXML(self,doc,node=None):
        pass

    def end(self,filename,line):
        self.onCreate()
        

class ErrorNode(_ExceptionNode):
    comment = """
                If the condition is met, this element will expand to nothing,
                otherwise it will cause an error. The content of the element is
                plain text and will be used as error message.
              """
    nodeName = 'error'
    metaElement = True
    paragraphElement = False

    def onCreate(self):
        msg = ''.join(self)
        raise CondError("ERROR @ %s(%d): %s" % (self.pos[0],self.pos[1],msg))

class WarningNode(_ExceptionNode):
    comment = """
                This element will expand to nothing.  If the condition is not
                met it will cause a warning to be printed. The content of the
                element is plain text and will be used as warning message.
              """
    nodeName = 'warning'
    metaElement = True
    paragraphElement = False

    
    def onCreate(self):
        msg = ''.join(self)
        print "WARNING @ %s(%d): %s" % (self.pos[0],self.pos[1],msg)

######################################################################
#  Math Node classes
######################################################################


class InlineMathNode(_MathNode):
    nodeName         = 'm'
    traceInfo        = True
    paragraphElement = False

    comment          = '''
                         Inline math element. This is placed as an element in
                         the text rather than in a separate paragraph.
                       '''

class MathEnvNode(_MathNode):
    nodeName    = 'math'
    traceInfo   = True
    acceptAttrs = Attrs([ Attr('class'), 
                    Attr('id'),
                    Attr('numbered') ])
    comment     = '''
                    A math paragraph. Id the id attribute is defined, a number
                    is generated, which can be used when referring to the
                    paragraph. 
                  '''


class MathEqnNode(_MathNode):
    nodeName = 'eqn'
    traceInfo   = True
    acceptAttrs = Attrs([ Attr('class'), 
                          Attr('id') ])

class MathEqnArrayNode(Node):
    acceptAttrs = Attrs([ Attr('class'),
                    Attr('numbered') ])
    macroMode = MacroMode.Text
    nodeName = 'eqnarray'
    contIter = ' <eqn>* '
    structuralElement = True

class MathFontNode(_MathNode):
    nodeName = 'mfont'
    macroMode = MacroMode.Inherit
    acceptAttrs = Attrs([ Attr('class'), Attr('family'), Attr('style') ])

    def end(self,filename,line):
        if self.hasAttr('family') and not self.getAttr('family') in mathFonts:
            raise NodeError('Invalid math font "%s" at %s:%d' % (self.getAttr('family'),self.pos[0],sel.pos[1]))

class MathTextNode(Node):
    nodeName  = 'mtext'
    macroMode = MacroMode.Text
    contIter  = ' [ T %s ]* ' % _simpleTextNodes
    paragraphElement = False

    comment   = '''
                  An element behaving as a normal inline text element. 
                '''



class MathRowNode(_MathNode):
    nodeName = 'mrow'
    comment   = '''
                  A structural grouping element for math mode. This is used to
                  group text and elements when writing fractions, subscripts
                  etc. It has no visual effect.
                '''

class MathOperatorNode(_MathNode):
    nodeName = 'mo'
    macroMode = MacroMode.SimpleMath
    acceptAttrs = Attrs([ Attr('class'), 
                          Attr('op', default='', descr='(sum|prod|int) Denotes a symbolic operator.') ])
    comment   = '''
                  Math operator. This is mostly a logical element telling that
                  a certain group is an mathematical operator like ``+'',
                  ``-'', ``='' etc. This may affect the typesetting. 

                  The ``op'' attribute can be used to insert a symbolic
                  operator in which case the element should be empty.
                '''

class MathIdentifierNode(_MathNode):
    nodeName = 'mi'
    macroMode = MacroMode.SimpleMath
    acceptAttrs = Attrs([ Attr('class') ])
    comment   = '''
                  Denotes a math identifier. All letters in math mode is
                  treated as single-char identifiers unless the markup
                  indicates otherwise. This element can be used to make
                  multi-char identifiers (which may affect the typesetting).
                '''

class MathNumberNode(_MathNode):
    nodeName = 'mn'
    macroMode = MacroMode.SimpleMath
    acceptAttrs = Attrs([ Attr('class') ])
    comment   = '''
                  Denotes a number. This may affect the typesetting.
                '''

class MathSubscriptNode(_MathNode):
    nodeName = 'msub'
    comment   = '''
                  Denotes a subscript. This contains exactly two \\tagref{mrow}
                  elements; the base and the operand.
                '''
    contIter = ' <mrow> <mrow> '

class MathSuperscriptNode(_MathNode):
    nodeName = 'msup'
    comment   = '''
                  Denotes a superscript. This contains exactly two \\tagref{mrow}
                  elements; the base and the operand.
                '''
    contIter = ' <mrow> <mrow> '

class MathSubSuperscriptNode(_MathNode):
    nodeName = 'msubsup'
    comment   = '''
                  Denotes a superscript+subscript. This contains exactly three \\tagref{mrow}
                  elements; the base, the sub operand and the super operand.
                '''
    contIter = ' <mrow> <mrow> <mrow>'

class MathSquareRootNode(_MathNode):
    nodeName = 'msqrt'
    
    comment   = '''
                  Denotes a square root.
                '''

class MathRootNode(_MathNode):
    nodeName = 'mroot'
    comment   = '''
                  Denotes an n-root. This contains exactly two operands; the n and the operand.
                '''
    contIter = ' <mrow> <mrow> '

class MathFracNode(_MathNode):
    nodeName = 'mfrac'
    comment   = '''
                  Denotes an fraction; a horizontal line with one operand above
                  and one below. This contains exactly two operands; the
                  numerator and the denominator.
                '''
    contIter = ' <mrow> <mrow> '

class MathFencedNode(_MathNode):
    nodeName = 'mfenced'
    comment = '''
                A group surrounded by parentheses.

                The frontend does nothing with the open and close attributes
                --- these are simply passed to the backend. The ``ceil'' value
                should be interpreted as <tt>lceil</tt> and <tt>rceil</tt> for
                the left and right side of the group, and likewise for
                ``floor''.
              '''
    acceptAttrs = Attrs([ Attr('class'), 
                          Attr('open', default="", descr='Left parenthesis. The following should be recognized: "(", "[", "\\{", "|", "&lt;", "|", "||", "ceil", "floor" and ".". These are passed verbatim to the backend. '), 
                          Attr('close', default="", descr='Left parenthesis. The following should be recognized: ")", "]", "\\}", "|", "&gt;", "|", "||", "ceil", "floor" and ".". These are passed verbatim to the backend. ') ])

class MathTableNode(_MathNode):
    comment     = '''
                    A math table. The table element allows special table syntax:
                    <ilist>
                        <li> "\\\\:" for starting a new \\tagref{mtr} element, and</li>
                        <li> "\\\\!" for starting a new \\tagref{mtd} element.</li>
                    </ilist>
                  '''
    examples = [ ('Create a table using special table syntax:',
                  '\n'.join(['<mtable>',       
                             '  \\: Cell(1,1) \\! Cell(1,2) \\! Cell(1,3)',
                             '  \\: Cell(2,1) \\! Cell(2,2) \\! Cell(2,3)',
                             '</mtable>'])),
                 ('Create a table using tags:',
                  '\n'.join(['<mtable>',       
                             '  <mtr><mtd> Cell(1,1) </mtd><mtd> Cell(1,2) </mtd><mtd> Cell(1,3) </mtd></mtr>',
                             '  <mtr><mtd> Cell(2,1) </mtd><mtd> Cell(2,2) </mtd><mtd> Cell(2,3) </mtd></mtr>',
                             '</mtable>']))]
    nodeName = 'mtable'
    macroMode = MacroMode.Math
    contIter = ' <mtr>* '
    acceptAttrs = Attrs([Attr('id'), 
                    Attr('class'),
                    Attr('cellvalign'),
                    Attr('cellhalign'), ])
    allowTableSyntax = True
    tablerowelement = 'mtr'
    tablecellelement = 'mtd'

    def end(self,filename,line):
        halign = None
        valign = None
        rows = [ r for r in self if isinstance(r,MathTableRowNode) ]

        ncells = max([ len(r) for r in rows ])

        if  self.hasAttr('cellhalign'):
            halign = re.split(r'\s+', self.getAttr('cellhalign'))
            for i in halign:
                if i not in [ 'left','right','center' ]:
                    raise NodeError('Invalid cellhalign attribute value in %s:%d' % self.pos)

        if  self.hasAttr('cellvalign'):
            valign = re.split(r'\s+', self.getAttr('cellvalign'))
            for i in valign:
                if i not in [ 'top','bottom','middle' ]:
                    raise NodeError('Invalid cellvalign attribute value in %s:%d' % self.pos)

        if halign is not None and valign is not None:
            if   len(halign) != len(valign):
                raise NodeError('Vertical and horizontal alignment definitions do not match at %s:%d' % pos)
        elif halign is not None:
            valign = [ 'top' ] * len(halign)
        elif valign is not None:
            halign = [ 'left' ] * len(valign)
        else:
            valign = [ 'top' ] * ncells
            halign = [ 'left' ] * ncells

        for r in rows:
            if len(r) > len(halign) or len(r) > len(valign):
                raise NodeError('Alignment definitions do not match row width at %s:%d' % r.pos)

        self.__halign = halign
        self.__valign = valign

    def toXML(self,doc):
        node = doc.createElement('mtable')
        rows = [ r for r in self if isinstance(r,MathTableRowNode) ]

        if self.hasAttr('class'):
            node.setAttribute('class',self.getAttr('class'))
        node.setAttribute('cellhalign',' '.join(self.__halign))
        node.setAttribute('cellvalign',' '.join(self.__valign))

        rowlen = len(self.__halign)

        for r in rows:
            n = r.toXML(doc,rowlen)
            if n is not None:
                node.appendChild(n)
        
        return node

class MathVectorNode(_MathNode):
    nodeName = 'mvector'
    macroMode = MacroMode.Math
    contIter = ' <mtd>* '
    acceptAttrs = Attrs([ Attr('id'), 
                    Attr('class'),
                    Attr('cellvalign'),
                    Attr('cellhalign'), ])

class MathTableRowNode(_MathNode):
    nodeName = 'mtr'
    macroMode = MacroMode.Math
    contIter = ' <mtd>* '
    def __init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line):
        _MathNode.__init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line)
        self.__len = None
    def __len__(self):
        return self.__len
    def end(self,filename,line):
        self.__len = len([ cell for cell in self if isinstance(cell,MathTableCellNode) ])
        
    def toXML(self,doc,rowlen):
        node = doc.createElement(self.nodeName)
        cells = [ r for r in self if isinstance(r,MathTableCellNode) ]
        cells += [ None ] * (rowlen - len(cells))

        for c in cells:
            n = c.toXML(doc)
            if n is not None:
                node.appendChild(n)
        return node


class MathTableCellNode(_MathNode):
    nodeName = 'mtd'

######################################################################
#  Root Node classes
######################################################################

class _RootNode:
    rootElementlass = None
    rootElement      = None

    def __init__(self,manager,parent,cmddict,nodeDict,attrs,filename,line):
        self.documentElement = None
        self.__cmddict       = cmddict
        self.__nodeDict      = nodeDict
        self.__parent        = parent
        self.__manager       = manager

        assert isinstance(nodeDict,dict)
        ## Create a new XML parser and read the fileanme 
    def newChild(self,name,attrs,filename,line):
        if name == self.rootElement:
            if self.documentElement is not None:
                raise NodeError('Duplicate root element <%s> at %s:%d' % (name,self.rootElementClass.nodeName,filename,line))

            self.documentElement = self.rootElementClass(self.__manager,
                                                         self.__parent,
                                                         self.__cmddict, 
                                                         self.__nodeDict, 
                                                         attrs, 
                                                         filename, 
                                                         line)
            return self.documentElement
        else:
            raise NodeError('Invalid element <%s>. Expected <%s> at %s:%d' % (name,self.rootElement,filename,line))
    def handleText(self,data,filename,line):
        pass

    def endOfElement(self,file,line):
        self.end(file,line)
    def end(self,file,line):
        assert self.documentElement is not None 

class DocumentRoot(_RootNode):
    rootElementClass = DocumentNode
    rootElement      = 'sdocml'
    nodeName         = 'sdocml'
    contIter         = _SectionNode.contIter
    
    comment = None
    examples = []
    acceptAttrs = Attrs([])
    macroMode = MacroMode.Text
        
    def __init__(self,manager,parent,cmddict,nodeDict,filename,line):
        _RootNode.__init__(self,manager,parent,cmddict,nodeDict,None,filename,line)

    def toXML(self):
        impl = xml.dom.minidom.getDOMImplementation()
        doc = impl.createDocument(None, 'sdocmlx', None)
        self.documentElement.toXML(doc,doc.documentElement)
        return doc.documentElement
        

class ExternalSectionRoot(_RootNode):
    rootElementClass = _SectionNode
    rootElement      = 'section'
    def __init__(self,manager,parent,cmddict,nodeDict,attrs,file,line):
        _RootNode.__init__(self,manager,parent,cmddict,nodeDict,attrs,file,line)
        self.__attrs = attrs
    def newChild(self,name,attrs,filename,line):
        # Note this is a hack; we wish to use attributes from the element that included the section, not from the root element in the included file.
        return _RootNode.newChild(self,name,self.__attrs,filename,line)

class ExternalDefineRoot(_RootNode):
    rootElementClass = DefinesNode
    rootElement      = 'defines'

    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 file,
                 line):
        _RootNode.__init__(self,manager,parent,cmddict,nodeDict,None,file,line)

class Manager:
    def __init__(self,
                 conds={},
                 incpaths=[],
                 maxsectdepth=None,
                 dtdpaths=[]):
        self.__conds = dict([ (k,bool(v)) for k,v in conds.items()])
        self.__conds['true'] = True
        self.__conds['false'] = False
        self.__incpaths = incpaths
        self.__maxsectdepth = maxsectdepth
        self.__entityresolver = entityhandler(dtdpaths)

        self.__ids = {} # all IDs necountered
        self.__reqids = [] # ID references encountered

    def getCiteRefs(self):
        #print  [ (k,n.getAttr('type')) for (k,n) in self.__reqids ]
        return [ (k,n) for (k,n) in self.__reqids if n.getAttr('type') == 'cite' ] 

    def expandURL(self,url,baseurl):
        return self.findFile(url,baseurl)
    def getEntityResolver(self):
        return self.__entityresolver

    def readFrom(self,filename,encoding):
        realurl = filename
        try:
            msg('Reading from external data source %s' % realurl) 
            if encoding.lower() == 'utf-8':
                text = open(realurl).read().decode('utf-8')
            elif encoding.lower() == 'ascii':
                text = open(realurl).read().decode('ascii')
            else:
                raise NodeIncludeError("Invalid incoding of file %s" % realurl)
            return text
        except IOError:
            raise NodeIncludeError("Failed to read file %s" % realurl) 
    
    def saveId(self,key,item):
        if self.__ids.has_key(key):
            olditem = self.__ids[key]
            raise XMLIdError('Duplicate ID "%s" originally defined at %s:%d, redefined at %s:%d' % (key,olditem.pos[0],olditem.pos[1],item.pos[0],item.pos[1]))
        else:
            self.__ids[key] = item
    def refId(self,key,src):
        self.__reqids.append((key,src))
    def findFile(self,url,baseurl):
        proto,server,path,r0,r1,r2 = urlparse.urlparse(url)
        if proto:
            if proto != 'file':
                log(self.__url)
                raise NodeError('Only local includes allowed, got "%s"' % attrs['url'])
            else:
                return path
        else:
            #assert baseurl
            #print "look for: %s" % path
            if baseurl is not None:
                base = urlparse.urlparse(baseurl)
                fullname = os.path.join(os.path.dirname(base[2]),path)
                #print "check: %s" % fullname
                if os.path.exists(fullname):
                    return fullname

            for p in self.__incpaths:
                fullname = os.path.join(p,path)
                #print "check: %s" % fullname
                if os.path.exists(fullname):
                    return fullname
            raise NodeError('File "%s" not found' % url) 
    def checkSectionDepth(self,d):
        return self.__maxsectdepth is None or self.__maxsectdepth >= d

    def checkIdRefs(self):
        errs = []
        for k,src in self.__reqids:
            if not self.__ids.has_key(k):
                err('Missing ID: "%s" referenced at %s:%d' % (k,src.pos[0],src.pos[1]))
                errs.append('Missing ID: "%s" referenced at %s:%d' % (k,src.pos[0],src.pos[1]))
        return errs


    def evalCond(self,value,filename,line):
        try:
            return cond.eval(value,self.__conds)
        except cond.CondError,e:
            raise CondError('%s at %s:%d' % (e,filename,line))

        condregex = re.compile('|'.join([r'\?(?P<isdef>[a-zA-Z0-9@:_\.\-\*]+)',
                                         r'(?P<not>!)',
                                         r'(?P<and>\+)',
                                         r'(?P<or>\|)',
                                         r'(?P<xor>/)',
                                         r'(?P<lpar>\()',
                                         r'(?P<rpar>\))',
                                         r'(?P<key>[a-zA-Z0-9@:_\.\-\*]+)',
                                         r'(?P<space>\s\+)']))
        pos = 0

        root = []
        stack = [root]

        while pos < len(value):
            o = condregex.match(value,pos)    
            if o is not None:
                pos = o.end(0)
                if   o.group('space'):
                    pass
                elif o.group('isdef'):
                    stack[-1].append(CondIsDef(o.group('isdef')))
                elif o.group('not'): stack[-1].append(Cond.Not)
                elif o.group('and'): stack[-1].append(Cond.And)
                elif o.group('or'):  stack[-1].append(Cond.Or)
                elif o.group('xor'): stack[-1].append(Cond.Xor)
                elif o.group('key'):
                    stack[-1].append(CondTerm(o.group(0)))
                elif o.group('lpar'):
                    stack.append(CondExp())
                elif o.group('rpar'):
                    if len(stack) <= 1:
                        raise CondError('Unbalanced conditional expression "%s" at %s:%d' % (value,filename,line))
                    else:
                        top = stack.pop()
                        stack[-1].append(top)
            else:
                raise CondError('Invalid condition key "%s" at %s:%d' % (value,filename,line))

        conds = self.__conds
        def evalc(exp):
            if isinstance(exp,CondTerm):
                if conds.has_key(exp):
                    return conds[exp]
                else:
                    raise CondError('Undefined condition key "%s" at %s:%d' % (exp,filename,line))
            elif isinstance(exp,CondIsDef):
                return conds.has_key(exp)
            else:
                oprs = dict([ (v,v) for v in exp if isinstance(v,CondOpr) and v is not Cond.Not]).keys()
                if len(oprs) > 1:
                    raise CondError('Invalid condition key "%s" at %s:%d' % (value,filename,line))
                l = exp
                res = []
                while l:
                    head = l.pop(0)
                    if head is Cond.Not:
                        if not l:
                            raise CondError('Invalid condition key "%s" at %s:%d' % (value,filename,line))
                        res.append(not evalc(l.pop(0)))
                    elif isinstance(head,CondTerm) or isinstance(head,CondExp):
                        res.append(evalc(head))
                    else:
                        raise CondError('Invalid condition key "%s" at %s:%d' % (value,filename,line))
                    if l and not (l.pop(0) is oprs[0]):
                        raise CondError('Invalid condition key "%s" at %s:%d' % (value,filename,line))
                if len(res) <= 1:
                    return res[0]
                else:
                    opr = oprs[0]
                    if   opr is Cond.Or:
                        return reduce(operator.__or__,res)
                    elif opr is Cond.And:
                        return reduce(operator.__and__,res)
                    elif opr is Cond.Xor:
                        return reduce(operator.__xor__,res)
                    else:
                        print "OPR = ",opr
                        assert 0
        
        res = evalc(root)
        return res

    def getCond(self,key):
        return self.__conds[key]

######################################################################
#  Node dictionary      
######################################################################
#from BibNode import *

globalNodeDict =  { 'sdocml'   : DocumentRoot,
                    'section'  : SectionNode,
                    'bibliography' : BibliographyNode,
                    'bibitem'  : BibItemNode,

                    'head'     : HeadNode,
                    'abstract' : AbstractNode, 
                    'defines'  : DefinesNode,
                    'incdef'   : IncDefNode,
                    'def'      : DefNode,
                    'defenv'   : DefEnvNode,
                    'e'        : DefElementNode,
                    'attr'     : DefElementAttrNode,
                    'd'        : DefDataNode,
                    'c'        : DefMacroRefNode,
                    'dictentry': DictEntryNode, # Experimental!!!
                    'lookup'   : LookupNode, # Experimental!!!
                    'arg'      : DefMacroArgNode,
                    'title'    : TitleNode,
                    'date'     : DateNode,
                    'authors'  : AuthorsNode,
                    'author'   : AuthorNode,
                    'firstname': AuthorFirstNameNode,
                    'lastname' : AuthorLastNameNode,
                    'email'    : AuthorEmailNode,
                    'institution': AuthorInstitutionNode,
                    'name'     : AuthorInstitutionNameNode,
                    'address'  : AuthorInstitutionAddressNode,

                    'desc'     : DescriptionNode,
                    
                    # Plain text elements
                    'em'       : EmphasizeNode,
                    'tt'       : TypedTextNode,
                    'bf'       : BoldFaceNode,
                    'sc'       : SmallCapsNode,
                    'span'     : SpanNode,
                    'br'       : BreakNode,
                    'nx'       : NoExpandInlineNode,

                    'xxsmall'  : dummy('xxsmall'),
                    'xsmall'   : dummy('xsmall'),
                    'small'    : dummy('small'),
                    'large'    : dummy('large'),
                    'xlarge'   : dummy('xlarge'),
                    'xxlarge'  : dummy('xxlarge'),
                    'larger'   : dummy('larger'),
                    'smaller'  : dummy('smaller'),

                    'font'     : FontNode,

                    'ref'      : ReferenceNode,
                    'linktext' : LinkTextNode,
                    'href'     : HyperRefNode,
                    'a'        : AnchorNode,

                    # Structural text elements
                    'ilist'    : ItemListNode,
                    'li'       : ListItemNode,
                    'dlist'    : DefinitionListNode,
                    'dt'       : DefinitionTitleNode,
                    'dd'       : DefinitionDataNode,

                    'center'   : CenterNode,
                    'flushleft' : FlushLeftNode,
                    'flushright' : FlushRightNode,

                    'table'    : TableNode,
                    'col'      : TableColumnNode, 
                    'tr'       : TableRowNode,
                    'td'       : TableCellNode,
                    'float'    : FloatNode,
                    'floatbody': FloatBodyNode,
                    'caption'  : FloatCaptionNode,
                    'noexpand' : NoExpandNode,
                    'pre'      : PreformattedNode,
                    'div'      : DivNode,


                    # Math stuff
                    ## Environments
                    'm'        : InlineMathNode,
                    'math'     : MathEnvNode,
                    'eqnarray' : MathEqnArrayNode,
                    'eqn'      : MathEqnNode,
                    ## Elements
                    "mroot"    : MathRootNode,
                    "msqrt"    : MathSquareRootNode,
                    'mfenced'  : MathFencedNode,
                    'mfont'    : MathFontNode, # not mathML
                    'mfrac'    : MathFracNode,
                    'mi'       : MathIdentifierNode,
                    'mn'       : MathNumberNode,
                    'mo'       : MathOperatorNode,
                    'mrow'     : MathRowNode,
                    'msub'     : MathSubscriptNode,
                    'msubsup'  : MathSubSuperscriptNode,
                    'msup'     : MathSuperscriptNode,
                    'mtable'   : MathTableNode,
                    'mtd'      : MathTableCellNode,
                    'mtext'    : MathTextNode,
                    'mtr'      : MathTableRowNode,
                    'mvector'  : MathVectorNode,
                    
                    'img'      : ImageNode,
                    'imgitem'  : ImageItemNode,

                    # Administrative elements
                    'warning'  : WarningNode,
                    'error'    : ErrorNode,
                    'note'     : NoteNode,

                    }
