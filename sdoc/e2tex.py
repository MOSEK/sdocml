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
import logging
import e2html
from e2html import counter, Node, \
        SectionNode, \
        BibliographyNode, \
        BibItemNode, \
        HeadNode, \
        BodyNode, \
        TitleNode, \
        AbstractNode, \
        AuthorsNode, \
        TitleNode, \
        AuthorsNode, \
        AuthorNode, \
        AuthorFirstNameNode, \
        AuthorLastNameNode, \
        AuthorEmailNode, \
        AuthorInstitutionNode, \
        AuthorInstitutionNameNode, \
        AuthorInstitutionAddressNode, \
        ParagraphNode, \
        DivNode, \
        SpanNode, \
        EmphasizeNode, \
        TypedTextNode, \
        BoldFaceNode, \
        SmallCapsNode, \
        FontNode, \
        BreakNode, \
        ReferenceNode, \
        HyperRefNode, \
        AnchorNode, \
        ItemListNode, \
        ListItemNode, \
        DefinitionListNode, \
        DefinitionTitleNode, \
        DefinitionDataNode, \
        CenterNode, \
        FlushLeftNode, \
        FlushRightNode, \
        TableNode, \
        TableColumnNode, \
        TableRowNode, \
        TableCellNode, \
        FloatNode, \
        FloatBodyNode, \
        FloatCaptionNode, \
        PreformattedNode, \
        InlineMathNode, \
        MathEnvNode, \
        MathEqnArrayNode, \
        MathRootNode, \
        MathSquareRootNode, \
        MathFencedNode, \
        MathFontNode, \
        MathFracNode, \
        MathIdentifierNode, \
        MathNumberNode, \
        MathOperatorNode, \
        MathRowNode, \
        MathSubscriptNode, \
        MathSubSuperscriptNode, \
        MathSuperscriptNode, \
        MathTableNode, \
        MathTableCellNode, \
        MathTextNode, \
        MathTableRowNode, \
        MathVectorNode, \
        ImageNode, \
        ImageItemNode, \
        NoteNode
      
class NodeError(Exception): pass

def mk_MathModeContentNode(man,node,res):
    nc = node.__class__
    
    if   nc is MathRootNode: pass
    elif nc is MathSquareRootNode: pass
    elif nc is MathFencedNode: pass
    elif nc is MathFontNode: pass
    elif nc is MathFracNode: pass
    elif nc is MathIdentifierNode: pass
    elif nc is MathNumberNode: pass
    elif nc is MathOperatorNode: pass
    elif nc is MathRowNode: pass
    elif nc is MathSubscriptNode: pass
    elif nc is MathSubSuperscriptNode: pass
    elif nc is MathSuperscriptNode: pass
    elif nc is MathTableNode: pass
    elif nc is MathTableCellNode: pass
    elif nc is MathTextNode: pass
    elif nc is MathTableRowNode: pass
    elif nc is MathVectorNode: pass
    
    elif nc is EmphasizeNode:
        res.groupStart().macro('em')
        mk_MathModeContent(man,node,res)
        res.groupEnd()
    elif nc is TypedTextNode: 
        res.groupStart().macro('tt')
        mk_MathModeContent(man,node,res)
        res.groupEnd()
    elif nc is BoldFaceNode:  
        res.groupStart().macro('bf')
        mk_MathModeContent(man,node,res)
        res.groupEnd()
    elif nc is SmallCapsNode: 
        res.groupStart().macro('sc')
        mk_MathModeContent(man,node,res)
        res.groupEnd()
    elif nc is FontNode: pass  
    elif nc is AnchorNode:
        label(node,res)
    else:
        raise NodeError('Invalid node "%s" encountered in math mode at %s' % (node.nodeName,node.pos))

def mk_MathModeContent(man,node,res):
    for n in node:
        if isinstance(n,basestring):
            res.append(n)
        else:
            mk_MathModeContentNode(man,n,res)
    return res

def mk_MathEnv(man,node,res):
    res.append('\n')
    if not node.hasAttr('id'):
        res.macro('[')
    else:
        res.begin('equation')
        res.macro('label').groupStart()._raw(node.getAttr('id')).groupEnd()
    res.startMathMode()
    mk_MathModeContent(man,node,res)
    res.endMathMode()
    if not node.hasAttr('id'):
        res.macro(']')
    else:
        res.end('equation')
    return res

def mk_MathEqnArrayNode(man,node,res):
    pass    

def mk_InlineTextModeContentNode(man,node,res):
    nc = node.__class__
    if   nc is SpanNode: pass
    elif nc is EmphasizeNode: pass
    elif nc is TypedTextNode: pass
    elif nc is BoldFaceNode: pass
    elif nc is SmallCapsNode: pass
    elif nc is FontNode: pass
    elif nc is BreakNode: pass
    elif nc is ReferenceNode: pass
    elif nc is HyperRefNode: pass
    elif nc is AnchorNode: pass
    elif nc is InlineMathNode: pass
    else:
        raise NodeError('Invalid node "%s" encountered in inline-mode at %s' % (node.nodeName,node.pos))
    return res


def label(node,res):
    if node.hasAttr('id'): res.macro('label').groupStart()._raw(node.getAttr('id')).groupEnd()
    return res


def mk_InlineTextModeContent(man,node,res):
    for n in node:
        if isinstance(n,basestring):
            r.append(n)
        else:
            mk_InlineTextModeContentNode(man,n,res)
    return res



def mk_VerbatimModeContentNode(man,node,res):
    if   nc is SpanNode: 
        mk_VerbatimModeContent(man,node,res)
    elif nc is EmphasizeNode:
        res.groupStart().macro('em')
        mk_VerbatimModeContent(man,node,res)
        res.groupEnd()
    elif nc is TypedTextNode:
        res.groupStart().macro('tt')
        mk_VerbatimModeContent(man,node,res)
        res.groupEnd()
    elif nc is BoldFaceNode:
        res.groupStart().macro('bf')
        mk_VerbatimModeContent(man,node,res)
        res.groupEnd()
    elif nc is SmallCapsNode: 
        res.groupStart().macro('sc')
        mk_VerbatimModeContent(man,node,res)
        res.groupEnd()
    elif nc is FontNode:
        mk_VerbatimModeContent(man,node,res)
    elif nc is BreakNode: 
        res.verbatim('\n')
    elif nc is ReferenceNode: pass
    elif nc is HyperRefNode: pass
    elif nc is AnchorNode: pass
    else:
        raise NodeError('Invalid node "%s" encountered in verbatim-mode at %s' % (node.nodeName,node.pos))
    return res

def mk_VerbatimModeContent(man,node,res):
    for n in node:
        if isinstance(n,basestring):
            r.verbatim(n)
        else:
            mk_VerbatimModeContent(man,n,res)

def mk_BlockTextModeContentNode(man,node,res,prev=None):
    nc = node.__class__

    if prev is not None and prev.forceTexPar and node.forceTexPar:
        res.macro('par').comment()
    
    label(node,res)

    if   nc is ItemListNode:
        ns = [ i for i in n if isinstance(n,Node) ]
        if ns:
            res.comment()
            res.begin('itemize')
            for n in ns:
                res.macro('item')
                label(n,res)
                mk_BlockTextModeContent(man,n,res)
            res.end('itemize')
    elif nc is DefinitionListNode:
        ns = [ i for i in n if isinstance(n,Node) ]
        if ns:
            res.comment()
            res.begin('description')
            for n in ns:
                if isinstance(n,DefinitionTitleNode):
                    res.macro('item').groupStart()
                    label(n,res)
                    mk_InlineTextModeContent(man,n,res)
                else:
                    bk_BlockTextModeContent(man,n,res)

                mk_BlockTextModeContent(man,cn,res)
            res.end('description')
    elif nc is TableNode:
        cellhalign = [ s[0] for s in re.split(r'\s+',node.getAttr('cellhalign')) ]
        res.begin('tabular').group(''.join(cellhalign)).append('\n')
        
        for ntr in node:
            if ntr.__class__ is TableRowNode:
                for ntd in ntr.data[:-1]:
                    mk_InlineTextModeContent(man,ntd,res)
                    res.tab()
                mk_InlineTextModeContent(man,ntr.data[-1],res)
                res.rowend().lf()
        res.end('tabular')
        return res

    elif nc is CenterNode:
        res.comment()
        res.begin('center')
        mk_BlockTextMode(man,node,res)
        res.end('center')
    elif nc is FlushLeftNode:   
        res.comment()
        res.begin('flushleft')
        mk_BlockTextMode(man,node,res)
        res.end('flushleft')
    elif nc is FlushRightNode:
        res.comment()
        res.begin('flushright')
        mk_BlockTextMode(man,node,res)
        res.end('flushright')
    elif nc is FloatNode:
        res.begin('figure')# need some options too...
        if node.getBody() is not None:
            mk_BlockTextModeContent(man,node.getBody(),res)
        res.macro('caption').groupStart()
        label(node,res)
        if node.getCaption():
            mk_InlineTextModeContent(man,node.getCaption(),res)
        res.groupEnd()
        res.end('figure')
    elif nc is PreformattedNode:
        if node.hasAttr('class'):
            clsd = dict([ (v,v) for v in re.split(r'[ ]+', node.getAttr('class').strip()) ])
        else:
            clsd = {}
        lineno = node.getFirstLine()
        nodes = list(node)

        if lineno is not None and node.getURLBase() is not None and not clsd.has_key('link:no'):
            res.macro('beginpre').group(node.getURLBase()).group(str(lineno)).comment()
        else:
            res.macro('beginpreplain').comment()
        
        mk_VerbatimModeContent(man,node,res)

        res.comment().macro('endpre').lf()
        
    elif nc is MathEnvNode:
        mk_MathEnv(man,node,res)
    elif nc is MathEqnArrayNode:
        mk_MathEqnArrayNode(man,node,res)
    elif nc is ParagraphNode:
        mk_InlineTextModeContent(n)
    elif nc is DivNode: # should probably look at 
        mk_InlineTextModeContent(n)
    else:
        raise NodeError('Invalid node "%s" encountered in block-mode at %s' % (node.nodeName,node.pos))
    return res

def mk_BlockTextModeContent(man,node,res):
    prev = None
    for n in node:
        if isinstance(n,basestring):
            raise NodeError('Got text in block-mode at %s' % (node.pos))
        else:
            mk_BlockTextModeContentNode(man,n,res,prev)
        prev = n
    return res

def mk_TextBody(man,node,res):
    return mk_BlockTextModeContent(man,node,res)
 
sectcmds = [ 'chapter', 'section', 'subsection','subsubsection', 'subsubsection*' ]
def mk_SectionNode(man,level,node,res):
    macro = sectcmds[level-1]

    res.append('\n')
    res.macro(macro)
    res.groupStart()

    mk_InlineTextModeContent(man,node.getTitle(),res)
    res.groupEnd().comment()
    if node.hasAttr('id'):
        res.macro('label').groupStart()._raw(node.getAttr('id')).groupEnd().comment()
    
    mk_TextBody(man,node.getBody(),res)
    
    for sect in node.getSections():
        mk_SectionNode(man,level+1,sect,res)
    
    return res

def mk_Doc(man,node,res):
    node.getTitle().contentToTeX(res['TITLE'])
    res['DATE']
    auths = node.getAuthors()
    if auths:
        node.getAuthors().contentToTeX(res['AUTHOR'])
    else:
        res['AUTHOR']
    
    body    = res['BODY']
    preface = res['PREFACE']

    mk_BlockTextModeContent(man,node.getBody(),preface)

    sects = list(node.__sections)

    for sect in sects:
        mk_SectionNode(man,1,node,body)
    return res
       
       
        
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

        self.__error = False

        self.__log = logging.getLogger("SdocTeX")

    def failed(self): return self.__error

    def writeInTemplate(self,filename,repl):
        scan_re = re.compile(r'%{FILE:(?P<file>[^}]+)}%|%.*',re.MULTILINE)
  
        #scan_re = re.compile(r'^%%BEGIN\s+(?P<begin>SDOCINFO).*|^%%END\s+(?P<end>SDOCINFO).*|^%(?P<line>[a-zA-Z].*)',re.MULTILINE)
        
        templatebase = os.path.abspath(os.path.dirname(self.__config['template']))

        f = open(self.__config['template'],'rt')
        data = f.read()
        f.close()
        
        repldict = {  }
        repldict.update(repl)

        for o in scan_re.finditer(data):
            if o.group('file') is not None:
                val = o.group('file')
                repldict['FILE:%s' % val] = os.path.join(templatebase,val)
        
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError:
            pass
        of = open(filename,'wt')
                
        template_re = re.compile(r'%\{(?P<key>(?:[^}]|\}[^%])+)\}%|%.*',re.MULTILINE)
        pos = 0
        for o in template_re.finditer(data):
            if o.group('key') is not None:
                if o.start(0) > pos:
                    of.write(data[pos:o.start(0)])
                pos = o.end(0)
                try:
                    item = repldict[o.group(1)] 
                    if isinstance(item,basestring):
                        of.write(item)
                    else:
                        of.writelines(item)
                except KeyError:
                    msg('No such key "%s". Valid keys are:\n\t%s' % (o.group(1),'\n\t'.join(repldict.keys())))
                    raise
        if pos < len(data):
            of.write(data[pos:])
            

        of.close()
        
        
    def Error(self,msg):
        self.__log.error(msg)
        self.__error = True
    
    def Warning(self,msg):
        self.__log.warning(msg)
    def makeNodeName(self,depth,title): # dummy
        return ''

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
        styles = { 'language-syntax-keyword'  : ['SDocSyntaxKeyword'],
                   'language-syntax-string'   : ['SDocSyntaxString'],
                   'language-syntax-comment'  : ['SDocSyntaxComment'],
                   'language-syntax-language' : ['SDocSyntaxLanguage'],
                    }
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
    logging.basicConfig(level=logging.INFO)
    import config
    msg = logging.info
    Warnig = logging.warning

    args = sys.argv[1:]
    
    conf = config.Configuration(
        {   'infile'      : config.UniqueDirEntry('infile'),
            'outfile'     : config.UniqueDirEntry('outfile'),
            'incpath'     : config.DirListEntry('incpath'),
            'pdftexbin'   : config.UniqueDirEntry('pdftexbin',default='pdflatex'),
            'tempdir'     : config.UniqueDirEntry('tempdir',default="temp"),
            'debug'       : config.UniqueBoolEntry('debug'),
            'titlepagebg' : config.UniqueDirEntry('titlepagebg'),
            'pagebg'      : config.UniqueDirEntry('pagebg'),
            'template'    : config.UniqueDirEntry('template'),
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
        elif arg == '-template':
            conf.update('template',args.pop(0))
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
        
        data = e2html.DefaultDict(lambda: e2html.texCollector(manager))
        #data = e2html.texCollector()   
        try:
            root.toTeX(data)
        except:
            import traceback
            traceback.print_exc()
            raise
        msg('Writing file %s' % outfile) 
        try:
            manager.writeInTemplate(outfile,data)
            msg('Fini!')

            if manager.failed():
                sys.exit(1)
        except Exception,e:
            msg('Failed!')
            import traceback
            traceback.print_exc()
            sys.exit(1)


