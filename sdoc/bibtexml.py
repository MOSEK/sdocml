import xml.dom.minidom
import urlparse

import logging

logbib = logging.getLogger('BibXML')

def Warning(*msgs):
    logbib.warning(' '.join([str(v) for v in msgs])) 

class BibEntryError(Exception): pass
class BibXMLError(Exception): pass
class BibKeyError(Exception): pass

class UniqueItem:
    def __init__(self,name,eid):
        self.name  = name
        self.value = None
        self.__id  = eid
        self.__valueSet = False
    def update(self,node):
        if self.__valueSet:
            raise BibEntryError('Multiple "%s" items in entry "%s"' % (self.name, self.__id))
        self.__valueSet = True
        #self.value = node.firstChild.data
        if node.firstChild is not None:
            if node.firstChild.nodeType == node.TEXT_NODE:
                self.value = node.firstChild.data
            else:
                raise BibEntryError('Invalid data for "%s" field in %s' % (self.name, self.__id))
        else:
            #raise BibEntryError('Invalid data for "%s" field in %s' % (self.name, self.__id))
            self.value = ""
            Warning('Invalid data for "%s" field in %s' % (self.name, self.__id))

class ItemAppearance: pass
class Required(ItemAppearance): pass
class Optional(ItemAppearance): pass

class ListItem:
    def __init__(self,name,eid):
        self.name = name
        self.__id = eid
        self.value = []
    def update(self,node):
        if node.firstChild is not None:
            if node.firstChild.nodeType == node.TEXT_NODE:
                self.value.append(node.firstChild.data)
            else:
                raise BibEntryError('Invalid data for "%s" field in %s' % (self.name, self.__id))
        else:
            self.value = ""
            Warning('Invalid data for "%s" field in %s' % (self.name, self.__id))
            #raise BibEntryError('Invalid data for "%s" field in %s' % (self.name, self.__id))


class _BibEntry:
    bibitems = { 'address'       : UniqueItem,
                 'annote'        : UniqueItem,
                 'author'        : ListItem,
                 'booktitle'     : UniqueItem,
                 'chapter'       : UniqueItem,
                 'crossref'      : UniqueItem,
                 'edition'       : UniqueItem,
                 'editor'        : ListItem,
                 'howpublished'  : UniqueItem,
                 'institution'   : UniqueItem,
                 'journal'       : UniqueItem,
                 'key'           : UniqueItem,
                 'month'         : UniqueItem,
                 'note'          : ListItem,
                 'number'        : UniqueItem,
                 'organization'  : UniqueItem,
                 'pages'         : UniqueItem,
                 'publisher'     : UniqueItem,
                 'school'        : UniqueItem,
                 'series'        : UniqueItem,
                 'title'         : UniqueItem,
                 'type'          : UniqueItem,
                 'volume'        : UniqueItem,
                 'year'          : UniqueItem,
                 }
    accepts = None
    def __init__(self,eid,node):
        self.id = eid
        #self.__d = dict([ (k,v(k,eid)) for k,v in self.bibitems.items() ])
        self.__d = {}

        for n in node.childNodes:
            if n.nodeType == n.ELEMENT_NODE:
                self.handle(n)
        if self.accepts is not None:
            for k,v in self.accepts.items():
                if v is Required and not self.__d.has_key(k):
                    #raise BibEntryError('Missing "%s" field in "%s"' % (k,self.id))
                    Warning('Missing "%s" field in "%s"' % (k,self.id))
    def handle(self,n):
        if n.nodeType == n.ELEMENT_NODE:
            k = n.nodeName
            if self.__d.has_key(k) or self.bibitems.has_key(k):
                if not self.__d.has_key(k):
                    self.__d[k] = self.bibitems[k](k,self.id)

                self.__d[k].update(n)
            else:
                #raise BibEntryError('Unhandled item "%s" in bib entry "%s".' % (n.nodeName,self.id))
                Warning('Unhandled item "%s" in bib entry "%s".' % (n.nodeName,self.id))
    def __getitem__(self,key):
        try:
            return self.__d[key].value
        except KeyError:
            if self.accepts is not None and self.accepts.has_key(key):
                return None
            else:
                raise BibKeyError('Unrecognized key "%s" in %s' % (key,self.id))
    def has_key(self,key):
        #print "*** bib has key: %s? %s" % (key, self.__d.has_key(key))
        return self.__d.has_key(key)
class Article(_BibEntry):
    name = 'article'
    accepts = { 'author'   : Required, 
                'crossref' : Optional, 
                'journal'  : Required,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Optional,
                'number'   : Optional,
                'pages'    : Optional,
                'title'    : Required,
                'volume'   : Optional,
                'year'     : Required,  
                }
class Book(_BibEntry):
    name = 'book'
    accepts = { 'address'  : Optional, 
                'author'   : Optional, # Required: author or editor
                'crossref' : Optional, 
                'edition'  : Optional,
                'editor'   : Optional,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Optional,
                'number'   : Optional,
                'publisher': Required,
                'title'    : Required,
                'volume'   : Optional,
                'year'     : Required,  
                }
class InBook(_BibEntry):
    name = 'inbook'
    accepts = { 'address'  : Optional, 
                'author'   : Optional, # Required: author or editor
                'chapter'  : Optional,
                'crossref' : Optional, 
                'edition'  : Optional,
                'editor'   : Optional,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Optional,
                'number'   : Optional,
                'pages'    : Optional,
                'publisher': Required,
                'title'    : Required,
                'type'     : Optional,
                'volume'   : Optional,
                'year'     : Required,  
                }
class InCollection(_BibEntry):
    name = 'incollection'
    accepts = { 'address'  : Optional, 
                'author'   : Optional,
                'booktitle': Required,
                'chapter'  : Optional,
                'crossref' : Optional, 
                'edition'  : Optional,
                'editor'   : Optional,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Optional,
                'number'   : Optional,
                'pages'    : Optional,
                'publisher': Required,
                'title'    : Required,
                'volume'   : Optional,
                'year'     : Required,  
                }
class InProceedings(_BibEntry):
    name = 'inproceedings'
    accepts = { 'address'  : Optional, 
                'author'   : Optional, 
                'booktitle': Required,
                'crossref' : Optional, 
                'editor'   : Optional,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Optional,
                'number'   : Optional,
                'organization' : Optional,
                'pages'    : Optional,
                'publisher': Required,
                'title'    : Required,
                'volume'   : Optional,
                'year'     : Required,  
                }
class MastersThesis(_BibEntry):
    name = 'mastersthesis'
    accepts = { 'address'  : Optional, 
                'author'   : Optional, 
                'crossref' : Optional, 
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Optional,
                'school'   : Required,
                'title'    : Required,
                'type'     : Optional,
                'year'     : Required,  
                }
class PhdThesis(_BibEntry):
    name = 'phdthesis'
    accepts = MastersThesis.accepts
class TechReport(_BibEntry):
    name = 'techreport'
    accepts = { 'address'  : Optional, 
                'author'   : Optional, 
                'crossref' : Optional, 
                'institution'   : Required,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Optional,
                'number'   : Optional,
                'organization' : Optional,
                'pages'    : Optional,
                'publisher': Required,
                'title'    : Required,
                'type'     : Optional,
                'year'     : Required,  }
class Unpublished(_BibEntry):
    name = 'unpublished'
    accepts = { 'author'   : Required, 
                'crossref' : Optional, 
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Required,
                'title'    : Required,
                'year'     : Optional,  }
class Misc(_BibEntry):
    name = 'misc'
    accepts = { 'author'   : Optional, 
                'crossref' : Optional, 
                'howpublished' : Optional,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Required,
                'title'    : Optional,
                'year'     : Optional,  }
class Manual(_BibEntry):
    name = 'maunal'
    accepts = { 'address'  : Optional,
                'author'   : Optional, 
                'crossref' : Optional, 
                'edition'  : Optional,
                'key'      : Optional,
                'month'    : Optional,
                'note'     : Required,
                'title'    : Required,
                'year'     : Optional,  }

class BibDB:
    parserDB = { 'article'       : Article,
                 'book'          : Book,
                 #booklet
                 #conference
                 'inbook'        : InBook,
                 'incollection'  : InCollection,
                 'inproceedings' : InProceedings,
                 'manual'        : Manual,
                 'mastersthesis' : MastersThesis,
                 'misc'          : Misc,
                 'phdthesis'     : PhdThesis,
                 #proceedings
                 'techreport'    : TechReport,
                 'unpublished'   : Unpublished,
                 }

    def __init__(self,url):
        urlbits = urlparse.urlparse(url)
        if   urlbits[0] in ['file','']:
            filename = urlbits[2]
        else:
            assert 0

        self.__db = {}
        
        try:
            doc = xml.dom.minidom.parse(filename)
        except:
            raise BibXMLError("Error in bibliography file '%s'" % filename)
        root = doc.documentElement

        for node in root.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.nodeName == 'entry':
                self.appendEntry(node)

    def appendEntry(self,node):
        entryID = node.getAttribute('id')
        n = node.firstChild
        while n is not None and n.nodeType != n.ELEMENT_NODE:
            n = n.nextSibling
        if n is not None:\
            self.__db[entryID] = self.parserDB[n.nodeName](entryID,n)
    def __getitem__(self,key):
        return self.__db[key]
    def __iter__(self):
        return iter(self.__db.values())
    def has_key(self,key):
        return self.__db.has_key(key)


if __name__ == '__main__':
    import sys
    db = BibDB(sys.argv[1])


    for v in db: 
        print '[%s] %s' % (v.id,v['author'])
    


    
