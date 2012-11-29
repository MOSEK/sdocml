"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/

    
    Copyright (c) 2009,2010 Mosek ApS 
"""
from   UserDict import UserDict
from   UserList import UserList

from   EvHandler import AlternativeSAXHandler, dtdhandler, entityhandler, Pos
from   bibtexml import BibDB

from util import *

import urlparse
import xml.sax
import sys,os,operator
import Iters
import syntax
import cond

import re
import logging

import macro
from macro import DelayedText, DelayedMacro,DelayedEnvironment,DelayedSubScript, DelayedSuperScript, DelayedElement,DelayedGroup,DelayedTableContent,ResolvedMacro,Placeholder,Group,MacroParser

log = logging.getLogger("SDocML Expander")
#log.setLevel(logging.ERROR)
msg = log.info


ERROR_OCCURRED = False # Not nice, but it works.
def err(msg):
    global ERROR_OCCURRED
    log.error(msg)
    
def dbg(msg,*args):
    if args:
        log.debug(msg % args)
    else:
        log.debug(msg)

def debug(*args):
    pass

simpleTextNodeList = [ 'em','tt','bf','sc','font','nx','span','br', 'note' ]
structTextNodeList = [ 'ilist','dlist','div','table','float','img','noexpand','pre','center','flushleft','flushright' ]
linkNodeList       = [ 'a','ref','href' ]
mathEnvNodeList    = [ 'math','m','eqnarray' ]
textNodeList       = [ 'ilist','dlist','table','a','ref','href','float', 'img' ] + simpleTextNodeList + mathEnvNodeList

mathNodeList       = [ 'mrow','msup','msub','msubsup','mfenced', 'mi','mo','mn','mtable', 'mvector', 'mfont', 'mtext', 'mfrac', 'mroot','msqrt' ]

mathFonts          = [ 'mathbb','mathcal','mathtt','mathrm','mathbf','mathit','mathfrac' ]
textFonts          = [ 'tt','rm','sc','sans','serif' ]

_simpleTextNodes = ' '.join([ '<%s>' % i for i in simpleTextNodeList ])
_structTextNodes = ' '.join([ '<%s>' % i for i in structTextNodeList ])
_linkNodes       = ' '.join([ '<%s>' % i for i in linkNodeList ])
_mathEnvNodes    = ' '.join([ '<%s>' % i for i in mathEnvNodeList ])
_mathNodes       = ' '.join([ '<%s>' % i for i in mathNodeList ])

def lineiter(s):
    p = 0
    while True:
        pt = s.find('\n',p)
        if pt < 0:
            break
        else:
            yield s[p:pt+1]
            p = pt+1
    yield s[p:]

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

######################################################################
#  Helper functionality
######################################################################

def escape(s):
    def repl(o):
        if o.group(0) == '\\>': return '>'
        elif o.group(0) == '\\<': return '<'
        elif   o.group(0) == '<': return '&lt;'
        elif o.group(0) == '>': return '&gt;'
        elif o.group(0) == '&': return '&amp;'
    return re.sub(r'\\\>|\\\<|<|>|&',repl,s)
    #return re.sub(r'<|>|&',repl,s)

def xescape(s):
    
    def repl(o):
        if o.group(0) == '\\>': return '>'
        elif o.group(0) == '\\<': return '<'
        elif   o.group(0) == '<': return '&lt;'
        elif o.group(0) == '>': return '&gt;'
        elif o.group(0) == '&': return '&amp;'
        else:                   return '&#%d;' % ord(o.group(0))
    text =  re.sub(u'\\\>|\\\<|<|>|&|[\u0080-\u8000]',repl,s)
    #text =  re.sub(u'<|>|&|[\u0080-\u8000]',repl,s)
    return text

def unescape(s):
    #please do rewrite if you are more knowledge about regexs then me
    def quot(o):
        if o.group(1)=='&quot;':return o.group(0).replace(o.group(1),'\"')
    s = re.sub(r'\\\&lt;.*?(&quot;).*?\\\&gt;',quot,s)
    def amp(o):
        if o.group(1) == '&amp;':return o.group(0).replace(o.group(1),'&')
    s = re.sub(r'\\\&lt;.*?(&amp;).*?\\\&gt;',amp,s)
    def repl(o):
        if o.group(0) == '\\&gt;': return '>'
        elif o.group(0) == '\\&lt;': return '<'
    return re.sub(r'\\\&gt;|\\\&lt;',repl,s)
    

class Attr:
    defaultDescr = {
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



class Attrs(UserDict):
    def __init__(self,items={}):
        UserDict.__init__(self,[ (item.name, item) for item in items])
    def defaultValues(self):
        return dict([ (item.name, item.default) for item in self.values()])

        

######################################################################
# Macro expansion helper functionality
######################################################################
#class UnexpandedItem: pass

class ExpandedList(UserList): pass

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
class ExpectScriptArg:
    def __init__(self,base,tp):
        self.pos = base.pos
        assert isinstance(self.pos,utils.Position)
        if base.__class__ is DelayedGroup:
            base = ResolvedSubSuperScript(base.pos,base)
        elif not isinstance(base,ResolvedSubSuperScript):
            assert 0
        self.base = base
        self.__tp = tp
    def apply(self,arg):
        if self.__tp == '^':
            if self.base.superscr is None:
                self.base.superscr = arg
            else:
                raise MacroError('%s: Duplicate superscript argument' % self.base.pos)
        else:
            if self.base.subscr is None:
                self.base.subscr = arg
            else:
                raise MacroError('%s: Duplicate subscript argument' % self.base.pos)
        return self.base
        


######################################################################
# 
######################################################################



#class DontAcceptNoneList(UserList):
#    def append(self,item):
#            assert item is not None
#            assert not isinstance(item,UnexpandedItem)
#            UserList.append(self,item)
class CheckedAppendError(Exception): pass

class CheckedAppend:
    def __init__(self,check,data):
        self.__check = check
        self.data = data
    def __len__(self):
        return len(self.data)
    def pop(self):
        return self.data.pop()
    def append(self,item):
        if not  self.__check(item):
            raise CheckedAppendError("Failed check: %s" % repr(item))
        self.data.append(item)
    def __iter__(self):
        return iter(self.data)
    def __getitem__(self,key):
        return self.data.__getitem__(key)
    def __delitem__(self,key):
        self.data.__delitem__(key)
    def extend(self,items):
        for i in items:
            self.append(item)
    def __repr__(self):
        #return 'CheckedAppend(%s)' % (self.data.__class__.__name__)        
        return 'CheckedAppend(%s)' % (repr(self.data))

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

    def __init__(self,
                 manager,
                 parent,
                 macroDict, # dictionary of available macros
                 nodeDict,  # dictionary of all known element names ??
                 attrs, # None or a dictionary of attributes
                 pos):
        #print "START :: <%s> @ %s" % (self.nodeName,pos)
        self.pos = pos 
        self.__manager = manager

        self.__sealed   = False # disallow any more content
        self.__closed   = False
        
        self.__cmddict  = macroDict
        self.__id       = None
        self.__ns       = None # do we even use this?
        self.__parent   = parent
        self.__nodeDict = nodeDict
        self.__attrs    = {}
        self.__data     = ""
        self.__macroHandler = None

        class NodeContentChecker(CheckedAppend):
            def __init__(self,data):
                CheckedAppend.__init__(self,lambda item: item is not None,data)
        self.__content  = NodeContentChecker(XList())
        #self.__cstack   = [ ContentManager(ExpandManager(self.__cmddict,self), self.__cmddict) ] 
        class DelayedItemChecker(CheckedAppend):
            def __init__(self,data):
                CheckedAppend.__init__(self,lambda item: isinstance(item,macro._DelayedItem),data)
        class NotNodeChecker(CheckedAppend):
            def __init__(self,data):
                CheckedAppend.__init__(self,lambda item: not isinstance(item,Node),data)
        self.__cstack   = NotNodeChecker( [ DelayedItemChecker([]) ])
        
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
            try:
                manager.saveId(attrs['id'],self)
            except XMLIdError:
                err('%s: Duplicate ID "%s"' % (pos,attrs['id']))
                raise
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
        
        self.__attrs.update(self.acceptAttrs.defaultValues())
        if attrs is not  None:
            for k,v in attrs.items():
                if self.__attrs.has_key(k):
                    self.__attrs[k] = v
                elif k == 'xmlns' or 'trace' in k:
                    pass
                else:
                    raise NodeError('Invalid attribute "%s" in <%s> at %s' % (k,self.nodeName,pos))

    def getCmdDict(self):
        returnee = None
        try:
            returnee = self.__cmddict
        except AttributeError:
            print "Warning:<%s> doesnt have a cmddict"%(self.nodeName)
        return returnee
    
    def seal(self):
        self.__sealed = True
    def __iter__(self):
        return iter(self.__content)
    def __len__(self):
        return len(self.__content)
    def asList(self):
        res = []
        for i in self:
            if isinstance(i,basestring):
                res.append(i)
            else:
                res = res + i.asList()
        return res
   
    ##\brief Append a new child, append it and return it. This is called by the
    #        SAX parser when an tag-open event occurs.
    # \note We create the node using the dictionary from _this_ Node, not from
    # the node that actually will contain it. We assume that the dictionary is
    # static so it's should be correct.

    def getMacroDefs(self):
        return self.__cmddict.items()

    def evaluate(self,name,pos):
        start = pos
        data = self.__data
        self.__data = ""
        if not data:
            return
        assert pos is not  None
        if  self.macroMode in [ MacroMode.Invalid, MacroMode.NoExpand ]:
            #dgb('<%s>.handleRawText: %s' % (self.nodeName,repr(data)))
            data = self.__macroHandler.handleRawText(data)
            self.append(data)
        elif self.macroMode in [ MacroMode.Text, MacroMode.Math ]:
            (data,pos) = self.__macroHandler.handleText(self.__cmddict,data,pos)
            self.append(data)
        else:
            assert 0 
            
    def endChildElement(self,name,pos):
        """
        End current child element.
        """
        pass

    def startElement(self,name,attrs,pos):
        print self.__nodeDict
        try:
            nodecon = self.__nodeDict[name]
        except KeyError:
            raise NodeError('Unknown element <%s> in <%s> at %s' % (name,self.nodeName, pos))
        try:
            node = nodecon(self.__manager,self,self.__cmddict,self.__nodeDict,attrs,pos)
        except TypeError:
            print "Failed to instantiate: <%s>" % name
            raise
        return node 
    def macroHandler(self,macrohandler):
        self.__macroHandler = macrohandler

    def startChildElement(self,name,attrs,pos):
        dbg('startChildElement: %s' % name)
        dbg(attrs)
        try:
            nodecon = self.__nodeDict[name]
        except KeyError:
            print self.__nodeDict
            raise NodeError('Unknown element <%s> in <%s> at %s' % (name,self.nodeName, pos))
        try:
            node = nodecon(self.__manager,self,self.__cmddict,self.__nodeDict,attrs,pos)
        except TypeError:
            print "Failed to instantiate: <%s>" % name
            raise
        #node = self.startElement(name,attrs,pos)
        if self.__macroHandler == None:
            self.__macroHandler = MacroParser()
        node.macroHandler(self.__macroHandler)
        self.append(node)
        return node


    ##\brief Handle text. Called by the SAX parser to parse a text string.
    def handleText(self,data,pos):
        if(data.split()):
            self.__data = self.__data + data

    def append(self,item):
        #if len(self.__cstack) > 1:
        #    #dgb('Append item. Cstack = \n\t%s' % '\n\t'.join([ repr(i) for i in self.__cstack]))
        #    pass
        #assert len(self.__cstack) == 1
        assert not self.__closed
        if   self.__sealed:
            raise NodeError('%s: Content not allowed in <%s>' % (self.pos,self.nodeName, self.pos))
            #raise NodeError("Content not allowed in <%s> at %s" % (self.nodeName, self.pos))
        elif isinstance(item,Node) or isinstance(item,basestring):
            if isinstance(item,Node) and item.metaElement:
                pass # Allowed everywhere, ignored
            else:
                try:
                    self.__content.append(item)
                except TypeError:
                    raise NodeError('%s: Failed to append item to node <%s>'%
                    (self.pos,self.nodeName))
        else:
            print item,repr(item)
            #assert 0

    def handleRawText(self,data,pos):
        """
        Handle text without expansion.
        """
        if self.macroMode == MacroMode.Invalid:
            if data.strip():
                #raise NodeError('Text not allowed in <%s> at %s' % (self.nodeName,pos))
                raise NodeError('%s: Text not allowed in <%s>' % (pos,self.nodeName))
            else:
                # Just ignore.
                pass
        else:
            self.append(data)


    def getID(self):
        return self.__id
    def getNS(self):
        return self.__ns

    def hasAttr(self,key):
        return self.__attrs.has_key(key) and self.__attrs[key] is not None
    def getAttr(self,key):
        return self.__attrs[key]
    def attrs(self):
        return iter(self.__attrs.items())

    def setXMLattrs(self,node):
        for k,v in self.__attrs.items():
            if v is not None:
                node.setAttribute(k,v)
    def end(self,pos):
        pass

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
                #Rewrite
                for item in p:
                    node.appendChild(item)
                #par = doc.createElement('p')
                #node.appendChild(par)
                #for item in p:
                #    assert not isinstance(item,list)
                #    par.appendChild(item)
        

    def toXML(self,doc,node=None):
        '''
        Convert the node to XML. Return either the generated node or None.
        '''
        if self.expandElement:
            if node is None:
                node = doc.createElement(self.nodeName)
            if self.structuralElement or self.mathElement:
                for item in self:
                    if isinstance(item,basestring):
                        node.appendChild(doc.createTextNode(item))
                    else:
                        n = item.toXML(doc)
                        assert not isinstance(n,list)
                        if n is not None:
                            node.appendChild(n)
            else:
                lst = []
                for item in self:
                    if isinstance(item,basestring):
                        #make it into nodes again.
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
                            assert not isinstance(n,list)
                            if n is not None:
                                node.appendChild(n)
                        else:
                            text = re.sub(r'\s+',' ',''.join(item))
                            node.appendChild(doc.createTextNode(text))
            for k,v in self.__attrs.items():
                if v is not None and k not in [ 'macroexpand' ]:
                    node.setAttribute(k,v)
            if self.traceInfo and not isinstance(self.pos,int):
                if self.pos is not None and self.pos.filename is not None and self.pos.line is not None:
                    node.setAttribute("xmlns:trace","http://odense.mosek.com/emotek.dtd")
                    node.setAttribute('trace:file',str(self.pos.filename))
                    node.setAttribute('trace:line',str(self.pos.line))
        assert not isinstance(node,list)
        return node

    def __str__(self):
        return '<%s%s>' % (self.nodeName,' '.join([' %s="%s"' % itm for itm in self.__attrs.items() if itm[1]]))
        if self.hasAttr('id'):
            return '<%s id="%s" @ %s>' % (self.nodeName,self.getAttr('id'),self.pos.brief() )
        else:
            return "<%s @ %s>" % (self.nodeName, self.pos.brief())

    __repr__ = __str__

class _MathNode(Node):
    macroMode = MacroMode.Math
    contIter = ' [ T %s ]* ' % _mathNodes
    mathElement = True
  
    #__init__ = Node.__init__
######################################################################
# Meta nodes for the reparsing
######################################################################

class BodyNode(Node):
    comment = 'this comment shouldnt be shown'
    nodeName = 'body'
    macroMode = MacroMode.NoExpand
    contIter = ' T '


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
    acceptAttrs = Attrs([Attr('key',required=True,descr="The key under which the text is saved.")])
    macroMode   = MacroMode.NoExpand
    contIter = ' T '
    structuralElement = True

    def __init__(self, manager, parent, cmddict, nodeDict, attrs, pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        self.__cmddict = cmddict
    def end(self,pos):
        key = self.getAttr('key')
        self.value = u''.join(self)
        try:
            self.__cmddict.dictSet(key,self)
        except KeyError:
            e = self.__cmddict.dictLookup(key)
            raise NodeError('%s: Key "%s" already defined at "%s"' % (self.pos, key, e.pos))
        Node.end(self,pos)

class IncDefNode(Node):
    comment     = '''
                    Include an external file containing macro definitions. This
                    file must be a valid XML file having the TeXML
                    \\tagref{defines} as the document element.
                    It works as if the definitions from the included file was inserted
                    directly into the context where the inclusion appears, i.e.
                    there must be no local name clashes.
                  '''
    nodeName    = 'incdef'
    acceptAttrs = Attrs([Attr('url',descr='The address of the definition file to incude.'),
                         Attr('type',default='text/xml-defines')])
    contIter    = ''
    structuralElement = True
    
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        self.__cmddict = cmddict
        #self.__url = urlparse.urlparse(attrs['url'])
        self.__url = attrs['url']
        filename = pos.filename
        fullname = manager.findFile(self.__url,filename)
        if 0:
            proto,server,path,r0,r1,r2 = self.__url
            if proto and proto != 'file':
                log(self.__url)
                raise NodeError('Only local includes allowed, got "%s"' % attrs['url'])

            basepath = os.path.dirname(filename)
            fullname = os.path.join(basepath,path) # currently only relative paths allowed. No checking done
        P = xml.sax.make_parser()
        N = ExternalDefineRoot(manager,self,self.__cmddict,nodeDict,Pos(fullname,1))
        h = AlternativeSAXHandler(fullname,N,manager) 
        P.setContentHandler(h)
        P.setEntityResolver(manager.getEntityResolver())

        try:
            msg("Parse external definitions %s (%s)" % (self.__url,fullname))
            P.parse(fullname)
        except Exception,e:
            import traceback
            traceback.print_exc()
            raise NodeError('%s: Failed to parse file "%s":\n\t%s' % (pos,fullname,str(e)))
    def end(self,pos):
    #    print "incdef nod is being terminated"
        pass

class DefElementNode(Node):
    nodeName    = 'e'
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
    acceptAttrs = Attrs([ Attr('n',descr='The name of the element')])
    macroMode   = MacroMode.Invalid
    contIter    = ' <attr>* [ <e> <d> <c> <lookup> ]*'
    structuralElement = True
   
    def getName(self):
        return self.getAttr('n')

    def asList(self):
        returnee = ["\<"+self.getName()]
        end = ["\</"+self.getName()+"\>"]
        for i in self:
            if isinstance(i,basestring):
                returnee.append(i)
            elif isinstance(i,DefElementAttrNode):
                treeList = i.asList()
                returnee.extend(treeList)
            else:
                if(not returnee[-1] == "\>"):
                    returnee.append("\>")
                treeList = i.asList()
                returnee.extend(treeList)
        #To ensure we are closing the node correctly
        ending = False
        for i in returnee:
            if i =="\>":
                ending = True
        if not ending:
            returnee.append("\>")
        returnee.extend(end)
        return returnee

    def asDef(self,res):
        attrs = {}
        body = []
        for i in self:
            if isinstance(i,DefElementAttrNode):
                attrs[i.getName()] = i.asDef([])
                #attrs[i.getName()] = [ attr.asDef([]) for attr in i ]
            else:
                body.append(i.asDef(DelayedGroup(self.pos)))
        r = DelayedElement(self.getAttr('n'),attrs,self.pos)
        r.extend(body)
        res.append(r)
        return res
    def end(self,pos):
        pass

    def len(self):
        count = 0
        for i in self:
            if isinstance(i,basestring):
                count = count +1
            else:
                count = count +i.len()
        return count
            
    
    def __repr__(self):
        return '<e n="%s"><\e>' % (self.getAttr('n'))
    

    
class _DefDataNode(Node):
    macroMode   = MacroMode.NoExpand
    contIter    = ' [ T <lookup> ]* '

    argre = re.compile(r'{{(?:(?P<intref>[0-9]+)|(?P<nameref>BODY|SUBSCRIPT|SUPERSCRIPT))}}')
    structuralElement = True

    def len(self):
        count =0
        for i in self:
            if isinstance(i,basestring):
                count = count +1
            else:
                count = count + i.len()
        return count

    def asList(self):
        returnee = []
        for i in self:
            if isinstance(i,basestring):
                text = i
                p = 0
                for o in self.argre.finditer(text):
                    if p < o.start(0):
                        returnee.append(text[p:o.start(0)])
                    p = o.end(0)
                    if   o.group('intref') is not None:
                        #returnee.append(macro.DelayedArgRef(int(o.group('intref')),self.pos))
                        returnee.append(macro.Placeholder(o.group('intref')))
                    else:
                        #returnee.append(macro.DelayedArgRef(o.group('nameref'),self.pos))
                        returnee.append(macro.Placeholder(o.group('nameref')))
                if p < len(text):
                    returnee.append(text[p:])
            else:
                pass
        return returnee
                
        if isinstance(self,LookupNode):
            return macro.MacroRef(returnee,None,None)
        elif isinstance(self,DefElementAttrNode):
            start = [self.getName() + "="].extend(returnee)
            return start
        return returnee



        
    def asDef(self,res):
        for i in self:
            if isinstance(i,basestring):
                text = i
                p = 0
                for o in self.argre.finditer(text):
                    if p < o.start(0):
                        res.append(macro.DelayedText(text[p:o.start(0)],self.pos))
                    p = o.end(0)
                    if   o.group('intref') is not None:
                        res.append(macro.DelayedArgRef(int(o.group('intref')),self.pos))
                    else:
                        res.append(macro.DelayedArgRef(o.group('nameref'),self.pos))
                if p < len(text):
                    res.append(macro.DelayedText(text[p:],self.pos))
            else:
                 i.asDef(res)
        return res

    #def end(self,pos):
    #    pass
        #try:
        #    self.__citer = Iters.parsedef(self.contIter)()
        #except Iters.SyntaxDefError,e:
        #    raise Iters.SyntaxDefError(unicode(e) + ' in %s' % self.nodeName)

        #else:
        #    p = 0
        #    text = ''.join(self)
        #    #print text
        #    for o in self.argre.finditer(text):
        #        if p < o.start(0):
        #            #print "+ %s" % text[p:o.start(0)]
        #            res.append(macro.DelayedText(text[p:o.start(0)],self.pos))
        #        p = o.end(0)
        #        if   o.group('intref') is not None:
        #            #print "+ arg#%d" % int(o.group('intref'))
        #            res.append(macro.DelayedArgRef(int(o.group('intref'))))
        #        else:
        #            #print "+ arg %s" % o.group('nameref')
        #            res.append(macro.DelayedArgRef(o.group('nameref')))
        #    if p < len(text):
        #        #print "+ %s" % text[p:]
        #        res.append(macro.DelayedText(text[p:],self.pos))
        #    
        #    #print "ret ",repr(res)
        #    return res
        #    

class DefDataNode(_DefDataNode):
    nodeName    = 'd'
    comment     = '''
                    Text entry in a macro definition. The content is pure text,
                    but the placeholders \{\{n\}\} where "n" is a number, and
                    \{\{BODY\}\} are expanded to the corresponding argument and the
                    environment content (for \\tagref{defenv} only).
                  '''

class LookupNode(_DefDataNode):
    nodeName = 'lookup'
    comment =   '''
                    The \\tag{lookup} looks up the dictionary entry made with \\tagref{dictentry}.
                '''

    examples = [("Define a macro performing lookup of the key ``XYZ'':",
                 '<def m="lookupXYZ"><d>The Value of XYZ is "<lookup>XYZ</lookup>"</d></def>'),
                ("Define a macro performing lookup of a key given as a macro argument:",
                 '<def m="lookup" n="1"><lookup>\\{\\{0\\}\\}</lookup></def>')]
    acceptAttrs = Attrs([])
    macroMode   = MacroMode.NoExpand
    contIter    = ' T '
   
    def __init__(self, manager, parent, cmddict, nodeDict, attrs, pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        self.__cmddict = cmddict

    def asDef(self,res):
        res.append(macro.DelayedLookup(self.pos, _DefDataNode.asDef(self,[])))
        #r = _DefDataNode.asDef(self,[])
        #res.append(macro.DelayedLookup(r))
        return res
    def len(self):
        count = 0
        for i in self:
            if isinstance(i,basestring):
                count = count +1
            else:
                count = count + i.len()
        return 0

class DefElementAttrNode(_DefDataNode):
    comment     = """
                  Defines an attribute value for an element specification in a macro.
                  The content must be pure text, and the placeholders "\\{\\{0\\}\\}", "\\{\\{1\\}\\}"...  
                  can be used to refer to arguments 0, 1, ...
                  """
    nodeName    = 'attr'
    acceptAttrs = Attrs([Attr('n',descr='Name of the attribute.')])
    macroMode   = MacroMode.NoExpand
    
    def getName(self):
        return self.getAttr('n')

    def asList(self):
        returnee = [' '+self.getName()+"=\""]
        for i in self:
            if isinstance(i,basestring):
                text = i
                p = 0
                for o in self.argre.finditer(text):
                    if p < o.start(0):
                        returnee.append(text[p:o.start(0)])
                    p = o.end(0)
                    if   o.group('intref') is not None:
                        #returnee.append(macro.DelayedArgRef(int(o.group('intref')),self.pos))
                        returnee.append(macro.Placeholder(o.group('intref')))
                    else:
                        #returnee.append(macro.DelayedArgRef(o.group('nameref'),self.pos))
                        returnee.append(macro.Placeholder(o.group('nameref')))
                if p < len(text):
                    returnee.append(text[p:])
            else:
                returnee += i.asList()
        returnee.append("\"")
        return returnee

    @staticmethod
    def __checkarg(arg):
        for i in arg:
            if not isinstance(i,MacroEvent_NoExpandText):
                print "Invalid item: %s" % repr(i)
                raise MacroArgError('Elements are not allowed in attributes')

class DefMacroRefNode(Node):
    comment     = """
                  This can be used inside a macro definition to refer to another
                  defined macro. The macro referred need not be defined at the
                  point where the current macro is defined, but it must be
                  defined at the point where the current macro is expanded.
                  In other words: If the definition of a  macro \\\\A contains a
                  reference to a macro \\\\B, then \\\\B will expand to whatever
                  \\\\B is in the context where \\\\A is used.
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
                 pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        self.__name = self.getAttr('n')
        self.__subscr = None
        self.__superscr = None
    
    def len(self):
        count = 0
        for i in self:
            if isinstance(i,basestring):
                count = count +1
            else:
                count = count + i.len()
        return count

    def asList(self):
        returnee = [macro.Macroref(self.__name,self.__subscr,self.supscr)]
        for i in self:
            if isinstance(i,basestring):
                returnee.append(i)
            else:
                returnee = returnee +i.asList()
        return returnee

    def asDef(self,res):
        subscr = None
        superscr = None
        if self.__subscr is not None:
            subscr = self.__subscr.asDef()
        if self.__superscr is not None:
            superscr = self.__superscr.asDef()
        args = [ item.asDef(DelayedGroup(self.pos)) for item in self ]
        #print "MACRO ref:%s" % self.__name
        #print "  args = %s" % self,[i for i in self],len(args)
        #print "  args[0] =",args[0] if args else None
        res.append(macro.DelayedMacro(self.__name, self.pos, 
                                      args=args,
                                      subscr = subscr,
                                      superscr = superscr))
        return res

class DefMacroArgNode(Node):
    comment     = "Defines an argument for a macro reference."
    nodeName    = 'arg'
    macroMode   = MacroMode.NoExpand
    contIter    = ' [ <d> <e> <c> <lookup> ]* '
    structuralElement = True

    def len(self):
        count = 0
        for i in self:
            if isinstance(i,basestring):
                count = count +1
            else:
                count = count + i.len()
        return count

   # def asList(self):
   #     returnee = []
   #     for i in self:
   #         returnee.append(i.asList)
   #     return returnee

    def asDef(self,res):       
        for i in self:
            i.asDef(res)
        return res



class DefNode(Node):
    nodeName    = 'def'
    comment     = """
                  Define a new macro.

                  The placeholders "\\{\\{0\\}\\}", "\\{\\{1\\}\\}"... can be used in the body of the macro to
                  refer to argument 0, 1...
                  
                  In math mode subscript and superscript can be referred to
                  using "\\{\\{SUBSCRIPT\\}\\}" and "\\{\\{SUBSCRIPT\\}\\}".
                  """
    acceptAttrs = Attrs([Attr('m',descr="Name of the macro."),
                         Attr('n',default='0', descr='Number of arguments required by the macro.'),
                         Attr('subscript-arg',   default='no', descr='(yes|no) The macro accepts subscript. Only relevant in math mode.'),
                         Attr('superscript-arg', default='no', descr='(yes|no) The macro accepts superscript. Only relevant in math mode.') ])
    macroMode   = MacroMode.Invalid
    contIter    = ' <desc>? [ <d> <e> <c> <lookup>]* '
    structuralElement = True

    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        self.__cmddict = cmddict
        self.__name = attrs['m']
        self.__accept_subscr = attrs.has_key('subscript-arg')   and attrs['subscript-arg'].lower()   == 'yes'
        self.__accept_supscr = attrs.has_key('superscript-arg') and attrs['superscript-arg'].lower() == 'yes'
        self.__descr = None
        self.macro = None 
    
    def acceptsSubscript(self):
        return self.__accept_subscr
    def acceptsSuperscript(self):
        return self.__accept_supscr

    def getDescr(self):
        return self.__descr and ''.join(self.__descr)

    def macroName(self):
        return self.getAttr('m')

    def docExpandMacro(self):
        return ''.join(self.macro.asDoc([]))
 
    def nArgs(self):
        return int(self.getAttr('n'))
    def len(self):
        count = 0
        for i in self:
            if isinstance(i,basestring):
                count = count +1
            elif isinstance(i,DescriptionNode):
                pass
            else:
                count = count + i.len()
        return count
    def asList(self):
        treeList = []
        for i in self:  
            if isinstance(i,basestring):
                treeList.extend(i)
            elif isinstance(i,DescriptionNode):
                pass
            else:
                treeList = treeList +i.asList()
        return treeList

    def end(self,pos):
        try:
            self.__cmddict[self.__name] = self
        except KeyError:
            m = self.__cmddict[self.__name]
            raise MacroError('Macro "\\%s" at %s  already defined at %s' % (self.__name,pos,m.pos))
        length = self.len()
        body = macro.DelayedGroup(self.pos)
        self.__desc = None
        for d in self:
            if isinstance(d,DescriptionNode):
                self.__descr = d
            else:
                d.asDef(body)
        treeList = self.asList()
        self.macro = macro.Macro(self.__name, self.__desc,self.nArgs(),body,treeList,sub=self.__accept_subscr,sup=self.__accept_supscr)

    def __repr__(self):
        return 'macro(%s)' % self.__name
    def __str__(self):
        return 'macro(%s)' % self.__name

class DefEnvNode(Node):
    comment = """
    The defenv element defines an element that n requires arguments and contains a body text.
    In the body of the definition the placeholders "\\{\\{0\\}\\}", "\\{\\{1\\}\\}" ... refer to argument 0, 1 etc, and
    "\\{\\{BODY\\}\\}" refers to the content of the environment.

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
<defenv m="mylist" n="1"><e n="ilist"><attr n="class">\\{\\{0\\}\\}</attr><d>\\{\\{BODY\\}\\}</d></e></defenv>

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
    contIter    = ' <desc>? <defines>? [ <d> <e> <c> <lookup> ]* '
    structuralElement = True

    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 pos):
        self.__localdict = CommandDict() 
        Node.__init__(self,manager,parent,self.__localdict,nodeDict,attrs,pos)
        self.__name = attrs['m']
        self.__defs = None
        self.__cmddict = cmddict
        self.__descr = None

    def getDescr(self):
        return self.__descr and ''.join(self.__descr)

    def macroName(self):
        return self.getAttr('m')

    def docExpandMacro(self):
        return ''.join(self.env.asDoc([]))

    def nArgs(self):
        return int(self.getAttr('n'))

    def getDefs(self):
        return self.__defs

    def asList(self):
        treeList = []
        for i in self:
            if isinstance(i,basestring):
                treeList.extend(i)
            elif(isinstance(i,DescriptionNode) or isinstance(i,DefinesNode) or
                isinstance(i,DefElementAttrNode)):
                pass
            else:
                treeList = treeList +i.asList()
        return treeList

    def end(self,pos):
        try:
            self.__cmddict[self.__name] = self
        except KeyError:
            m = self.__cmddict[self.__name]
            raise MacroError('%s: Macro "\\%s"  already defined at %s' % (pos,self.__name,m.pos))
        body = macro.DelayedGroup(self.pos)
        for d in self:
            dcls = d.__class__
            if   dcls is DescriptionNode:
                self.__descr = d
            elif dcls is DefinesNode:
                self.__defs = d
            else:
                d.asDef(body)
        desc = self.__descr
        treeList = self.asList()
        self.env =macro.Environment(self.__name,desc,self.__localdict,self.nArgs(),None, body,treeList)

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
                 pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        #print "Defines node @ %s" % pos
        self.__cmddict = cmddict
    def append(self,item):
        return Node.append(self,item)
    def end(self,pos):
        #print "Defines end @ %s. dict = %s" % (pos,self.__cmddict)
        pass


def SectionNode(manager,parent,cmddict,nodedict,attrs,pos):
    if attrs.has_key('url'):
        filename = pos.filename
        url = urlparse.urlparse(attrs['url'])
        fullpath = manager.findFile(attrs['url'],filename)

        P = xml.sax.make_parser()
        N = ExternalSectionRoot(manager,parent, cmddict,nodedict,attrs,pos)
        h = AlternativeSAXHandler(fullpath,N,manager) 
        P.setContentHandler(h)
        P.setEntityResolver(manager.getEntityResolver())
        if 1: # try:
            msg("Parse external section %s (%s)" % (attrs['url'],fullpath))
            P.parse(fullpath)
        else: # except Exception,e:
            import traceback
            traceback.print_exc()
            raise NodeError('%s: Failed to parse file "%s"' % (pos,path))
        return N.documentElement
    else:
        return _SectionNode(manager,parent,cmddict,nodedict,attrs,pos) 

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
                         Attr('url',descr='Adderess of the external bibliography database to use.')])
    #contIter    = ' <head>  <bibitem> * '
    contIter    = ' <bibitem> * '

    def __init__(self, manager, parent, cmddict, nodeDict, attrs, pos):
        _SectionBaseElement.__init__(self,manager,parent,CommandDict(cmddict),nodeDict,attrs,pos)
        self.__bibdb = None
        self.__cmddict  = cmddict
        self.__nodedict = nodeDict
        self.__manager  = manager

        if self.hasAttr('url'):
            print "url... ", self.getAttr('url')
            biburl = 'file://' + manager.findFile(self.getAttr('url'),pos.filename).replace('\\','/')
            self.__bibdb = BibDB(biburl)
        else:
            self.__bibdb = None
        
        self.__genitems = []
        self.__pp = False # postprocessed
        self.__endpos = None
    
    def end(self,pos):
        self.__endpos = pos

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
                        Warning('No bib item found for "%s". Referenced at: \n\t%s' % (k, '\n\t'.join([ '%s' % n.pos for n in citedb[k]])))
                    else:
                        item = self.__bibdb[k]
                        
                        #print "-- Adding bibitem node for cite key %s" % k
                        node = BibItemNode(self.__manager,
                                           self,
                                           self.__cmddict,
                                           self.__nodedict,
                                           { 'key' : k,
                                             'id'  : k },
                                           self.__endpos)
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
                assert not isinstance(n,list)
                if n is not None:
                    node.appendChild(n)
                num += 1
                    
        for i in self.__genitems:
            n = i.toXML(doc)
            assert not isinstance(n,list)
            if n is not None:
                node.appendChild(n)

        assert not isinstance(node,list)
        return node

class BibItemNode(Node):
    nodeName = 'bibitem'
    contIter = ' [ T %s <href> <m> ] * ' % _simpleTextNodes
    acceptAttrs = Attrs([Attr('key',descr="The cite key."),
                         Attr('id'), # temporary hack
                          ])
    macroMode = MacroMode.Text
    paragraphElement = False 

    bibtemplate = { 'article'       : '${author}. ${title}. ${journal}$[month]{ ${month}}$[(number|volume)]{ ${number|volume}$[pages]{:${pages}}{}}{$[pages]{p. ${pages}}{}}.$[note]{ ${note}}',
                    'book'          : '$[author]{${author}}{${editor}, editor}. ${title}$[series+(volume|number)]{, ${series} ${volume|number}}$[edition]{, ${edition} edition}, ${year}. ${publisher}$[address]{, ${address}}.$[note]{ ${note}}',
                    'booklet'       : '$[author]{${author}. }${title}. $[howpublished]{${howpublished}$[year]{, ${year}.}}{$[year]{$year}.$[note]{ ${note}}}',
                    'conference'    : '${author}. ${title}, ${booktitle}, $[volume]{vol. ${volume}}{no. ${number}}$[organization]{, ${organization}}, ${year}.$[publisher]{ ${publisher}$[address]{, ${address}}.}',
                    'inbook'        : '$[author]{${author}}{${editor}, editor}. ${title}$[series+(volume|number)]{, ${series} ${volume|number}}$[edition]{, ${edition} edition}, ${year}, $[chapter]{chapter ${chapter}}{p. ${pages}}. ${publisher}$[address]{, ${address}}.$[note]{ ${note}}',
                    'incollection'  : '${author}. ${title}, ${booktitle}$[series]{, ${series}}{}$[volume]{, vol. ${volume}}{$[number]{, no. ${number}{}}}$[chapter|pages]{ $[chapter]{chapter ${chapter}}{p. ${pages}}}{}, ${year}. ${publisher}$[address]{, ${address}}.',
                    'inproceedings' : '${author}. ${title}, ${booktitle}$[series]{, ${series}}{}$[volume]{, vol. ${volume}}{$[number]{, no. ${number}{}}}$[organization]{, ${organization}}{}, ${year}. ${publisher}$[address]{, ${address}}.',
                    'manual'        : '$[author]{${author}. }${title}$[edition]{, ${edition} edition}$[year]{, ${year}}.$[organization]{ ${organization}$[address]{, ${address}}.}$[note]{ ${note}',
                    'mastersthesis' : '${author}. $[type]{${type}}{Masters thesis}: ${title}, ${year}. ${school}$[address]{, ${address}}.$[note]{ ${note}.}',
                    'misc'          : '$[author]{${author}. }$[title]{${title}. }$[howpublished]{${howpublished}. }$[note]{${note}.}',
                    'phdthesis'     : '${author}. $[type]{${type}}{PhD thesis}: ${title}, ${year}. ${school}$[address]{, ${address}}.$[note]{ ${note}.}',
                    'proceedings'   : '$[author]{${author}. }{$[editor]{${editor}, editor. }}${title}, ${booktitle}, $[volume]{vol. ${volume}}{no. ${number}}$[organization]{, ${organization}}, ${year}.$[publisher]{ ${publisher}$[address]{, ${address}}.}',
                    'techreport'    : '${author}. $[type]{${type}: }${title}$[number]{ no. ${number}}, ${year}. ${institution}$[address]{, ${address}}.$[note]{ ${note}}',
                    'unpublished'   : '${author}. ${title}$[year]{, ${year}}. ${note}.',
                    }  

    fmtre = re.compile(r'\$\{(?P<ref>[a-z\|]+)\}|\$\[(?P<cond>[a-z\|\(\)\+! \n\t\r]+)\]|(?P<endbrace>\})|(?P<beginbrace>\{)|(?P<space>\s+)')
    bracere = re.compile(r'(?P<endbrace>})|(?P<beginbrace>{)')
    condre = re.compile(r'([()&|])|([^()&|]+)')
    def __init__(self, manager, parent, cmddict, nodeDict, attrs, pos):
        Node.__init__(self,manager,parent,CommandDict(cmddict),nodeDict,attrs,pos)
        self.__manager = manager

    def handleText(self,text,pos):
        Node.handleText(self,unicode(text),pos)
    def __handleText(self,text):
        #print "GOT : %s" % text
        self.handleText(text,self.pos)
    def formatBibEntry(self,node):
        #
        #!!TODO!! Bib entry formatting should be handled in a more flexible way.
        #
        d = node
        keyd = dict([ (k,node.has_key(k)) for k in node.bibitems.keys() ])
        pos = self.pos

        def formatentry(k):
            items = d[k]
            if isinstance(items,str) or isinstance(items,unicode):
                n = self.startChildElement('span',{ 'class' : 'bib-item-%s' % k},pos)
                n.handleText(items,pos)                
                n.end(pos)
                self.endChildElement('span',pos)
            else:
                
                assert len(items) > 0
                    
                n = self.startChildElement('span',{ 'class' : 'bib-item-%s' % k},pos)
                n.handleText(items[0],pos)
                n.end(pos)
                self.endChildElement('span',pos)
                if   len(items) > 1:
                    for sep,i in zip([ ', '] * (len(items)-2) + [' and '],items[1:]):
                        self.handleText(sep,pos)
                        n = self.startChildElement('span',{ 'class' : 'bib-item-%s' % k},pos)
                        n.handleText(i,pos)
                        n.end(pos)
                        self.endChildElement('span',pos)


        def formatref(ref):
            refs = [ r for r in ref.split('|') if d.has_key(r) ]
            if not refs:
                raise BibItemError('Reference to undefined item "%s"' % ref)
            formatentry(refs[0])


        def ignoregroup(s,p):
            if not s[p] == '{':
                raise BibItemError('Expected {:\n     %s\nHere:%s^' % (s,' '*p))
            p += 1
            lvl = 1
            while lvl > 0 :
                o = self.bracere.search(s,p) 
                if o is not None:
                    p = o.end(0)
                    if o.group('beginbrace'):
                        lvl += 1
                    else:
                        lvl -= 1
                else:
                    # format string syntax error - unbalanced parens
                    raise BibItemError('Unbalanced parenthesis:\n     %s\nHere:%s^' % (s,' '*p))
            return p

        def parsegroup(s,p):
            if s[p] != '{':
               raise BibItemError('Expected {:\n     %s\nHere:%s^' % (s,' '*p))

            p += 1
            lvl = 1
            #print "PROG = ...%s" % s[p:]
            while lvl > 0:
                o = self.fmtre.search(s,p)  
                if o is not None:
                    #print "TEXT='%s'" % s[p:o.start(0)]
                    #print "G = '%s'" % o.group(0)
                    if p < o.start(0):
                        self.__handleText(s[p:o.start(0)])
                    if o.group('ref'):
                        formatref(o.group('ref'))
                        p = o.end(0)
                    elif o.group('cond'):
                        r = cond.eval(o.group('cond'),keyd)
                        if r:
                            p = parsegroup(s,o.end(0))
                            if s[p] == '{':
                                p = ignoregroup(s,p)
                        else:
                            p = ignoregroup(s,o.end(0))
                            if s[p] == '{':
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
                    elif o.group('space'):
                        self.__handleText(' ')
                        p = o.end(0)
                    else:
                        # format string syntax error
                        assert 0 
                else:
                    # format string syntax error - unbalanced parens
                    raise BibItemError('Syntax error:\n     %s\nHere:%s^' % (s,' '*p))
            #if p < len(s):
            #    self.__handleText(s[p:])
            return p
               
        def parsefmtstr(s,p):
            """
            \param s is the format string
            \param p is the current position in the string
            """
            #print "parsefmtstr: ...%s" % s[p:]
            while p < len(s):
                #print "-- parsefmtstr: |%s" % s[p:]
                o = self.fmtre.search(s,p)
                if o is not None:
                    if p < o.start(0):
                        self.__handleText(s[p:o.start(0)])
                    #print o.groups()                        
                    if o.group('ref'):
                        refs = [ r for r in o.group('ref').split('|') if d.has_key(r) ]
                        if refs:
                            formatentry(refs[0])
                        else:
                            err('Missing key "%s" in "%s"' % (o.group('ref'), node.id))
                            self.__handleText('<missing>')
                        p = o.end(0)
                    elif o.group('cond'):
                        r = cond.eval(o.group('cond'),keyd)

                        if r:
                            p = parsegroup(s,o.end(0))
                            if len(s) > p and s[p] == '{':
                                p = ignoregroup(s,p)
                        else:
                            p = ignoregroup(s,o.end(0))
                            if len(s) > p and s[p] == '{':
                                p = parsegroup(s,p)
                    elif o.group('space'):
                        self.__handleText(' ')
                        p = o.end(0)
                    else:
                        raise BibItemError('Syntax error in %s:\n     %s\nHere:%s' % (node.name,s,' '*p))
                else:
                    break
            if p < len(s):
                self.__handleText(s[p:])

        if node.name in self.bibtemplate.keys():
            try:
                #print "FORMAT BibItem %s" % node.name
                parsefmtstr(self.bibtemplate[node.name], 0)
            except BibItemError,e:
                print e
                raise
        else:
            assert 0

        


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
                         Attr('config'),
                         Attr('url',descr='Read the section content from an external source. If this is given, the section element must be empty.'),
                         ])
    contIter    = ' <head> [ T %s %s %s %s ]* <section>* ' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)
    
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 pos):
        assert isinstance(nodeDict, dict)
        _SectionBaseElement.__init__(self,manager,parent,CommandDict(cmddict),nodeDict,attrs,pos)
        self.__head = None
        if parent is not None:
            self.__depth = parent.getDepth()+1
        else:
            self.__depth = 1
        self.__parent = parent
        if not manager.checkSectionDepth(self.__depth):
            raise NodeError('Section nested too deep:\n\t' + '\n\t'.join(self.makeSectionTrace([])))
        self.__macrostack = []
   
    def makeSectionTrace(self,res):
        res.append('Section at %s' % self.pos)
        if self.__parent is not None:
            self.__parent.makeSectionTrace(res)
        return res

    def getDepth(self):
        return self.__depth
    def end(self,pos):
        for n in self:
            if isinstance(n,Node) and n.nodeName == 'head':
                self.__head = n
        _SectionBaseElement.end(self,pos)
        
    
    def getHeadNode(self):
        return self.__head
    def asString(self):
        print "hest"
        for i in self:
            print i
        return []

    def toXML(self,doc,node=None,formating=True):
        if node is None:
            node = doc.createElement(self.nodeName)
            if self.hasAttr('class'):
                node.setAttribute('class', self.getAttr('class'))
            if self.hasAttr('id'):
                node.setAttribute('id', self.getAttr('id'))
        
        nodes = PushIterator(self) 
        while nodes and not isinstance(nodes.peek(),HeadNode):
            nodes.next()

        if nodes: 
            n = nodes.next().toXML(doc)
            assert not isinstance(n,list)
            node.appendChild(n)
        node.appendChild(doc.createTextNode('\n'))

        body = doc.createElement('body')
        node.appendChild(body)
       
        lst = [] 
        while nodes and not isinstance(nodes.peek(),_SectionNode):
            item = nodes.next()
            if isinstance(item,basestring):
                if not lst or isinstance(lst[-1],Node):
                    lst.append([item])
                else:
                    lst[-1].append(item)
            else:
                lst.append(item)
        if self.paragraphElement and formating:
            # generate paragraphs 
            self.paragraphifyXML(lst,doc,body)
        for item in nodes:
            if isinstance(item,_SectionBaseElement):
                node.appendChild(item.toXML(doc))
                node.appendChild(doc.createTextNode('\n'))
            else:
                pass
                #assert not item.strip()
        assert not isinstance(node,list)
        return node

class HeadNode(Node):
    comment = 'Contains the header definitions for a \\tagref{section} in the document.'
    nodeName = 'head'
    
    contIter = ' [ <title> <authors> <date> <defines> <abstract> ]* '
    structuralElement = True
        
    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 attrs,
                 pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        
        self.__date     = None
        self.__title    = None
        self.__authors  = None
        self.__abstract = None
        self.__defines  = None

    def getTitleNode(self):
        return self.__title
    def getDefinesNode(self):
        return self.__defines

    def end(self,pos):
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
                          Attr('macroexpand',default='yes') ])
    contIter    = ' [ T %s %s ]* ' % (_simpleTextNodes,_linkNodes)

class DivNode(Node):
    comment = 'A logical division element that creates a new paragraph.'
    nodeName  = 'div'
    acceptAttrs = Attrs([ Attr('id'),
                          Attr('class'), 
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
    acceptAttrs = Attrs([])
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
    acceptAttrs = Attrs([ ])
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
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), ])

class DefinitionTitleNode(_ListElementNode):
    comment     = 'Definition list label node.'
    nodeName = 'dt'
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), ])

class DefinitionDataNode(_ListElementNode):
    comment     = 'Definition list data node.'
    nodeName = 'dd'
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), ])

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
                          Attr('float',default='no', descr="(left|right|no) Defines where the figure should float. The backend may choose to ignore this.") ])
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
                          Attr('config'),
                          Attr('orientation',default='rows'), # DEPRECATED!!
                          Attr('cellvalign',descr='Vertical alignment of cells. This is a space-separated list of (top|middle|bottom) defining the alignment of cells in the individual columns.'),
                          Attr('cellhalign',descr='Horizontal alignment of cells. This is a space-separated list of (left|right|center) defining the alignment of cells in the individual columns.'), ])
    structuralElement = True

    def __init__(self, manager, parent, cmddict, nodedict, attrs, pos):
        Node.__init__(self,manager,parent,cmddict,nodedict,attrs,pos)

        self.__halign = None
        self.__valign = None

        self.__tablesyntaxdisabled = False
        self.__cstack = None

    def end(self,pos):
        halign = None
        valign = None

        if self.__cstack is not None:
            self.__cstack.pop().end(pos)
            self.__cstack.pop().end(pos)
            self.__cstack = None

        Node.end(self,pos)
        self.seal()

        ncells = max([ len(r) for r in self ])

        if  self.hasAttr('cellhalign'):
            halign = re.split(r'\s+', self.getAttr('cellhalign'))
            for i in halign:
                if i not in [ 'left','right','center' ]:
                    raise NodeError('Invalid cellhalign attribute value in %s' % self.pos)

        if  self.hasAttr('cellvalign'):
            valign = re.split(r'\s+', self.getAttr('cellvalign'))
            for i in valign:
                if i not in [ 'top','bottom','middle' ]:
                    raise NodeError('Invalid cellvalign attribute value in %s' % self.pos)

        if halign is not None and valign is not None:
            if   len(halign) != len(valign):
                raise NodeError('Vertical and horizontal alignment definitions do not match at %s' % pos)
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
                raise NodeError('Alignment definitions do not match row width at %s' % self.pos)

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
                    raise NodeError('Non-whitespace text not allowed in table at %s' % self.pos)
            else:
                n = r.toXML(doc,rowlen)            
                if n is not None:
                    node.appendChild(n)
        
        assert not isinstance(node,list)
        return node
    def newTableRow(self,pos):
        #print "newTableRow "
        if self.__cstack is not None:
            # close prev row and cell
            assert len(self.__cstack) == 2
            top = self.__cstack.pop()
            top.end(pos)
            top = self.__cstack.pop()
            top.end(pos)
            
        if self.__cstack is None:
            self.__cstack = [ ]

        trnode = self.startElement(self.tablerowelement,{},pos)
        Node.append(self,trnode)
        self.__cstack.append(trnode)
        tcnode = trnode.startElement(self.tablecellelement,{},pos)
        self.__cstack[-1].append(tcnode)
        self.__cstack.append(tcnode)
        assert len(self.__cstack) == 2

    def newTableCell(self,pos): 
        #print "newTableCell "
        if self.__cstack is None:
            raise MacroError('%s: Table may not start with \\! (new cell)' % self.pos)

        # close prev cell
        assert len(self.__cstack) == 2
        top = self.__cstack.pop()
        top.end(pos)
            
        trnode = self.__cstack[-1] 
        tcnode = trnode.startElement(self.tablecellelement,{},pos)
        self.__cstack[-1].append(tcnode)
        self.__cstack.append(tcnode)
        assert len(self.__cstack) == 2

    def append(self,item):
        if  self.__cstack is not None:
            assert len(self.__cstack) == 2
            self.__cstack[-1].append(item)
        else:
            # hardcode: Only elements and space is allowed in table 
            if isinstance(item,basestring) and len(item.strip()) == 0:
                pass
            elif isinstance(item,Node):
                Node.append(self,item)
            else:
                raise NodeError('Text not allowed in <%s>' % self.nodeName)



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
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), ])
    structuralElement = True

    def __len__(self):
        return len([ i for i in self if isinstance(i,TableCellNode)])
    
    def toXML(self,doc,rowlen):
        node = doc.createElement('tr')
        for k,v in self.attrs():
            if v is not None and k not in [ 'macroexpand' ]:
                node.setAttribute(k,v)

        cells = list(self)
        cells.extend([ None ] * (rowlen - len(cells)))

        for cell in cells:
            if cell is not None:
                node.appendChild(cell.toXML(doc))
            else:
                node.appendChild(doc.createElement('td'))
        assert not isinstance(node,list)
        return node

class TableCellNode(Node):
    comment = 'Table can be used to label a column of cells or define the format of a table.'
    nodeName = 'td'
    macroMode = MacroMode.Text
    contIter  = ' [ T %s %s %s %s ]* ' % (_simpleTextNodes, _structTextNodes, _linkNodes, _mathEnvNodes)
    acceptAttrs = Attrs([ Attr('id'), Attr('class'), ])
    paragraphElement = True

class DocumentNode(_SectionNode):
    nodeName   = 'sdocmlx'
#NOTE: we should support appendixes too at some point...
    contIter    = ' <head> [ T %s %s %s %s ]* <section>* <bibliography>?' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)

    def __init__(self,manager,parent,cmddict,nodeDict,attrs,pos):
        _SectionNode.__init__(self,manager,None,cmddict,nodeDict,attrs,pos)


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
                    Attr('type',default='text/plain',descr=
                         "MIME type of the text element content or of the URL target.\n"
                         "SDoc can hilight a few types, currently 'source/LANG', where LANG is one of: python, c, java, csharp or matlab."),
                    Attr('encoding',default='ascii'), # (ascii|utf-8)
                    Attr('macroexpand',default='no',descr="Tells if macros should be processed in the content of the element. For external sources this is ignored."), # (yes|no)
                    Attr('flushleft',default='yes',
                         descr="Flush text left as much as possible while preserving the relative indention. White-space is only remove from the top-level pre-element, not from any child nodes."),
                    ])
    macroMode = MacroMode.NoExpand
    contIter  = ' [ T %s <a> ]* ' % (_simpleTextNodes )
    structuralElement = True
    paragraphElement = True

    def __init__(self, manager, parent, cmddict, nodeDict, attrs, pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)

        self.__realurl = None
        if isinstance(pos,int):
            pass
        else:
            filename = pos.filename

            if self.hasAttr('url'):
                url = self.getAttr('url')
                #dgb("In <pre> : url='%s', pos=%s",url,pos)
                self.__realurl = os.path.abspath(manager.findFile(url,filename))
                lines = manager.readFrom(self.__realurl,self.getAttr('encoding')).split('\n')
                firstline = 0
                if self.hasAttr('firstline'):
                    firstline = max(int(self.getAttr('firstline'))-1,0)
                lastline = len(lines)
                if self.hasAttr('lastline'):
                    lastline = min(int(self.getAttr('lastline'))-1,lastline)

                if firstline >= lastline:
                    raise NodeError('Empty inclusion from "%s" in <pre> at %s' % (url,self.pos))
                
                while firstline < lastline and not lines[firstline].strip():
                    firstline += 1
                while firstline < lastline and not lines[lastline-1].strip():
                    lastline -= 1
                if firstline == lastline:
                    raise NodeError('Only blank lines in inclusion in <pre> at %s' % self.pos)
                inclines = lines[firstline:lastline]

                for l in inclines[:-1]:
                    self.handleRawText(l,pos)
                    self.handleRawText(u'\n',pos)
                self.handleRawText(inclines[-1],pos)

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


        minindent = sys.maxint

        xlines = [ [] ]
        for i in items:
            if isinstance(i,basestring):
                it = lineiter(i)
                if xlines[-1] and isinstance(xlines[-1][-1],basestring):
                    xlines[-1][-1] += it.next()
                else:
                    xlines[-1].append(it.next())
                for i in it:
                    xlines.append([ i ])
            else:
                xlines[-1].append(i)

        if self.getAttr('flushleft') != 'no':
            for l in xlines:
                try:
                    if isinstance(l[0],basestring):
                        if len(l) > 1 or len(l[0].strip()) > 0: # disregard all-blank lines
                            minindent = min(minindent, len(l[0])-len(l[0].lstrip()))
                    else:
                        minindent = 0
                except IndexError:
                    minindent = 0
        else:
            minindent = 0
                        
        for line in xlines:
            if minindent > 0:
                line[0] = line[0][minindent:]
                
            for item in line:
                if isinstance(item,basestring):
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
            node.setAttribute("xmlns:trace","http://odense.mosek.com/emotek.dtd")
            node.setAttribute('trace:file',self.pos.filename)
            node.setAttribute('trace:line',str(self.pos.line))
        assert not isinstance(node,list)
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
                          Attr('ref',descr='A globally unique ID of another element'),
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
    acceptAttrs = Attrs([ Attr('id'), 
                          Attr('target',descr="The id of another element that anchor ``binds'' to."),
                          Attr('type', descr="Indicates what kind of anchor is generated. Default is a normal anchor referrable with a \\tagref{ref}. Alternative value is ``index'' indicating that a corresponding element should be placed in the generated index.") ])
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
    acceptAttrs = Attrs([ Attr('type'),
                          Attr('url',descr='Source of the image file.')])
    contIter    = ''

    def __init__(self, manager, parent, cmddict, nodeDict, attrs, pos):
        Node.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        
        url = self.getAttr('url')
        filename = pos.filename
        self.__realurl = os.path.abspath(manager.findFile(url,filename))

    def toXML(self,doc,node=None):
        if self.expandElement:
            if node is None:
                node = doc.createElement(self.nodeName)

            node.setAttribute('type',self.getAttr('type'))

            
            node.setAttribute('url',self.__realurl)

        assert not isinstance(node,list)
        return node
        

######################################################################
#  Some administrative Node classes
######################################################################

class _ExceptionNode(Node):
    macroMode   = MacroMode.NoExpand
    acceptAttrs = Attrs([  ])
    contIter    = ' T  '
    structuralElement = True


    def __init__(self,
                 manager,
                 parent,
                 cmddict, # dictionary of available macros
                 nodedict, # dictionary of all known element names
                 attrs, # None or a dictionary of attributes
                 pos
                 ):
        Node.__init__(self,manager,parent,cmddict,nodedict,attrs,pos)
    
    def onCreate(self):
        pass

    def toXML(self,doc,node=None):
        return node
        pass

    def end(self,pos):
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
        raise CondError("ERROR @ %s: %s" % (self.pos,msg))

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
        print "WARNING @ %s: %s" % (self.pos,msg)

######################################################################
#  Math Node classes
######################################################################


class InlineMathNode(_MathNode):
    nodeName         = 'm'
    paragraphElement = False

    comment          = '''
                         Inline math element. This is placed as an element in
                         the text rather than in a separate paragraph.
                       '''

class MathEnvNode(_MathNode):
    nodeName    = 'math'
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

    def end(self,pos):
        if self.hasAttr('family') and not self.getAttr('family') in mathFonts:
            raise NodeError('Invalid math font "%s" at %s' % (self.getAttr('family'),self.pos))

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
    
    def __init__(self, manager, parent, cmddict, nodedict, attrs, pos):
        _MathNode.__init__(self,manager,parent,cmddict,nodedict,attrs,pos)

        self.__tablesyntaxdisabled = False
        self.__cstack = None

    def end(self,pos):
        Node.end(self,pos)
        
        halign = None
        valign = None

        if self.__cstack is not None:
            #print "@@@@@@@@@@@@@@@@ at %s" % self.pos
            #print "@@@@@@@@@@@@@@@@ flush cstack:",self.__cstack
            self.__cstack.pop().end(pos)
            self.__cstack.pop().end(pos)
            self.__cstack = None
        
        #print "ZZZ@@@@@@@@ <%s>::end @ %s--%s" % (self.nodeName,self.pos,pos)

        self.seal()

        rows = [ r for r in self if isinstance(r,MathTableRowNode) ]

        if len(rows) > 0:
            ncells = max([ len(r) for r in rows ])
        else:
            log.warning("TODO: Fix math tables special syntax (%s)" % (pos,))
            #raise NodeError("%s: Empty table" % self.pos)
            ncells = 1

        if  self.hasAttr('cellhalign'):
            halign = re.split(r'\s+', self.getAttr('cellhalign'))
            for i in halign:
                if i not in [ 'left','right','center' ]:
                    raise NodeError('Invalid cellhalign attribute value in %s' % self.pos)

        if  self.hasAttr('cellvalign'):
            valign = re.split(r'\s+', self.getAttr('cellvalign'))
            for i in valign:
                if i not in [ 'top','bottom','middle' ]:
                    raise NodeError('Invalid cellvalign attribute value in %s' % self.pos)

        if halign is not None and valign is not None:
            if   len(halign) != len(valign):
                raise NodeError('Vertical and horizontal alignment definitions do not match at %s' % pos)
        elif halign is not None:
            valign = [ 'top' ] * len(halign)
        elif valign is not None:
            halign = [ 'left' ] * len(valign)
        else:
            valign = [ 'top' ] * ncells
            halign = [ 'left' ] * ncells

        for r in rows:
            if len(r) > len(halign) or len(r) > len(valign):
                raise NodeError('Alignment definitions do not match row width at %s' % r.pos)

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
        
        assert not isinstance(node,list)
        return node
    def newTableRow(self,pos):
        #print "newTableRow in <%s>" % self.nodeName
        
        if self.__cstack is None:
            self.__cstack = [ ]
        else:
            assert len(self.__cstack) == 2
            top = self.__cstack.pop()
            top.end(pos)
            top = self.__cstack.pop()
            top.end(pos)

        trnode = self.startElement(self.tablerowelement,{},pos)
        Node.append(self,trnode)
        self.__cstack.append(trnode)
        tcnode = trnode.startElement(self.tablecellelement,{},pos)
        self.__cstack[-1].append(tcnode)
        self.__cstack.append(tcnode)
        assert len(self.__cstack) == 2

    def newTableCell(self,pos): 
        #print "newTableCell in <%s>" % self.nodeName
        if self.__cstack is None:
            raise MacroError('%s: Table may not start with \\! (new cell)' % self.pos)

        # close prev cell
        assert len(self.__cstack) == 2
        top = self.__cstack.pop()
        top.end(pos)
            
        trnode = self.__cstack[-1] 
        tcnode = trnode.startElement(self.tablecellelement,{},pos)
        self.__cstack[-1].append(tcnode)
        self.__cstack.append(tcnode)
        assert len(self.__cstack) == 2

    def append(self,item):
        if  self.__cstack is not None:
            assert len(self.__cstack) == 2
            self.__cstack[-1].append(item)
        else:
            # hardcode: Only elements and space is allowed in table 
            if isinstance(item,basestring) and len(item.strip()) == 0:
                pass
            elif isinstance(item,Node):
                Node.append(self,item)
            else:
                log.Error('%s: Text not allowed in <%s>' % (self.pos, self.nodeName))
                #raise NodeError('Text not allowed in <%s>' % self.nodeName)


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
    def __init__(self,manager,parent,cmddict,nodeDict,attrs,pos):
        _MathNode.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        self.__len = None

    def __len__(self):
        if self.__len is None:
            assert 0
        return self.__len

    def end(self,pos):
        #print "@@@@@@@@@@@ <%s>::end @ %s--%s" % (self.nodeName,self.pos,pos)
        self.__len = len([ cell for cell in self if isinstance(cell,MathTableCellNode) ])
        
    def toXML(self,doc,rowlen):
        node = doc.createElement(self.nodeName)
        cells = [ r for r in self if isinstance(r,MathTableCellNode) ]
        cells += [ None ] * (rowlen - len(cells))
        for c in cells:
            if c is not None:
                n = c.toXML(doc)
            else:
                n = doc.createElement('mtd')
            if n is not None:
                node.appendChild(n)
        assert not isinstance(node,list)
        return node


class MathTableCellNode(_MathNode):
    nodeName = 'mtd'

######################################################################
#  Root Node classes
######################################################################

class _RootNode:
    rootElementlass = None
    rootElement      = None

    def __init__(self,manager,parent,cmddict,nodeDict,attrs,pos):
        self.documentElement = None
        self.__cmddict       = cmddict
        self.__nodeDict      = nodeDict
        self.__parent        = parent
        self.__manager       = manager
        self.__macroHandler = None
        assert isinstance(nodeDict,dict)
        ## Create a new XML parser and read the fileanme 
    def startChildElement(self,name,attrs,pos):
        if name == self.rootElement:
            if self.documentElement is not None:
                raise NodeError('Duplicate root element <%s> at %s' % (name,self.rootElementClass.nodeName,pos))
            if self.__macroHandler == None:
                self.__macroHandler = MacroParser()
            self.documentElement = self.rootElementClass(self.__manager,
                                                         self.__parent,
                                                         self.__cmddict, 
                                                         self.__nodeDict, 
                                                         attrs, 
                                                         pos)
            self.documentElement.macroHandler(self.__macroHandler)
            return self.documentElement
        else:
            raise NodeError('Invalid element <%s>. Expected <%s> at %s' % (name,self.rootElement,pos))
    def endChildElement(self,name,pos):
        pass

    def handleText(self,data,pos):
        pass
    def evaluate(self,name,pos):
        pass

    def endOfElement(self,file,line):
        self.end(file,line)
    def end(self,pos):
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
        
    def __init__(self,manager,parent,cmddict,nodeDict,pos):
        print "odfajiojaos"
        _RootNode.__init__(self,manager,parent,cmddict,nodeDict,None,pos)

    def toXML(self,formating=True):
        impl = xml.dom.minidom.getDOMImplementation()
        doc = impl.createDocument(None, 'sdocmlx', None)
        self.documentElement.toXML(doc,doc.documentElement,formating)
        node = doc.documentElement
        return node

class MetaDocumentRoot(_RootNode):
    rootElementClass = DocumentNode
    rootElement      = 'sdocmlx'
    nodeName         = 'sdocmlx'
    contIter    = ' <head> [ T %s %s %s %s ]* <body>* <section>* ' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)
    
    comment = None
    examples = []
    acceptAttrs = Attrs([])
    macroMode = MacroMode.NoExpand

    def __init__(self,manager,parent,cmddict,nodeDict,pos):
        _RootNode.__init__(self,manager,parent,cmddict,nodeDict,None,pos)
        contIter    = ' <head> <body>* [ T %s %s %s %s ]*  <section>* ' % (_simpleTextNodes,_structTextNodes,_linkNodes,_mathEnvNodes)

    def toXML(self,formating=True):
        impl = xml.dom.minidom.getDOMImplementation()
        doc = impl.createDocument(None, 'sdocmlx', None)
        self.documentElement.toXML(doc,doc.documentElement,formating)
        node = doc.documentElement
        return node

class ExternalSectionRoot(_RootNode):
    rootElementClass = _SectionNode
    rootElement      = 'section'
    def __init__(self,manager,parent,cmddict,nodeDict,attrs,pos):
        _RootNode.__init__(self,manager,parent,cmddict,nodeDict,attrs,pos)
        self.__attrs = attrs
    def startChildElement(self,name,attrs,pos):
        # Note this is a hack; we wish attributes from the element that
        # included the section to override attributes from the element in the
        # included file. We merge the attributes:

        attrd = {}
        attrd.update(self.__attrs)
        
        for k in attrs:
            if k == 'id': 
              if not attrd.has_key(k):
                attrd[k] = attrs[k]
            elif k == 'class': 
              attrd[k] = attrd.get(k,'') + ' ' + attrs[k]
            elif k == 'config': 
              attrd[k] = attrs[k] + ' ' + attrd.get(k,'')
            elif not attrd.has_key(k):
              attrd[k] = attrs[k]

        return _RootNode.startChildElement(self,name,attrd,pos)

class ExternalDefineRoot(_RootNode):
    rootElementClass = DefinesNode
    rootElement      = 'defines'

    def __init__(self,
                 manager,
                 parent,
                 cmddict,
                 nodeDict,
                 pos):
        _RootNode.__init__(self,manager,parent,cmddict,nodeDict,None,pos)

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

        self.__cached_file = {}

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
            if self.__cached_file.has_key(realurl):
                text = self.__cached_file[realurl]
            else:
                msg('Reading from external data source %s' % realurl) 
                if encoding.lower() == 'utf-8':
                    text = open(realurl).read().decode('utf-8')
                elif encoding.lower() == 'ascii':
                    text = open(realurl).read().decode('ascii')
                else:
                    raise NodeIncludeError("Invalid incoding of file %s" % realurl)
                self.__cached_file[realurl] = text

            return text
        except IOError:
            raise NodeIncludeError("Failed to read file %s" % realurl) 
    
    def saveId(self,key,item):
        if self.__ids.has_key(key):
            olditem = self.__ids[key]
            raise XMLIdError('Duplicate ID "%s" originally defined at %s, redefined at %s' % (key,olditem.pos,item.pos))
        else:
            self.__ids[key] = item
    def refId(self,key,src):
        self.__reqids.append((key,src))
    def findFile(self,url,baseurl):
        proto,server,path,r0,r1,r2 = urlparse.urlparse(url)
        if proto:
            if proto != 'file':
                raise NodeError('Only local includes allowed, got "%s"' % url)
            else:
                return path
        else:
            if baseurl is not None:
                base = urlparse.urlparse(baseurl)
                fullname = os.path.abspath(os.path.join(os.path.dirname(base[2]),path))
                if os.path.exists(fullname):
                    return fullname

            for p in self.__incpaths:
                fullname = os.path.join(p,path)
                #print "check: %s" % fullname
                if os.path.exists(fullname) and os.path.isfile(fullname):
                    return fullname
            raise NodeError('File "%s" not found' % url) 
    def checkSectionDepth(self,d):
        return self.__maxsectdepth is None or self.__maxsectdepth >= d

    def checkIdRefs(self):
        errs = []
        for k,src in self.__reqids:
            if not self.__ids.has_key(k):
                err('Missing ID: "%s" referenced at %s' % (k,src.pos))
                errs.append('Missing ID: "%s" referenced at %s' % (k,src))
        return errs


    def evalCond(self,value,pos):
        try:
            return cond.eval(value,self.__conds)
        except cond.CondError,e:
            raise CondError('%s at %s' % (e,pos))

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
                        raise CondError('Unbalanced conditional expression "%s" at %s' % (value,pos))
                    else:
                        top = stack.pop()
                        stack[-1].append(top)
            else:
                raise CondError('Invalid condition key "%s" at %s' % (value,pos))

        conds = self.__conds
        def evalc(exp):
            if isinstance(exp,CondTerm):
                if conds.has_key(exp):
                    return conds[exp]
                else:
                    raise CondError('Undefined condition key "%s" at %s' % (exp,pos))
            elif isinstance(exp,CondIsDef):
                return conds.has_key(exp)
            else:
                oprs = dict([ (v,v) for v in exp if isinstance(v,CondOpr) and v is not Cond.Not]).keys()
                if len(oprs) > 1:
                    raise CondError('Invalid condition key "%s" at %s' % (value,pos))
                l = exp
                res = []
                while l:
                    head = l.pop(0)
                    if head is Cond.Not:
                        if not l:
                            raise CondError('Invalid condition key "%s" at %s' % (value,pos))
                        res.append(not evalc(l.pop(0)))
                    elif isinstance(head,CondTerm) or isinstance(head,CondExp):
                        res.append(evalc(head))
                    else:
                        raise CondError('Invalid condition key "%s" at %s' % (value,pos))
                    if l and not (l.pop(0) is oprs[0]):
                        raise CondError('Invalid condition key "%s" at %s' % (value,pos))
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

metaNodeDict = {
                    'sdocmlx': MetaDocumentRoot,
                    'body' : BodyNode
                }
metaNodeDict.update(globalNodeDict)
