"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009 Mosek ApS 
"""

import config
import zipfile
import UserList
from UserDict import UserDict
import xml.sax
import urlparse
import re
import sys
import time
import os
import HTMLParser


import logging

################################################################################
################################################################################
class _mathUnicodeToTex:
    unicoderegex = re.compile(u'[\u0080-\u8000]')
    
    unicodetotex = {
        160  : '~',
        215  : '{\\times}',
        # Greek letters
        913 : '{\\rm A}',
        914 : '{\\rm B}',
        915 : '{\\Gamma}',
        916 : '{\\Delta}',
        917 : '{\\rm E}',
        918 : '{\\rm Z}',
        919 : '{\\rm H}',
        920 : '{\\Theta}',
        921 : '{\\rm I}',
        922 : '{\\rm K}',
        923 : '{\\Lambda}',
        924 : '{\\rm M}',
        925 : '{\\rm N}',
        926 : '{\\Xi}',
        927 : '{\\rm O}',
        928 : '{\\Pi}',
        929 : '{\\rm P}',
        931 : '{\\Sigma}',
        932 : '{\\rm T}',
        933 : '{\\Upsilon}',
        934 : '{\\Phi}',
        935 : '{X}',
        936 : '{\\Psi}',
        937 : '{\\Omega}',
        945 : '{\\alpha}',
        946 : '{\\beta}',
        947 : '{\\gamma}',
        948 : '{\\delta}',
        949 : '{\\epsilon}',
        950 : '{\\zeta}',
        951 : '{\\eta}',
        952 : '{\\theta}',
        953 : '{\\iota}',
        954 : '{\\kappa}',
        955 : '{\\lambda}',
        956 : '{\\mu}',
        957 : '{\\nu}',
        958 : '{\\xi}',
        959 : 'o',
        960 : '{\\pi}',
        961 : '{\\rho}',
        962 : '{\\sigmaf}',
        963 : '{\\sigma}',
        964 : '{\\tau}',
        965 : '{\\upsilon}',
        966 : '{\\phi}',
        967 : '{\\chi}',
        968 : '{\\psi}',
        969 : '{\\omega}',
        # misc
        8230 : '\\ldots{}',
        8285 : '\\vdots{}',
        8704 : '\\forall{}',
        8712 : '\\in{}',
        8721 : '\\sum{}',
        8742 : '\\|',
        8804 : '\\leq{}',
        8805 : '\\geq{}',
        8834 : '\\subset{}',
        8901 : '\\cdot{}',
        8943 : '\\cdots{}',
        8945 : '\\ddots{}',
    }

class _unicodeToTex:
    ## Text mode 
    unicoderegex = re.compile(u'[\u0080-\u8000]')
    unicodetotex = {  
        160  : '~',
        
        169  : '\\copyright{}',
        173  : '-',
        215  : '$\\times$',
        216  : '\\O{}',
        224  : '\\`a',
        228  : '\\"a',
        229  : '\\aa{}',
        231  : '\\c{c}',
        232  : "\\`e",
        233  : "\\'e",
        235  : '\\"e',

        246  : '\\"o',
        248  : '\\o{}',

        351  : '\\c{s}',

        8211 : '--',
        8212 : '---',
    
        8216 : '`',# &lsquo
        8217 : "'",# &rsquo

        8220 : "''", 
        8221 : "''", # cheatin: TeX will switch these for teh real quotes.
    }

    combchar_math = {
        0x0302 : 'hat',
        0x0304 : 'bar',
    }

    combchar_text = {
        0x0300 : '`',
        0x0302 : '^',
        0x0304 : '=',
    }

    @staticmethod
    def unicodeToTeXMath(text):
        # Assumes text mode
        def repl(o):
            return _unicodeToTex.unicodetotex[ord(o.group(0))]
        return re.sub(_unicodeToTex.unicoderegex,repl,text)



################################################################################
################################################################################
class UnicodeToTeXError(Exception):
    pass

class texCollector(UserList.UserList):
    MathMode = 'mode:math'
    TextMode = 'mode:text'
    def __init__(self,man,mode=TextMode):
        UserList.UserList.__init__(self)
        self.__stack = []
        self.__mode = mode
        self.man = man

    def texescape(self,data,r):
        pos = 0
        #unicoderegex = re.compile(u'[\u0080-\u8000]')
        for o in re.finditer(ur'(?P<backslash>\\)|(?P<spctex>{|}|<|>|#|\$|\^|_|&|%)|(?P<combined>[a-zA-Z][\u0300-\u036f]+)|(?P<unicodecombined>[\u0080-\u8000][\u0300-\u036f]?)',data):
            # backslash -> '\'
            # spctex    -> single char special tex characters
            # combined  -> combining character: normal char + combining chars (one or more, but we only support one)
            # combined unicode -> Any unicode char followed by one or more combining chars
            if o.start(0) > pos:
                r.append(str(data[pos:o.start(0)]))
            pos = o.end(0)
            if   o.group('backslash'):
                if self.__mode is self.TextMode:
                    r.append('$\\tt\\backslash$')
                else:
                    r.append('\\tt\\backslash{}')
            elif o.group('spctex'):
                t = o.group('spctex')
                if t in [ '^','_' ]:
                    if self.__mode == self.MathMode:
                        r.append('\\%s' % str(t))
                    else:
                        r.append('\\char%d{}' % ord(t))
                elif t in [ '<', '>' ]:
                    if self.__mode == self.MathMode:
                        r.append(str(t))
                    else:
                        r.append('\\char%d{}' % ord(t))
                else:
                    r.append('\\%s' % str(t))
            elif o.group('combined'):
                t = o.group('combined')
                ch = t[0]
                cm = t[1:]
                if len(cm) > 1:
                    self.man.Error('Multiple combining characters are not supported: 0x%x + 0x%x 0x%x' % (ord(ch),ord(cm[0]),ord(cm[1])))
                else:
                    cm = ord(cm)

                try:
                    if self.__mode is self.TextMode:
                        r.append('\\%s%s' % (_unicodeToTex.combchar_text[cm],ch))
                    else: # self.__mode is self.MathMode:
                        r.append('\\%s{%s}' % (_unicodeToTex.combchar_math[cm],ch))
                except KeyError:
                    self.man.Error('Unknown combining character 0x%x 0x%x (%s)' % (cm,ord(ch),t))
            elif o.group('unicodecombined'):
                t = o.group('unicodecombined')
                ch = t[0]
                cm = t[1:]

                if len(cm) > 1:
                    self.man.Error('Multiple combining characters are not supported: 0x%x + 0x%x 0x%x' % (ord(ch),ord(cm[0]),ord(cm[1])))
                elif len(cm) == 0:
                    uidx = ord(ch)
                    if self.__mode == self.MathMode:
                        try:
                            r.append(_mathUnicodeToTex.unicodetotex[uidx])
                        except KeyError:
                            Warning('Unknown unicode: %d' % uidx)
                            r.append('.')
                    else:
                        try:
                            #r.append(_mathUnicodeToTex.textunicodetotex[uidx])
                            r.append('%s' % _unicodeToTex.unicodetotex[uidx])
                        except KeyError:
                            self.man.Error('Could not convert char %d/0x%x (%s)' % (uidx,uidx,unicode(t).encode('utf-8')))
                else:
                    if self.__mode is self.TextMode:
                        raise UnicodeError('Combining unicode characters not allowed in text mode')
                    else: #if self.__mode is self.MathMode:
                        r.append('\\%s%s' % (_unicodeToTex.combchar_math[cm],_unicodeToTex.unicodetotex[ch]))
            else: 
                uidx = ord(o.group(0))
                if self.__mode == self.MathMode:
                    try:
                        r.append(_mathUnicodeToTex.unicodetotex[uidx])
                    except KeyError:
                        Warning('Unknown unicode: %d' % uidx)
                        r.append('.')
                else:
                    try:
                        r.append('$%s$' % _mathUnicodeToTex.unicodetotex[uidx])
                    except KeyError:
                        self.man.Error('Could not convert char %d/0x%x (%s)' % (uidx,uidx,unicode(t).encode('utf-8')))

        if pos < len(data):
            r.append(str((data[pos:])))

        return r

    def texverbatim(self,data,r):
        pos = 0
        for o in re.finditer(ur'(?P<unicode>[\u0080-\u8000])|(?P<lf>\n)|(?P<space>[ ]+)|(?P<escape>%|\#|&)|(?P<special>\\|~|\^|\$|{|}|_|%)',data,re.MULTILINE):
            if o.start(0) > pos:
                r.append(str(data[pos:o.start(0)]))
            pos = o.end(0)
            if o.group('space'):
                #r.append('\\ ' * len(o.group('space')))
                #r.append('\\nullbox{}')
                r.append(o.group('space'))
            elif o.group('escape'):
                r.append('\\%s' % o.group('escape'))
            elif o.group('special'):
                r.append('\\char%d{}' % ord(o.group('special')))
            elif o.group('unicode'):
                uidx = ord(o.group('unicode'))
                if   _unicodeToTex.unicodetotex.has_key(uidx):
                    r.append('%s' % _unicodeToTex.unicodetotex[uidx])
                elif _mathUnicodeToTex.unicodetotex.has_key(uidx):
                    r.append('$%s$' % _mathUnicodeToTex.unicodetotex[uidx])
                else: 
                    Warning('Unicode in verbatim field: %d' % uidx)
                    r.append('\\#4%d' % uidx)
            elif o.group('lf'):
                #r.append('\\par%\n')
                r.append('\n\\nullbox{}')
            else:
                print "TEXT = '%s'" % o.group(0)
                assert 0
            
        if pos < len(data):
            r.append(str((data[pos:])))

        return r
        
    def verbatim(self,item):
        if   isinstance(item,unicode):
            self.texverbatim(item,self.data)
        elif isinstance(item,str):
            self.texverbatim(item,self.data)
#        elif isinstance(item,Group):
#            self.groupStart()
#            self.extend(item)
#            self.groupEnd()
#        elif isinstance(item,Options):
#            self.moptStart()
#            self.extend(item)
#            self.moptEnd()
#        elif isinstance(item,InlineMath):
#            self.inlineMathStart()
#            self.startMathMode()
#            self.extend(item)
#            self.endMathMode()
#            self.inlineMathEnd()
#        elif isinstance(item,Begin):
#            self.begin(item.name)
#        elif isinstance(item,End):
#            self.end(item.name)
#        elif isinstance(item,Macro):
#            self.macro(item.name)
        else:
            print item
            assert 0
        return self
    
    def _raw(self,data):
        assert isinstance(data,basestring)
        self.data.append(str(data))
        return self
    def comment(self,text=''):
        lines = text.split('\n')
        self.data.extend([ '%% %s\n' % l for l in lines ])
        return self
    def lf(self):
        self.data.append('\n')
        return self
    def macro(self,name):
        assert name not in [ 'begin', 'end' ]
        self.data.append('\\%s' % name)
        return self
    def moptStart(self):
        self.data.append('[')
        self.__stack.append('[')
        return self
    def moptEnd(self):
        assert self.__stack.pop() == '['
        self.data.append(']')
        return self
    def groupEmpty(self):
        self.data.append('{}')
        return self
    def options(self,data=[]):
        if data:
            self.moptStart()
            if isinstance(data,str):
                self.append(data)
            else:
                self.extend(data)
            self.moptEnd()
        return self
    def group(self,data=[]):
        self.groupStart()
        if isinstance(data,str):
            self.append(data)
        else:
            self.extend(data)
        self.groupEnd()
        return self
    def groupStart(self,mode=None):
        if mode is None:
            self.data.append('{')
        elif self.__mode == self.MathMode:
            if   mode == '^':
                self.data.append('^{')
            elif mode == '_':
                self.data.append('_{')
            else:
                assert 0
        else:
            print self.__mode
            assert 0
        self.__stack.append('{')
        return self
    def tab(self):
        self.data.append('&')
        return self
    def rowend(self):
        self.data.append('\\\\')
        return self
        
    def groupEnd(self):
        assert self.__stack.pop() == '{'
        self.data.append('}')
        #print '\tlevel=%d' % len(self.__stack),self.__stack
        return self
    def begin(self,name):
        self.data.append('\\begin{%s}' % name)
        self.__stack.append(name)
        return self
    def end(self,name):
        self.data.append('\\end{%s}' % name)
        topname = self.__stack.pop()
        if topname != name:
            print "Error: \\begin{%s} ... \end{%s}" % (topname,name)
            assert 0
        return self
    def startMathMode(self):
        #print "Math mode start"
        assert self.__mode is not self.MathMode
        self.__stack.append(self.__mode)
        #print '\tlevel=%d' % len(self.__stack)
        self.__mode = self.MathMode
        return self
    def endMathMode(self):
        #print "Math mode end"
        assert self.__mode is self.MathMode
        self.__mode = self.__stack.pop()
        #print '\tlevel=%d' % len(self.__stack)
        return self
    def inlineMathStart(self):
        self.__stack.append('$')
        self.data.append('$')
        self.startMathMode()
        return self
    def inlineMathEnd(self):
        self.endMathMode()
        assert self.__stack.pop() == '$'
        self.data.append('$')
        return self
    def extend(self,items):
        for i in items:
            self.append(i)
        return self
    def append(self,item):
        if   isinstance(item,unicode):
            self.texescape(item,self.data)
        elif isinstance(item,str):
            self.texescape(item,self.data)
        elif isinstance(item,Group):
            self.groupStart()
            self.extend(item)
            self.groupEnd()
        elif isinstance(item,Options):
            self.moptStart()
            self.extend(item)
            self.moptEnd()
        elif isinstance(item,InlineMath):
            self.inlineMathStart()
            self.startMathMode()
            self.extend(item)
            self.endMathMode()
            self.inlineMathEnd()
        elif isinstance(item,Begin):
            self.begin(item.name)
        elif isinstance(item,End):
            self.end(item.name)
        elif isinstance(item,Macro):
            self.macro(item.name)
        else:
            print item
            assert 0
        return self

class DefaultDict(UserDict):
    def __init__(self,dcon):
        UserDict.__init__(self)
        self.__dcon = dcon
    def __getitem__(self,key):
        if not self.data.has_key(key):
            self.data[key] = self.__dcon()
        return self.data[key]

#def msg(m):
#    m = unicode(m)
#    sys.stderr.write('SDocML: ')
#    sys.stderr.write(m.encode('utf-8'))
#    sys.stderr.write('\n')

#def Warning(*args):
#    sys.stderr.write('WARNING: ')
#    sys.stderr.write(' '.join(args))
#    sys.stderr.write('\n')

def counter():
    i = 0
    while True:
        yield i
        i = i + 1

def asUTF8(s):
    if isinstance(s,unicode):
        return s.encode('utf-8')
    else:
        return s
def texescape(data,r):
    pos = 0

    for o in re.finditer(r'\\|{|}|#',data):
        if o.start(0) > pos:
            r.append(data[pos:o.start(0)])
        pos = o.end(0)
        t = o.group(0)
        if   t == '\\':
            r.append('\\backslash')
        elif t == '{':
            r.append('\\{')
        elif t == '}':
            r.append('\\}')
        elif t == '#':
            r.append('\\#')
        else: 
            assert 0
    if pos < len(data):
        r.append(data[pos:])

    return r


def escape(data,r):
    pos = 0
    for o in re.finditer(r'&|<|>',data):
        if o.start(0) > pos:
            r.append(data[pos:o.start(0)])
        pos = o.end(0)
        t = o.group(0)
        if   t == '&':
            r.append('&amp;')
        elif t == '<':
            r.append('&lt;')
        else: #t == '<':
            r.append('&gt;')
    if pos < len(data):
        r.append(data[pos:])

    return r

class IncludeError(Exception):
    pass
        
class NodeError(Exception):
    pass

class MathNodeError(Exception):
    pass

class MathImgError(Exception):
    pass

class tag:
    def __init__(self,name,attrs=None,empty=False):
        self.name = name
        self.attrs = attrs
        self.empty = empty
def emptytag(name,attrs=None):
    return tag(name,attrs,True)

class tagend:
    def __init__(self,name):
        self.name = name

class entity:
    def __init__(self,name):
        self.name = name

hr_delim = tag('hr',{'class' : 'content-delimiter' })

class htmlCollector(UserList.UserList):
    unendedtags = dict([ (v,None) for v in ['hr','link','br','img','meta','p' ]])
    partags     = dict([ (v,None) for v in ['div','center','table','tr','br','hr','head','title','link','style','meta' ]])

    def __init__(self):
        UserList.UserList.__init__(self)
        self.__stack = []
    def append(self,item):
        if isinstance(item,unicode) or isinstance(item,str):
            escape(item,self.data)
        elif isinstance(item,tag):
            self.tag(item.name,item.attrs,item.empty)
        elif isinstance(item,tagend):
            self.tagend(item.name)
        elif isinstance(item,entity):
            self.entity(item.name)
        else:
            raise TypeError('Only text and tags can be appended')
        return self
    def appendRaw(self,item):
        self.data.append(item)
        return self
    
    def div(self,cls):
        self.tag('div',{ 'class' : cls })
        return self
    def span(self,cls):
        self.tag('span',{ 'class' : cls })
        return self
        
    def anchor(self,href,cls=None):
        if cls:
            self.tag('a',{ 'href' : href, 'class' : cls })
        else:
            self.tag('a',{ 'href' : href })
        return self

    def extend(self,items):
        for i in items:
            self.append(i)
        return self

    def entity(self,name):
        self.data.append('&%s;' % name)
        return self

    def tag(self,name,attrs=None,empty=False):
        if not self.unendedtags.has_key(name) and not empty:
            self.__stack.append(name)
        if attrs is None or not attrs:
            attrstr = ''
        else:
            attrstr = ' ' + ' '.join([ '%s="%s"' % item for item in attrs.items()])
        if empty:
            self.data.append('<%s%s/>' % (name,attrstr))
        else:
            self.data.append('<%s%s>' % (name,attrstr))
        if empty and name in self.partags:
            self.append('\n')
        return self
    def emptytag(self,name,attrs=None):
        self.tag(name,attrs,True)
        if name in self.partags:
            self.append('\n')
        return self
    def tagend(self,name):
        if name not in self.unendedtags:
            if   not self.__stack:
                raise TypeError('HTML error: Unmatched </%s>. Stack is empty.' % (name))
            elif self.__stack[-1] != name:
                print "The document so far:"
                print ''.join(self)
                raise TypeError('HTML error: <%s> ... </%s>. Stack is:\n\t%s' % (self.__stack[-1],name,'\n\t'.join(self.__stack)))
            else:
                self.__stack.pop()
                self.data.append('</%s>' % name)
            if name in self.partags:
                self.append('\n')
        return self


        

class lineCollector(UserList.UserList):
    def append(self,item):
        if isinstance(item,unicode):
            item = item.encode('utf-8')
        elif not isinstance(item,str):
            raise TypeError('only text is accepted')
        self.data.append(item)
    def extend(self,items):
        for i in items:
            self.append(i)

    
################################################################################
################################################################################

def dummy(name,htmltag=None,attrs={}):
    class _DummyNode(Node):
        nodeName  = name
        htmlTag   = htmltag
        htmlAttrs = attrs
        #def toTeX(self,r):
        #    raise NodeError('Unimplemented toTeX: %s' % self.nodeName)
    return _DummyNode

class FakeTextNode(UserList.UserList):
    def toHTML(self,res):
        res.extend(self.data)
        return res
    def contentToTeX(self,res):
        res.extend(self.data)
        return res
    def toPlainText(self,res):
        res.extend(self.data)
        return res
        
    toPlainHTML = toHTML

class Node(UserList.UserList):
    nodeName  = '<scratch>'
    htmlTag   = None
    htmlAttrs = {}
    ignoreSpace = False
    structuralNode = False
    ## forceTexPar: In TeX an explicit \par should be inserted between two elements that both have forceTexPar == True
    forceTexPar = False
    def __init__(self,manager,parent,attrs,filename,line):
        UserList.UserList.__init__(self)
        self.__attrs = attrs
        self.__filename = filename
        self.__line = line
        self.__parent = parent
        self.__manager = manager
        self.manager = manager
        
        self.__class = []
        if attrs.has_key('class'):
            s = attrs['class'].strip()
            if s:
                self.__class = re.split(r'\s+',s)

        self.pos = filename,line
      
        if attrs.has_key('id'):
            elmid = attrs['id']
            if elmid[0] == '@':
                raise NodeError('Element IDs starting with "@" are reserved for intenal use at %s:%d.' % self.pos)
            self.__manager.addIDTarget(elmid,self)

        if isinstance(self,SectionNode):
            self.__sect = self
        elif parent is None:
            self.__sect = None
        else:
            self.__sect = parent.getSection()

    def getParent(self):
        return self.__parent

    def getSection(self):
        return self.__sect
    def getFilename(self):
        return self.__sect.getSectionFilename()

    def isClass(self,key):
        return key in self.__class

    def hasAttr(self,key):
        return self.__attrs.has_key(key)
    def getAttr(self,key):
        try:
            return self.__attrs[key]
        except KeyError:
            return None
    def getAttrs(self):
        return self.__attrs.items()
    def parentSection(self):
        return self.__sect
    def linkText(self):
        return None
    def makeChild(self,name,attrs,filename,line):
        return globalNodeDict[name](self.__manager, self, attrs, filename, line)
    def newChild(self,name,attrs,filename,line):
        n = self.makeChild(name,attrs,filename,line)
        self.append(n)
        return n
    def handleText(self,data,filename,line):
        if self.ignoreSpace and not data.strip():
            pass
        else:
            self.append(data)
    def endOfElement(self,filename,line):
        pass

    def contentToHTML(self,res):
        for i in self:
            if isinstance(i,Node):
                i.toHTML(res)
            else:
                res.append(i)
        return res

    def toPlainText(self,res):
        for item in self:
            if isinstance(item,basestring):
                res.append(item)
            else:
                item.toPlainText(res)
        return res

    def toHTML(self,res):
        tag = self.htmlTag
        if tag is None:
            for i in self:
                if isinstance(i,Node):
                    if isinstance(i,ParagraphNode):
                        print self.__class__.__name__
                        print self.htmlTag
                        print self.nodeName
                        assert 0
                    i.toHTML(res)
                else:
                    res.append(i)
        else:
            if self.hasAttr('class'):
                attrs = { 'class' : self.getAttr('class') }
            else:
                attrs = None
            if len(self) > 0:
                res.tag(tag,attrs)
                
                if self.hasAttr('id'):
                    res.emptytag('a', { 'name' : self.getAttr('id') } )
                self.contentToHTML(res)
                res.tagend(tag)
            else:
                res.emptytag(tag,attrs)
            if self.structuralNode:
                res.append('\n')
        return res
    def toPlainHTML(self,r):
        for i in self:
            if isinstance(i,Node):
                i.toPlainHTML(r)
            else:
                r.append(i)
        return r
    def toPlainText(self,r):
        for i in self:
            if isinstance(i,Node):
                i.toPlainText(r)
            else:
                r.append(i)
        return r

    def toTeX(self,res):
        Warning('Unhandled %s %s' % (self.__class__.__name__,self.pos))
        try:
            for i in self:
                if isinstance(i,Node):
                    i.toTeX(res)
                else:
                    res.append(i)
            return res
        except None, e:
            print "ASSERT in %s at %s" % (self.__class__.__name__,self.pos)
            raise Exception(e)

    def contentToTeX(self,r):
        for i in self:
            if isinstance(i,Node):
                i.toTeX(r)
            else:

                r.append(i)
        return r
    
    def contentToVerbatimTeX(self,r):
        for i in self:
            if isinstance(i,Node):
                i.toVerbatimTeX(r)
            else:
                r.verbatim(i)
        return r
        

class _StructuralNode(Node):
    """
    Base class for all nodes that work like a paragraph; these have the
    property that they contain _only_ StructuralNode elements (i.e. all inline text
    elements are contained in a <p> or a similar element).
    """
    structuralNode = True
     
    def contentToHTML(self,res):
        nodes = list(self)
        
        while nodes:
            n = nodes.pop(0)
            if isinstance(n,ParagraphNode):
                n.contentToHTML(res)
                if nodes and isinstance(nodes[0],ParagraphNode):
                    res.tag('p')
                res.append('\n')
            elif isinstance(n,basestring):
                print "!!!!Node", self.nodeName,self.pos
            else:

                n.toHTML(res)
        return res
    
    def contentToTeX(self,r):
        if len(self) > 0:
            i = self[0]
            i.toTeX(r)
            prev = i
            
            items = list(self)
            for i in items[1:]:
                assert isinstance(i,Node)                
                if  i.forceTexPar and prev.forceTexPar:
                    r.macro('par').comment('i.forceTexPar = %s, prev.forceTexPar = %s' % (i.forceTexPar,prev.forceTexPar))
                    #print "Insert par!"
                else:
                    r.comment('i.forceTexPar = %s, prev.forceTexPar = %s' % (i.forceTexPar,prev.forceTexPar))
                    #print "Don't insert par: %s, %s" % (i.__class__.__name__,prev.__class__.__name__)
                i.toTeX(r)
                prev = i    
        return r

class SectionNode(Node):
    nodeName = 'section'

    sectcmds = [ 'chapter', 'section', 'subsection','subsubsection', 'subsubsection*' ]

    def __init__(self,
                 manager,
                 parent,
                 sectidx,
                 sectlevel,
                 separatefile, # the child is in a separate file
                 attrs,
                 filename,
                 line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        self.__head = None
        self.__body = None
        self.__sections = []
        self.__sectlvl = sectlevel
        self.__sectidx = sectidx
        self.__ssectcounter = counter()
        self.__manager = manager
        self.__nodeIndex = manager.nextNodeIndex()
        self.__separatefile = separatefile
        self.__parent = parent

        #print "Attributes :",self.getAttr('class')
        if   not separatefile:
            #print "sectidx = %s, not separate file" % str(sectidx)
            self.__childrenInSepFiles = False
        elif self.isClass('split:yes'):
            #print "sectidx = %s, is separate, do split children" % str(sectidx)
            self.__childrenInSepFiles = True
        elif self.isClass('split:no'):
            #print "sectidx = %s, is separate, do not split children" % str(sectidx)
            self.__childrenInSepFiles = False
        elif sectlevel < manager.globalSplitLevel():
            #print "sectidx = %s, is separate, split-level not reached" % str(sectidx)
            self.__childrenInSepFiles = True
        else: # sectlevel >= manager.globalSplitLevel():
            #print "Split level %d >= %d" % (sectlevel, manager.globalSplitLevel())
            #print "sectidx = %s, is separate, split-level reached" % str(sectidx)
            self.__childrenInSepFiles = False
        if separatefile:
            #self.__nodefilename = 'node%0.4d.html' % self.__nodeIndex
            #self.__nodefilename = manager.makeNodeName(sectlevel,)
            self.__nodefilename = None # we cannot know this until we have the section title
        else:
            self.__nodefilename = parent.getSectionFilename()
        
        if attrs.has_key('id'):
            self.__sectionLinkName = attrs['id']
        else:
            self.__sectionLinkName = 'section-node-%s' % self.__nodeIndex

        self.__eqncounter = counter()
        self.__figcounter = counter()
    def newChild(self,name,attrs,filename,line):
        if self.__head is None:
            if name != 'head':
              print 'At %s:%d' % (filename,line)
              assert name == 'head'
            n = HeadNode(self.__manager,self,attrs,filename,line)
            self.__head = n
        elif name == 'body':
            n = BodyNode(self.__manager,self,attrs,filename,line)
            self.__body = n
        elif name == 'section':
            # Special case: parent node is the top-level
            if attrs.has_key('class') and 'preface' in attrs['class'].split(' '):
                sectidx = None
            else:
                sectidx = self.__sectidx + (self.__ssectcounter.next(),)
    
            n = SectionNode(self.__manager,
                            self,
                            sectidx,
                            self.__sectlvl+1,
                            self.__childrenInSepFiles,
                            attrs,
                            filename,
                            line)
            self.__sections.append(n)
        elif name == 'bibliography':
            n = BibliographyNode(self.__manager,
                            self,
                            self.__childrenInSepFiles,
                            attrs,
                            filename,
                            line)
            self.__sections.append(n)
        else:
            print "INVALID in section: ",name
            assert 0
            n = Node.newChild(self,name,attrs,filename,line)
        return n
    def handleText(self,data,filename,line):
        if self.__head is not None and not self.__sections:
            if self.data or data.strip():
                self.append(data)
    def getAuthors(self):
        return self.__head.getAuthors()
    def linkText(self):
        if self.__sectidx:
            return ['.'.join([str(v+1) for v in  self.__sectidx])]
        else:
            assert 0
    def getSectionIndex(self):
        return self.__sectidx
    def nextEquationIndex(self):
        return self.__sectidx + (self.__eqncounter.next(),)
    def nextFigureIndex(self):
        return self.__sectidx + (self.__figcounter.next(),)
    def getSectionLink(self):
        return self.__sectionLinkName
    def getSectionFilename(self):
        if self.__nodefilename is None:
            title = self.getTitle()
            if title is None:
                print "Asked for the section node name before title was available"
                assert 0
            self.__nodefilename = self.__manager.makeNodeName(self.__sectlvl,self.getTitle())
        
        return self.__nodefilename 
    def getSectionURI(self):
        return '%s#%s' % (self.getSectionFilename(),self.__sectionLinkName)
    def appendSubsection(self,node):
        self.__sections.append(node)
    def numChildSections(self):
        return len(self.__sections)

    def getTitle(self):
        return self.__head.getTitle()

    def toHTML(self,res,level):
        """
        Level denotes the depth relative to the split level.
        level=0 means that this section is the outermost in the current file.
        """
        assert not self.__separatefile
        tagn = 'h%d' % (level+1)
        cls = self.getAttr('class')

        if cls is not None:
            res.tag('div',{ 'class' : cls })
        res.extend([tag(tagn),tag('a',{ 'name' : self.__sectionLinkName })])
        res.append('%s. ' % '.'.join([str(i+1) for i in self.__sectidx]))
        self.getTitle().toHTML(res)
        if self.__manager.doDebug():
            filename = self.getAttr('filename')
            line     = self.getAttr('line')

            if filename and line:
                res.append(u'(%s:%d)' % (filename,line))


        res.extend([tagend('a'),tagend(tagn)])
   
        self.__body.contentToHTML(res)
        
        for sect in self.__sections:
            sect.toHTML(res,level+1)

        if cls is not None:
            res.tagend('div')
    def makeFooter(self,res):
        res.extend([self.__manager.getTimeStamp()])
    def makeNavigation(self,d,prev=None,next=None,up=None,top=None,index=None,position='top'):
        #res.extend([tag('div', { 'class' : 'iconbar-navigation' }), tag('table'), tag('tr')])
        assert isinstance (d,dict)

        if prev is None:
            icon = self.__manager.getIcon('prev-passive')
            d['navbutton:icon:prev'].extend([tag('img',{ 'src' : icon})])
        else:
            icon = self.__manager.getIcon('prev')

            d['navbutton:icon:prev'].extend([tag('a',   { 'href' : prev.getSectionFilename(),'alt' : 'Previous' }),
                                             tag('img', { 'src' : icon }),
                                             tagend('a'),
                                             ])
        if up is None:
            icon = self.__manager.getIcon('up-passive')
            d['navbutton:icon:up'].extend([tag('img',{ 'src' : icon })])
        else:
            icon = self.__manager.getIcon('up')
            d['navbutton:icon:up'].extend([tag('a', { 'href' : up.getSectionFilename() }),
                                           tag('img',{ 'src' : icon }),
                                           tagend('a'),
                                           ])
        res = d['navbutton:icon:next']
        if next is None:
            icon = self.__manager.getIcon('next-passive')
            res.extend([tag('img',{ 'src' : icon })])
        else:
            icon = self.__manager.getIcon('next')
            res.extend([ tag('a', { 'href' : next.getSectionFilename(),'alt' : 'Next' }),
                        tag('img',{ 'src' : icon }), 
                        tagend('a'),
                        ])
        
        #res.tag('td',{ 'class' : 'iconbar-doctitle' })
        #if root is not None:
        #    root.getTitle().toHTML(res)
        #res.tagend('td')       

        res = d['navbutton:icon:contents']
        if root is None:
            icon = self.__manager.getIcon('passive')
            res.extend([tag('img',{ 'src' : icon })])
        else:
            icon = self.__manager.getIcon('content')
            res.extend([ tag('a',{ 'href':top.getSectionFilename()}),
                        tag('img',{ 'src' : icon }),
                        tagend('a'),
                        ])

        res = d['navbutton:icon:index']            
        if index is None:
            icon = self.__manager.getIcon('passive')
            res.extend([tag('img',{ 'src' : icon })])
        else:
            icon = self.__manager.getIcon('index')
            res.extend([ tag('a',{ 'href': index}),
                        tag('img',{ 'src' : icon }),
                        tagend('a') ])
        #res.extend([tagend('tr'),tagend('table'),tagend('div')])

        #res.extend([tag('div', { 'class' : 'navigation' }), tag('table'), tag('tr')])
        res = d['navbutton:prev'] 
        if prev is not None:
            res.extend(['Prev: ', tag('a', { 'href' :prev.getSectionFilename() })])
            prev.getTitle().toHTML(res)
            res.extend([tagend('a')])

        res = d['navbutton:up'] 
        if up is not None:
            res.extend(['Up: ',tag('a', { 'href' : up.getSectionFilename() })])
            up.getTitle().toHTML(res)
            res.extend([tagend('a')])
        res = d['navbutton:next'] 
        if next is not None:
            res.extend(['Next: ', tag('a', { 'href' : next.getSectionFilename() })])
            next.getTitle().toHTML(res)
            res.extend([tagend('a')])
        
        
        res = d['navbutton:contents'] 
        if root is not None:
            res.extend([tag('a',{ 'href' : top.getSectionFilename()}),
                        'Contents',
                        tagend('a'),
                        ])
        
        res = d['navbutton:index'] 
        if index is not None:
            res.extend([ tag('a',{ 'href' : index}),
                        'Index',
                        tagend('a'),
                        ])

        #res.extend([tagend('tr'),tagend('table'),tagend('div')])
    


    def makeContents(self,res,curlvl,maxlvl,fullLinks=False,index=None):
        if len(self.__sections) > 0 and curlvl <= maxlvl:
            res.tag('ul', { 'class' : 'contents-level-%d' % curlvl } )
            for s in self.__sections:
                res.tag('li')
                sidx = s.getSectionIndex()
                if sidx:
                    res.append('.'.join([ str(v+1) for v in s.getSectionIndex() ]) + '. ')
                if self.__separatefile or fullLinks:
                    link = s.getSectionURI()
                else:
                    link = '#%s' % s.getSectionLink()
                res.tag('a',{ 'href' : link })
                s.getTitle().toPlainHTML(res)
                res.tagend('a')
                res.append('\n')
                s.makeContents(res,curlvl+1,maxlvl,fullLinks or self.__separatefile)
                res.tagend('li')
            #if index is not None:
            #    res.extend([tag('li'),tag('a',{ 'href' : index }),'Index',tagend('a'),tagend('li')])
            res.tagend('ul')
    def makeSidebarContents(self,res,cnt):
        if len(self.__sections) > 0:
            res.tag('ul', { 'class' : 'sidebar-contents-list' } )
            for s in self.__sections:
                subsecidx = cnt.next()
                res.tag('li')
                sidx = s.getSectionIndex()
                #res.span('sidebar-content-list-button-div')
                enable_expandable_toc = False
                
                if enable_expandable_toc:
                    res.tag('div',{ 'style' : 'float:left; width:0px;' })
                    res.tag('div',{ 'style' : 'float:right;' })
                    if s.numChildSections() > 0:
                        res.tag('a',{ 'href' : 'javascript:toggleDisplayBlock(\'sidebar-content-subsec-%d\')' % subsecidx }).tag('img', { 'src' : self.__manager.getIcon('content-expand-button'),'style' : 'vertical-align : middle;' }).tagend('a').entity('nbsp')
                    else:
                        res.tag('img', { 'src' : self.__manager.getIcon('content-noexpand-button'),'style' : 'vertical-align : middle;' }).entity('nbsp')
                    res.tagend('div').tagend('div')
                
                if sidx:
                    res.append('.'.join([ str(v+1) for v in sidx ]) + '. ')

                link = s.getSectionURI()
                res.tag('a',{ 'href' : link, 'target' : '_top' })
                s.getTitle().toPlainHTML(res)
                res.tagend('a')
                if enable_expandable_toc:
                    res.tag('div',{ 'id' : 'sidebar-content-subsec-%d' % subsecidx, 'style' : 'display:none;' }).append('\n')
                else:
                    res.tag('div',{ 'id' : 'sidebar-content-subsec-%d' % subsecidx }).append('\n')
                ## Hm.... Hardcoded max depth?!? Not nice...
                if self.__sectlvl < 3:
                    s.makeSidebarContents(res,cnt)
                res.tagend('div')
                res.tagend('li')
            res.tagend('ul')
    def makeSidebarIndex(self,r):
        alist = [ (n, ''.join(n.toPlainText([]))) for n in self.__manager.getAnchors() if n.hasAttr('class') and 'index' in re.split(r'\s+',n.getAttr('class')) ]
        alist.sort(lambda lhs,rhs: cmp(lhs[1],rhs[1]))
        
        # List of all letters 
        r.tag('ul',{ 'class' : 'sidebar-index-list' })
        for n,label in alist:
            link = '%s#%s' % (n.getFilename(),n.getAnchorID())
            r.tag('li').tag('a', { 'href' : link,'target' : '_top' })
            n.anchorTextToPlainHTML(r)
            r.tagend('a').tagend('li').append('\n')
        r.tagend('ul')
        
    def toHTMLFile(self,prevNode,nextNode,parentNode,topNode,indexFile):
        assert self.__separatefile
        filename = self.getSectionFilename()

        d = {
                'title:plain'             : htmlCollector(),
                'title:html'              : htmlCollector(),

                'navbutton:icon:prev'     : htmlCollector(),
                'navbutton:icon:next'     : htmlCollector(),
                'navbutton:icon:up'       : htmlCollector(),
                'navbutton:icon:index'    : htmlCollector(),
                'navbutton:icon:contents' : htmlCollector(),
                'navbutton:icon:dummy'    : htmlCollector(),
                'navbutton:prev'          : htmlCollector(),
                'navbutton:next'          : htmlCollector(),
                'navbutton:up'            : htmlCollector(),
                'navbutton:index'         : htmlCollector(),
                'navbutton:contents'      : htmlCollector(),
                
                'sidebar:contents'        : htmlCollector(),
                'sidebar:index'           : htmlCollector(),
                
                'footer'                  : htmlCollector(),
            }
        self.getTitle().toPlainText(d['title:plain'])
        self.getTitle().toHTML(d['title:html'])
        self.makeSidebarIndex(d['sidebar:index'])
        topNode.makeSidebarContents(d['sidebar:contents'])

        d['navbutton:icon:dummy'].extend([tag('img',{ 'src' : self.__manager.getIcon('passive') })])
        
        self.makeNavigation(d,up=parentNode,prev=prevNode,next=nextNode,top=topNode,index='xref.html')

        if self.__sections:
            d['toc:local'] = htmlCollector()
            self.makeContents(d['toc:local'],1,2)
       
        authors = self.__head.getAuthors()
        if authors:
            acollect = htmlCollector()
            d['authors:html'] = acollect
            acollect.div('author')
            ait = iter(authors)
            ait.next().toHTML(acollect)
            acollect.tagend('div')
            for author in ait:
                acollect.appendRaw('&bull;')
                acollect.div('author')
                authors[0].toHTML(acollect)
                acollect.tagend('div')
        
        if self.__body.data or (self.__sections and not self.__childrenInSepFiles):
            d['body'] = htmlCollector()
            res = d['body']
            cls = self.getAttr('class')
            if cls is not None:
                res.tag('div',{ 'class' : cls })

            self.__body.contentToHTML(res)
            
            if not self.__childrenInSepFiles:
                for sect in self.__sections:
                    sect.toHTML(res,1)

            if cls is not None:
                res.tagend('div')
        
        self.makeFooter(d['footer'])
        
        self.__manager.writeHTMLfile(filename,d)  
        
        if self.__childrenInSepFiles:
            for prev,sect,next in zip([None] + self.__sections[:-1],
                                      self.__sections,
                                      self.__sections[1:] + [None]):
                sect.toHTMLFile(prev,next,self,topNode,indexFile)
    def contentToTeX(self,res,level):
        self.__body.contentToTeX(res)
        
        for sect in self.__sections:
            sect.toTeX(res,level+1)
        return res 

    def toTeX(self,res,level):
        macro = self.sectcmds[level-1]

        res.append('\n')
        res.macro(macro)
        res.groupStart()
        self.getTitle().contentToTeX(res)
        res.groupEnd().comment()
        if self.hasAttr('id'):
            res.macro('label').groupStart()._raw(self.getAttr('id')).groupEnd().comment()
            #res.macro('hypertarget').groupStart()._raw(self.getAttr('id')).groupEnd().groupStart()
            #self.getTitle().contentToTeX(res)
            #res.groupEnd().comment()

        self.contentToTeX(res,level)
        return res
       

class BibliographyNode(SectionNode):
    nodeName = 'bibliography'
    def __init__(self,
                 manager,
                 parent,
                 separatefile, # the child is in a separate file
                 attrs,
                 filename,
                 line):
        SectionNode.__init__(self,manager,parent,(),0,True,attrs,filename,line)
        self.__manager = manager
        #self.__nodeIndex = manager.nextNodeIndex()
        #self.__sectionLinkName = 'section-node-%s' % self.__nodeIndex

        self.__items = []

        if separatefile:
            self.__nodefilename = self.getSectionFilename()
            #'node%0.4d.html' % self.__nodeIndex
        else:
            self.__nodefilename = parent.getSectionFilename()
    def getTitle(self):
        return FakeTextNode(['Bibliography']);

    def handleText(self,data,filename,line):
        pass

    def newChild(self,name,attrs,filename,line):
        if name == 'bibitem':
            n = BibItemNode(self.__manager, self,attrs,filename,line)
            self.__items.append(n)
        else:
            n = SectionNode.newChild(self,name,attrs,filename,line)
        return n

    def toHTMLFile(self,prevNode,nextNode,parentNode,topNode,indexFile):
        d = {
                'title:plain'             : htmlCollector(),
                'title:html'              : htmlCollector(),

                'navbutton:icon:prev'     : htmlCollector(),
                'navbutton:icon:next'     : htmlCollector(),
                'navbutton:icon:up'       : htmlCollector(),
                'navbutton:icon:index'    : htmlCollector(),
                'navbutton:icon:contents' : htmlCollector(),
                'navbutton:icon:dummy'    : htmlCollector(),
                'navbutton:prev'          : htmlCollector(),
                'navbutton:next'          : htmlCollector(),
                'navbutton:up'            : htmlCollector(),
                'navbutton:index'         : htmlCollector(),
                'navbutton:contents'      : htmlCollector(),
                
                'sidebar:contents'        : htmlCollector(),
                'sidebar:index'           : htmlCollector(),
                
                'footer'                  : htmlCollector(),
                'body'                    : htmlCollector(),
            }
        
        d['title:plain'].append('Bibliography')
        self.getTitle().toHTML(d['title:html'])
        self.makeSidebarIndex(d['sidebar:index'])
        topNode.makeSidebarContents(d['sidebar:contents'])

        d['navbutton:icon:dummy'].extend([tag('img',{ 'src' : self.__manager.getIcon('passive') })])
        
        r = d['body']
        
        r.div("document-bibliography")

        r.tag('dl',{ 'class' : 'bibliography-item-list'})
        for n in self.__items:
            n.toHTML(r)
            
        r.tagend('dl')
        
        r.tagend('div')

        self.__manager.writeHTMLfile(self.__nodefilename,d)  

    def contentToTeX(self,r,level):
        if self.__items:
            r.macro(self.sectcmds[0]).group('Bibliography').lf()
            r.begin('thebibliography').group(['XXXXXX']).lf()
            for n in self.__items:
                n.toTeX(r) 

            r.end('thebibliography').lf()
        return r
    def toTeX(self,r,level):
        return self.contentToTeX(r,level)


class BibItemNode(Node):
    nodeName = 'bibitem'
    
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        self.__citeidx = manager.getNewCiteIdx()
        self.__citelabel = u'[%d]' % (self.__citeidx+1)
        self.__anchorname = '@cite-%s' % attrs['key']

        manager.addIDTarget(self.__anchorname,self)
    def linkText(self):
        return self.__citelabel

    def toHTML(self,r):
        r.tag('dt').tag('a',{ 'name' : self.__anchorname}).append(self.__citelabel).tagend('a').tagend('dt')
        r.tag('dd')
        Node.toHTML(self,r)
        r.tagend('dd')
        return r

    def toTeX(self,r):
        r.macro('bibitem').groupStart()._raw(self.getAttr('key')).groupEnd()
        Node.toTeX(self,r)
        r.lf()
        return r

class _IndexNode(SectionNode):
    def __init__(self,
                 manager,
                 parent):
        SectionNode.__init__(self,manager,parent,(),0,True,{},'xref.html',0)
        self.__manager = manager
        self.__parent = parent
    def getTitle(self):
        return FakeTextNode(['Index'])
    def getSectionFilename(self):
        return 'xref.html'
    def getSectionURI(self):
        return self.getSectionFilename()
    def toHTMLFile(self,prevNode,nextNode,parentNode,topNode,indexFile):
        manager = self.__manager

        d = {
                'title:plain'             : htmlCollector(),
                'title:html'              : htmlCollector(),

                'navbutton:icon:prev'     : htmlCollector(),
                'navbutton:icon:next'     : htmlCollector(),
                'navbutton:icon:up'       : htmlCollector(),
                'navbutton:icon:index'    : htmlCollector(),
                'navbutton:icon:contents' : htmlCollector(),
                'navbutton:icon:dummy'    : htmlCollector(),
                'navbutton:prev'          : htmlCollector(),
                'navbutton:next'          : htmlCollector(),
                'navbutton:up'            : htmlCollector(),
                'navbutton:index'         : htmlCollector(),
                'navbutton:contents'      : htmlCollector(),
                
                'sidebar:contents'        : htmlCollector(),
                'sidebar:index'           : htmlCollector(),
                
                'footer'                  : htmlCollector(),
                'body'                    : htmlCollector(),
            }
        
        d['title:plain'].append('Index')
        self.getTitle().toHTML(d['title:html'])
        self.makeSidebarIndex(d['sidebar:index'])
        topNode.makeSidebarContents(d['sidebar:contents'])

        d['navbutton:icon:dummy'].extend([tag('img',{ 'src' : self.__manager.getIcon('passive') })])



        alist = [ (n, ''.join(n.toPlainText([]))) for n in manager.getAnchors() if n.hasAttr('class') and 'index' in re.split(r'\s+',n.getAttr('class')) ]
        
        adict = dict([('#',[])] + [ (chr(i),[]) for i in range(ord('a'),ord('z')+1) ])
        
        for n,k in alist:
            keyltr = k[0].lower()
            if not adict.has_key(keyltr):
                adict['#'].append((k,n))
            else:
                adict[keyltr].append((k,n))
        for k in adict:
            adict[k].sort(lambda lhs,rhs: cmp(lhs[0],rhs[0]))

        r = d['body']

        # List of all letters 
        keys = adict.keys()
        keys.sort()
        def _alphaindexlink(k):
            if adict[k]:
                r.tag('a',{ 'href' : '#@index-letter-%s' % k}).append('%s' % k.upper()).tagend('a')
            else:
                r.append('%s' % (k or '.').upper())
        r.div('index-summary')
        _alphaindexlink(keys[0])
        for k in keys[1:]:
            r.append(' | ')
            _alphaindexlink(k)
        r.tagend('div')
        
        r.div('index-list')
        for k in keys:
            l = adict[k]
            if l:
                r.div('index-letter')
                r.tag('h1').tag('a',{ 'name' : '@index-letter-%s' % k }).append(k.upper()).tagend('a').tagend('h1')
                r.tag('ul')
                for label,n in l:
                    link = '%s#%s' % (n.getFilename(),n.getAnchorID())
                    r.tag('li').tag('a', { 'href' : link })
                    n.anchorTextToPlainHTML(r)
                    r.tagend('a').tagend('li')
                r.tagend('ul')
                r.tagend('div')
        r.tagend('div')
        
        manager.writeHTMLfile('xref.html',d)
    def toTeX(self,r,level):
        return r
    def contentToTeX(self,r):
        return r

class DocumentNode(SectionNode):
    nodeName = 'sdocmlx'
    def __init__(self,manager,parent,attrs,filename,line):
        self.__manager = manager
        SectionNode.__init__(self,manager,parent,(),1,True,attrs,filename,line)
        self.__body = None
        self.__sections = []
    def getSectionFilename(self):
        return 'index.html'
    def endOfElement(self,filename,line):
        self.appendSubsection(_IndexNode(self.__manager,self))
        SectionNode.endOfElement(self,filename,line)
    def newChild(self,name,attrs,filename,line):
        # horrible hack to intercept body and sections
        n = SectionNode.newChild(self,name,attrs,filename,line)
        if   name == 'body':    self.__body = n
        elif name == 'section': self.__sections.append(n)
        
        return n
    def makeSidebarFile(self,filename='sidebar.html'):
        # Create a file containing sidebar stuff (index and contents)
        d = {   'sidebar:contents' : htmlCollector(),
                'sidebar:index'    : htmlCollector() }
        self.makeSidebarContents(d['sidebar:contents'],counter())
        self.makeSidebarIndex(d['sidebar:index']) 

        self.__manager.writeHTMLfile(filename,d,'sidebar')  

    def toTeX(self,res):
        self.getTitle().contentToTeX(res['TITLE'])
        res['DATE']
        auths = self.getAuthors()
        if auths:
            self.getAuthors().contentToTeX(res['AUTHOR'])
        else:
            res['AUTHOR']
        
        #self.contentToTeX(res['BODY'],0)

        #self.__body.contentToTeX(res['PREFACE'])

        body    = res['BODY']
        preface = res['PREFACE']

        self.__body.contentToTeX(preface) 

        sects = list(self.__sections)
        while sects and sects[0].hasAttr('class'):
            cls = sects[0].getAttr('class')
            if 'preface' in cls.split(' '):
                sects.pop(0).toTeX(preface,1)
            else:
                break

        for sect in sects:
            sect.toTeX(body,1)
        return res


class BodyNode(_StructuralNode):
    nodeName = 'body'

class HeadNode(Node):
    nodeName = 'head'
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        self.__abstract = None
        self.__authors  = None
        self.__title    = None
        self.__date     = None
        self.__manager  = manager

    def newChild(self,name,attrs,filename,line):
        if name == 'defines':
            n = DummyNode(self.__manager,self,attrs,filename,line)
        else:
            n = Node.makeChild(self,name,attrs,filename,line)
            if name == 'date' : 
                self.__date = n
            elif name == 'title':
                self.__title = n
            elif name == 'authors':
                self.__authors = n
            elif name == 'abstract':
                self.__abstract = n
            else:
                print('Invalid element in head: <%s>' % name)
                assert 0
        return n

    def getAuthors(self):
        return self.__authors
    def getTitle(self):
        assert self.__title is not None
        return self.__title

DummyNode               = dummy('*dummy*')

class AbstractNode(Node):
    nodeName = 'abstract'
    pass

class AuthorsNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toHTML(self,r):
        if self.data:
            r.extend([tag('div', { 'class' : "authors" }),
                      tag('table'),
                      tag('tr'),
                      tag('td', { 'align' : "center", 'class' : "author" }) ])
            self[0].toHTML(r)
            r.tagend('td')
            r.tagend('tr')

            r.extend([tag('tr'),
                      tag('td', { 'align' : "center" }),
                      entity('bull'),
                      tagend('td'),
                      tagend('tr') ])
            for author in self.data[1:]:
                r.extend([tag('tr'),tag('td', { 'align' : "center", 'class' : "author" }) ])
                author.toHTML(r)
                r.tagend('td')
                r.tagend('tr')
            r.tagend('table')
            r.tagend('div')
    def contentToTeX(self,r):
        self[0].toTeX(r)

        for author in self.data[1:]:
            r.macro('\\').macro('authorsep').macro('\\')
            author.toTeX(r)
         
            
class AuthorNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toHTML(self,r):
        d = { 'firstname' : None,
              'lastname'  : None,
              'email'     : None,
              'institution' : [],
               }
        for n in self:
            d[n.nodeName] = n

        if d['firstname'] or d['lastname']: 
            r.div('author-name')
            if d['firstname'] and d['lastname']:
                d['firstname'].toHTML(r)
                r.append(' ')
                d['lastname'].toHTML(r)
            elif d['lastname']:
                d['lastname'].toHTML(r)
            elif d['firstname']:
                d['firstname'].toHTML(r)
            r.tagend('div')

        if d['email']:
            r.div('author-email')
            d['email'].toHTML(r)
            r.tagend('div')
    def toTeX(self,r):
        return self.contentToTeX(r)

        
    def contentToTeX(self,r):
        d = { 'firstname' : None,
              'lastname'  : None,
              'email'     : None,
              'institution' : [],
               }
        for n in self:
            d[n.nodeName] = n
        
        hasname = False
        if d['firstname'] or d['lastname']:
            if d['firstname'] and d['lastname']:            
                d['firstname'].toTeX(r)
                r.append(' ')
                d['lastname'].toTeX(r)
                hasname = True
            elif d['lastname']:
                d['lastname'].toTeX(r)
                hasname = True
            elif d['firstname']:
                d['firstname'].toTeX(r)
                hasname = True

        if d['email']:
            if hasname:
                r.append('{, }')
            d['email'].toTeX(r)
        

class TitleNode(Node):
    def toTeX(self,res):
        res.macro('title')
        res.groupStart()
        self.contentToTeX(res)
        res.groupEnd()

AuthorFirstNameNode     = dummy('firstname')
AuthorLastNameNode      = dummy('lastname')
AuthorEmailNode         = dummy('email')
AuthorInstitutionNode   = dummy('institution')
AuthorInstitutionNameNode = dummy('name')
AuthorInstitutionAddressNode = dummy('address')

class ParagraphNode(Node):
    htmlTag = 'p'
    forceTexPar = True
    def toTeX(self,res):
        self.contentToTeX(res)
    def contentToTeX(self,res):
        for i in self:
            if isinstance(i,Node):
                i.toTeX(res)
            else:
                res.append(i)
    def toHTML(self,res):
        assert 0

class DivNode(_StructuralNode):
    htmlTag = 'div'
    def toTeX(self,res):
        self.contentToTeX(res)

class _SimpleNode(Node):
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
    
    def toPlainHTML(self,res):
        res.tag(self.htmlTag,self.htmlAttrs)
        for i in self:
            if isinstance(i,Node):
                i.toPlainHTML(res)
            else:
                res.append(i)
        res.tagend(self.htmlTag)
        
    def toTeX(self,res):
        res.groupStart()
        res.macro(self.macro)
        res.append(' ')
        self.contentToTeX(res)
        res.groupEnd()

    def toVerbatimTeX(self,res):
        res.groupStart()
        res.macro(self.macro)
        res.append(' ')
        self.contentToVerbatimTeX(res)
        res.groupEnd()
    
    def toHTML(self,res):
        attrs = dict(self.getAttrs())
        res.tag(self.htmlTag,attrs)
        for i in self:
            if isinstance(i,Node):
                i.toHTML(res)
            else:
                res.append(i)
        res.tagend(self.htmlTag)

class EmphasizeNode(_SimpleNode):
    htmlTag = 'em'
    macro = 'em'
class TypedTextNode(_SimpleNode):
    htmlTag = 'tt'
    macro = 'tt'
class BoldFaceNode(_SimpleNode):
    htmlTag = 'b'
    macro = 'bf'
class SmallCapsNode(_SimpleNode):
    htmlTag = 'div'
    htmlAttrs = { 'class' : 'textsc' }
    macro = 'sc'
class SpanNode(_SimpleNode):
    htmlTag = 'span'
    def toTeX(self,res):
        if self.hasAttr('class'):
            styles = self.manager.styleLookup(self.getAttr('class'))
            for s in styles:
                res.macro(s).groupStart()

            self.contentToTeX(res)
            for s in styles:
                res.groupEnd()
        else:
            self.contentToTeX(res)
    def toVerbatimTeX(self,res):
        if self.hasAttr('class'):
            styles = self.manager.styleLookup(self.getAttr('class'))
            for s in styles:
                res.macro(s).groupStart()
            self.contentToVerbatimTeX(res)
            for s in styles:
                res.groupEnd()
        else:
            self.contentToVerbatimTeX(res)

        

class FontNode(_SimpleNode):
    htmlTag = 'font'

class BreakNode(_SimpleNode):
    nodeName = 'br'
    htmlTag = 'br'
    def toTeX(self,res):
        res.macro('nullbox').macro('\\') 


                           
#XXSmallNode = dummy('XXSmallNode')
#XSmallNode  = dummy('XSmallNode')
#SmallNode   = dummy('SmallNode')
#LargeNode   = dummy('LargeNode')
#XLargeNode  = dummy('XLargeNode')
#XXLargeNode = dummy('XXLargeNode')
#LargerNode  = dummy('LargerNode')
#SmallerNode = dummy('SmallerNode')
                                   
class ReferenceNode(Node):
    nodeName = 'ref' 
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)

        if attrs.has_key('exuri'):
            self.__exuri = attrs['exuri']
            self.__ref   = attrs['ref']
        else:
            self.__exuri = None
            if attrs.has_key('type'):
                self.__ref = manager.getIDTarget('@%s-%s' % (attrs['type'], attrs['ref']),self)
            elif attrs.has_key('ref'):
                self.__ref   = manager.getIDTarget(attrs['ref'],self)
            else:
                raise NodeError("Missing attribute 'type' or 'ref' at %s:%d" % (filename,line))
    def toHTML(self,r):
        if self.__exuri:
            r.append('[??]')
        else:
            f,k = self.__ref.getLink()
            if f == self.getFilename():
                link = '#%s' % k
            else:
                link = '%s#%s' % (f,k)
            if self.hasAttr('class'):
                r.anchor(link,self.getAttr('class'))
            else:
                r.anchor(link)

            if len(self.data):
                self.contentToHTML(r)
            else:
                linkText = self.__ref.linkText()
                if linkText is None:
                    pass # raise NodeError('Required linktext at %s:%d' % self.pos)
                    r.append('[??]')
                else:
                    r.extend(self.__ref.linkText())
            r.tagend('a')
    def toTeX(self,r):
        if self.__exuri:
            r.append('[??]')
        else:
            #r.macro('hyperlink')
            #r.group(self.__ref.linkText())
            #r.group([u'XXXX'])
            #r.groupStart()
            #self.contentToTeX(r)
            #r.groupEnd()
            r.macro('hyperref').moptStart()._raw(self.__ref.getID()).moptEnd()
            if len(self.data) > 0:
                r.groupStart()
                self.contentToTeX(r)
                r.groupEnd()
            else:
                # horrible hack: We don't want to mix _out_ numbering with TeX's automatic numbering. 
                # TeX produces numbers for certain things like equations, figures and tables, so in these
                # cases we ignore any "linktext" and just use a \ref{} instead
                linktext = self.__ref.linkText()
                if linktext:
                    r.group(self.__ref.linkText())
                else:
                    r.groupStart().macro('ref').groupStart()._raw(self.__ref.getID()).groupEnd().groupEnd()


class HyperRefNode(Node):
    nodeName = 'a'
    def toHTML(self,r):
        clsstr = ''
        url = self.getAttr('url')
        if self.hasAttr('class'):
            r.anchor(url,self.getAttr('class'))
        else:
            r.anchor(url)
        if self:
            for i in self:
                if isinstance(i,Node):
                    i.toHTML(r)
                else:
                    r.append(i)
        else:
            r.append(url)
        r.tagend('a')
    def toTeX(self,r):
        r.macro('htmladdnormallink')
        if not self:
            r.groupStart()._raw(self.getAttr('url')).groupEnd()
        else:
            r.groupStart()
            for i in self:
                if isinstance(i,Node):
                    i.toTeX(r)
                else:
                    r.append(i)
            r.groupEnd()        
        r.groupStart()._raw(self.getAttr('url')).groupEnd()
        return r

LinkTextNode            = dummy('LinkTextNode')

class AnchorNode(Node):
    nodeName = 'a'
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        manager.addAnchor(self)
        if attrs.has_key('id'):
            self.__anchor_name = attrs['id']
        else:
            self.__anchor_name = '@generated-ID:%x' % id(self)

    def getAnchorID(self):
        return self.__anchor_name
    def linkText(self):
        r = []
        self.contentToHTML(r)
        return r
    def anchorTextToPlainHTML(self,res):
        return self.toPlainHTML(res)
    def toHTML(self,res):
        return res.emptytag('a', { 'name' : self.__anchor_name }) 
    def toTeX(self,res):
        res.macro('label').groupStart()._raw(self.__anchor_name).groupEnd().comment()
        #res.macro('hypertarget').groupStart()._raw(self.__anchor_name).groupEnd().group(self.linkText()).comment()
        return res


class ItemListNode(Node):
    htmlTag = 'ul'
    def toTeX(self,r):
        if len(self):
            r.comment()
            r.begin('itemize')
            for i in self:
                if isinstance(i,Node):
                    i.toTeX(r)
            r.end('itemize').lf()
class DefinitionListNode(Node):
    htmlTag = 'dl'
    def toTeX(self,r) :
        if len(self) > 0:
            r.comment()
            r.begin('description')
            for i in self:
                if isinstance(i,Node):
                    i.toTeX(r)
            r.end('description').lf()
class ListItemNode(_StructuralNode): 
    htmlTag = 'li'
    def toTeX(self,r):
        r.macro('item').group()
        if self.hasAttr('id'):
            r.macro('label').groupStart()._raw(self.getAttr('id')).groupEnd()
        self.contentToTeX(r)
        r.append('\n')
class DefinitionTitleNode(_StructuralNode):
    htmlTag = 'dt'
    def toTeX(self,r) :
        r.macro('item')
        r.groupStart()
        if self.hasAttr('id'):
            r.macro('label').groupStart()._raw(self.getAttr('id')).groupEnd()
        self.contentToTeX(r)
        r.groupEnd().macro('nullbox').macro('par').lf()

class DefinitionDataNode(_StructuralNode): 
    htmlTag = 'dd'
    def toTeX(self,r):
        self.contentToTeX(r)
        r.append('\n')
    
                   
class _AlignNode(_StructuralNode):
    alignText = 'left'
    def toHTML(self,res):
        res.tag('div',{ 'style' : 'text-align : %s;' % self.alignText })
        self.contentToHTML(res)
        res.tagend('div')
    
class CenterNode(_AlignNode):
    alignText = 'center'
    def toTeX(self,r):
        r.begin('center')
        r.append('\n')
        self.contentToTeX(r)
        r.end('center')
        r.append('\n')
class FlushLeftNode(_AlignNode):
    alignText = 'left'
    def toTeX(self,r):
        r.begin('flushleft')
        r.append('\n')
        self.contentToTeX(r)
        r.end('flushleft')
        r.append('\n')
class FlushRightNode(_AlignNode):
    alignText = 'right'
    def toTeX(self,r):
        r.begin('flushright')
        r.append('\n')
        self.contentToTeX(r)
        r.end('flushright')
        r.append('\n')


class NoteNode(_StructuralNode): 
    def toHTML(self,res):
        res.tag('div',{ 'class' : 'note-element' })
        res.append('NOTE:')
        res.tag('div',{ 'class' : 'note-content' })
        self.contentToHTML(res)
        res.tagend('div')
        res.tagend('div')
    def toTeX(self,res):
        pass

class TableNode(Node):
    htmlTag = 'table'
    forceTexPar = True

    def handleText(self,data,filename,line):
        pass

    def toHTML(self,res):
        if self.hasAttr('class'):
            cls = self.getAttr('class')
        else:
            cls = 'generic-table'
        res.tag('table', { 'class' : cls })
        for row in self:
            if isinstance(row,TableRowNode):
                row.toHTML(res)
        res.tagend('table')
        return res
    def toTeX(self,r):
        #if self.hasAttr('class') and self.getAttr('class') == 'class-item-list':
        #    print "Table node in: %s @ %s" % (self.getParent().__class__.__name__,self.pos)
        cellhalign = [ s[0] for s in re.split(r'\s+',self.getAttr('cellhalign')) ]
        r.begin('tabular').group(''.join(cellhalign)).append('\n')
        self.contentToTeX(r)
        r.end('tabular')
        return r

TableColumnNode         = dummy('TableColumnNode') 
class TableRowNode(Node):
    htmlTag = 'tr'
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        for n in self.data[:-1]:
            n.toTeX(r)
            r.tab()
        self.data[-1].toTeX(r)
        r.rowend().lf()
        return r
class TableCellNode(_StructuralNode):
    htmlTag = 'td'
    def toTeX(self,r):
        return self.contentToTeX(r)

class FloatNode(_StructuralNode):
    nodeName = 'float'
    def handleText(self,data,filename,line):
        pass
    def __init__(self,manager,parent,attrs,filename,line):
        _StructuralNode.__init__(self,manager,parent,attrs,filename,line)
        self.__body = None
        self.__caption = None
        
        if attrs.has_key('id'):
            self.__index = self.parentSection().nextFigureIndex()
        else:
            self.__index = None

    def getLabel(self):
        if self.__index is None:
            return None
        else:
            return u'.'.join([str(v+1) for v in  self.__index])

    def linkText(self):
        if self.__index is None:
            raise NodeError('Requested linktext for a id-less node "%s"' % self.nodeName)
        return ['.'.join([str(v+1) for v in  self.__index])]

    def append(self,item):
        if   isinstance(item,FloatBodyNode):
            self.__body = item
        elif isinstance(item,FloatCaptionNode):
            self.__caption = item
        else:
            assert 0
        
    def toHTML(self,res):
        if self.hasAttr('class'):
            cls = re.split(r'\s+',self.getAttr('class'))
        else:
            cls = [ ]
        f = None
        if self.hasAttr('float'):
            f = self.getAttr('float')
            if   f == 'left':
                cls.append('float-left-element')
            elif f == 'right':
                cls.append('float-right-element')
            else: # f == 'no':
                cls.append('nofloat-element')

        res.tag('div',{ 'class' : ' '.join(cls) })
        if f == 'no':
            res.tag('center')
        res.tag('table',{ 'class' : 'float-content'})
        res.tag('tr')
        self.__body.toHTML(res)
        res.tagend('tr')

        res.tag('tr')
        self.__caption.toHTML(res)
        res.tagend('tr')
        res.tagend('table')
        if f == 'no':
            res.tagend('center')
        res.tagend('div')
    def toTeX(self,r):
        # we're cheap, so we just use LaTeX's "figure" environment
        r.begin('figure')# need some options too...
        if self.__body is not None:
            self.__body.toTeX(r)
        r.macro('caption').groupStart()
        if self.hasAttr('id') is not None:
            r.macro('label').groupStart()._raw(self.getAttr('id')).groupEnd()
        if self.__caption:
            self.__caption.toTeX(r)
        r.groupEnd()
        r.end('figure')

class FloatBodyNode(_StructuralNode):
    def toHTML(self,res):
        res.tag('td',{ 'class' : 'float-body' })
        self.contentToHTML(res)
        res.tagend('td')
    def toTeX(self,r):
        self.contentToTeX(r)

class FloatCaptionNode(_SimpleNode):
    def __init__(self,manager,parent,attrs,filename,line):
        _SimpleNode.__init__(self,manager,parent,attrs,filename,line)
        self.__parent = parent
    def toHTML(self,res):
        res.tag('td',{ 'class' : 'float-caption' })
        label = self.__parent.getLabel()
        if label:
            res.append('Fig. %s. ' % label)
        self.contentToHTML(res)
        res.tagend('td')
    def toTeX(self,r):
        self.contentToTeX(r)

class PreformattedNode(Node):
    # class: nolink
    nodeName = 'pre'
    htmlTag = 'pre'
    converted = False
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        if self.hasAttr('type'):
            self.__type = self.getAttr('type').split('/')
        else:
            self.__type = 'text','plain'
        if self.hasAttr('url'):
            self.__url = self.getAttr('url')
            self.__internalurl,self.__urlbase = manager.includeExternalURL(self.__url)
        else:
            self.__url = None
            self.__internalurl,self.__urlbase = None,None
        self.__firstline = None
        if attrs.has_key('firstline'):
            self.__firstline = int(attrs['firstline'])
        self.__unique_index = manager.getUniqueNumber()

    def toHTML(self,r):
        clss = []
        if self.hasAttr('class'):
            attrs = { 'class' : self.getAttr('class') }
            clss = re.split(r'\s+',self.getAttr('class').lower())
        else:
            attrs = {}
        
        if 'lineno:yes' in clss:
            lineno = self.__firstline
            if lineno is None: lineno = 1
        elif 'lineno:no' in clss:
            lineno = None
        else:
            lineno = self.__firstline
        attrs['id'] = '@preformatted-node-%d' % self.__unique_index
        r.tag('pre',attrs)

        if self.__url is not None and not 'link:no' in clss:
            r.span("source-link")
            r.anchor(self.__internalurl)
            r.append('Download %s' % self.__urlbase)
            r.tagend('a')
            if lineno is not None:
                r.append(' | ')
                r.anchor('javascript:toggleLineNumbers(\'%s\')' % attrs['id'])
                r.append('Toggle line no.')
                r.tagend('a')
            r.tagend('span')
            lineno = self.__firstline
            


        if 1:
            nodes = list(self)
                
            #
            #while nodes and not isinstance(nodes[0],Node)  and not nodes[0].strip():  
            #    if lineno is not None:
            #         lineno += 1
            #    nodes.pop(0)
            #while nodes and not isinstance(nodes[-1],Node) and not nodes[-1].strip(): 
            #    nodes.pop()

            if lineno is None:
                for n in nodes:
                    if isinstance(n,Node):
                        n.toHTML(r)
                    else:
                        r.append(n)
            else:
                lst = []
                cur = []
                for l in nodes:
                    if isinstance(l,Node):
                        if cur:
                            lst.append(cur)
                            cur = []
                        lst.append(l)
                    else:
                        cur.append(l)
                if cur:
                    lst.append(cur)

                
                r.span('line-no')
                r.append('%3d ' % lineno)
                r.tagend('span')
                lineno = lineno + 1
                for l in lst:
                    if isinstance(l,Node):
                        l.toHTML(r)
                    else:
                        lines = ''.join(l).split('\n')

                        r.append(lines[0])
                        for line in lines[1:]:
                            r.append('\n')
                            r.span('line-no')
                            r.append('%3d ' % lineno)
                            r.tagend('span')
                            r.append(line)
                            lineno = lineno + 1

        r.tagend('pre')
        
    def toTeX(self,r):
        if self.hasAttr('class'):
            clsd = dict([ (v,v) for v in re.split(r'[ ]+', self.getAttr('class').strip()) ])
        else:
            clsd = {}
        lineno = self.__firstline
        nodes = list(self)

        if lineno is not None and self.__urlbase is not None and not clsd.has_key('link:no'):
            #r.macro('beginpre').group(self.__urlbase).group(str(lineno)).macro('nullbox').group()
            r.macro('beginpre').group(self.__urlbase).group(str(lineno)).comment()
        else:
            #r.macro('beginpreplain').macro('nullbox').group()
            r.macro('beginpreplain').comment()
        
        for n in nodes:
            if isinstance(n,Node):
                n.toVerbatimTeX(r)
            else:
                r.verbatim(n)
        
        r.comment().macro('endpre').lf()
                           
                           
class InlineMathNode(Node):
    nodeName = 'm'
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        self.__eqnidx = None
        if attrs.has_key('filename') and attrs.has_key('line'):
            self.__filename = attrs['filename']
            self.__line     = attrs['line']
        else:
            self.__filename = None 
            self.__line     = None
    
    def getEqnIdx(self):
        if self.__eqnidx is None:
            self.__eqnidx = manager.addEquation('$%s$' % ''.join(self.contentToTeX(texCollector(self.manager,texCollector.MathMode))),self.__filename, self.__line)
        return self.__eqnidx
    def toTeX(self,r):
        r.inlineMathStart()
        self.contentToTeX(r)
        r.inlineMathEnd()
        return r
        
    def toHTML(self,r):
        r.span('m')
        r.tag('img', { 'src' : self.getEqnIdx() } )
        r.tagend('span')

class MathEnvNode(Node):
    nodeName = 'math'
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)

        if attrs.has_key('id'):
            self.__index = self.parentSection().nextEquationIndex()
        else:
            self.__index = None
        self.__eqnidx = None
        if attrs.has_key('filename') and attrs.has_key('line'):
            self.__filename = attrs['filename']
            self.__line     = attrs['line']
        else:
            self.__filename = None 
            self.__line     = None
    
    def getEqnIdx(self):
        if self.__eqnidx is None:
            self.__eqnidx = manager.addEquation('$\\displaystyle{}%s$' % ''.join(self.contentToTeX(texCollector(self.manager,texCollector.MathMode))),self.__filename, self.__line)
        return self.__eqnidx
    def toTeX(self,r):
        r.append('\n')
        if not self.hasAttr('id'):
            r.macro('[')
        else:
            r.begin('equation')
            r.macro('label').group(self.getAttr('id'))
            #r.macro('hypertarget').group(self.getAttr('id')).group()
        r.startMathMode()
        self.contentToTeX(r)
        #for i in self:
        #    if isinstance(i,Node):
        #        i.toTeX(r)
        #    else:
        #        r.append(i)
        r.endMathMode()
        if not self.hasAttr('id'):
            r.macro(']')
        else:
            r.end('equation')
        return r
    def linkText(self):
        if self.__index is None:
            raise NodeError('Requested linktext for a id-less node "%s"' % self.nodeName)
        return ['.'.join([str(v+1) for v in  self.__index])]
    def toHTML(self,r):
        r.div('math-equation')
        if self.hasAttr('id'):
            r.emptytag('a',{ 'name' : self.getAttr('id') } )
        r.tag('table', {'width' : '100%' })
        r.tag('tr')
        r.tag('td',{ 'width' : "100%%", 'class' : "math" })
        r.tag('img', {'src' : self.getEqnIdx() })
        r.tagend('td')
        if self.__index is not None:
            r.extend([tag('td',{ 'width' :"0px" }),
                      '(',
                      '.'.join([str(i+1) for i in self.__index]),
                      ')',
                      tagend('td') ])
        else:
            r.emptytag('td')
        r.tagend('tr')
        r.tagend('table')
        r.tagend('div')

class MathEqnArrayNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toHTML(self,r):
        r.append('<div class="math-eqnarray"><table width="100%">')

        for n in self:
            r.append('<tr>')
            n.toHTML(r)
            r.append('</tr>\n')

        r.append('</table></div>\n')
class EqnNode(Node):
    nodeName = 'eqn'
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)

        if attrs.has_key('id'):
            self.__index = self.parentSection().nextEquationIndex()
        else:
            self.__index = None
        
        self.__eqnidx = None
        if attrs.has_key('filename') and attrs.has_key('line'):
            self.__filename = attrs['filename']
            self.__line     = attrs['line']
        else:
            self.__filename = None 
            self.__line     = None
    
    def getEqnIdx(self):
        if self.__eqnidx is None:
            self.__eqnidx = manager.addEquation(''.join(self.toTeX([])),self.__filename,self.__line)
        return self.__eqnidx

    def toTeX(self,r):
        r.append('$\\displaystyle 123 $')
        return r
    def linkText(self):
        if self.__index is None:
            raise NodeError('Requested linktext for a id-less node "%s"' % self.nodeName)
        return [ '.'.join([str(v+1) for v in  self.__index]) ]
    def toHTML(self,r):
        r.append('<td width="100%%" class="math"><img src="math/math%d.png"></td>' % (self.getEqnIdx()+1))
        if self.__index is not None:
            r.append('<td width="0px">(%s)</td>' % '.'.join([str(i+1) for i in self.__index]))
        else:
            r.append('<td/>')
        
        
        
        #r.append('<div class="math"><img src="math/math%d.png"</div>' % (self.__eqnidx+1))
                           

         

class _MathNode(Node):
    def contentToTeX(self,r):
        for i in self:
            if isinstance(i,ParagraphNode):
                print self.__class__.__name__
                assert 0

            if isinstance(i,Node): i.toTeX(r)
            else: r.append(i)#texescape(i,r)
    def toTeX(self,r):
        assert 0



class MathSquareRootNode(_MathNode):
    def toTeX(self,r):
        r.macro('sqrt').groupStart()
        self.contentToTeX(r)
        r.groupEnd()
        return r 

class MathRootNode(_MathNode):
    pass
    
class MathFencedNode(_MathNode):
    def toTeX(self,r):
        open = '.'
        close = '.'
        if self.hasAttr('open'):
            open = self.getAttr('open')
            if open == '{':
                open = '\\{'
            elif open == '||':
                open = '\\Vert'
            open = open or '.'

                
        if self.hasAttr('close'):
            close = self.getAttr('close')
            if close == '}':
                close = '\\}'
            elif close == '||':
                close = '\\Vert'
            close = close or '.'
       
        r.macro('left')._raw(open).group()
        self.contentToTeX(r)
        r.macro('right')._raw(close).group()

class MathFontNode(_MathNode):
    def toTeX(self,r):
        if self.hasAttr('family'):
            fam = self.getAttr('family')
            if fam in [ 'mathtt', 'mathrm','mathbb','mathfrac','mathcal']:
                cmd = fam
            else:
                cmd = fam
                print "At %s:%d" % self.pos
                print "Font family: %s" % cmd

                assert 0
            r.macro(cmd).groupStart()
            self.contentToTeX(r)
            r.groupEnd()
        else:
            self.contentToTeX(r)
            
class MathFracNode(_MathNode):
    def toTeX(self,r):
        r.macro('frac').groupStart()
        self[0].toTeX(r)
        r.groupEnd().groupStart()
        self[1].toTeX(r)
        r.groupEnd()
        return r
    
class MathIdentifierNode(_MathNode):
    def toTeX(self,r):
        self.contentToTeX(r)
        
class MathNumberNode(_MathNode):
    def toTeX(self,r):
        self.contentToTeX(r)
        return r

class MathOperatorNode(_MathNode):
    def toTeX(self,r):
        if self.hasAttr('op') and len(self.getAttr('op')) > 0:
            op = self.getAttr('op')
            if op in [ 'sum','lim','prod','sup','inf','int' ]:
                r.macro(op)
            else:
                raise MathNodeError('Unknown opearator "%s" @ %s:%d' % (op,self.pos[0],self.pos[1])) 
        else:
            self.contentToTeX(r)
        return r

class MathRowNode(_MathNode):
    def toTeX(self,r):
        self.contentToTeX(r)
        return r

class MathSubscriptNode(_MathNode):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        assert len(self) >= 2
        self[0].toTeX(r)
        r.groupStart('_')
        self[1].toTeX(r)
        r.groupEnd()
        return r
         
class MathSubSuperscriptNode(_MathNode):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        assert len(self) >= 3
        base = self[0]  
        subarg = self[1]
        suparg = self[2]

        self[0].toTeX(r)
        r.groupStart('_')
        self[1].toTeX(r)
        r.groupEnd().groupStart('^')       
        self[2].toTeX(r)
        r.groupEnd()
        return r

class MathSuperscriptNode(_MathNode):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        assert len(self) >= 2
        self[0].toTeX(r)
        r.groupStart('^')
        self[1].toTeX(r)
        r.groupEnd()
        return r


class MathTableNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        cellhalign = [ s[0] for s in re.split(r'\s+',self.getAttr('cellhalign')) ]
        r.begin('array').group([''.join(cellhalign)]).append('\n')
        for i in self:
            i.toTeX(r)
            r.append('\n')
        r.end('array')
        return r

class MathTableRowNode(_MathNode):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        for n in self.data[:-1]:
            n.toTeX(r)
            r.tab()
        self.data[-1].toTeX(r)
        r.rowend()
        return r

class MathTableCellNode(_MathNode):
    def toTeX(self,r):
        return self.contentToTeX(r)


class MathTextNode(_MathNode):
    def toTeX(self,r):
        r.macro('mbox').groupStart()
        self.contentToTeX(r)
        r.groupEnd()
        return r

class MathVectorNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        r.begin('array').group(['c'])
        for n in self.data[:-1]:
            n.toTeX(r)
            r.rowend()
        n.toTeX(r)
        r.end('array')
        return r

                           
class ImageNode(Node):
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        self.__manager = manager

    def handleText(self,data,filename,line):
        pass

    def toHTML(self,r):
        imgs = DefaultDict(list)

        filename,line = self.pos[0],self.pos[1]

        if self.hasAttr('filename'):
            filename = self.getAttr('filename')
            line = 0
            if self.hasAttr('line'):
                line = self.getAttr('line')

        for n in self:
            imtype = n.getAttr('type')
            imurl  = n.getAttr('url')
            imgs[imtype.lower()].append(imurl)
            
        if imgs.has_key('image/png'):
            url = imgs['image/png'][0]
        elif imgs.has_key('image/jpeg'):
            url = imgs['image/jpeg'][0]
        elif imgs.has_key('image/gif'):
            url = imgs['image/gif'][0]
        else:
            raise NodeError('No suitable image source found at %s:%d' % (filename,line))
       
         
        imgpath,imgfile = self.__manager.includeExternalURL(url)
        
        r.extend([tag('img', { 'src' : imgpath } )])
        return r
    def toTeX(self,r):
        imgs = DefaultDict(list)

        filename,line = self.pos[0],self.pos[1]

        if self.hasAttr('filename'):
            filename = self.getAttr('filename')
            line = 0
            if self.hasAttr('line'):
                line = self.getAttr('line')

        for n in self:
            imtype = n.getAttr('type')
            imurl  = n.getAttr('url')
            imgs[imtype.lower()].append(imurl)
        
        if imgs.has_key('image/pdf'):
            url = imgs['image/pdf'][0]
        elif imgs.has_key('image/png'):
            url = imgs['image/png'][0]
        else:
            raise NodeError('No suitable image source found at %s:%d' % (filename,line))
        
        r.macro('includegraphics').groupStart()._raw(self.manager.resolveExternalURL(url)).groupEnd()
        # Add options later, maybe.
        return r
        

class ImageItemNode(Node):
    pass

################################################################################
################################################################################
################################################################################
################################################################################

globalNodeDict = {  'sdocmlx'      : DocumentNode,
                    'section'      : SectionNode,
                    'bibliography' : BibliographyNode,
                    'bibitem'      : BibItemNode,
                    'head'         : HeadNode,
                    'body'         : BodyNode,
                    'title'        : TitleNode,
                    'abstract'     : AbstractNode,
                    'authors'      : AuthorsNode,

                    'title'        : TitleNode,
                    'authors'      : AuthorsNode,
                    'author'       : AuthorNode,
                    'firstname'    : AuthorFirstNameNode,
                    'lastname'     : AuthorLastNameNode,
                    'email'        : AuthorEmailNode,
                    'institution'  : AuthorInstitutionNode,
                    'name'         : AuthorInstitutionNameNode,
                    'address'      : AuthorInstitutionAddressNode,

                    # Paragraph element
                    'p'            : ParagraphNode,
                    'div'          : DivNode,
                    # Plain text elements
                    'span'         : SpanNode,
                    'em'           : EmphasizeNode,
                    'tt'           : TypedTextNode,
                    'bf'           : BoldFaceNode,
                    'sc'           : SmallCapsNode,
                    'font'         : FontNode,
                    'br'           : BreakNode,

                    'ref'          : ReferenceNode,
                    'href'         : HyperRefNode,
                    'a'            : AnchorNode,


                    # Structural text elements
                    'ilist'        : ItemListNode,
                    'li'           : ListItemNode,
                    'dlist'        : DefinitionListNode,
                    'dt'           : DefinitionTitleNode,
                    'dd'           : DefinitionDataNode,

                    'center'       : CenterNode,
                    'flushleft'    : FlushLeftNode,
                    'flushright'   : FlushRightNode,

                    'table'        : TableNode,
                    'col'          : TableColumnNode, 
                    'tr'           : TableRowNode,
                    'td'           : TableCellNode,
                    'float'        : FloatNode,
                    'floatbody'    : FloatBodyNode,
                    'caption'      : FloatCaptionNode,
                    'pre'          : PreformattedNode,

                    # Math stuff
                    'm'            : InlineMathNode,
                    'math'         : MathEnvNode,
                    'eqnarray'     : MathEqnArrayNode,
                    'eqn'          : dummy('eqn'),

                    "mroot"        : MathRootNode,
                    "msqrt"        : MathSquareRootNode,
                    'mfenced'      : MathFencedNode,
                    'mfont'        : MathFontNode, # not mathML
                    'mfrac'        : MathFracNode,
                    'mi'           : MathIdentifierNode,
                    'mn'           : MathNumberNode,
                    'mo'           : MathOperatorNode,
                    'mrow'         : MathRowNode,
                    'msub'         : MathSubscriptNode,
                    'msubsup'      : MathSubSuperscriptNode,
                    'msup'         : MathSuperscriptNode,
                    'mtable'       : MathTableNode,
                    'mtd'          : MathTableCellNode,
                    'mtext'        : MathTextNode,
                    'mtr'          : MathTableRowNode,
                    'mvector'      : MathVectorNode,
                    
                     # Images
                    'img'          : ImageNode,
                    'imgitem'      : ImageItemNode,
                    
                    # Meta
                    'note'         : NoteNode,
              }


class RootElement:
    def __init__(self,manager,filename,line):
        self.__filename = filename
        self.__line     = line
        self.__manager  = manager

        self.__linktext = None
        self.__id       = None

        self.documentElement = None

    def newChild(self,name,attrs,filename,line):
        if self.documentElement is not None:
            raise NodeError('Duplicate root element <%s> at %s:%d' % (name,self.rootElementClass.nodeName,filename,line))

        self.documentElement = \
            globalNodeDict[name](self.__manager,
                                 self,
                                 attrs,
                                 filename,
                                 line)
        return self.documentElement
        
    def getSectionFilename(self):
        return 'index.html'
    def numChildNodes(self):
        return self.documentElement.numChildNodes()
    def makeSidebarContents(self,r):
        self.documentElement.makeSidebarContents(r,counter())
    def makeSidebarIndex(self,r):
        self.documentElement.makeSidebarIndex(r)
    def toTeX(self,res):
        return self.documentElement.toTeX(res)
    def toHTML(self):
        self.documentElement.toHTMLFile(None,None,self,self,'xref.html')
    def makeSidebar(self,filename):
        self.documentElement.makeSidebarFile(filename)

    def getTitle(self):
        return self.documentElement.getTitle()

    def handleText(self,data,filename,line):
        pass
    def endOfElement(self,filename,line):
        pass
    def getSectionFilename(self):
        return 'index.html'

class SymIDRef:
    def __init__(self,manager,key):
        self.__manager = manager
        self.__key = key
    def getID(self):
        return self.__key
    def resolve(self):
        return self.__manager.resolveIDTarget(self.__key)
    def getLink(self):
        try:
            n = self.resolve()
            return n.getFilename(),self.__key
        except KeyError:
            return '','??'
    def linkText(self):
        try:
            return self.resolve().linkText()
        except KeyError:
            return ['??']
        
class TemplateParser(HTMLParser.HTMLParser):
    mark_re = re.compile(r'\$\{([a-zA-Z][a-zA-Z0-9_:]*)\}')
    def __init__(self,substs,linkmap):
        """
        substs
            A dictionary mapping key -> list of text, where key is
            a string and text is the content to be substituted into 
            the keys position in the template file.
        linkmap
            A dictionary mapping urls to urls.
        """
        HTMLParser.HTMLParser.__init__(self)
        self.sub = substs
        self.linkmap = linkmap
        self.errors = []
        self.res = []

        self.__stack = []
        self.__state = True

        self.__currentfilename = None

    def feedfile(self,filename):
        self.__currentfilename = filename
        f = open(filename,'rt')
        self.feed(f.read())
        f.close()
        self.__currentfilename = None
    def handle_starttag(self,tag,attrs):
        if   tag == 'sdoc:if':
            d = dict(attrs)
            self.__stack.append(self.__state)
            if   d.has_key('has'):
                self.__state = self.__state and self.sub.has_key(d['has'])
            elif d.has_key('hasnot'):
                self.__state = self.__state and not self.sub.has_key(d['has'])
        elif self.__state:            
            if   tag == 'sdoc:item':
                if attrs and attrs[0][0] == 'key':
                    key = attrs[0][1]
                    if self.__state:
                        if self.sub.has_key(key):
                            self.res.extend(self.sub[key])
                        else:
                            Warning('In HTML template %s an undefined key "%s" was referenced' % (self.__currentfilename,key))
                else:
                    Warning('In HTML template %s an <sdoc:item> element with no key was specified' % (self.__currentfilename))
            else:
                if tag in [ 'a','link' ]:
                    nattrs = []
                    for k,v in attrs:
                        if k == 'href' and urlparse.urlparse(v)[0] in  ['','file']:
                            nattrs.append((k,self.linkmap[v]))
                        else:
                            nattrs.append((k,v))
                elif tag in [ 'img','script' ]:
                    nattrs = []
                    for k,v in attrs:
                        if k == 'src':
                            nattrs.append((k,self.linkmap[v]))
                        else:
                            nattrs.append((k,v))
                else:
                    nattrs = attrs
                            
                self.res.append('<%s%s>' % (tag,' '.join(([''] + [ '%s="%s"' % i for i in nattrs ]))))
    def handle_charref(self,name):
        if self.__state:
            self.res.append('&#%s;' % name)
    def handle_entityref(self,name):
        if self.__state:
            self.res.append('&%s;' % name)
    def handle_endtag(self,tag):
        if tag in 'sdoc:if':
            self.__state = self.__stack.pop()
        elif tag == 'sdoc:item':
            pass
        elif self.__state:
            self.res.append('</%s>' % tag)
    def handle_comment(self,data):
        if self.__state:
            self.res.append('<!--')
            self.handle_data(data)
            self.res.append('-->')
    def handle_data(self,data):
        if self.__state:
            self.res.append(data)

def scanHTMLTemplate(filename):
    """
    Scan a HTML template file for dependencies.
    """
    class HTMLTemplateScanner(HTMLParser.HTMLParser):
        def __init__(self):
            HTMLParser.HTMLParser.__init__(self)
            self.links  = {}
        def handle_starttag(self,tag,attrs):
            if   tag in [ 'link' ]:
                attrs = dict(attrs)
                if attrs.has_key('href'):
                    if attrs.has_key('rel'):
                        self.links[attrs['href']] = attrs['rel'].lower()
                    else:
                        self.links[attrs['href']] = 'misc'
            elif tag in [ 'img' ]:
                for k,v in attrs:
                    if k == 'src':
                        self.links[v] = 'img'
            elif tag in [ 'script' ]:
                for k,v in attrs:
                    if k == 'src':
                        self.links[v] = 'javascript'
    P = HTMLTemplateScanner()
    P.feed(open(filename,'rt').read())
    return P.links.items()

def nameIterator(base,ext):
    yield base+ext
    i = 0
    while True:
        yield '%s-%d%s' % (base,i,ext)
        i +=  1
        
class Manager:
    def __init__(self,
                 outf, # ZipFile object
                 topdir, # base path for files in zip file
                 timestampstr,
                 icons       = {}, 
                 appicon     = None,
                 debug       = False,
                 searchpaths = [],
                 template    = None,
                 sidebartemplate = None,
                 gsbin       = 'gs',
                 pdflatexbin = 'pdflatex',
                 pdf2svgbin  = None):
        self.__log = logging.getLogger("SdocHTML")
        self.__error = False

        self.__zipfile = outf
        self.__topdir = topdir
        self.__iddict = {}

        self.__citeidx = counter()
        self.__citeanchors = {}
        self.__eqnlist = []
        self.__eqndict = {}
        self.__eqnsrcdict = {}
        self.__mathRequire = { }

        self.__gsbin = gsbin
        self.__pdflatexbin = pdflatexbin
        self.__pdf2svgbin = pdf2svgbin

        self.__anchors = []

        self.__refdIDs = {}

        self.__timestamp = time.localtime()[:6]
        self.__timestampstr = timestampstr
        self.__nodeCounter = counter()
        self.__globalSplitLevel = 2

        self.__unique_index_counter = counter()

        self.__includedfiles = {}

        self.addMathRequirement('amsmath')
        self.addMathRequirement('amssymb')

        self.__stylesheet = []
        self.__javascript = []
        self.__icons = {}

        self.__debug = debug

        self.__htmltemplate = template
        self.__htmlsidebartemplate = sidebartemplate
        self.__linkmap = {}

        self.__nodeNames = { 'index' : 0, 'xref' : 0 }
        
        
        mappedlinks = {}
        mappedtgts  = {}
        templatebase = os.path.dirname(template)
        for tmpl in [template,sidebartemplate]:
            for lnk,rel in scanHTMLTemplate(tmpl):
                # External links are mapped to themselves.
                # Local links are resolved, the target is copied and the link is
                # mapped to to copied resource.
                proto,server,address,_,_ = urlparse.urlsplit(lnk)
                if server:#absolute link
                    self.__linkmap[lnk] = lnk
                elif not self.__linkmap.has_key(lnk):
                    if address[0] == '/': # absolute path
                        p = os.path.normpath(address[0])
                    else:                    
                        p = os.path.normpath(os.path.abspath(os.path.join(templatebase,address)))

                    if not mappedlinks.has_key(p):# this file has not been included yet
                        bn = os.path.basename(p)
                        b,e = os.path.splitext(bn)
                        if rel == 'shortcut icon':
                            tgtdir = 'img'
                        elif rel == 'javascript':
                            tgtdir = 'script'
                        elif rel == 'stylesheet':
                            tgtdir = 'style'
                        else:
                            tgtdir = 'misc'

                        nameiter = nameIterator('%s/%s' % (tgtdir,b),e)
                        tgt = nameiter.next()
                        while mappedtgts.has_key(tgt):
                            tgt = nameiter.next()
                        mappedtgts[tgt] = tgt
                        mappedlinks[p] = tgt
                        self.__linkmap[lnk] = tgt

                        self.__zipfile.write(p,'%s/%s' % (topdir,tgt))
                    else:
                        self.__linkmap[lnk] = mappedlinks[p]
        self.__searchpaths = searchpaths

        iconsadded = {}
        for key,icon in icons.items():
            if icon is not None:
                iconbasename = os.path.basename(icon)
                iconfile = 'icons/%s' % iconbasename
                self.__icons[key] = iconfile
                if not iconsadded.has_key(iconbasename):
                    iconsadded[iconbasename] = None
                    self.Message('Adding Icon : %s' % iconfile)
                    self.__zipfile.write(icon,'%s/%s' % (topdir,iconfile))
        del iconsadded

    def failed(self): return self.__error

    def Error(self,msg):
        self.__log.error(msg)
        self.__error = True
    
    def Warning(self,msg):
        self.__log.warning(msg)
    def Message(self,msg):
        self.__log.info(msg)


    def makeNodeName(self,depth,title):
        titlestr = str(re.sub(r'[^a-zA-Z0-9\-]+','_',''.join(title.toPlainText([])).strip(),re.MULTILINE))
        if len(titlestr) > 40:
            titlestr = titlestr[:40]
        if not self.__nodeNames.has_key(titlestr):
            self.__nodeNames[titlestr] = 0
            titlestr = titlestr + '.html'
        else:
            self.__nodeNames[titlestr] += 1
            titlestr = titlestr + '__%d.html' % self.__nodeNames[titlestr]
        #print "---------- Node name = ",titlestr
        return titlestr
     

    def doDebug(self):
        return self.__debug

    def getNewCiteIdx(self):
        return self.__citeidx.next()
    
    def getIcon(self,key):
        if self.__icons.has_key(key):
            return self.__icons[key]
        else:
            Warning('Icon not found: %s. Using default.' % key)
            #print self.__icons.keys()
            return self.getDefaultIcon()

    def getDefaultIcon(self):
        if self.__icons.has_key('error'):
            return self.__icons['error']
        else:
            return 'imgs/error.png'

    def getUniqueNumber(self):
        return self.__unique_index_counter.next()
    def includeExternalURL(self,url):
        proto,server,address,_,_ = urlparse.urlsplit(url)
       
        address = str(address)
        for p in self.__searchpaths:
            try:
                fn = os.path.join(p,address)
                bn = os.path.basename(fn)

                if not self.__includedfiles.has_key(bn):
                    self.Message("Adding to archive: %s" % bn)
                    
                    f = open(fn,'rt')

                    zi = zipfile.ZipInfo(self.__topdir + '/data/%s' % bn, self.__timestamp)
                    zi.internal_attr |= 1 # text file
                    zi.external_attr = 0x81a40001 #0x80000001 + (0688 << 16). Permissions
                    self.__zipfile.writestr(zi, f.read())

                    f.close()
                    
                    self.__includedfiles[bn] = 'data/%s' % bn
                return 'data/%s' % bn,bn
            except IOError:
                pass
        #print "Looked in:\n",' \n'.join(self.__searchpaths)
        raise IncludeError('File not found "%s". Looked in:\n\t%s' % (address,'\n\t'.join(self.__searchpaths)))

    def readFromURL(self,url):
        proto,server,address,_,_ = urlparse.urlsplit(url)
        
        for p in self.__searchpaths:
            try:
                fn = os.path.join(p,address)
                f = open(fn,'r')
                text = f.read()
                f.close()
                return text
            except IOError:
                pass
        raise IncludeError('File not found "%s"' % address)

    def getMainStylesheet(self):
        return self.__stylesheet
    def addAnchor(self,node):
        self.__anchors.append(node)
    def getAnchors(self):
        return self.__anchors
    def globalSplitLevel(self):
        return self.__globalSplitLevel
    def getTimeStamp(self):
        return self.__timestampstr
    def nextNodeIndex(self):
        return self.__nodeCounter.next()
    def addMathRequirement(self,pkg,opts=None):
        self.__mathRequire[pkg] = opts
    def addEquation(self,s,filename,line):
        s = re.sub(r'[ \n\t\r]+',' ',s) # NOTE: paragraphs in the middle of math explode.
        if self.__eqndict.has_key(s):
            self.__eqnsrcdict[s].append((filename,line))
            idx = self.__eqndict[s]
        else:
            idx = len(self.__eqnlist)
            self.__eqndict[s] = idx
            self.__eqnlist.append(s)
            self.__eqnsrcdict[s] = [(filename,line)]
        if self.__pdf2svgbin is not None:
            return 'math/math%d.svg' % (idx+1)
        else:
            return 'math/math%d.png' % (idx+1)
    def resolveIDTarget(self,name):
        return self.__iddict[name]
    def getIDTarget(self,name,referrer):
        if not self.__refdIDs.has_key(name):
            self.__refdIDs[name] = []
        self.__refdIDs[name].append(referrer)
        return SymIDRef(self,name)
    def addIDTarget(self,name,target):
        if self.__iddict.has_key(name):
            raise KeyError('Id "%s" already defined')
        self.__iddict[name] = target
    def checkInternalIDRefs(self):
        for k,v in self.__refdIDs.items():
            if not self.__iddict.has_key(k):
                for n in v:
                    if n.hasAttr('filename') and n.hasAttr('line'):
                        filename = n.getAttr('filename')
                        line     = int(n.getAttr('line'))
                    else:
                        filename,line = n.pos

                    Warning('Reference to undefined id "%s" at %s:%d' % (k,filename,line))
    def getAllIDRefs(self):
        r = []
        for k,v in self.__iddict.items():
            r.append((k, v.getFilename(), v.getAttr('id')))        
        return r
    def writelinesfile(self,filename,lines):
        text = ''.join([ asUTF8(l) for l in lines])
        print "Adding to archive: %s" % filename
        zi = zipfile.ZipInfo(self.__topdir + '/' + filename, self.__timestamp)
        zi.internal_attr |= 1 # text file
        zi.external_attr = 0x81a40001 #0x80000001 + (0688 << 16). Permissions
        self.__zipfile.writestr(zi, text)
    def writeHTMLfile(self,filename,items,type='node'):
        """
        Write an HTML file using the HTML template as base.
            filename 
                Name of the file to be writted.
            items
                A dictinary mapping template items to text lists.
        """
        if type == 'sidebar':
            P = TemplateParser(items,self.__linkmap)
            P.feedfile(self.__htmlsidebartemplate) 
            self.writelinesfile(filename,''.join(P.res))
        else:
            P = TemplateParser(items,self.__linkmap)
            P.feedfile(self.__htmltemplate) 
            self.writelinesfile(filename,''.join(P.res))
        
    def writeTexMath(self,filename):
        if self.__eqnlist:
            outf = open(filename,'w')
            outf.write('\\documentclass[12pt]{book}\n')

            for pkg,opts in self.__mathRequire.items():
                if opts:
                    outf.write('\\usepackage[%s]{%s}\n' % (opts,pkg))
                else:
                    outf.write('\\usepackage{%s}\n' % (pkg))
            outf.write('\\usepackage{palatino}\n') # hmm...

            outf.write('\\begin{document}\n')
            outf.write('\\openout9=dims.out\n'
                       '\\newdimen\\mathwidth\n'
                       '\\newdimen\\mathheight\n'
                       '\\newdimen\\mathwidthx\n'
                       '\\newdimen\\mathheightx\n'
                       )

            idx = 1
            for eq in self.__eqnlist:
                # 72.27 pt == 1 in
                outf.write('%% PAGE %d\n' % idx)
                for pos in self.__eqnsrcdict[eq]:
                    if pos[0] is not None and pos[1] is not None:
                        outf.write('%% Appeared at %s:%d\n' % pos)

                if 1:
                    # This works "good enough". The extra space of 1pt around the
                    # math must be there because parts of the black may poke outside the box.
                    outf.write('\\setbox0=\\vbox{'
                               '\\hbox{\\rule{0pt}{1pt}}\\nointerlineskip'
                               '\\hbox{\\rule{1pt}{0pt}%s\\rule{1pt}{0pt}}\\nointerlineskip'
                               '\\hbox{\\rule{0pt}{1pt}}'
                               '}\n' 
                               % _unicodeToTex.unicodeToTeXMath(eq))
                else:
                    outf.write('\\setbox0=\\hbox{%s}\n' % _mathUnicodeToTex.unicodeToTeXMath(eq))
                outf.write('\\mathwidth=\\wd0 \\mathheight=\\ht0\n')
                outf.write('\\write9{page%d(\\the\\mathwidth,\\the\\mathheight)}\n' % idx)
                outf.write('\\setlength\\pdfpagewidth{\\mathwidth}\n')
                outf.write('\\setlength\\pdfpageheight{\\mathheight}\n')
                outf.write('\\shipout\\vbox{\\vspace{-1in}\\nointerlineskip\\hbox{\\hspace{-1in}\\box0}}\n')
                idx += 1

            outf.write('\\closeout9\n')
            outf.write('\\end{document}\n')
            outf.close()
           
            #basepath = os.path.abspath(os.path.dirname(filename))
            basepath = os.path.dirname(filename)
            filename = os.path.basename(filename)
            #filename = os.path.basename(filename)
            basename = os.path.splitext(filename)[0]
            ## Run pdflatex on the file to generate a PDF file with one formula on each page
            oldcwd = os.getcwd()
            os.chdir(basepath)
            import subprocess
            r = subprocess.call([ self.__pdflatexbin, 
                                  filename ],
                                  env = os.environ)
            os.chdir(oldcwd)

            pdffile = os.path.join(basepath,'%s.pdf' % basename)

            if r == 0:
                imgbasename = 'imgs/tmpimg%d.png'
                #r = subprocess.call([ 'gs','-dNOPAUSE','-dBATCH','-sOutputFile=%s' % imgbasename,'-sDEVICE=pngalpha','-r100x100',pdffile ])
                r = subprocess.call([ self.__gsbin,'-dGraphicsAlphaBits=4','-dTextAlphaBits=4','-dNOPAUSE','-dBATCH','-sOutputFile=%s' % os.path.join(basepath,'mathimg%d.png'),'-sDEVICE=pngalpha','-r100x100',pdffile ])
            if r == 0 and self.__pdf2svgbin is not None:
                r = subprocess.call([ self.__pdf2svgbin, pdffile, os.path.join(basepath,'mathimg%d.svg'),'all' ])
                if r == 0:
                    for i in xrange(len(self.__eqnlist)):
                        self.__zipfile.write(os.path.join(basepath,'mathimg%d.svg' % (i+1)),'/'.join([self.__topdir,'math','math%d.svg' % (i+1),])) 
            if r == 0:
                # convert and crop all images. Not necessary since images are produces in the right size.
                for i in range(len(self.__eqnlist)):
                    mimg = 'mathimg%d.png' % (i+1)
                    if False:
                        r = subprocess.call([ 'pngcrop',
                                              imgbasename % (i+1), 
                                              os.path.join(basepath,mimg)
                                              ])
                    if r == 0:
                        self.__zipfile.write(os.path.join(basepath,mimg),'/'.join([self.__topdir,'math','math%d.png' % (i+1)])) 
            if r != 0:
                raise MathImgError('Error generating math images')

class dtdhandler(xml.sax.handler.DTDHandler):
    def __init__(self):
        pass
    def notationDecl(self,name,publicId,systemId):
        print("--Decl: name=%s, pubid=%s, sysid=%s" % (name,publicId,systemId))
    def unparsedEntityDecl(self,name,publicId,systemId,ndata):
        print("--Entidydecl: name=%s, pubid=%s, sysid=%s" % (name,publicId,systemId))

class XMLHandler(xml.sax.handler.ContentHandler):
    def __init__(self,filename,rootElement):
        xml.sax.handler.ContentHandler.__init__(self)
        self.__indent = 0
        self.__locator = None
        self.__filename = filename

        self.__rootnode = rootElement
        self.__nodestack = [ rootElement ] 
    def setDocumentLocator(self,locator):
        self.__locator = locator

    def startDocument(self):
        pass
    def endDocument(self):
        self.__nodestack.pop().endOfElement(self.__filename,self.__locator.getLineNumber())
    def startElement(self,name,attr):
        topnode = self.__nodestack[-1]
        self.__nodestack.append(topnode.newChild(name,attr,self.__filename,self.__locator.getLineNumber()))
        #print '%s<%s pos="%s:%d">' % (' ' * self.__indent*2,name,self.__filename,self.__locator.getLineNumber())
        self.__indent += 1
    def endElement(self,name):
        self.__nodestack.pop().endOfElement(self.__filename,self.__locator.getLineNumber())
        self.__indent -= 1
        #print "%s</%s>" % (' ' * self.__indent*2,name)
    def characters(self,content):
        topnode = self.__nodestack[-1]
        topnode.handleText(content,self.__filename,self.__locator.getLineNumber())
        #if c: print ">>%s<<" % c
    def processingInstruction(self,target,data):
        log("PROC INSTR:",target,data)

    def skippedEntry(self,name):
        log("Skipped Entry: %s" % name)

    def getDocumentElement(self):
        return self.__rootnode.documentElement
    
    def dump(self,out):
        self.__rootnode.dump(out,0)



    
 

if __name__ == "__main__":
    args = sys.argv[1:]

    logging.basicConfig(level=logging.INFO)
    conf = config.Configuration({   'infile'     : config.UniqueEntry('infile'),
                                    'outfile'    : config.UniqueEntry('outfile'),
                                    'stylesheet' : config.DirListEntry('stylesheet'),
                                    'javascript' : config.DirListEntry('javascript'),
                                    'incpath'    : config.DirListEntry('incpath'),
                                    'docdir'     : config.UniqueEntry('docdir',default="doc"),
                                    'appicon'    : config.UniqueDirEntry('appicon'),
                                    'icon'       : config.DefinitionListDirEntry('icon'),
                                    'template'   : config.UniqueDirEntry('template'),
                                    'sidebartemplate' : config.UniqueDirEntry('sidebartemplate'),
                                    'tempdir'    : config.UniqueDirEntry('tempdir'),

                                    # TODO: Use platform dependant default values for binaries:
                                    'gsbin'      : config.UniqueDirEntry('gsbin', default='gs'),
                                    'pdftexbin'  : config.UniqueDirEntry('pdftexbin', default='pdflatex'),
                                    'pdf2svgbin' : config.UniqueDirEntry('pdf2svgbin'),

     })
   
    debug = False
    
    while args:
        arg = args.pop(0)
        if   arg == '-o':
            conf.update('outfile', args.pop(0))
        elif arg == '-style':
            conf.update('stylesheet', args.pop(0))
        elif arg == '-js':
            conf.update('javascript', args.pop(0))
        elif arg == '-config':
            conf.updateFile(args.pop(0))
        elif arg == '-i':
            conf.update('incpath', args.pop(0))
        elif arg == '-docdir':
            conf.update('docdir', args.pop(0))
        elif arg == '-appicon':
            conf.update('appicon', args.pop(0))
        elif arg == '-debug':
            debu= True
        elif arg == '-icon':
            conf.update('icon', args.pop(0))
        elif arg == '-tempdir':
            conf.update('tempdir', args.pop(0))
        elif arg == '-template':
            conf.update('template', args.pop(0))
        elif arg == '-sidebartemplate':
            conf.update('sidebartemplate', args.pop(0))
        elif arg == '-gsbin':
            conf.update('gsbin', args.pop(0))
        elif arg == '-pdftexbin':
            conf.update('pdftexbin', args.pop(0))
        elif arg == '-pdf2svgbin':
            conf.update('pdf2svgbin', args.pop(0))
        elif arg and arg[-1] == '-':
            raise Exception('Invalid argument "%s"' % arg)
        else:
            conf.update('infile',arg)

    tempimgdir = os.path.join(conf['tempdir'] or '.','imgs')

    try:
        timestamp = '%s @ host %s' % (time.strftime("%a, %d %b %Y %H:%M:%S"),os.environ['HOSTNAME'])
    except KeyError:
        timestamp = '%s' % (time.strftime("%a, %d %b %Y %H:%M:%S"))
        

    infile = conf['infile']
    outfile = conf['outfile']

    if infile is not None and outfile is not None:
        try:
            sourcebase = os.path.dirname(infile)
            searchpaths = [sourcebase] + conf['incpath']
            
            dstpath = os.path.dirname(outfile)
            try:
                os.makedirs(dstpath)
            except OSError:
                pass

            outf = zipfile.ZipFile(outfile,"w")
            manager = Manager(outf,
                              conf['docdir'],
                              timestamp,
                              searchpaths=searchpaths,
                              appicon=conf['appicon'],
                              icons=conf['icon'],
                              debug=debug,
                              template=conf['template'],
                              sidebartemplate=conf['sidebartemplate'],
                              gsbin=conf['gsbin'] or 'gs',
                              pdflatexbin=conf['pdftexbin'] or 'pdflatex',
                              pdf2svgbin=conf['pdf2svgbin'],
                              )
          
           
            manager.Message('Read XML document') 
            P = xml.sax.make_parser()
            root = RootElement(manager,infile,1)
            h = XMLHandler(infile,root)
            P.setContentHandler(h)
            P.setDTDHandler(dtdhandler())
            P.parse(infile)

            manager.checkInternalIDRefs()

            manager.Message('Writing ZIP files') 
            root.toHTML()
            if conf['sidebartemplate'] is not None:
                root.makeSidebar('sidebar.html')
                print "Got: Sidebar"
            else:
                print "No got sidebar"
            
            try: os.makedirs(tempimgdir)
            except OSError: pass

            mathfile = os.path.join(tempimgdir,'math.tex')
            manager.Message('Writing Math TeX file as %s' % mathfile) 
            manager.writeTexMath(mathfile)

            #idrefs = manager.getAllIDRefs()
            #print '\n'.join([ '%s : %s#%s' % r for r in idrefs ])
            
            #manager.writelinesfile('xref.html',makeIndex(manager))


            outf.close() 
            manager.Message('Fini!')

            if manager.failed():
                sys.exit(1)
            else:
                sys.exit(0)
        except Exception, e:
            import traceback
            traceback.print_exc()
            print e
            sys.exit(1)


