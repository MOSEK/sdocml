"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009 Mosek ApS 
"""
import zipfile
import UserList
from UserDict import UserDict
import xml.sax
import urlparse
import re
import sys
import time
import os

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
        8804 : '\\leq{}',
        8805 : '\\geq{}',
        8834 : '\\subset{}',
        8901 : '\\cdot{}',
        8943 : '\\cdots{}',
        8945 : '\\ddots{}',
    }
    
    textunicodetotex = {  
        173  : '-',
        228  : '\\"a',
        229  : '\\aa{}',
        231  : '\\c{c}',
        232  : "\\`e",
        233  : "\\'e",
        235  : '\\"e',

        246  : '\\"o',
        248  : '\\o{}',

        351  : '\\c{s}',

        8212 : '---',
        8220 : '``',
        8221 : "''",
    }


################################################################################
################################################################################
class DefaultDict(UserDict):
    def __init__(self,dcon):
        UserDict.__init__(self)
        self.__dcon = dcon
    def __getitem__(self,key):
        if not self.data.has_key(key):
            self.data[key] = self.__dcon()
        return self.data[key]

def msg(m):
    m = unicode(m)
    sys.stderr.write('SDoc2TeX: ')
    sys.stderr.write(m.encode('utf-8'))
    sys.stderr.write('\n')

def Warning(*args):
    sys.stderr.write('WARNING: ')
    sys.stderr.write(' '.join(args))
    sys.stderr.write('\n')

def counter():
    i = 0
    while True:
        yield i
        i = i + 1


class IncludeError(Exception):
    pass
        
class NodeError(Exception):
    pass

class MathNodeError(Exception):
    pass

class Group(UserList.UserList):
    pass
class Options(UserList.UserList):
    pass

class TeXCommand:
    def __init__(self,name):
        self.name = name
class Macro(TeXCommand):
    pass
class Begin(TeXCommand):
    pass
class End(TeXCommand):
    pass
class InlineMath(UserList.UserList):
    pass


class texCollector(UserList.UserList):
    MathMode = 'mode:math'
    TextMode = 'mode:text'
    def __init__(self):
        UserList.UserList.__init__(self)
        self.__stack = []
        self.__mode = self.TextMode

    def texescape(self,data,r):
        pos = 0
        #unicoderegex = re.compile(u'[\u0080-\u8000]')
        for o in re.finditer(ur'\\|{|}|<|>|#|\$|\^|_|[\u0080-\u8000]',data):
            if o.start(0) > pos:
                r.append(str(data[pos:o.start(0)]))
            pos = o.end(0)
            t = o.group(0)
            if   t == '\\':
                if self.__mode is self.TextMode:
                    r.append('$\\tt\\backslash$')
                else:
                    r.append('\\tt\\backslash{}')
            elif t in [ '{', '}', '#','$','&' ]:
                r.append('\\%s' % str(t))
            elif t in [ '^','_' ]:
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
                uidx = ord(o.group(0))
                if self.__mode == self.MathMode:
                    try:
                        r.append(_mathUnicodeToTex.unicodetotex[uidx])
                    except KeyError:
                        Warning('Unknown unicode: %d' % uidx)
                        r.append('.')
                else:
                    try:
                        r.append(_mathUnicodeToTex.textunicodetotex[uidx])
                    except KeyError:
                        print unicode(t).encode('utf-8'),uidx
                        assert 0

        if pos < len(data):
            r.append(str((data[pos:])))

        return r

    def texverbatim(self,data,r):
        pos = 0
        for o in re.finditer(ur'(?P<unicode>[\u0080-\u8000])|(?P<lf>\n)|(?P<space>[ ]+)|(?P<escape>%|\#|&)|(?P<special>\\|~|\^|\$|{|}|_)',data,re.MULTILINE):
            if o.start(0) > pos:
                r.append(str(data[pos:o.start(0)]))
            pos = o.end(0)
            if o.group('space'):
                r.append('\\ ' * len(o.group('space')))
            elif o.group('escape'):
                r.append('\\%s' % o.group('escape'))
            elif o.group('special'):
                r.append('\\char%d{}' % ord(o.group('special')))
            elif o.group('unicode'):
                uidx = ord(o.group('unicode'))
                if _mathUnicodeToTex.textunicodetotex.has_key(uidx):
                    r.append(_mathUnicodeToTex.textunicodetotex[uidx])
                elif _mathUnicodeToTex.unicodetotex.has_key(uidx):
                    r.append('$%s$' % _mathUnicodeToTex.unicodetotex[uidx])
                else: 
                    Warning('Unicode in verbatim field: %d' % uidx)
                    r.append('\\#4%d' % uidx)
            elif o.group('lf'):
                r.append('\\nullbox\\par%\n')
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
    def lf(self):
        self.data.append('\n')
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

class lineCollector(UserList.UserList):
    def append(self,item):
        if isinstance(item,unicode):
            item = item.encode('ASCII')
        elif not isinstance(item,str):
            pass
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
        def toTeX(self,r):
            raise NodeError('Unimplemented toTeX: %s' % self.nodeName)
    return _DummyNode

class Node(UserList.UserList):
    nodeName  = '<scratch>'
    htmlTag   = None
    htmlAttrs = {}
    ignoreSpace = False
    structuralNode = False
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

    def toTeX(self,res):
        print 'WARNING: UNHANDLED ',self.__class__.__name__,self.pos
        for i in self:
            if isinstance(i,Node):
                i.toTeX(res)
            else:
                res.append(i)
        return res
    def contentToTeX(self,r):
        for i in self:
            if isinstance(i,Node):
                i.toTeX(r)
            else:
                r.append(i)
#    def toPlainTeX(self,r):
#        for i in self:
#            if isinstance(i,Node):
#                i.toPlainTeX(r)
#            else:
#                r.append(i)

class _StructuralNode(Node):
    """
    Base class for all nodes that work like a paragraph; these have the
    property that they contain _only_ StructuralNode elements (i.e. all inline text
    elements are contained in a <p> or a similar element).
    """
    structuralNode = True
    
    def contentToTeX(self,res):
        nodes = list(self)
        
        while nodes:
            n = nodes.pop(0)
            if isinstance(n,ParagraphNode):
                n.contentToTeX(res)
                if nodes and isinstance(nodes[0],ParagraphNode):
                    res.append('\n')
                    res.macro('par').group()
            else:
                n.toTeX(res)
        return res

class SectionNode(Node):
    sectcmds = [ 'chapter', 'section', 'subsection','subsubsection', 'subsubsection*' ]

    nodeName = 'section'
    def __init__(self,
                 manager,
                 parent,
                 sectidx,
                 sectlevel,
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
    def newChild(self,name,attrs,filename,line):
        if self.__head is None:
            assert name == 'head'
            n = HeadNode(self.__manager,self,attrs,filename,line)
            self.__head = n
        elif name == 'body':
            n = BodyNode(self.__manager,self,attrs,filename,line)
            self.__body = n
        elif name == 'section':
            n = SectionNode(self.__manager,
                            self,
                            self.__sectidx + (self.__ssectcounter.next(),), 
                            self.__sectlvl+1,
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
        return ['.'.join([str(v+1) for v in  self.__sectidx])]
    def getTitle(self):
        return self.__head.getTitle()
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
        res.groupEnd()
        if self.hasAttr('id'):
            res.append('\n')
            res.macro('label').group(self.getAttr('id'))
            res.macro('hypertarget').group(self.getAttr('id')).group()
        res.append('\n')

        self.contentToTeX(res,level)
        return res

class DocumentNode(SectionNode):
    nodeName = 'sdocmlx'
    def __init__(self,manager,parent,attrs,filename,line):
        SectionNode.__init__(self,manager,parent,(),1,attrs,filename,line)
    def toTeX(self,res):
        res.macro('documentclass').group('book')
        
        res.macro('setcounter').group('secnumdepth').group('4')
        for p in ['amsmath',
                  'amssymb',
                  'latexsym',
                  'amsfonts',
                  'verbatim',
                  'makeidx',
                  'listings',
                  'color']:
            res.macro('usepackage').group(p).lf()
        res.macro('usepackage').group('eso-pic').lf()
        res.macro('usepackage').group('hyperref').lf()
        res.macro('usepackage').options('left=3cm,right=3cm').group('geometry').lf()
        res.macro('usepackage').options('pdftex').group('graphicx').lf()


        res.macro('hypersetup').group('colorlinks=true').lf()
        res.macro('hypersetup').group('latex2html=true').lf()
        res.macro('hypersetup').group('pdfpagelabels=true').lf()
        res.macro('hypersetup').group('plainpages=false').lf()
        res.macro('hypersetup').group('pdfkeywords=true').lf()

        # Our own pseudo-verbatim environment... not very flexible, but usable.
        res._raw('\\newcount\\prelineno\\newbox\\preheadbox\\newdimen\\preheadbarwidth\n')
        res._raw('\\def\\preputlineno{\llap{{\\tiny\\the\\prelineno}\hspace{1em}}\\advance\\prelineno by1}\n')
        #res._raw('\\def\\prehead#1{\\setbox\\preheadbox=\\hbox{\\ #1}\\preheadbarwidth=\\textwidth\\advance\\preheadbarwidth by -\\wd\\preheadbox \\rule{\\preheadbarwidth}{1pt}{\\ #1}}\n')
        res._raw('\\def\\prehead#1{\\leaders\\hbox{\\rule[.2em]{1em}{1pt}}\\hfill{#1}}\n')
        res._raw('\\def\\predelimplain{\\leaders\\hbox{\\rule[.2em]{1em}{1pt}}\\hfill\\rule{0in}{0in}}\n')

        #res._raw('\\def\\beginpre#2{\\prelineno=#2\\par\\noindent\\prehead{\\sc #1}\\par\\begingroup\\parindent=0in\\obeylines\\tt{}\\everypar{\\advance\\prelineno by1\\llap{{\\footnotesize\\the\\prelineno\\ \\ }}}}\n')
        res._raw('\\def\\beginpre#1#2{\\prelineno=#2\\par\\noindent\\prehead{\\sc #1}\\par\\begingroup\\footnotesize\\parindent=0in\\obeylines\\tt{}\\everypar{\\preputlineno}}\n')
        res._raw('\\def\\beginpreplain{\\par\\noindent\\predelimplain\\par\\begingroup\\footnotesize\\parindent=0in\\obeylines\\tt{}}\n')
        res._raw('\\def\\endpre{\\endgroup\\par\\noindent\\predelimplain\\par}\n')

        res.append('\n\n')
        res.macro('makeindex').group()
        self.getTitle().toTeX(res)
        auths = self.getAuthors()
        if auths:
            self.getAuthors().toTeX(res)
        res.macro('date').group()


        res.macro('bibliographystyle').group('plain')
        res.begin('document').append('\n')
        res.macro('maketitle')
        res.macro('tableofcontents')

        self.contentToTeX(res,0)
        res.end('document')
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
    def toTeX(self,r):
        r.macro('author')
        r.groupStart()
        
        L = list(self)
        L.pop(0).toTeX(r)
        while len(L) > 1:
            r.macro('\\').macro('rule').group('0in').group('2em').append('\n')
            L.pop(0).toTeX(r)

        if L:
            r.macro('\\').macro('rule').group('0in').group('2em').group().append('\n')
            L.pop().toTeX(r)

        



        r.groupEnd()
            
class AuthorNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        d = { 'firstname' : None,
              'lastname'  : None,
              'email'     : None,
              'institution' : [],
               }
        for n in self:
            d[n.nodeName] = n
            print n.nodeName
        if d['firstname'] or d['lastname']: 
            if d['firstname'] and d['lastname']:
                d['firstname'].contentToTeX(r)
                r.append('~')
                d['lastname'].contentToTeX(r)
            elif d['lastname']:
                d['lastname'].contentToTeX(r)
            elif d['firstname']:
                d['firstname'].contentToTeX(r)
        return r

                
class TitleNode(Node):
    def toTeX(self,res):
        res.macro('title')
        res.groupStart()
        for i in self:
            if isinstance(i,Node):
                i.toTeX(res)
            else:
                res.append(i)
        res.groupEnd()
    def contentToTeX(self,res):
        for i in self:
            if isinstance(i,Node):
                i.toTeX(res)
            else:
                res.append(i)

class _PlainTextNode(Node):
    pass

class AuthorFirstNameNode(_PlainTextNode):
    nodeName = 'firstname'
class AuthorLastNameNode(_PlainTextNode):
    nodeName = 'lastname'
class AuthorEmailNode(_PlainTextNode):
    nodeName = 'email'
class AuthorInstitutionNode (_PlainTextNode):
    pass
class AuthorInstitutionNameNode(_PlainTextNode):
    pass
class AuthorInstitutionAddressNode(_PlainTextNode):
    pass

class ParagraphNode(Node):
    def contentToTeX(self,res):
        for i in self:
            if isinstance(i,Node):
                i.toTeX(res)
            else:
                res.append(i)

class _SimpleNode(Node):
    macro = None
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
    def toTeX(self,res):
        res.macro(self.macro)
        res.groupStart()
        self.contentToTeX(res)
        res.groupEnd()
        
    def toPlainTeX(self,res):
        if self.macro is not None:
            res.macro(self.macro)
        res.groupStart()
        for i in self:

            if isinstance(i,Node):
                i.toTeX(res)
            else:
                res.append(i)
        res.groupEnd()

class EmphasizeNode(_SimpleNode):
    macro = 'emph'
class TypedTextNode(_SimpleNode):
    macro = 'texttt'
class BoldFaceNode(_SimpleNode):
    macro = 'textbf'
class SmallCapsNode(_SimpleNode):
    macro = 'textsc'
class SpanNode(_SimpleNode):
    macro = None
    def toTeX(self,r):
        return self.contentToTeX(r)

class FontNode(_SimpleNode):
    macro = None
    
class BreakNode(Node):
    def toTeX(self,r):
        r.macro('\\')
        return r
                           
class ReferenceNode(Node):
    nodeName = 'ReferenceNode' 
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)

        if attrs.has_key('exuri'):
            self.__exuri = attrs['exuri']
            self.__ref   = attrs['ref']
        else:
            self.__exuri = None
            self.__ref   = attrs['ref']

    def toTeX(self,r):
        if self.__exuri:
            r.append('[??]')
        else:
            if len(self) > 0:
                r.macro('hyperlink')
                r.group(self.__ref)
                r.groupStart()
                self.contentToTeX(r)
                r.groupEnd()
            else:
                r.extend([Macro('ref'),Group([self.__ref])])

class HyperRefNode(Node):
    def toTeX(self,r):
        r.macro('htmladdnormallink')
        r.groupStart()

        for i in self:
            if isinstance(i,Node):
                i.toTeX(r)
            else:
                r.append(i)

        r.groupEnd()

    def toPlainTeX(self,r):
        assert 0

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
    def toHTML(self,res):
        return res.emptytag('a', { 'name' : self.__anchor_name }) 


class ItemListNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r) :
        r.append('\n')
        r.begin('itemize')
        r.append('\n')
        self.contentToTeX(r)
        r.append('\n')
        r.end('itemize')

class DefinitionListNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r) :
        r.append('\n')
        r.begin('description')
        r.append('\n')
        self.contentToTeX(r)
        r.append('\n')
        r.end('description')
class ListItemNode(_StructuralNode): 
    def toTeX(self,r) :
        r.macro('item').group()
        self.contentToTeX(r)
        r.append('\n')
class DefinitionTitleNode(_StructuralNode):
    def toTeX(self,r) :
        r.macro('item')
        r.groupStart()
        if self.hasAttr('id'):
            r.macro('hypertarget').group(self.getAttr('id')).groupStart()
            self.contentToTeX(r)
            r.groupEnd()
        else:
            self.contentToTeX(r)
        r.groupEnd()
        r.append('\n')

class DefinitionDataNode(_StructuralNode): 
    def toTeX(self,r) :
        self.contentToTeX(r)
        r.append('\n')
                   
class _AlignNode(_StructuralNode):
    alignText = 'left'
    
class CenterNode(_AlignNode):
    def toTeX(self,r):
        r.begin('center')
        r.append('\n')
        self.contentToTeX(r)
        r.end('center')
        r.append('\n')

class FlushLeftNode(_AlignNode):
    def toTeX(self,r):
        r.begin('flushleft')
        r.append('\n')
        self.contentToTeX(r)
        r.end('flushleft')
        r.append('\n')

class FlushRightNode(_AlignNode):
    def toTeX(self,r):
        r.begin('flushright')
        r.append('\n')
        self.contentToTeX(r)
        r.end('flushright')
        r.append('\n')

class NoteNode(_StructuralNode): 
    def toTeX(self,r):
        return r

class TableNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        cellhalign = [ s[0] for s in re.split(r'\s+',self.getAttr('cellhalign')) ]
        r.begin('tabular').group(''.join(cellhalign)).append('\n')
        self.contentToTeX(r)
        r.end('tabular')
        return r

TableColumnNode         = dummy('TableColumnNode') 
class TableRowNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        for n in self.data[:-1]:
            n.toTeX(r)
            r.tab()
        self.data[-1].toTeX(r)
        r.macro('\\').append('\n')
        return r

class TableCellNode(_StructuralNode):
    def toTeX(self,r):
        return self.contentToTeX(r)

class FloatNode(_StructuralNode):
    def handleText(self,data,filename,line):
        pass
    def __init__(self,manager,parent,attrs,filename,line):
        _StructuralNode.__init__(self,manager,parent,attrs,filename,line)
        self.__body = None
        self.__caption = None
        
        if attrs.has_key('id'):
            self.__id = attrs['id']
        else:
            self.__id = None

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

    def toTeX(self,r):
        # we're cheap, so we just use LaTeX's "figure" environment
        r.begin('figure')# need some options too...
        if self.__body is not None:
            self.__body.toTeX(r)
        r.macro('caption').groupStart()
        if self.__id is not None:
            r.macro('label').groupStart()._raw(self.__id).groupEnd()
        if self.__caption:
            self.__caption.toTeX(r)
        r.groupEnd()
        r.end('figure')

class FloatBodyNode(_StructuralNode):
    def toTeX(self,r):
        self.contentToTeX(r)

class FloatCaptionNode(_SimpleNode):
    def __init__(self,manager,parent,attrs,filename,line):
        _SimpleNode.__init__(self,manager,parent,attrs,filename,line)
        self.__parent = parent
    def toTeX(self,r):
        self.contentToTeX(r)

class PreformattedNode(Node):
    nodeName = 'pre'
    converted = False

    langdict = { 'python' : 'Python',
                 'csharp' : 'Java',
                 'java'   : 'Java',
                 'c'      : 'C'
                  }

    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)
        if self.hasAttr('type'):
            self.__type = self.getAttr('type').split('/')
        else:
            self.__type = 'text','plain'
        if self.hasAttr('url'):
            self.__url = self.getAttr('url')
            url = urlparse.urlparse(self.__url)
            self.__pathname = url[2]
            self.__basename = self.__pathname.split('/')[-1]
        else:
            self.__url = None
            self.__basename = None
            self.__pathname = None
        self.__firstline = None
        if attrs.has_key('firstline'):
            self.__firstline = int(attrs['firstline'])

    def toTeX(self,r):
        if self.hasAttr('class'):
            attrs = { 'class' : self.getAttr('class') }
        else:
            attrs = None

        lineno = self.__firstline
        nodes = list(self)

        while nodes and not isinstance(nodes[0],Node)  and not nodes[0].strip():
            if lineno is not None:
                firstline += 1
            nodes.pop(0)
        while nodes and not isinstance(nodes[-1],Node) and not nodes[-1].strip():
            nodes.pop()
    

        if True: 
            if lineno is not None and self.__basename is not None:
                r.macro('beginpre').group(self.__basename).group(str(lineno)).lf()
            else:
                r.macro('beginpreplain').lf()
            
            for n in nodes:
                if isinstance(n,Node):
                    n.toVerbatimTeX(r)
                else:
                    r.verbatim(n)
            
            r.macro('endpre').lf()
        else:
            lstset = []
            if self.__type[0] == 'source':
                l = self.__type[1]
                if self.langdict.has_key(l):
                    lstset.append('language=%s' % self.langdict[l])
            lstset.append('frame=single')
            lstset.append('showspaces=false')
            lstset.append('showstringspaces=false')
            if lineno is not None:
                lstset.append('numbers=left')
                lstset.append(['numberstyle=',Macro('tiny') ])
                lstset.append('firstnumber=%d' % lineno)
            else:
                lstset.append('numbers=none')
            lstset.append(['basicstyle=',Macro('footnotesize'),Macro('ttfamily')])

            if lstset:
                r.append('\n') 
                r.macro('lstset')
                r.groupStart()
                item = lstset[0]
                if isinstance(item,str):
                    r.append(item)
                else:
                    r.extend(item)
                for item in lstset[1:]:
                    if isinstance(item,str):
                        r.append(',').append(item)
                    else:            
                        r.append(',').extend(item)
                r.groupEnd()
                
            r.append('\n') 
            if self.__basename is not None:
                r.macro('hfill').group().macro('emph').groupStart().append('File: ').macro('texttt').group(self.__basename).groupEnd().macro('nopagebreak').append('\n')
            r.begin('lstlisting')
            #r.moptStart()
            #r.append('texcl')
            #r.moptEnd()
            r.append('\n')
            
            for n in nodes:
                if isinstance(n,Node):
                    n.toVerbatimTeX(r)
                else:
                    r.verbatim(n)
           
            r.append('\n') 
            r.end('lstlisting')
            r.append('\n') 

        
                           
                           
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
    
    def toTeX(self,r):
        r.inlineMathStart()
        for i in self:
            if isinstance(i,Node):
                i.toTeX(r)
            else:
                r.append(i)
        r.inlineMathEnd()
        return r
        

class MathEnvNode(Node):
    nodeName = 'math'
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)

        if attrs.has_key('id'):
            self.__id = attrs['id']
        else:
            self.__id = None

        if attrs.has_key('filename') and attrs.has_key('line'):
            self.__filename = attrs['filename']
            self.__line     = attrs['line']
        else:
            self.__filename = None
            self.__line     = None
    
    def toTeX(self,r):
        r.append('\n')
        if self.__id is None:
            r.macro('[')
        else:
            r.begin('equation')
            r.macro('label').group(self.__id)
            r.macro('hypertarget').group(self.__id).group()
        r.startMathMode()
        for i in self:
            if isinstance(i,Node):
                i.toTeX(r)
            else:
                r.append(i)
        r.endMathMode()
        if self.__id is None:
            r.macro(']')
        else:
            r.end('equation')
        return r
    def linkText(self):
        if self.__index is None:
            raise NodeError('Requested linktext for a id-less node "%s"' % self.nodeName)
        return ['.'.join([str(v+1) for v in  self.__index])]

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

            if isinstance(i,Node): 
                i.toTeX(r)
            else: 
                r.append(i)



class MathSquareRootNode(_MathNode):
    def toTeX(self,r):
        r.macro('sqrt')
        r.groupStart()
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
                r.macro('left').append('{')
            elif open == '|':
                r.macro('left|')
            elif open == '||':
                r.macro('left').macro('Vert')
            elif open == '[':
                r.macro('left[')
            elif open == '(':
                r.macro('left(')
            elif open in [ '', '.' ]:
                r.macro('left.')
            else:
                print "Unknown open fence '%s'" % open 
                assert 0
        else:
            r.macro('left').append('.')
                
        self.contentToTeX(r)

        if self.hasAttr('close'):
            close = self.getAttr('close')
            if close == '}':
                r.macro('right').append('}')
            elif close == '||':
                r.macro('right|')
            elif close == '||':
                r.macro('right').macro('Vert')
            elif close == ']':
                r.macro('right]')
            elif close == ')':
                r.macro('right)')
            elif close in [ '', '.' ]:
                r.macro('right.')
            else:
                print "Unknown close fence '%s'" % close
                assert 0
        else:
            r.macro('right').append('.')
       
class MathFontNode(_MathNode):
    def toTeX(self,r):
        if self.hasAttr('family'):
            fam = self.getAttr('family')
            if fam in [ 'mathtt', 'mathrm','mathbb','mathfrac','mathcal']:
                cmd = fam
            #if fam == 'tt':
            #    cmd = 'mathtt'
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
        if self.hasAttr('op'):
            op = self.getAttr('op')
            if op in [ 'sum','lim','prod','sup','inf' ]:
                r.macro(op).group()
            else:
                raise MathNodeError('Unknown opearator %s' % op) 
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
    #def handleText(self,data,filename,line):
    #    pass
    def toTeX(self,r):
        cellhalign = [ s[0] for s in re.split(r'\s+',self.getAttr('cellhalign')) ]
        r.begin('array').group(''.join(cellhalign))
        self.contentToTeX(r)
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
        r.macro('\\')
        return r

class MathTableCellNode(_MathNode):
    def toTeX(self,r):
        return self.contentToTeX(r)


class MathTextNode(_MathNode):
    def toTeX(self,r):
        r.macro('mbox').groupStart()
        self.contentToTeX(r)
        r.groupEnd()

class MathVectorNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        r.begin('array').group('c')
        for n in self.data[:-1]:
            n.contentToTeX(r)
            r.macro('\\')
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

class ImageItemNode(Node):
    pass

################################################################################
################################################################################
################################################################################
################################################################################

globalNodeDict = {  'sdocmlx'      : DocumentNode,
                    'section'      : SectionNode,
                    #'bibliography' : BibliographyNode,
                    #'bibitem'      : BibItemNode,
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
                    #'div'          : DivNode,
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

        print globalNodeDict.keys()
        self.documentElement = \
            globalNodeDict[name](self.__manager,
                                 self,
                                 attrs,
                                 filename,
                                 line)
        return self.documentElement
        
    def getSectionFilename(self):
        return 'index.html'
    def toTeX(self,res):
        return self.documentElement.toTeX(res)

    def getTitle(self):
        return self.documentElement.getTitle()

    def handleText(self,data,filename,line):
        pass
    def endOfElement(self,filename,line):
        pass
    def getSectionFilename(self):
        return 'index.html'

if 0:
    class SymIDRef:
        def __init__(self,manager,key):
            self.__manager = manager
            self.__key = key
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
        
        
class Manager:
    def __init__(self,
                 timestampstr,
                 tempdir,
                 config,
                 searchpaths = []):
        self.__iddict = {}

        self.__config = config

        self.__eqnlist = []
        self.__eqndict = {}
        self.__eqnsrcdict = {}
        self.__mathRequire = { }

        self.__anchors = []

        self.__refdIDs = {}

        self.__timestamp = time.localtime()[:6]
        self.__timestampstr = timestampstr
        self.__nodeCounter = counter()
        self.__globalSplitLevel = 2

        self.__includedfiles = {}

        self.addMathRequirement('amsmath')
        self.addMathRequirement('amssymb')

        self.__searchpaths = searchpaths

        self.__unique_index_counter = counter()

        self.__refdIDs = {}
        self.__citeidx = counter()

    def getNewCiteIdx(self):
        return self.__citeidx.next()

    def getTitlePageBackground(self):
        url = self.__config['titlepagebg']
        return url
    def getAnyPageBackground(self):
        url = self.__config['pagebg']
        return url

    def getUniqueNumber(self):
        """Return a number guaranteed to be unique (i.e. return integers starting at 0)"""
        return self.__unique_index_counter.next()
    def includeExternalURL(self,url):
        fn = self.resolveExternalURL(url)
        bn = os.path.basename(fn)
        self.__includedfiles[bn] = fn
        return fn,bn
    def resolveExternalURL(self,url):
        """
            Return an url or path to an externally linked resource.

            Currently only local urls are supported.
        """
        proto,server,address,_,_ = urlparse.urlsplit(url)
       
        address = str(address)
        for p in self.__searchpaths:
            fn = os.path.join(p,address)
            if os.path.exists(fn):
                return os.path.abspath(fn)
        raise IncludeError('File not found "%s". Looked in:\n\t%s' % (address,'\n\t'.join(self.__searchpaths)))
    def getIDTarget(self,name,referrer):
        if not self.__refdIDs.has_key(name):
            self.__refdIDs[name] = []
        self.__refdIDs[name].append(referrer)
        return e2html.SymIDRef(self,name)


    
    def styleLookup(self,key):
        # hardcoded for now...
        styles = { 'language-syntax-keyword' : ['sdocBlue'],
                   'language-syntax-string'  : ['textsl','sdocGreen'],
                   'language-syntax-comment' : ['sdocRed'] }
        if styles.has_key(key):
            return styles[key]
        else:
            return []
            


    def addDefaultHeader(self,r):
        r.tag('meta', { 'http-equiv' : "Content-Type", 'content' : "text/html; charset=UTF-8" })
        if self.__appicon is not None:
            r.tag('link', { 'href' : self.__appicon, 'rel' : 'shortcut icon' })
        for ss in self.__stylesheet:
            r.tag('link', { 'rel' : "StyleSheet", 'href' : ss, 'type' : "text/css" })

#    def getIcon(self,key):
#        if self.__icons.has_key(key):
#            return self.__icons[key]
#        else:
#            return self.getDefaultIcon()
#
#    def getDefaultIcon(self):
#        if self.__icons.has_key('error'):
#            return self.__icons['error']
#        else:
#            return 'imgs/error.png'
#

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
    def getAnchors(self,node):
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
        s = s.strip()
        if self.__eqndict.has_key(s):
            self.__eqnsrcdict[s].append((filename,line))
            return self.__eqndict[s]
        else:
            idx = len(self.__eqnlist)
            self.__eqndict[s] = idx
            self.__eqnlist.append(s)
            self.__eqnsrcdict[s] = [(filename,line)]
            return idx
    def resolveIDTarget(self,name):
        return self.__iddict[name]
    #def getIDTarget(self,name,referrer):
    #    if not self.__refdIDs.has_key(name):
    #        self.__refdIDs[name] = []
    #    self.__refdIDs[name].append(referrer)
    #    return SymIDRef(self,name)
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
        #zi.external_attr = (08644 << 16)
        self.__zipfile.writestr(zi, text)
    def writeTexMath(self,filename):
        if self.__eqnlist:
            outf = open(filename,'w')
            outf.write('\\documentclass[12pt]{book}\n')

            for pkg,opts in self.__mathRequire.items():
                if opts:
                    outf.write('\\usepackage[%s]{%s}\n' % (opts,pkg))
                else:
                    outf.write('\\usepackage{%s}\n' % (pkg))

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
                               % _mathUnicodeToTex.unicodeToTeXMath(eq))
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
            r = subprocess.call([ 'pdflatex', filename ])
            os.chdir(oldcwd)

            pdffile = os.path.join(basepath,'%s.pdf' % basename)

            if r == 0:
                imgbasename = 'imgs/tmpimg%d.png'
                #r = subprocess.call([ 'gs','-dNOPAUSE','-dBATCH','-sOutputFile=%s' % imgbasename,'-sDEVICE=pngalpha','-r100x100',pdffile ])
                r = subprocess.call([ 'gs','-dNOPAUSE','-dBATCH','-sOutputFile=%s' % os.path.join(basepath,'mathimg%d.png'),'-sDEVICE=pngalpha','-r100x100',pdffile ])
            if r == 0:
                # convert and crop all images
                for i in range(len(self.__eqnlist)):
                    mimg = 'mathimg%d.png' % (i+1)
                    if False:
                        r = subprocess.call([ 'pngcrop',
                                              imgbasename % (i+1), 
                                              os.path.join(basepath,mimg)
                                              ])
                    if r == 0:
                        self.__zipfile.write(os.path.join(basepath,mimg),'/'.join([self.__topdir,'math','math%d.png' % (i+1)])) 

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
    import config
    import e2html
    msg = e2html.msg
    Warning = e2html.Warning

    args = sys.argv[1:]
    
    conf = config.Configuration(
        {   'infile'            : config.UniqueDirEntry('infile'),
            'outfile'           : config.UniqueDirEntry('outfile'),
            'incpath'           : config.DirListEntry('incpath'),
            'pdftexbin'         : config.UniqueDirEntry('pdftexbin',default='pdflatex'),
            'tempdir'           : config.UniqueDirEntry('tempdir',default="temp"),
            'debug'             : config.UniqueBoolEntry('debug'),
            'titlepagebg'       : config.UniqueDirEntry('titlepagebg'),
            'pagebg'            : config.UniqueDirEntry('pagebg'),
            }
        )
    
    
    while args:
        arg = args.pop(0)
        if   arg == '-o':
            conf.update('outfile', args.pop(0))
        elif arg == '-i':
            conf.update('incpath',args.pop(0))
        elif arg == '-tempdir':
            conf.update('tempdir',args.pop(0))
        elif arg == '-titlepagebg':
            conf.update('titlepagebg',args.pop(0))
        elif arg == '-pagebg':
            conf.update('pagebg',args.pop(0))
        elif arg == '-debug':
            conf.update('debug',args.pop(0))
        elif arg == '-config':
            conf.updateFile(args.pop(0))
        elif arg[0] != '-':
            conf.update('infile',arg)
        else:
            assert 0

    timestamp = '%s' % (time.strftime("%a, %d %b %Y %H:%M:%S"))


    infile  = conf['infile']
    outfile = conf['outfile']

    print("SDoc->PDF Configuration:")
    print('\tin file     : %s' % conf['infile'])
    print('\tout file    : %s' % conf['outfile'])
    print('\ttemp dir    : %s' % conf['tempdir'])
    print('\tinclude path : ')
    for p in conf['incpath']:
        print('\t\t%s' % p)

    if infile is not None and outfile is not None:
        msg('Infile = %s' % infile)
        sourcebase = os.path.dirname(infile)
        searchpaths = [sourcebase] + conf['incpath']
        
        dstpath = os.path.dirname(outfile)
        try: os.makedirs(dstpath)
        except OSError: pass
       
        temppath = conf['tempdir']
        try: os.makedirs(temppath)
        except OSError: pass

        manager = Manager(timestamp,temppath,conf,searchpaths=searchpaths)
       
        msg('Read XML document') 

        if False: # Old stuff
            P = xml.sax.make_parser()
            root = RootElement(manager,infile,1)
            h = XMLHandler(infile,root)
            P.setContentHandler(h)
            P.setDTDHandler(dtdhandler())
            P.parse(infile)
        else: # Use e2html's structures instead
            P = xml.sax.make_parser()
            root = e2html.RootElement(manager,infile,1)
            h = XMLHandler(infile,root)
            P.setContentHandler(h)
            P.setDTDHandler(dtdhandler())
            P.parse(infile)     


        # Verify that all internal references are satisfied
        manager.checkInternalIDRefs()

        outf = open(outfile,"w")
        data = e2html.texCollector()
        try:
            root.toTeX(data)
        except:
            import traceback
            traceback.print_exc()
            raise
        msg('Writing file %s' % outfile) 
        outf.writelines(data)
        outf.close()
        msg('Fini!')





