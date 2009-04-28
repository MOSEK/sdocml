"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009 Mosek ApS 
"""

import re

class ConfigEntryError(Exception):
    pass

class _anyEntry:
    def __init__(self,name,doc=None):
        self.name = name
        self.doc = doc
    def convertValue(self,value):
        o = re.match(r'[ ]*(?:"(?P<dqstr>[^"\\]|(?:\\"))*"|\'(?P<sqstr>[^\'\\]|(?:\\\'))*\')\s*$|.*', value)
        return o.group('dqstr') or o.group('sqstr') or value.strip()

class UniqueEntry(_anyEntry):
    def __init__(self,name,default=None,doc=None):
        _anyEntry.__init__(self,name,doc)
        self.value = default
        self.__valueIsSet = False
    def update(self,value):
        if self.__valueIsSet:
            raise ConfigEntryError('Value for %s is already set' % self.name)
        self.value = self.convertValue(value)
        self.__valueIsSet = True
   
class UniqueBoolEntry(UniqueEntry):
    def convertValue(self,value):
        return value.lower() in [ 'yes', 'on', 'true' ]
class UniqueIntEntry(UniqueEntry):
    def convertValue(self,value):
        return int(value)
class OverridableEntry(_anyEntry):
    def __init__(self,name,default=None,doc=None):    
        _anyEntry.__init__(self,name,doc)
        self.value = default
    def update(self,value):
        self.value = self.convertValue(value)
    
class ListEntry(_anyEntry):
    def __init__(self,name,doc=None):
        _anyEntry.__init__(self,name,doc)
        self.value = []
    def update(self,value):
        self.value.append(self.convertValue(value))

class DefinitionListEntry(_anyEntry):
    def __init__(self,name,doc=None):
        _anyEntry.__init__(self,name,doc)
        self.value = {}
    def update(self,value):
        k,v = self.convertValue(value)
        assert not self.value.has_key(k)
        self.value[k] = v
    def convertValue(self,value):
        #o = re.match(r'[ ]*(?P<key>[a-zA-Z09_]+)\s*=\s*(?:"(?P<dqstr>(?:[^"\\]|(?:\\"))*)"|\'(?P<sqstr>(?:[^\'\\]|(?:\\\'))*)\'|(?P<unqstr>\S+))[ ]*$', value)
        o = re.match(r'\s*(?P<key>[a-zA-Z][a-zA-Z0-9_\-]*)\s*=\s*' +
                     r'(?:' + 
                     r'"(?P<dqstr>(?:[^"\\]|(?:\\"))*)"' + '|' +
                     r"'(?P<sqstr>(?:[^'\\]|(?:\\'))*)'" + '|' +
                     r'(?P<str>\S+)' +
                     r')\s*$', 
                     value)
        if not o:
            raise ConfigEntryError('Invalid definition entry "%s"' % value)
        return o.group('key'),o.group('dqstr') or o.group('sqstr') or o.group('str')

class BoolDefListEntry(DefinitionListEntry):
    def convertValue(self,value):
        k,v = DefinitionListEntry.convertValue(value)
        v = v.lower() in [ 'yes', 'true', 'on' ]
        return k,v
        
class Configuration:
    def __init__(self, accepts={}):
        self.__accepts = {}
        self.__accepts.update(accepts)
    def update(self,key,value):
        self.__accepts[key].update(value)
    def updateFile(self,filename):
        for l in open(filename,'rt'):
            if l.strip() and l[0] != '#':
                o = re.match(r'([a-z\-\.]+)\s*:(.*)',l)
                if o is not None:
                    arg = o.group(1)
                    val = o.group(2) 
                    self.__accepts[arg].update(val)

    def __getitem__(self,key):
        return self.__accepts[key].value
