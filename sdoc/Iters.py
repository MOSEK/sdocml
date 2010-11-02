"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009 Mosek ApS 
"""

import re
import UserList

class ContentIteratorError(Exception):
    pass

class SyntaxDefError(Exception):
    pass

parsedefre = re.compile('|'.join([r'<(?P<tag>[a-zA-Z:][a-zA-Z:\-]*)>\s*(?P<tagcounter>\*|\+|\?)?',
                                  #r'(?P<any>\.)',
                                  r'(?P<text>T)',
                                  r'(?P<fencestart>\[)',
                                  r'(?P<fenceend>\])\s*(?P<fencecounter>\*|\+|\?|!|/)?',
                                  r'(?P<space>[ \t\n]+)']))
def parsedef(s):
    pos = 0
    r = parsedefre


    class Seq(UserList.UserList):
        def render(self):
            if not self.data:
                return NoContent
            else:
                l = []
                for i in self.data:
                    if i == '.':
                        assert 0
                    elif i == 'T':
                        l.append(TextIterator)
                    else:
                        l.append(i.render())
                return SequenceOfIterator(l)
            
    class AnyOf(UserList.UserList):
        def __init__(self):
            UserList.UserList.__init__(self)
            self.counter = None
        def setCounter(self,counter):
            self.counter = counter
        def render(self):
            if   self.counter is None:
                if 'T' in self.data:
                    raise SyntaxDefError("Invalid syntax definition '%s'" % s)
                else:
                    return OneOfIterator([ i.name for i in self.data ])
            elif self.counter == '*':
                if 'T' in self.data:
                    return ZeroOrMoreOfIterator([ i.name for i in self.data if i != 'T' ],or_text=True)
                else:
                    return ZeroOrMoreOfIterator([ i.name for i in self.data ])
            elif self.counter == '+':
                if 'T' in self.data:
                    return OneOrMoreOfIterator([ i.name for i in self.data if i != 'T' ],or_text=True)
                else:
                    return OneOrMoreOfIterator([ i.name for i in self.data ])
            elif self.counter == '?':
                if 'T' in self.data:
                    return ZeroOrOneOfIterator([ i.name for i in self.data if i != 'T' ],or_text=True)
                else:
                    return ZeroOrOneOfIterator([ i.name for i in self.data ])
            elif self.counter == '!': # Meaning: Exactly one of each, in any order
                if 'T' in self.data:
                    raise SyntaxDefError("Invalid syntax definition '%s'" % s)
                else:
                    return OneOfEachIterator([ i.name for i in self.data ])
            elif self.counter == '/': # Meaning: Exactly one of each, in any order
                if 'T' in self.data:
                    return ZeroOrOneOfEachIterator([ i.name for i in self.data if i != 'T' ],or_text=True)
                else:
                    return ZeroOrOneOfEachIterator([ i.name for i in self.data ])
            else:
                assert 0
                
    class Tag:
        def __init__(self,item,counter=None):
            self.name = item
            self.counter = counter
        def render(self):
            if   self.counter is None:
                return OneOfIterator([self.name])
            elif self.counter == '*':
                return ZeroOrMoreOfIterator([self.name])
            elif self.counter == '+':
                return ZeroOrMoreOfIterator([self.name])
            elif self.counter == '?':
                return ZeroOrOneOfIterator([self.name])
            else:
                print "Tag: Got '%s'" % self.counter
                assert 0 
            
    seq = Seq()
    stack = [seq]

    while pos < len(s):
        o = r.match(s,pos)
        if o is None:
            print "String part 1: '%s'" % s[:pos]
            print "String part 2: '%s'" % s[pos:]
            raise SyntaxDefError("Invalid syntax definition '%s'" % s)
        pos = o.end(0)
        if   o.group('space'):
            pass
        elif o.group('tag'):
            counter = o.group('tagcounter')
            if counter and len(stack) > 1:
                raise SyntaxDefError("Invalid syntax definition '%s'" % s)
            stack[-1].append(Tag(o.group('tag'),counter))
        elif o.group('text'):
            stack[-1].append('T')
        elif o.group('fencestart'):
            if len(stack) != 1:
                raise SyntaxDefError("Invalid syntax definition '%s'" % s)
            else:
                stack.append(AnyOf())
        elif o.group('fenceend'):
            fcounter = o.group('fencecounter')
            if len(stack) == 1:
                raise SyntaxDefError("Invalid syntax definition '%s'" % s)
            else:
                item = stack.pop()
                item.setCounter(fcounter)
                stack[-1].append(item)
        else:
            assert 0
        
    return seq.render()

class ContentIteratorError(Exception):
    pass

class BaseContentIterator:
    def __init__(self): 
        pass
    def element(self,item):
        raise ContentIteratorError('Element not accepted')
    def text(self,item):
        if item.strip():
            raise ContentIteratorError('Text not accepted')

    ## \brief Return True if the item matches the sequence, False if it ends
    #         the sequence correctly. If it incorrectly terminates the sequence,
    #         ContentIteratorError is raised.
    def __call__(self,item):
        if isinstance(item,unicode):
            return not item.strip() or self.text(item)
        else:
            return self.element(item)
    def current(self):
        return self
    def end(self):
        return True

class NoContent(BaseContentIterator):
    def repr(self):
        return 'EMPTY'

def ZeroOrOneOfIterator(names,or_text=False):
    # Implements : 
    #   [ <tag1> ... <tagn> ]
    # and 
    #   [ <tag1> ... <tagn> ] | TEXT
    class _ZeroOrOneOfIterator(BaseContentIterator):
        def __init__(self):
            BaseContentIterator.__init__(self)
            self.__gotText    = False
            self.__gotElement = False
            self.__ended      = False

        def element(self,item):
            if   self.__ended:
                return BaseContentIterator.element(item)
            elif self.__gotText or self.__gotElement or item.nodeName not in names:
                self.__ended = True
                return False
            else:
                self.__gotElement = True
                return True
        def text(self,item):
            if   self.__ended:      
                return BaseContentIterator.element(item)
            elif self.__gotElement:
                self.__ended = True
                return False
            elif or_text: 
                self.__gotText = True
                return True
            else:                   
                return BaseContentIterator.element(item)
        @classmethod
        def repr(self):
            return 'ZeroOrOne(%s)' % ','.join(names)

    return _ZeroOrOneOfIterator    

def ZeroOrMoreOfIterator(names,or_text=False):
    class _ZeroOrMoreOfIterator(BaseContentIterator):
        def __init__(self):
            BaseContentIterator.__init__(self)
            self.__ended      = False

        def element(self,item):
            if   self.__ended:
                return BaseContentIterator.element(item)
            elif item.nodeName not in names:
                self.__ended = True
                return False
            else:
                return True
        def text(self,item):
            if   self.__ended:      
                return BaseContentIterator.element(item)
            elif or_text: 
                return True
            else:                   
                self.__ended = True
                return False
        @classmethod
        def repr(self):
            return 'Zero+(%s)' % ','.join(names)

    return _ZeroOrMoreOfIterator

def OneOfIterator(names):
    # Implements : 
    #   <tag>
    class _OneOfIterator(BaseContentIterator):
        def __init__(self):
            BaseContentIterator.__init__(self)
            self.__gotElement = False
            self.__ended      = False

        def element(self,item):
            if   self.__ended:
                return BaseContentIterator.element(item)
            elif self.__gotElement:
                self.__ended = True
                return False
            elif item.nodeName in names:
                self.__gotElement = True
                return True
            else:
                return BaseContentIterator.element(self,item)
        def text(self,item):
            if   self.__ended:      
                return BaseContentIterator.text(selfmitem)
            elif self.__gotElement:
                self.__ended = True
                return False
            else:                   
                return BaseContentIterator.text(self,item)
        def end(self):
            return self.__ended or self.__gotElement
            
        @classmethod
        def repr(self):
            return 'One(%s)' % ','.join(names)
    return _OneOfIterator    

def OneOfEachIterator(names):
    # Implements : 
    #   <tag>
    class _OneOfEachIterator(BaseContentIterator):
        def __init__(self):
            BaseContentIterator.__init__(self)
            self.__d = dict([ (n,False) for n in names ])
            self.__ended      = False

        def element(self,item):
            n = item.nodeName
            if   self.__ended:
                return BaseContentIterator.element(item)
            elif self.__d.has_key(n):
                if self.__d[n]: # implies end of scope
                    self.end()
                    return False
                else:
                    self.__d[n] = True
                    return True
            else:
                self.end()
        def text(self,item):
            if self.__ended:
                assert 0
            else:
                return BaseContentIterator.text(item)
        def end(self):
            if not self.__ended:
                for k,v in self.__d.items():
                    if not v:
                        raise ContentIteratorError('Missing element <%s>' % k)
                self.__ended = True

            return True
            
        @classmethod
        def repr(self):
            return 'OneOfEach(%s)' % ','.join(names)
    return _OneOfEachIterator    

def ZeroOrOneOfEachIterator(names):
    # Implements : 
    #   <tag>
    class _ZeroOrOneOfEachIterator(BaseContentIterator):
        def __init__(self):
            BaseContentIterator.__init__(self)
            self.__d = dict([ (n,False) for n in names ])
            self.__ended      = False

        def element(self,item):
            n = item.nodeName
            if   self.__ended:
                return BaseContentIterator.element(item)
            elif self.__d.has_key(n):
                if self.__d[n]: # implies end of scope
                    self.end()
                    return False
                else:
                    self.__d[n] = True
                    return True
            else:
                self.end()
        def text(self,item):
            if self.__ended:
                assert 0
            else:
                return BaseContentIterator.text(item)
        def end(self):
            self.__ended = True
            return True
            
        @classmethod
        def repr(self):
            return 'ZeroOrOne(%s)' % ','.join(names)

    return _ZeroOrOneOfEachIterator    

def OneOrMoreOfIterator(names,or_text):
    SequenceOfIterator([ OneOfIterator(names,or_text),ZeroOrMoreOfIterator(names,or_text) ])


#def ZeroOrMoreOfIterator(it):
#    # Implements : 
#    #   ANY* 
#    class _ZeroOrMoreIfIterator(BaseContentIterator):
#        def __init__(self):
#            BaseContentIterator.__init__(self)
#            self.__it    = it()
#            self.__ended = False
#        def any(self,item): 
#            if   self.__ended:
#                return BaseContentIterator.element(item)
#            elif not self.__it.element(item):
#                self.__it = it()
#                if not self.__it.element(item):
#                    self.__ended = True
#                    return False
#                else:
#                    return True
#            else:
#                return True
#        def element(self,item):
#            return any(self,item)
#        def text(self,item):
#            return any(self,item)
#        
#def OneOrMoreOfIterator(it):
#    # Implements : 
#    #   ANY+
#    class _OneOrMoreIfIterator(BaseContentIterator):
#        def __init__(self):
#            BaseContentIterator.__init__(self)
#            self.__gotOne = False
#            self.__it    = it()
#            self.__ended = False
#        def any(self,item): 
#            if   self.__ended:
#                return BaseContentIterator.element(item)
#            elif not self.__it.element(item):
#                self.__gotOne = True # Means that at least one iterator ended correctly (not necessarily that one element was accepted)
#                self.__it = it()
#                if not self.__it.element(item):
#                    self.__ended = True
#                    return False
#                else:
#                    return True
#            else:
#                return True
#        def element(self,item):
#            return any(self,item)
#        def text(self,item):
#            return any(self,item)
#        def end(self):
#            return self.__gotOne
#            
def SequenceOfIterator(iters):
    # Implements : 
    #   ANY ... ANY
    class _SequenceOfIterator(BaseContentIterator):
        def __init__(self):
            BaseContentIterator.__init__(self)
            self.__iters = iters[:]
            self.__it    = self.__iters.pop(0)()
            self.__ended = False
        def any(self,item): 
            if   self.__ended:
                return BaseContentIterator.element(self,item)
            else:
                while not self.__it(item):
                    if self.__iters:
                        self.__it = self.__iters.pop(0)()
                    else:
                        self.__ended = True
                        return False
                return True
        def element(self,item):
            return self.any(item)
        def text(self,item):
            return self.any(item)
        def end(self):
            if not self.__it.end():
                return False
            for it in self.__iters:
                if not it.end():
                    return False
            return True
        @classmethod
        def repr(self):
            return 'Sequence(%s)' % ','.join([ i.repr() for i in iters ])
    return _SequenceOfIterator

def AnyOneOfIterator(names,or_text=False):
    # Implements : 
    #   [ <tag0> ... <tag1> ] 
    # and
    #   [ <tag0> ... <tag1> ] | TEXT 
    class _AnyOneOfIterator(BaseContentIterator):
        def __init__(self):
            BaseContentIterator.__init__(self)
            self.__gotText    = False
            self.__gotElement = False
            self.__ended      = False

        def element(self,item):
            if   self.__ended:
                return BaseContentIterator.element(item)
            elif self.__gotText or self.__gotElement or item.nodeName not in names:
                self.__ended = True
                return False
            else:
                self.__gotElement = True
                return True
        def text(self,item):
            if   self.__ended:      
                return BaseContentIterator.element(item)
            elif self.__gotElement:
                self.__ended = True
                return False
            elif or_text: 
                self.__gotText = True
                return True
            else:                   
                return BaseContentIterator.element(item)
        def end(self):
            return self.__gotElement or or_text

    return _AnyOneOfIterator    
    

class TextIterator(BaseContentIterator):
    # Implements : 
    #   TEXT 

    def __init__(self):
        self.__ended = False
    def text(self,item):
        if self.__ended:
            BaseContentIterator.text(self,item)
        else:
            return True
    def element(self,item):
        if not self.__ended:
            self.__ended = True
            return False
        else:
            BaseContentIterator.text(self,item)
    @classmethod
    def repr(self):
        return 'TEXT'
    



if __name__ == '__main__':
    class Node:
        def __init__(self,name):
            self.nodeName = name
    
    V = parsedef('<head> [ T <tt> <rm> <em> <ilist> <dlist> ]* <section>*')
    print V.repr()
    
    I = V()
    for v in [ '   \n ',
               Node('head'),
               '     XX',
               Node('tt'),
               Node('em'),
               ' YY ',
               'ZZ',
               Node('section'),
               Node('section'),
               ]:
        if isinstance(v,Node):
            I.element(v)
        else:
            I.text(unicode(v))
    I.end()
    print "HOORAY!" 
    
    I = V()
    try:
        for v in [ '   \n ',
                   Node('head'),
                   '     XX',
                   Node('tt'),
                   Node('em'),
                   ' YY ',
                   'ZZ',
                   Node('section'),
                   'XX',
                   Node('section'),
                   ]:
            if isinstance(v,Node):
                I.element(v)
            else:
                I.text(unicode(v))
        I.end()
        assert 0
    except:
        pass

        
    print "HOORAY!"



