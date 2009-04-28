"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009 Mosek ApS 
"""

import xml.sax.handler
import urlparse 
import os

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
        basename = p.path.split('/')[-1].lower()
        #print "\tBASENAME: %s" % basename
        for p in self.__paths:
            fullname = os.path.join(p,basename)
            #print "\tTRY: %s" % fullname

            if os.path.exists(fullname):
                #print "\tRETURN: %s" % fullname
                return os.path.abspath(fullname)
        #print "\tRETURN: %s" % sysid
        return sysid

class handler(xml.sax.handler.ContentHandler):
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


