"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009, 2010 Mosek ApS 
"""

import xml.sax.handler
import urlparse 
import os
import logging
from macro import MacroParser

log = logging.getLogger("EVHandler")
log.setLevel(logging.ERROR)

from util import Position as Pos


class dtdhandler(xml.sax.handler.DTDHandler):
    def __init__(self):
        pass
    def notationDecl(self,name,publicId,systemId):
        log("--Decl: name=%s, pubid=%s, sysid=%s" % (name,publicId,systemId))
    def unparsedEntityDecl(self,name,publicId,systemId,ndata):
        log("--Entidydecl: name=%s, pubid=%s, sysid=%s" % (name,publicId,systemId))

class entityhandler(xml.sax.handler.EntityResolver):
    def __init__(self, paths):
        #xml.sax.handler.EntityResolver .__init__(self)
        self.__paths = paths
    def resolveEntity(self,pubid,sysid):
        
        #print "ENTITY RESOLVER. \n\tPublic ID: %s\n\tSystem ID: %s" % (pubid,sysid)
        
        p = urlparse.urlparse(sysid)
        basename = p[2].split('/')[-1]
        #print "  Look for '%s' in:" % basename
        #print '\n'.join([ '\t' + p for p in self.__paths])
        for p in self.__paths:
            fullname = os.path.join(p,basename)
            if os.path.exists(fullname):
                return os.path.abspath(fullname)
        return sysid

class handler(xml.sax.handler.ContentHandler):
    def __init__(self,filename,rootElement):
        xml.sax.handler.ContentHandler.__init__(self)
        self.__indent = 0
        self.__locator = None
        self.__filename = filename
        self.__rootnode = rootElement
        self.__nodestack = [ rootElement ] 
        self.__textline = None
        self.__storedtext = []
    def setDocumentLocator(self,locator):
        self.__locator = locator

    def startDocument(self):
        pass
    def endDocument(self):
        self.__nodestack.pop().endOfElement(self.__filename,self.__locator.getLineNumber())
    def startElement(self,name,attr):
        self.flushText()
        topnode = self.__nodestack[-1]
        self.__nodestack.append(topnode.newChild(name,attr,Pos(self.__filename,self.__locator.getLineNumber())))
        #print '%s<%s pos="%s:%d">' % (' ' * self.__indent*2,name,self.__filename,self.__locator.getLineNumber())
        self.__indent += 1
    def endElement(self,name):
        self.flushText()
        self.__nodestack.pop().endOfElement(Pos(self.__filename,self.__locator.getLineNumber()))
        self.__indent -= 1
        #print "%s</%s>" % (' ' * self.__indent*2,name)
    def flushText(self):
        if self.__storedtext:
            topnode = self.__nodestack[-1]
            
            lines = ''.join(self.__storedtext).split('\n')
            lineno = self.__textline
            for l in lines[:-1]:
                topnode.handleText(l+' \n',Pos(self.__filename,lineno))
                lineno += 1
            topnode.handleText(lines[-1],Pos(self.__filename,lineno))
            self.__storedtext = []        

    def characters(self,content):
        self.__textline = self.__locator.getLineNumber()
        self.__storedtext.append(content)
        #if c: print ">>%s<<" % c
    def processingInstruction(self,target,data):
        self.flushText()
        log("PROC INSTR:",target,data)

    def skippedEntry(self,name):
        self.flushText()
        log("Skipped Entry: %s" % name)

    def getDocumentElement(self):
        return self.__rootnode.documentElement
    
    def dump(self,out):
        self.__rootnode.dump(out,0)










class StandInNode:
    nodeName = '*stand-in*'
    def __init__(self,
                 owner,
                 name):
        self.__owner = owner
        self.nodeName = name
    def startChildElement(self,*args):
        return self.__owner.startChildElement(*args)
    def endChildElement(self,name,pos):
        return self.__owner.endChildElement(name,pos)
    def end(self,pos):
        pass
    def handleText(self,*args):
        return self.__owner.handleText(*args)
    def handleRawText(self,*args):
        return self.__owner.handleRawText(*args)
    def endOfElement(self,*args):
        return self.__owner.endOfElement(*args)

class DummyNode:
    nodeName = '*dummy*'
    def __init__(self,
                 name,
                 attrs,
                 pos):
        self.nodeName = name
        self.pos = pos
    def startChildElement(self,name,attrs,pos):
        return DummyNode(name,attrs,pos)
    def endChildElement(self,*args):
        pass
    def end(self,*args):
        pass
    def handleText(self,data,pos):
        pass
    def handleRawText(self,data,pos):
        pass
    def endOfElement(self,pos):
        pass

class AlternativeSAXHandler(xml.sax.handler.ContentHandler):
    def __init__(self,filename,rootElement,manager):
        xml.sax.handler.ContentHandler.__init__(self)
        self.__indent = 0
        self.__locator = None
        self.__filename = filename
        self.__manager = manager

        self.__rootnode = rootElement
        self.__nodestack = [ rootElement ]

        self.__textline = None
        self.__storedtext = []
        self.__macrohandler = MacroParser()


    def line(self): return self.__locator.getLineNumber()
    def pos(self): return Pos(self.__filename,self.line())

    def setDocumentLocator(self,locator):
        self.__locator = locator

    def startDocument(self):
        pass

    def endDocument(self):
        self.__nodestack.pop().end(self.pos())

    def startElement(self,name,attr):
        self.flushText()        
        #print "Starting "+name
        topnode = self.__nodestack[-1]
        topnode.evaluate(name,self.pos())
        if name == 'sdocml:conditional':
            if (not attr.has_key('cond')) or (attr['cond'].strip() and self.__manager.evalCond(attr['cond'],self.pos())):
                self.__nodestack.append(StandInNode(topnode,name))
                #topnode.startChildElement(name,attr,self.pos()))
            else:
                self.__nodestack.append(DummyNode(name,attr,self.pos()))
        elif attr.has_key('cond') and attr['cond'].strip() and not self.__manager.evalCond(attr['cond'],self.pos()):
            self.__nodestack.append(DummyNode(name,attr,self.pos()))
        else:
            attr = dict(attr)
            if attr.has_key('cond'):
                del attr['cond']
            if attr.has_key('xmlns:sdocml'):
                del attr['xmlns:sdocml']
            self.__nodestack.append(topnode.startChildElement(name,attr,self.pos()))
            #log.debug("%sOPEN <%s> (%s) @ %d" % (' '*len(self.__nodestack),name,self.__nodestack[-1].nodeName,self.line()))
            self.__indent += 1
    def endElement(self,name):
        self.flushText()
        p = self.pos()
        #print "Ending "+name
        #log.debug("%sCLOSE <%s> (%s) @ %d" % (' '*len(self.__nodestack),name,self.__nodestack[-1].nodeName,self.line()))
        #print ("%sCLOSE <%s> (%s) @ %d" % (' '*len(self.__nodestack),name,self.__nodestack[-1].nodeName,self.line()))
        topnode = self.__nodestack.pop()
        nc = topnode.__class__
        if   nc in [ DummyNode, StandInNode ]:
            pass
        else: 
            #turns strings into nodes if any is there
            topnode.evaluate(name,self.pos())
            #closes the node
            topnode.end(self.pos())
            #Do a check if the topnode is a validnode
            if self.__nodestack:
                self.__nodestack[-1].endChildElement(name,self.pos())
            self.__indent -= 1
    def flushText(self):
        if self.__storedtext:
            #print "Text being flushed"
            topnode = self.__nodestack[-1]
            lines = ''.join(self.__storedtext).split('\n')
            #print lines
            lineno = self.__textline
            for l in lines[:-1]:
                #log.debug("%s '%s' @ %d" % (' '*len(self.__nodestack),l,lineno))
                topnode.handleText(l+'\n',Pos(self.__filename,lineno))
                lineno += 1
            #log.debug("%s '%s' @ %d" % (' '*len(self.__nodestack),lines[-1],lineno))
            topnode.handleText(lines[-1],Pos(self.__filename,lineno))
            del self.__storedtext[:] 
    def characters(self,content):
        if not self.__storedtext: # keep index fo the first of multiple lines
            self.__textline = self.__locator.getLineNumber()
        self.__storedtext.append(content)
        #if c: print ">>%s<<" % c
    def processingInstruction(self,target,data):
        self.flushText()
        #log("PROC INSTR:",target,data)

    def skippedEntry(self,name):
        self.flushText()
        #log("Skipped Entry: %s" % name)

    def getDocumentElement(self):
        return self.__rootnode.documentElement
    
    def dump(self,out):
        self.__rootnode.dump(out,0)


