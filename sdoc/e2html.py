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

style = \
"""
    ul.enumerate        {
                                list-style-type : decimal;
                        }
    h2                  {       font-family : sans-serif; }
    h3                  {       font-family : sans-serif; }
    h4                  {       font-family : sans-serif; }
    h5                  {       font-family : sans-serif; }

"""

javascript =  \
"""
    function _showItem(id)
    {
        var elm = document.getElementById(id);
        elm.style.display = "block";
    }
    function _hideItem(id)
    {
        var elm = document.getElementById(id);
        elm.style.display = "none";
    }

    function showSidebarIndex()
    {
        _hideItem('sidebar-contents')
        _showItem('sidebar-index')
    }
    function showSidebarContents()
    {
        _hideItem('sidebar-index')
        _showItem('sidebar-contents')
    }

    function toggleSidebar()
    { 
        var elm = document.getElementById("sidebar-area");
        if (elm.style.display != "none")
        {
            elm.style.display = "none";
        }
        else
        {
            elm.style.display = "block";
        }
    }
    
    function toggleDisplayBlock(id)
    { 
        var elm = document.getElementById(id);
        if (elm.style.display != "none")
        {
            elm.style.display = "none";
        }
        else
        {
            elm.style.display = "block";
        }
    }


    function log(msg)
    {
        var elm = document.getElementById("debug-area");
        elm.innerHTML = elm.innerHTML + msg + "|";

    }

    function toggleLineNumbers(id)
    {
        var elm = document.getElementById(id);
        
        for (n=elm.firstChild; n != null; n = n.nextSibling)
        {
            if (n.nodeName == "SPAN"
                && n.attributes.getNamedItem("class").value == "line-no"
                )
            {
                if (n.style.display == "none")
                    n.style.display = "inline";
                else
                    n.style.display = "none";
            }
        }
    }
"""




################################################################################
################################################################################
class _unicodeToTex:
    unicoderegex = re.compile(u'[\u0080-\u8000]')
    unicodetotex = {  
        160  : '~',
        215  : '{\\times}',
        # Greek letters
        913 : '{\\Alpha}',
        914 : '{\\Beta}',
        915 : '{\\Gamma}',
        916 : '{\\Delta}',
        917 : '{\\Epsilon}',
        918 : '{\\Zeta}',
        919 : '{\\Eta}',
        920 : '{\\Theta}',
        921 : '{\\Iota}',
        922 : '{\\Kappa}',
        923 : '{\\Lambda}',
        924 : '{\\Mu}',
        925 : '{\\Nu}',
        926 : '{\\Xi}',
        927 : '{\\Omicron}',
        928 : '{\\Pi}',
        929 : '{\\Rho}',
        931 : '{\\Sigma}',
        932 : '{\\Tau}',
        933 : '{\\Upsilon}',
        934 : '{\\Phi}',
        935 : '{\\Chi}',
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
        959 : '{\\omicron}',
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

        8230 : '\\ldots ',
        8285 : '\\vdots ',
        8704 : '\\forall ',
        8712 : '\\in ',
        8721 : '\\sum',
        8804 : '\\leq ',
        8805 : '\\geq ',
        8834 : '\\subset ',
        8901 : '\\cdot ',
        8943 : '\\cdots ',
    }

    @staticmethod
    def unicodeToTeXMath(text):
        def repl(o):
            return _unicodeToTex.unicodetotex[ord(o.group(0))]
        return re.sub(_unicodeToTex.unicoderegex,repl,text)

        

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
    sys.stderr.write('TeXml2HTML: ')
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
        def toTeX(self,r):
            raise NodeError('Unimplemented toTeX: %s' % self.nodeName)
    return _DummyNode

class FakeTextNode(UserList.UserList):
    def toHTML(self,res):
        res.extend(self.data)
        return res
    toPlainHTML = toHTML

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

    def contentToHTML(self,res):
        for i in self:
            if isinstance(i,Node):
                i.toHTML(res)
            else:
                res.append(i)
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
            else:
                n.toHTML(res)
        return res

    

class SectionNode(Node):
    nodeName = 'section'
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

        if   not separatefile:
            self.__childrenInSepFiles = False
        elif self.isClass('split:yes'):
            self.__childrenInSepFiles = True
        elif self.isClass('split:no'):
            self.__childrenInSepFiles = False
        elif sectlevel < manager.globalSplitLevel():
            self.__childrenInSepFiles = True
        else: # sectlevel >= manager.globalSplitLevel():
            self.__childrenInSepFiles = False
            
            
        if separatefile:
            self.__nodefilename = 'node%0.4d.html' % self.__nodeIndex
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
            n = SectionNode(self.__manager,
                            self,
                            self.__sectidx + (self.__ssectcounter.next(),), 
                            self.__sectlvl+1,
                            self.__childrenInSepFiles,
                            attrs,
                            filename,
                            line)
            self.__sections.append(n)
        #elif name == 'appendix': pass
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
        return ['.'.join([str(v+1) for v in  self.__sectidx])]
    def getSectionIndex(self):
        return self.__sectidx
    def nextEquationIndex(self):
        return self.__sectidx + (self.__eqncounter.next(),)
    def nextFigureIndex(self):
        return self.__sectidx + (self.__figcounter.next(),)
    def getSectionLink(self):
        return self.__sectionLinkName
    def getSectionFilename(self):
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
        res.extend([tag('div',{ 'class' : 'page-footer'}),self.__manager.getTimeStamp(),tag('br'),
                    tagend('div')])
    def makeNavigation(self,res,prev=None,next=None,up=None,top=None,index=None,position='top'):
        def makeIconNavBar():
            res.extend([tag('div', { 'class' : 'iconbar-navigation' }), tag('table'), tag('tr')])

            if prev is None:
                icon = self.__manager.getIcon('prev-passive')
                res.extend([tag('td', { 'class' : "inactive icon" }), tag('img',{ 'src' : icon}),tagend('td')])
            else:
                icon = self.__manager.getIcon('prev')
                res.extend([tag('td',  { 'class' : "active icon" }), 
                            tag('a',   { 'href' : prev.getSectionFilename() }),
                            tag('img', { 'src' : icon }),
                            tagend('a'),
                            tagend('td'), ])
            if up is None:
                icon = self.__manager.getIcon('up-passive')
                res.extend([tag('td', { 'class' : "inactive icon" }), tag('img',{ 'src' : icon }), tagend('td')])
            else:
                icon = self.__manager.getIcon('up')
                res.extend([tag('td', { 'class' : "active icon" }), 
                            tag('a', { 'href' : up.getSectionFilename() }),
                            tag('img',{ 'src' : icon }),
                            tagend('a'),
                            tagend('td')])
            if next is None:
                icon = self.__manager.getIcon('next-passive')
                res.extend([tag('td', { 'class' : "inactive icon" }), tag('img',{ 'src' : icon }),tagend('td')])
            else:
                icon = self.__manager.getIcon('next')
                res.extend([tag('td', { 'class' : "active icon" }), 
                            tag('a', { 'href' : next.getSectionFilename() }),
                            tag('img',{ 'src' : icon }), 
                            tagend('a'),
                            tagend('td')])
            
            res.tag('td',{ 'class' : 'iconbar-doctitle' })
            if root is not None:
                root.getTitle().toHTML(res)
            res.tagend('td')

            # Add a dummy cell to place the title at the center
            res.extend([tag('td', { 'class' : "inactive icon" }), tag('img',{ 'src' : self.__manager.getIcon('passive')
     }),tagend('td')])
            if root is None:
                icon = self.__manager.getIcon('passive')
                res.extend([tag('td', { 'class' : "inactive icon" }), tag('img',{ 'src' : icon }),tagend('td')])
            else:
                icon = self.__manager.getIcon('content')
                res.extend([tag('td',{'class' : "active icon" }), 
                            tag('a',{ 'href':top.getSectionFilename()}),
                            tag('img',{ 'src' : icon }),
                            tagend('a'),
                            tagend('td')])
            
            if index is None:
                icon = self.__manager.getIcon('passive')
                res.extend([tag('td', { 'class' : "inactive icon" }), tag('img',{ 'src' : icon }),tagend('td')])
            else:
                icon = self.__manager.getIcon('index')
                res.extend([tag('td',{'class' : "active icon" }), 
                            tag('a',{ 'href': index}),
                            tag('img',{ 'src' : icon }),
                            tagend('a'),
                            tagend('td')])
            res.extend([tagend('tr'),tagend('table'),tagend('div')])

        def makeTextNavBar():
            res.extend([tag('div', { 'class' : 'navigation' }), tag('table'), tag('tr')])
            if prev is not None:
                res.extend([tag('td', { 'class' : "active" }), 'Prev: ', tag('a', { 'href' :prev.getSectionFilename() })])
                prev.getTitle().toHTML(res)
                res.extend([tagend('a'),tagend('td')])

            if up is not None:
                res.extend([tag('td', { 'class' : "active" }), 'Up: ',tag('a', { 'href' : up.getSectionFilename() })])
                up.getTitle().toHTML(res)
                res.extend([tagend('a'),tagend('td')])
            if next is not None:
                res.extend([tag('td', { 'class' : "active" }), 'Next: ', tag('a', { 'href' : next.getSectionFilename() })])
                next.getTitle().toHTML(res)
                res.extend([tagend('a'),tagend('td')])
            
            
            if root is not None:
                res.extend([tag('td',{'class' : "active" }), 
                            tag('a',{ 'href' : top.getSectionFilename()}),
                            'Contents',
                            tagend('a'),
                            tagend('td')])
            
            if index is not None:
                res.extend([tag('td',{'class' : "active" }), 
                            tag('a',{ 'href' : index}),
                            'Index',
                            tagend('a'),
                            tagend('td')])

            res.extend([tagend('tr'),tagend('table'),tagend('div')])
        res.div('navigation-%s' % position)
        if position == 'top':
            makeIconNavBar()
            makeTextNavBar()
        else:
            makeTextNavBar()
            makeIconNavBar()
        res.tagend('div')

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
                res.tag('div',{ 'style' : 'float:left; width:0px;' })
                res.tag('div',{ 'style' : 'float:right;' })
                if s.numChildSections() > 0:
                    res.tag('a',{ 'href' : 'javascript:toggleDisplayBlock(\'sidebar-content-subsec-%d\')' % subsecidx }).tag('img', { 'src' : self.__manager.getIcon('content-expand-button'),'style' : 'vertical-align : middle;' }).tagend('a').entity('nbsp')
                else:
                    res.tag('img', { 'src' : self.__manager.getIcon('content-noexpand-button'),'style' : 'vertical-align : middle;' }).entity('nbsp')
                res.tagend('div').tagend('div')
                if sidx:
                    res.append('.'.join([ str(v+1) for v in s.getSectionIndex() ]) + '. ')

                link = s.getSectionURI()
                res.tag('a',{ 'href' : link })
                s.getTitle().toPlainHTML(res)
                res.tagend('a')
                res.tag('div',{ 'id' : 'sidebar-content-subsec-%d' % subsecidx, 'style' : 'display:none;' }).append('\n')
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
            r.tag('li').tag('a', { 'href' : link })
            n.anchorTextToPlainHTML(r)
            r.tagend('a').tagend('li').append('\n')
        r.tagend('ul')
    def makeSidebarArea(self,r,top):
        r.tag('table',{ 'width' : '100%','style' : 'border-spacing:0px;'})
        r.tag('tr',) 
        r.tag('td', { 'class' : 'sidebar-table-cell sidebar-head-cell'}).tag('a', { 'href' : 'javascript:showSidebarContents()' }).append('Contents').tagend('a').tagend('td')
        r.tag('td', { 'class' : 'sidebar-head-sep'}).tagend('td')
        r.tag('td', { 'class' : 'sidebar-table-cell sidebar-head-cell'}).tag('a', { 'href' : 'javascript:showSidebarIndex()' }).append('Index').tagend('a').tagend('td')
        r.tag('td',{ 'width' : '100%'}).tagend('td')
        r.tagend('tr').tag('tr',)
        r.tag('td', { 'colspan' : '4', 'class' : 'sidebar-table-cell' })
        r.tag('div', { 'style' : 'width:200px;' }).tagend('div')
        r.tag('div', { 'id' : 'sidebar-contents' })
        top.makeSidebarContents(r)
        r.tagend('div')
        r.tag('div', { 'id' : 'sidebar-index', 'style' : 'display:none;' })
        self.makeSidebarIndex(r)
        r.tagend('div')
        r.tagend('td')
        r.tagend('tr')
        r.tag('tr').tag('td', { 'colspan' : '4', 'class' : 'sidebar-table-cell' }).tagend('td').tagend('tr')
        r.tagend('table')
        return r
        
    def toHTMLFile(self,prevNode,nextNode,parentNode,topNode,indexFile):
        assert self.__separatefile
        filename = self.getSectionFilename()
        res = htmlCollector()

        stylesheet = self.__manager.getMainStylesheet()

        res.tag('html')
        res.tag('head')
        manager.addDefaultHeader(res)
        res.tag('title')
        self.getTitle().toPlainText(res)
        res.tagend('title')
        res.extend([tag('style'), style, tagend('style')])
        res.extend([tagend('head'),
                    tag('body'),
                    tag('div', { 'id' : 'main-div'})])
        ################################################################################
        self.makeNavigation(res,up=parentNode,prev=prevNode,next=nextNode,top=topNode,index='xref.html')
        ###############################################################################
        #res.append(hr_delim)

        res.tag('table', { 'id' : 'top-level-content-table', 'height' : '100%', 'width' : '100%' } )
        res.tag('tr')

        # Sidebar cell
        res.tag('td', { 'id' : 'sidebar-cell'})
        #res.tag('table', {'id' : 'sidebar-area'}).tag('tr').tag('td')
        res.tag('div', { 'id' : 'sidebar-area', 'height' : '100%'})
        self.makeSidebarArea(res,topNode) 
        res.tagend('div')
        #res.tagend('td').tagend('tr').tagend('table')
        #res.tag('div',{ 'id' : 'debug-area' }).tagend('div')
        res.tagend('td')

        # Divider cell
        res.tag('td', { 'id' : 'sidebar-divider-cell', 'onclick' : 'toggleSidebar()'})
        res.entity('nbsp')

        res.tagend('td')

        # Content cell
        res.tag('td', { 'id' : 'content'})
       
        res.tag('center')
        res.tag('h1', { 'class' : 'node-file-header' })
        self.getTitle().toHTML(res)
        if self.__manager.doDebug():
            sfilename = self.getAttr('filename')
            sline     = self.getAttr('line')

            if sfilename and sline:
                res.append(u'(%s:%d)' % (sfilename,sline))

        res.tagend('h1')
        res.tagend('center')
        ################################################################################
        if self.__sections:
            res.append(hr_delim)
            res.tag('div',{ 'class' : 'toc'})
            self.makeContents(res,1,3)
            res.tagend('div')

        ################################################################################

        if self.__body.data or (self.__sections and not self.__childrenInSepFiles):
            res.append(hr_delim)
            cls = self.getAttr('class')
            if cls is not None:
                res.tag('div',{ 'class' : cls })

            self.__body.contentToHTML(res)
            
            if not self.__childrenInSepFiles:
                for sect in self.__sections:
                    sect.toHTML(res,1)

            if cls is not None:
                res.tagend('div')
        ################################################################################
        res.tagend('td').tagend('tr').tagend('table')
        #res.append(hr_delim)
        self.makeNavigation(res,up=parentNode,prev=prevNode,next=nextNode,top=topNode,index='xref.html',position='bottom')
        ################################################################################
        self.makeFooter(res)
        res.extend([tagend('div'),tagend('body'),tagend('html')])

        self.__manager.writelinesfile(filename,res)
        
        del res

        if self.__childrenInSepFiles:
            for prev,sect,next in zip([None] + self.__sections[:-1],
                                      self.__sections,
                                      self.__sections[1:] + [None]):
                sect.toHTMLFile(prev,next,self,topNode,indexFile)

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
        r = htmlCollector()
        r.tag('html')
        r.tag('head')
        manager.addDefaultHeader(r)
        r.tag('title').append('Bibliography').tagend('title')
        r.extend([tag('style'),style,tagend('style')])
        r.tagend('head')
        r.tag('body')

        ################################################################################
        self.makeNavigation(r,up=parentNode,prev=prevNode,next=nextNode,top=topNode,index=indexFile)
        ################################################################################
        r.append(hr_delim)
        r.tag('center')
        r.extend([tag('h1'),'Bibliography',tagend('h1')])
        r.tagend('center')
        ################################################################################
        r.append(hr_delim)
        r.div("document-bibliography")

        r.tag('dl',{ 'class' : 'bibliography-item-list'})
        for n in self.__items:
            n.toHTML(r)
            
        r.tagend('dl')
        
        r.tagend('div')

        ################################################################################
        r.append(hr_delim)
        self.makeNavigation(r,up=parentNode,prev=prevNode,next=nextNode,top=topNode,index=indexFile,position='bottom')
        ###############################################################################
        self.makeFooter(r)
        ###############################################################################


        r.tagend('body')
        r.tagend('html')
        
        self.__manager.writelinesfile(self.__nodefilename,r)

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
        r = htmlCollector()
        manager = self.__manager
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

        r.tag('html')
        r.tag('head')
        manager.addDefaultHeader(r)
        r.extend([tag('title'), 'Index', tagend('title') ])
        r.extend([tag('style'),style,tagend('style')])

        r.tagend('head')
        r.tag('body')
        ################################################################################
        self.makeNavigation(r,up=parentNode,prev=prevNode,next=nextNode,top=topNode,index='xref.html')
        ################################################################################
        r.append(hr_delim)
        r.tag('center')
        r.extend([tag('h1'),'Index',tagend('h1')])
        r.tagend('center')
        ################################################################################
        r.append(hr_delim)
        r.div("document-index")
        
        
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

        r.tagend('div')

        ################################################################################
        r.append(hr_delim)
        self.makeNavigation(r,up=parentNode,prev=prevNode,next=nextNode,top=topNode,index='xref.html',position='bottom')
        ###############################################################################
        self.makeFooter(r)
        ###############################################################################
        r.tagend('body')
        r.tagend('html')
        
        manager.writelinesfile('xref.html',r)


class DocumentNode(SectionNode):
    nodeName = 'sdocmlx'
    def __init__(self,manager,parent,attrs,filename,line):
        self.__manager = manager
        SectionNode.__init__(self,manager,parent,(),1,True,attrs,filename,line)
    def endOfElement(self,filename,line):
        self.appendSubsection(_IndexNode(self.__manager,self))
        SectionNode.endOfElement(self,filename,line)

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

class TitleNode(Node):
    pass
AuthorFirstNameNode     = dummy('firstname')
AuthorLastNameNode      = dummy('lastname')
AuthorEmailNode         = dummy('email')
AuthorInstitutionNode   = dummy('institution')
AuthorInstitutionNameNode = dummy('name')
AuthorInstitutionAddressNode = dummy('address')

class ParagraphNode(Node):
    htmlTag = 'p'
    def toHTML(self,res):
        assert 0

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
class TypedTextNode(_SimpleNode):
    htmlTag = 'tt'
class BoldFaceNode(_SimpleNode):
    htmlTag = 'b'
class SmallCapsNode(_SimpleNode):
    htmlTag = 'div'
    htmlAttrs = { 'class' : 'textsc' }
class SpanNode(_SimpleNode):
    htmlTag = 'span'

class FontNode(_SimpleNode):
    htmlTag = 'font'
    

BreakNode               = dummy('BreakNode','br')
                           
#XXSmallNode = dummy('XXSmallNode')
#XSmallNode  = dummy('XSmallNode')
#SmallNode   = dummy('SmallNode')
#LargeNode   = dummy('LargeNode')
#XLargeNode  = dummy('XLargeNode')
#XXLargeNode = dummy('XXLargeNode')
#LargerNode  = dummy('LargerNode')
#SmallerNode = dummy('SmallerNode')
                                   
class ReferenceNode(Node):
    nodeName = 'ReferenceNode' 
    def __init__(self,manager,parent,attrs,filename,line):
        Node.__init__(self,manager,parent,attrs,filename,line)

        if attrs.has_key('exuri'):
            self.__exuri = attrs['exuri']
            self.__ref   = attrs['ref']
        else:
            self.__exuri = None
            if attrs.has_key('type'):
                self.__ref = manager.getIDTarget('@%s-%s' % (attrs['type'], attrs['ref']),self)
            else:
                self.__ref   = manager.getIDTarget(attrs['ref'],self)
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
            


class HyperRefNode(Node):
    nodeName = 'a'
    def toHTML(self,r):
        clsstr = ''
        url = self.getAttr('url')
        if self.hasAttr('class'):
            r.anchor(url,self.getAttr('class'))
        else:
            r.anchor(url)
        for i in self:
            if isinstance(i,Node):
                i.toHTML(r)
            else:
                r.append(i)
        r.tagend('a')

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


class ItemListNode(Node):
    htmlTag = 'ul'
class DefinitionListNode(Node):
    htmlTag = 'dl'
class ListItemNode(_StructuralNode): 
    htmlTag = 'li'
class DefinitionTitleNode(_StructuralNode):
    htmlTag = 'dt'
class DefinitionDataNode(_StructuralNode): 
    htmlTag = 'dd'
    
                   
class _AlignNode(_StructuralNode):
    alignText = 'left'
    def toHTML(self,res):
        res.tag('div',{ 'style' : 'text-align : %s;' % self.alignText })
        self.contentToHTML(res)
        res.tagend('div')
    
class CenterNode(_AlignNode):
    alignText = 'center'
class FlushLeftNode(_AlignNode):
    alignText = 'left'
class FlushRightNode(_AlignNode):
    alignText = 'right'

class NoteNode(_StructuralNode): 
    def toHTML(self,res):
        res.tag('div',{ 'class' : 'note-element' })
        res.append('NOTE:')
        res.tag('div',{ 'class' : 'note-content' })
        self.contentToHTML(res)
        res.tagend('div')
        res.tagend('div')

class TableNode(Node):
    htmlTag = 'table'

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

TableColumnNode         = dummy('TableColumnNode') 
class TableRowNode(Node):
    htmlTag = 'tr'
    def handleText(self,data,filename,line):
        pass
class TableCellNode(_StructuralNode):
    htmlTag = 'td'

class FloatNode(_StructuralNode):
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

class FloatBodyNode(_StructuralNode):
    def toHTML(self,res):
        res.tag('td',{ 'class' : 'float-body' })
        self.contentToHTML(res)
        res.tagend('td')

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

            while nodes and not isinstance(nodes[0],Node)  and not nodes[0].strip():  
                if lineno is not None:
                    firstline += 1
                nodes.pop(0)
            while nodes and not isinstance(nodes[-1],Node) and not nodes[-1].strip(): 
                nodes.pop()

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
            self.__eqnidx = manager.addEquation(''.join(self.toTeX([])),self.__filename, self.__line)
        return self.__eqnidx
    def toTeX(self,r):
        r.append('$')
        for i in self:

            if isinstance(i,Node):
                i.toTeX(r)
            else:
                r.append(i)
        r.append('$')
        return r
        
    def toHTML(self,r):
        r.span('m')
        r.tag('img', { 'src' : "math/math%d.png" % (self.getEqnIdx()+1) } )
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
            self.__eqnidx = manager.addEquation(''.join(self.toTeX([])),self.__filename, self.__line)
        return self.__eqnidx

    def toTeX(self,r):
        r.append('$\displaystyle ')
        for i in self:
            if isinstance(i,Node):
                i.toTeX(r)
            else:
                r.append(i)
        r.append('$')
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
        r.tag('img', {'src' : "math/math%d.png" % (self.getEqnIdx()+1) })
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
            else: texescape(i,r)



class MathSquareRootNode(_MathNode):
    def toTeX(self,r):
        r.append('\\sqrt{')
        self.contentToTeX(r)
        r.append('}')
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
       
        r.append('\\left%s' % open)
        self.contentToTeX(r)
        r.append('\\right%s' % close)

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
            r.append('\\%s{' % cmd)
            self.contentToTeX(r)
            r.append('}')
        else:
            self.contentToTeX(r)
            
class MathFracNode(_MathNode):
    def toTeX(self,r):
        r.append('\\frac{')
        self[0].toTeX(r)
        r.append('}{')
        self[1].toTeX(r)
        r.append('}')
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
                r.append('\\%s' % op)
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
        r.append('_{')
        self[1].toTeX(r)
        r.append('}')
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
        r.append('_{')
        self[1].toTeX(r)
        r.append('}^{')
        self[2].toTeX(r)
        r.append('}')
        return r

class MathSuperscriptNode(_MathNode):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        assert len(self) >= 2
        self[0].toTeX(r)
        r.append('^{')
        self[1].toTeX(r)
        r.append('}')
        return r


class MathTableNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        cellhalign = [ s[0] for s in re.split(r'\s+',self.getAttr('cellhalign')) ]
        r.append('\\begin{array}{%s}' % ''.join(cellhalign))
        for i in self:
            i.toTeX(r)
            r.append('\n')
        r.append('\\end{array}')
        return r

class MathTableRowNode(_MathNode):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        for n in self.data[:-1]:
            n.toTeX(r)
            r.append('&')
        self.data[-1].toTeX(r)
        r.append('\\\\')
        return r

class MathTableCellNode(_MathNode):
    def toTeX(self,r):
        return self.contentToTeX(r)


class MathTextNode(_MathNode):
    def toTeX(self,r):
        r.append('\\mbox{')
        self.contentToTeX(r)
        r.append('}')

class MathVectorNode(Node):
    def handleText(self,data,filename,line):
        pass
    def toTeX(self,r):
        r.append('\\begin{array}{c}\n')
        for n in self.data[:-1]:
            n.toTeX(r)
            r.append('\\\\')
        n.toTeX(r)
        r.append('\\end{array}')
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
    def toHTML(self):
        filename = 'index.html'

        authors = self.documentElement.getAuthors()

        stylesheet = self.__manager.getMainStylesheet()
        r = htmlCollector()

        r.tag('html')
        r.tag('head')
        self.__manager.addDefaultHeader(r)
        r.extend([tag('style'),style,tagend('style') ])
        r.tagend('head')
        r.tag('body')
        ################################################################################
        r.append(hr_delim)
        r.tag('center')
        r.tag('h1')
        self.documentElement.getTitle().toHTML(r)
        r.tagend('h1')
        if authors:
            authors.toHTML(r)
        r.tagend('center')
        ################################################################################
        r.append(hr_delim)
        r.div("top-level-contents toc")
        self.documentElement.makeContents(r,1,5,True,'xref.html')
        r.tagend('div')

        ################################################################################
        r.append(hr_delim)
        r.div("page-footer")
        r.append(self.__manager.getTimeStamp())
        r.tagend('div')
        r.tagend('body')
        r.tagend('html')
        
        self.__manager.writelinesfile(filename,r)

        self.documentElement.toHTMLFile(None,None,self,self,'xref.html')

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
                 outf, # ZipFile object
                 topdir, # base path for files in zip file
                 timestampstr,
                 icons       = {}, 
                 appicon     = None,
                 debug       = False,
                 searchpaths = [],
                 stylesheet  = [], # filename 
                 javascript  = []): # list of filenames
        self.__zipfile = outf
        self.__topdir = topdir
        self.__iddict = {}

        self.__citeidx = counter()
        self.__citeanchors = {}
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

        self.__unique_index_counter = counter()

        self.__includedfiles = {}

        self.addMathRequirement('amsmath')
        self.addMathRequirement('amssymb')

        self.__stylesheet = []
        self.__javascript = []
        self.__icons = {}

        self.__debug = debug

        if stylesheet:
            for f in stylesheet:
                basename = os.path.basename(f)
                intname = 'style/%s' % basename
                self.__stylesheet.append(intname)
                self.__zipfile.write(f,'%s/%s' % (topdir,intname))
        if self.__javascript:
            for js in self.__javascript:
                basename = os.path.basename(js)
                intname = 'script/%s' % basename
                self.__javascript.append(intname)
                self.__zipfile.write(js,'%s/%s' % (topdir,intname))

        self.__searchpaths = searchpaths

        if appicon is not None:
            appiconbasename = os.path.basename(appicon)
            self.__appicon = 'imgs/%s' % appiconbasename
            msg('Adding AppIcon : %s' % self.__appicon)
            self.__zipfile.write(appicon,'%s/%s' % (topdir,self.__appicon))
        else:
            self.__appicon = None

        iconsadded = {}
        for key,icon in icons.items():
            if icon is not None:
                iconbasename = os.path.basename(icon)
                iconfile = 'imgs/%s' % iconbasename
                self.__icons[key] = iconfile
                if not iconsadded.has_key(iconbasename):
                    iconsadded[iconbasename] = None
                    msg('Adding Icon : %s' % iconfile)
                    self.__zipfile.write(icon,'%s/%s' % (topdir,iconfile))
        del iconsadded


    def doDebug(self):
        return self.__debug

    def getNewCiteIdx(self):
        return self.__citeidx.next()
    
    def addDefaultHeader(self,r):
        r.tag('meta', { 'http-equiv' : "Content-Type", 'content' : "text/html; charset=UTF-8" })
        if self.__appicon is not None:
            r.tag('link', { 'href' : self.__appicon, 'rel' : 'shortcut icon' })
        r.tag('script').appendRaw('<!--\n')
        r.appendRaw(javascript)
        r.appendRaw('\n-->\n').tagend('script')
        for ss in self.__stylesheet:
            r.tag('link', { 'rel' : "StyleSheet", 'href' : ss, 'type' : "text/css" })

    def getIcon(self,key):
        if self.__icons.has_key(key):
            return self.__icons[key]
        else:
            Warning('Icon not found: %s. Using default.' % key)
            print self.__icons.keys()
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

                if self.__includedfiles.has_key(bn):
                    raise IncludeError('File "%s" already included' % address)
              
                data = str(open(fn,'rt').read())
                zi = zipfile.ZipInfo('/'.join([self.__topdir, 'data', bn]), self.__timestamp)
                #self.__zipfile.write(fn,'doc/data/%s' % bn)
                self.__zipfile.writestr(zi,data)
                return 'data/%s' % bn,bn
            except IOError:
                pass
        raise IncludeError('File not found "%s"' % address)

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
    args = sys.argv[1:]

    conf = config.Configuration({   'infile' : config.UniqueEntry('infile'),
                                    'outfile' : config.UniqueEntry('outfile'),
                                    'stylesheet' : config.ListEntry('stylesheet'),
                                    'javascript' : config.ListEntry('javascript'),
                                    'incpath'    : config.ListEntry('incpath'),
                                    'docdir'     : config.UniqueEntry('docdir',default="doc"),
                                    'appicon'    : config.UniqueEntry('appicon'),
                                    'icon'       : config.DefinitionListEntry('icon'),
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
        elif arg == '-doc':
            conf.update('docdir', args.pop(0))
        elif arg == '-appicon':
            conf.update('appicon', args.pop(0))
        elif arg == '-debug':
            debu= True
        elif arg == '-icon':
            conf.update('icon', args.pop(0))
        else:
            conf.update('infile',arg)

    tempimgdir = 'imgs'
    timestamp = '%s @ host %s' % (time.strftime("%a, %d %b %Y %H:%M:%S"),os.environ['HOSTNAME'])

    infile = conf['infile']
    outfile = conf['outfile']

    if infile is not None and outfile is not None:
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
                          stylesheet=conf['stylesheet'],
                          javascript=conf['javascript'],
                          searchpaths=searchpaths,
                          appicon=conf['appicon'],
                          icons=conf['icon'],
                          debug=debug,
                          )
      
       
        msg('Read XML document') 
        P = xml.sax.make_parser()
        root = RootElement(manager,infile,1)
        h = XMLHandler(infile,root)
        P.setContentHandler(h)
        P.setDTDHandler(dtdhandler())
        P.parse(infile)

        manager.checkInternalIDRefs()

        msg('Writing ZIP files') 
        root.toHTML()
        
        try: os.makedirs(tempimgdir)
        except OSError: pass

        mathfile = os.path.join(tempimgdir,'math.tex')
        msg('Writing Math TeX file as %s' % mathfile) 
        manager.writeTexMath(mathfile)

        #idrefs = manager.getAllIDRefs()
        #print '\n'.join([ '%s : %s#%s' % r for r in idrefs ])
        
        #manager.writelinesfile('xref.html',makeIndex(manager))


        outf.close() 
        msg('Fini!')


