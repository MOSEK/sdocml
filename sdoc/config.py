"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009 Mosek ApS 
"""

import re,os

class ConfigEntryError(Exception):
    pass

class _anyEntry:
    def __init__(self,name,doc=None):
        self.name = name
        self.doc = doc
    def convertValue(self,value):
        #o = re.match(r'\s*(?:"(?P<dqstr>[^"\\]|(?:\\"))*"|\'(?P<sqstr>[^\'\\]|(?:\\\'))*\'|(?P<name>\S+))\s*$', value)
        o = re.match(r'\s*(?:"(?P<dqstr>(?:\\"|[^"\n])*)"|\'(?P<sqstr>(?:\\\'|[^\'\n])*)\'|(?P<name>\S+))\s*$', value)
        #print '############# string = >>>%s<<<' % value
        res = o.group('dqstr') or o.group('sqstr') or o.group('name')
        #print "match =",','.join([ '"%s"' % g for g in o.groups() ])
        #print "res = '%s'" % res
        return res

class UniqueEntry(_anyEntry):
    def __init__(self,name,default=None,doc=None):
        _anyEntry.__init__(self,name,doc)
        self.value = default
        self.__valueIsSet = False
    def _updatevalue(self,value):
        if self.__valueIsSet:
            raise ConfigEntryError('Value for %s is already set' % self.name)
        self.value = value
        self.__valueIsSet = True
    def update(self,value,base=''):
        self._updatevalue(self.convertValue(value))

class UniqueDirEntry(UniqueEntry):
    def update(self,value,base='.'):
        val = self.convertValue(value)
        if not os.path.isabs(value):
            val = os.path.normpath(os.path.join(base,val))
        self._updatevalue(val)
    
class UniqueBoolEntry(UniqueEntry):
    def convertValue(self,value):
        return value.strip().lower() in [ 'yes', 'on', 'true' ]
class UniqueIntEntry(UniqueEntry):
    def convertValue(self,value):
        return int(value)
class OverridableEntry(_anyEntry):
    def __init__(self,name,default=None,doc=None):    
        _anyEntry.__init__(self,name,doc)
        self.value = default
    def update(self,value,base=''):
        self.value = self.convertValue(value)
    
class ListEntry(_anyEntry):
    def __init__(self,name,doc=None):
        _anyEntry.__init__(self,name,doc)
        self.value = []
    def update(self,value,base=''):
        self.value.append(self.convertValue(value))

class DirListEntry(_anyEntry):
    def __init__(self,name,doc=None):
        _anyEntry.__init__(self,name,doc)
        self.value = []
    def update(self,value,base='.'):       
        val = self.convertValue(value)
        if not os.path.isabs(val):
            val = os.path.normpath(os.path.join(base,val))
        self.value.append(val)

class DefinitionListEntry(_anyEntry):
    def __init__(self,name,doc=None):
        _anyEntry.__init__(self,name,doc)
        self.value = {}
    def update(self,value,base=''):
        k,v = self.convertValue(value)
        assert not self.value.has_key(k)
        self.value[k] = v
    def convertValue(self,value):
        #o = re.match(r'[ ]*(?P<key>[a-zA-Z09_]+)\s*=\s*(?:"(?P<dqstr>(?:[^"\\]|(?:\\"))*)"|\'(?P<sqstr>(?:[^\'\\]|(?:\\\'))*)\'|(?P<unqstr>\S+))[ ]*$', value)
        o = re.match(r'\s*(?P<key>[a-zA-Z][a-zA-Z0-9_\-.:]*)\s*=\s*' +
                     r'(?:' + 
                     r'"(?P<dqstr>(?:[^"\\]|(?:\\"))*)"' + '|' +
                     r"'(?P<sqstr>(?:[^'\\]|(?:\\'))*)'" + '|' +
                     r'(?P<str>\S+)' +
                     r')\s*$', 
                     value)
        if not o:
            raise ConfigEntryError('Invalid definition entry "%s"' % value)
        return o.group('key'),o.group('dqstr') or o.group('sqstr') or o.group('str')

class DefinitionListDirEntry(DefinitionListEntry):
    def update(self,value,base='.'):
        k,v = self.convertValue(value)
        assert not self.value.has_key(k)
        if not os.path.isabs(v):
            v = os.path.normpath(os.path.join(base,v))
        self.value[k] = v


class BoolDefListEntry(DefinitionListEntry):
    def convertValue(self,value):
        k,v = DefinitionListEntry.convertValue(self,value)
        v = v.lower() in [ 'yes', 'true', 'on' ]
        return k,v
        
class Configuration:
    def __init__(self, accepts={}):
        self.__accepts = {}
        self.__accepts.update(accepts)
    def update(self,key,value):
        print "UPDATE: %s <- %s" % (key,value)
        self.__accepts[key].update('%s' % value)
    def updateFile(self,filename):
        print "UPDATE FILE: %s" % (filename)
        configbase = os.path.dirname(filename)
        for l in open(filename,'rt'):
            if l.strip() and l[0] != '#':
                o = re.match(r'([a-z\-\.]+)\s*:(.*)',l)
                if o is not None:
                    arg = o.group(1)
                    val = o.group(2)
                    print "UPDATE: %s <- %s" % (arg,val)
                    self.__accepts[arg].update(val,configbase)

    def keys(self):
        return self.__accepts.keys()
    def __getitem__(self,key):
        return self.__accepts[key].value
