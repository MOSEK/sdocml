"""
This module defines functionality used for representing macros and
environments.
"""

from util import *
import logging
import re
from EvHandler import Pos

log = logging.getLogger("SDocML Macro")
log.setLevel(logging.ERROR)


class SAXEvent:
    def __init__(self,pos):
        self.trace = [ pos ]
        self.pos = pos
    def tr(self,pos):
        self.trace.append(pos)
        return self

class SAXEvTableItemStart(SAXEvent):
    name = '*table-item*'
    def __repr__(self):
        return '<%s>' % self.name
class SAXEvTableItemEnd(SAXEvent):
    name = '*table-item*'
    def __repr__(self):
        return '</%s>' % self.name

class SAXEvTableRowStart(SAXEvTableItemStart):
    name = '*table-row*'
class SAXEvTableRowEnd(SAXEvTableItemEnd): 
    name = '*table-row*'
class SAXEvTableCellStart(SAXEvTableItemStart):
    name = '*table-cell*'
class SAXEvTableCellEnd(SAXEvTableItemEnd): 
    name = '*table-cell*'

class SAXEvStartTag(SAXEvent):
    def __init__(self,name,attrs,pos):
        SAXEvent.__init__(self,pos)
        self.name = name
        self.attrs = attrs
    def __repr__(self):
        return '<%s>' % self.name
class SAXEvEndTag(SAXEvent):
    def __init__(self,name,pos):
        SAXEvent.__init__(self,pos)
        self.name = name
    def __repr__(self):
        return '</%s>' % self.name
class SAXEvText(SAXEvent):
    """
    Represents a piece of pure text that has either already been parsed or
    should not be parsed at all.

    This should be handed to the Node using handleRawText().
    """
    def __init__(self,data,pos):
        SAXEvent.__init__(self,pos)
        #assert data # No: some operations may evaluate to empty string (e.g. dict lookup)
        assert isinstance(data,basestring)
        self.data = data
    def __repr__(self):
        return 'TEXT{%s}' % repr(self.data)
class SAXEvUnexpandedText(SAXEvent):
    """
    Represents a piece of text that has not been parsed yet.

    This should be handed to a node using handleText().
    """
    def __init__(self,data,pos):
        SAXEvent.__init__(self,pos)
        assert data
        assert isinstance(data,basestring)
        self.data = data
    def __repr__(self):
        return 'TEXT{%s}' % repr(self.data)

class _DelayedItem:
    autoClose = False
    def __init__(self,pos):
        self.pos = pos
        assert isinstance(pos,Position)
    def __repr__(self):
        return self.__class__.__name__

class DelayedMacro(_DelayedItem):
    def __init__ (self, name, pos, args=None, subscr=None, superscr=None):
        _DelayedItem.__init__(self,pos)
        self.name = name        
        self.args = args
        self.subscr = None
        self.superscr = None
    def asDoc(self,r):
        r.append('\\%s' % self.name)
        for a in self.args:
            r.append('{')
            a.asDoc(r)
            r.append('}')
        if subscr is not None:
            r.append('_{')
            subscr.asDoc(r)
            r.append('}')
        if superscr is not None:
            r.append('_{')
            superscr.asDoc(r)
            r.append('}')
        return r
    def __repr__(self):
        return 'DelayedMacro(%s)' % self.name

class DelayedArgRef(_DelayedItem):
    def __init__(self,key,pos):
        _DelayedItem.__init__(self,pos)
        self.key = key
    def asDoc(self,r):
        r.append('{{%s}}' % self.key)
        return r
    def __repr__(self):
        return 'DelayedArgRef(%s)' % self.key

class DelayedLookup(_DelayedItem):
    def __init__(self,pos,content):
        _DelayedItem.__init__(self,pos)
        self.content = content
        #log.debug('DelayedLookup content = %s' % content)
    def asDoc(self,r):
        r.append('<lookup>')
        for item in self.content:
            item.asDoc(r)
        r.append('</lookup>')
        return r
    def append(self,item):
        self.content.append(item)

class DelayedText(_DelayedItem):
    def __init__(self,data,pos):
        _DelayedItem.__init__(self,pos)
        self.data = data
    def asDoc(self,r):
        r.append(self.data)
    def __repr__(self):
        return 'DelayedText{%s}' % repr(self.data)
class DelayedUnexpandedText(_DelayedItem):
    def __init__(self,data,pos):
        _DelayedItem.__init__(self,pos)
        self.data = data
    def asDoc(self,r):
        assert 0
    def __repr__(self):
        return 'DelayedUnexpandedText{%s}' % repr(self.data)

class DelayedEnvironment(_DelayedItem):
    def __init__(self,name,pos):
        _DelayedItem.__init__(self,pos)
        self.endpos = None
        self.name = name
        self.content = []
    def asDoc(self,r):
        r.append('\\begin{%s}' % self.name)
        for a in self.args:
            a.asDoc(r)
        r.append('\\end{%s}' % self.name)
    def append(self,item):
        self.content.append(item)
    def end(self,name,pos):
        if name != self.name:
            raise MacroError('%s: Environment "%s" at %s ended by "%s"' % (pos,self.name,self.pos,name))
        self.endpos = pos
        #print "DelayedEnvironment(%s). Content: %s" % (self.name,len(self.content))
    def __repr__(self):
        return 'DelayedEnvironment(%s){%s}' % (self.name, ','.join([ repr(i) for i in self.content ]))
    def __iter__(self):
        return iter(self.content)

class DelayedGroup(_DelayedItem):
    def __init__(self,pos,args=None):
        """
        A not-yet-expanded group.

        The group can be instantiated with arguments (args, subscr, superscr
        and body), in which case these define the relevant substitutions inside
        the group. Otherwise the substitutions from the context of the group
        apply. 

        (args) Either None, meaning that the default context should be used,
            otherwise a tuple (args,subscr,superscr,body)
        """
        _DelayedItem.__init__(self,pos)
        self.endpos = None
        self.content = []
        self.args = args
    def asDoc(self,r):
        for i in self.content:
            i.asDoc(r)
        return r

    def append(self,item):
        if isinstance(item,DelayedElement) and item._mark:
            assert 0
        item._mark = True

        self.content.append(item)
    def extend(self,items):
        self.content.extend(items)

    def __iter__(self): return iter(self.content)
    def __len__(self): return len(self.content)
    def end(self,pos,tok):
        if tok != '}':
            raise MacroError('%s: Group at %s ended by "%s"' % (pos,self.pos,tok))
        self.endpos = endpos
    def __repr__(self):
        return 'DelayedGroup@[%s]{%s}' % (self.pos,','.join([ repr(i) for i in self.content ]))

class DelayedSubScript(_DelayedItem): pass
class DelayedSuperScript(_DelayedItem): pass

class DelayedTableContent(_DelayedItem):
    autoClose = True
    def __init__(self,pos):
        _DelayedItem.__init__(self,pos)
        self.__data = [ [ [] ] ]
        self.__cstack = [ self.__data, self.__data[0], self.__data[0][0] ]
    def row(self,pos):
        assert len(self.__cstack) == 3
        self.__cstack.pop()
        self.__cstack.pop()
        r = []
        self.__cstack[-1].append(r)
        self.__cstack.append(r)
        c = []
        self.__cstack[-1].append(c)
        self.__cstack.append(c)

    def cell(self,pos):
        if len(self.__cstack) != 3:
            print "CSTACK:"
            for i in self.__cstack:
                print "\t%s" % i
        assert len(self.__cstack) == 3
        self.__cstack.pop()
        c = []
        self.__cstack[-1].append(c)
        self.__cstack.append(c)
       
    def append(self,item):
        assert len(self.__cstack) > 1
        self.__cstack[-1].append(item)
    def get(self):
        return self.__data

class DelayedElement(_DelayedItem):
    """
    An element encountered originating either inside a group or an environment, or from a macro or environment definition.
    """
    def __init__(self,name,attrs,pos):
        _DelayedItem.__init__(self,pos)
        if name in [ 'dictentry', 'def','defenv', 'section' ]:
            raise Exception("ABBASDFAB")
        self.name = name
        self._mark = False
        self.nodeName = name
        self.attrs = attrs

        for v in attrs.values():
            assert isinstance(v,list)
            for i in v:
                assert isinstance(i,_DelayedItem)
        self.pos = pos
        self.endpos = None
        self.body = []
    def asDoc(self,r):
        attrs = []
        for k,v in self.attrs.items():
            l = []
            for i in v: i.asDoc(l)
            attrs.append((k,''.join(l)))
        r.append('<%s%s>' % (self.name, u''.join([ u' %s="%s"' % attr for attr in attrs ])))
        for i in self.body:
            i.asDoc(r)
        r.append('</%s>' % self.name)
    def startChildElement(self,name,attrs,pos):
        attrd = {}
        for k,v in attrs.items():
            attrd[k] = [ DelayedText(v,pos) ]
        node = DelayedElement(name,attrd,pos)
        self.body.append(node)
        node._mark = False
        return node
    def endChildElement(self,name,pos):
        pass
    def endThisElement(self,name,pos):
        pass
    def __iter__(self):
        return iter(self.body)
    def extend(self,items):
        for i in items:
            #log.debug('Append to <%s> : %s' % (self.name,i))
            assert isinstance(i,_DelayedItem)
            if isinstance(i,DelayedElement) and i._mark:
                assert 0
            self.body.append(i)
        
    def end(self,pos):
        #if name != self.name:
        #    raise MacroError('%s: Element "%s" at %s ended by "%s"' % (pos,self.name,self.pos,name))
        self.endpos = pos
    def __repr__(self):
        return 'DelayedElement@[%s](%s){%s}' % (self.pos,self.name,','.join([ repr(i) for i in self.body ]))


class Element:
    def __init__(self,name,attrs,content):
        self.name = name
        self.attrs = attrs
        self.content = content
    def __iter__(self):
        return iter(content)

class Placeholder:
    def __init__(self,arg):
        self.arg = arg
    def __repr__(self):
        return "Placeholder for :"+self.arg

class MacroRef:
    def __init__(self,ref,sub,sup):
        self.ref = ref
        self.sub = sub
        self.sup = sup

class Group:
    def __init__(self,p):
        self.end = False
        self.start = p
        self.content = ''
        self.sub= True
        self.sup = True
        self.nArgs = 0
    def __repr__(self):
        return "{"+self.content+"}"

class SubSup:
    def __init__(self,sub,sup):
        self.sup = sup
        self.sub = sub
    def __repr__(self):
        return '_'+self.sub+'^'+self.sup


class Sup:
    def __init__(self):
        self.sup = None

    def sub(self,sub=None):
        return SubSup(self.base,sub=sub,sup=self.sup)
        
        
class Sub:
    def __init__(self):
        self.sub = None

    def sup(self):
        return SubSup(self.base,sub=self.sub,sup=none)

class Macro:
    def __init__(self,name,desc,nargs,body,tree,sub=True,sup=True,pos=0):
        self.name = name
        self.desc  = desc # text
        self.nargs = nargs # int        
        self.body  = body
        self.args = {}
        self.sub = sub
        self.sup = sup
        self.pos = pos
        self.recv = 0
        self.start = []
        self.end = []
        self.tree = []
        self.tree.extend(tree)
        for i in xrange(len(self.tree)):
            node = self.tree[i]
            if isinstance(node,Placeholder):
                if node.arg in self.args:
                    self.args[node.arg].append(i)
                else:
                    self.args[node.arg] = [i]
    def copy(self,pos):
        return Macro(self.name,self.desc,self.nargs,self.body,self.tree,pos=pos)
    def asDoc(self, r):
        for i in self.body:
            i.asDoc(r)
        return r
    def handleSubp(char):
        if char == '_':
            key = 'SUBSCRIPT'
        else:
            key = 'SUPERSCRIPT'
        returnee = None
        if(self.sub):
            if(self.args.has_key(key)):
                self.nargs += 1
                self.args[self.nargs] = self.args[key]
                del self.args[key]
            else:
                raise MacroError(('<%s>: %s recived a %s but has no %s'+
                'argument')%(self.pos,self.name,char,key))
        else:
            if(self.nargs ==0):
                returnee = ''.join(self.content)
            else:
                raise MacroError('<%s>: %s does not accept %s' %
                (self.pos,self.name,key.lower()))
    def addArgument(self,group,pos):
        try:
            argument = str(group)[1:-1]
            for n in self.args[str(self.recv)]:
                self.tree[n] = argument
            self.nargs = self.nargs -1
            self.recv +=1
        except IndexError:
            raise MacroError(('%s: Macro %s needs no more '+
                'arguments')%(self.pos,self.name))
    def end(self):
        if not self.nargs == 0:
            raise MacroError('%s: %s missing arguments'%(self.pos,self.name))
        return self.body
    def __repr__(self):
        return self.name
    def nArgs(self):
        return self.nargs

class Environment:
    def __init__(self,name,desc,localcmds,nargs,defines,body,tree,sub=None,sup=None,pos='0'):
        self.desc    = desc
        self.defines = defines
        self.nargs   = nargs
        self.body    = body
        self.localcmds = localcmds
        self.recv = 0
        self.name = name
        self.sub = sub
        self.sup = sup
        self.pos = pos
        self.args = {}
        self.tree = tree
        self.printed = False
        for i in xrange(len(self.tree)):
            node = self.tree[i]
            if isinstance(node,Placeholder):
                if self.args.has_key(node.arg):
                    self.args[node.arg].append(i)
                else:
                    self.args[node.arg] = [i]
    def nArgs(self):
        return self.nargs
    def printable(self):
        if not self.printed:
            try:
                returnee = ''.join([self.tree[x] for x in (range(self.args['BODY'][0]))])
                self.printed = True
                return returnee
            except IndexError:
                raise MacroError(('<%s>:Environment %s does not have a {{BODY}}')
                %(self.pos,self.name))
        else:
            return ''
    def printend(self):
        r = range(self.args['BODY'][0]+1,len(self.tree))
        try:
            return ''.join([self.tree[x] for x in r])
        except IndexError:
            #This cant happen
            raise MacroError(('<%s>:Environment %s does not have a {{BODY}}')
            %(self.pos,self.name))

    def __repr__(self):
        return self.name

    def asDoc(self, r):
        for i in self.body:
            i.asDoc(r)
        return r
    def copy(self):
        return Environment(self.name,self.desc,self.localcmds,self.nargs,self.defines,self.body,self.tree)

    def addArgument(self,group,pos):
        if self.nArgs()!=0:
            try:
                for place in self.args[self.recv]:
                    self.tree[place] = group
                self.recv +=1
                self.args -=1
            except: 
                #print group
                raise MacroError(('%s: <%s> to many arguments '+
                'recieved')%(pos,self.name))
        #We are adding to the body
        else:
            if len(self.tree) >2:
                start = ''.join(self.tree[:-1])+group
                self.tree = [start,self.tree[-1]]
            else:
                self.tree[0] +=group
    def end(self):
        returnee = ''
        try:
            returnee.join([self.tree[x] for x in
            range(self.args['BODY'][0],len(self.args))])
        except IndexError:
            raise MacroError('<%s>: Enviroment %s failed'%
            (self.pos,self.name))
        return returnee
        
class EnvDict:
    def __init__(self,parent,d):
        self.__parent = parent
        self.__d = d
    def __getitem__(self,key):
        try:
            return self.__d[key]
        except KeyError:
            return self.__parent[key]
    def has_key(self,key):
        return self.__d.has_key(key) or self.__parent.has_key(key)
    
    # NOTE: This is read-only, so no need to implement all the set functions
    def dictLookup(self,key):
        try:
            return self.__d.dictLookup(key)
        except KeyError:
            return self.__parent.dictLookup(key)

class ResolvedSubSuperScript:
    def __init__(self,pos,base,subscr=None,superscr=None):
        self.pos      = pos
        self.base     = base
        self.subscr   = subscr
        self.superscr = superscr

class ResolvedMacro:
    def __init__(self,macro,pos):
        self.pos      = pos
        self.macro    = macro
        self.args     = []
        self.subscr   = None
        self.superscr = None
    def requireArgs(self):
        return self.macro.nArgs() - len(self.args)
    def append(self,arg):
        "Append argument"
        self.args.append(arg)

    def requireMoreArgs(self):
        return len(self.args) < self.macro.nArgs()

    def end(self):
        if self.macro.nArgs() < len(self.args):
            raise MacroError('%s: Missing macro argument for \\%s' % (self.pos,self.name))



def closeStack(macrostack,stopClass,pos,name):
    text = ''
    while(macrostack):
        top = macrostack.pop()
        if(isinstance(top,stopClass)):
            break
        else:
            try:
                if top.nArgs()==0:
                    text = text + ''.join(top.tree)
                else:
                    raise MacroError('%s:<%s> was closed preemptivly' %(pos,top.name))
            except AttributeError:
                raise MacroError('%s:while closing <%s> a unclosed group was'+
                'encountered'%(pos,name))
    return (text,macrostack)

class MacroParser:
    __macrostack= []
    __cmdstack = []

    def ___init__(self):
        self.__macrostack = []
        self.__cmdstack = []

    def handleText(self,cmddict,data,pos,table=False):
        text = ''
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
        p = 0
        for o in macro_re.finditer(data):
            #close the top element if the next isnt a ^ or _
            if(not o.group('subsuperscr') and self.__macrostack):
                while(self.__macrostack and isinstance(self.__macrostack[-1],Group) and
                self.__macrostack[-1].end):
                    top = self.__macrostack.pop()
                    if(self.__macrostack):
                        self.__macrostack[-1].addArgument(top,pos)
                    else:
                        text += top.content
                if(isinstance(self.__macrostack[-1],Environment) and
                    self.__macrostack[-1].nArgs()==0):
                    text += self.__macrostack[-1].printable()
                if(isinstance(self.__macrostack[-1],Macro) and self.__macrostack[-1].nArgs()==0):
                    top = self.__macrostack.pop()
                    text += ''.join(top.tree)
            #Slight misuse of try, this is meant to check if the text is inside a
            #group
            try:
                if self.__macrostack[-1].end:
                    if p < o.start(0):
                        text += data[p:o.start(0)]
            except IndexError:
                if p < o.start(0):
                    text += data[p:o.start(0)]
            except AttributeError:
                pass
            p= o.end(0)
            #should check if the macro is in the __cmddict
            if o.group('macro'):
                name = o.group('macro')
                try:
                    i = self.__macrostack[-1] 
                    if isinstance(i,unicode):
                        if i=="_" or i == "^":
                            raise MacroError("%s:%s can't have macro on"+\
                            "left hand side"%(pos,i))
                except IndexError:
                    pass
                assert name not in ['begin','']
                if name == ':':
                    if table:
                        #dgb("%s: New table row" % pos)
                        try:
                            self.started
                        except AttributeError:
                            self.started = True
                    else:
                        raise MacroError('%s: Row syntax used outside a Table'%pos)
                elif name == '!':
                    if table:
                        try:
                            if self.started:
                                #dgb("%s: New table cell" % pos)
                                pass
                        except AttributeError:
                            #dgb('%s: cstack = %s' % (pos,self.__cstack))
                            raise MacroError('%s: Table syntax must start with a row \\:' % pos)
                    else:
                        raise MacroError('%s: \! syntax used outside a Table'%pos)
                else:
                    try:
                        macronode = cmddict[name].macro
                        macronode = macronode.copy(pos)
                        self.__macrostack.append(macronode)
                    except KeyError:
                        print "Known Macros"
                        print cmddict
                        raise MacroError('%s: Unknown macro "%s"' % (pos,name))
                        
            elif o.group('env'):
                name = o.group('envname')
                if o.group('env') == 'begin':
                    #emitOpen(DelayedEnvironment(name,pos))
                    try:
                        envnode = cmddict[name]
                        d = envnode.getDefs()
                        envnode = envnode.env.copy()
                        self.__cmdstack.append(cmddict)
                        cmddict = CommandDict(cmddict) 
                        cmddict.update(d.getCmdDict())
                        self.__macrostack.append(envnode)
                    except KeyError:
                        raise MacroError('%s: Unknown environment\
                        "%s"'%(pos,name))
                else:
                    if (self.__macrostack and self.__macrostack[-1].name ==
                        name):
                        cmddict = self.__cmdstack.pop()
                        envdone = self.__macrostack.pop()
                        if envdone.nArgs()==0:
                            text = text + ''.join(envdone.printend())
                        else:
                            raise MacroError(('%s: <%s> ended '+
                                'before getting enough arguments')
                                %(self.pos,name))
                    else:
                        raise MacroError(('%s: <%s> end environment'+
                        'mismatch')%(pos,name))
            elif o.group('group'):
                #Either a start or an end or a group
                tok = o.group('group')
                if tok == '{': 
                    #self.__emitOpen(DelayedGroup(pos))
                    self.__macrostack.append(Group(p))
                else:
                    top = self.__macrostack[-1]
                    if(isinstance(top,Group)):
                        top.end = True
                        content = data[top.start:p-1]
                        top.content = content
                    else:
                        raise MacroError("%s: Umatched group close"%pos)
            elif o.group('subsuperscr'):
                char = o.group('subsuperscr')
                if len(self.__macrostack)>0:
                    self.__macrostack[-1].handleSubp(char)
                    if(data[p+1]!='{'):
                        p +=1
                        self.__macrostack[-1].addArgument(data[p],pos)
                else:
                    raise MacroError("<%s-%s>:Trying to apply %s to an"\
                    +"empty argument"%(start,pos,char))
            elif   o.group('longdash') is not None:
                if   o.group('longdash') == '--':
                    text += u'\u2013'
                    #self.__emitItem(DelayedText(u'\u2013',pos)) # &ndash;
                elif o.group('longdash') == '---':
                    text += u'\u2014'
                    #self.__emitItem(DelayedText(u'\u2014',pos)) # &ndash;
                    pass
                else:
                    text += o.group('longdash')
                    #self.__emitItem(DelayedText(o.group('longdash'),pos)) # &ndash;
            elif o.group('leftdquote') is not None:
                #self.__emitItem(DelayedText(u'\u201c',pos)) # &ldquote
                text += u'\u201c'
                pass
            elif o.group('rightdquote') is not None:
                #self.__emitItem(DelayedText(u'\u201d',pos)) # &rdquote
                text += u'\u201d'
            elif o.group('nbspace'):
                #self.__emitItem(DelayedText(u'\xa0',pos)) # &nbsp;
                text += u'\xa0'
            elif o.group('newline'):
                #self.__emitItem(DelayedText(u' \n',pos))
                text += u' \n '
                pos = Pos(pos.filename,pos.line + 1)
            else:
                #print 'GOT: "%s"' % o.group(0)
                assert 0
        if self.__macrostack:
            while(self.__macrostack and isinstance(self.__macrostack[-1],Group) and
            self.__macrostack[-1].end):
                top = self.__macrostack.pop()
                if(self.__macrostack):
                    self.__macrostack[-1].addArgument(top,pos)
                else:
                    text += top.content
            if(isinstance(self.__macrostack[-1],Environment) and
                self.__macrostack[-1].nArgs()==0):
                text += self.__macrostack[-1].printable()
            if(isinstance(self.__macrostack[-1],Macro) and self.__macrostack[-1].nArgs()==0):
                top = self.__macrostack.pop()
                text += ''.join(top.tree)
        if p < len(data):
            #print "NODE : <%s>" % self.nodeName
            #print len(self.__cstack),self.__cstack[-1].data
            #print repr(self.__cstack[-1])
            #self.__cstack[-1].append(DelayedText(data[p:],pos))
            text += data[p:]
        return (text,pos)
