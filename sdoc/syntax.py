"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009 Mosek ApS 
"""


import re


# NOTE: List of keywords is taken from the official Python 2.4 language documentation
python_keywords = ['and','del','from','not','while', 'as','elif','global','or','with', 'assert','else','if','pass','yield', 'break','except','import','print', 'class','exec','in','raise', 'continue','finally','is','return', 'def','for','lambda','try',]
python_language = ['None','True','False','dict','list','classmethod','staticmethod','super','str','unicode','object','id']
python_syntax = re.compile('|'.join([r'(?P<cmnt>#.*)',
                                     r'(?P<str>"(?:[^"]|\\")*"|\'(?:[^\']|\\\')*\')',
                                     r'(?P<word>\w+)',
                                     r'(?P<newline>\n)',
                                     r'(?P<mlstr>"""|\'\'\')',# Note: This will fail in the freak case where e.g. '\"""' appeared inside a multi-line string.
                                     ]))

# NOTE: List of keywords is taken from the official Java 1.6 language documentation.
java_keywords = [   "abstract", "assert", "boolean", "break", "byte",
                    "case", "catch", "char", "class", "const",
                    "continue", "default", "do", "double", "else",
                    "enum", "extends", "final", "finally", "float",
                    "for", "goto", "if", "implements", "import",
                    "instanceof", "int", "interface", "long", "native",
                    "new", "package", "private", "protected", "public",
                    "return", "short", "static", "strictfp", "super",
                    "switch", "synchronized", "this", "throw", "throws",
                    "transient", "try", "void", "volatile", "while" ]
java_language = ['null','true','false','String',]
java_syntax = re.compile('|'.join([r'(?P<cmnt>//.*)',
                                   r'(?P<str>"(?:[^"]|\\")*"|\'(?:[^\']|\\\')*\')',
                                   r'(?P<word>\w+)',
                                   r'(?P<newline>\n)',
                                   r'(?P<mlcmntstart>/\*)',
                                   r'(?P<mlcmntend>\*/)',
                                   ]))

xml_syntax = re.compile('|'.join([r'(?P<doctypestart><\!DOCTYPE)', # Not entirely correct since quoted strings may contain ">"
                                  r'(?P<directivestart><\?[a-zA-Z][a-zA-Z0-9:_]*)', # Not entirely correct since quoted strings may contain ">"
                                  r'(?P<directiveend>\?>)',
                                  r'(?P<tagstart><\s*(?P<tag>[a-zA-Z][a-zA-Z0-9_:.-]*))',
                                  r'(?P<tagend>>|/>)',
                                  r'(?P<endtag></[^>]+>)',
                                  r'(?P<comment><!--(?:-[^\-]|[^\-])*-->)',
                                  r'(?P<attrkey>[a-zA-Z][a-zA-Z0-9_:]*)(?P<attreq>\s*=\s*)(?P<attrval>"[^"]*"|\'[^\']*\')',
                                  r'(?P<lf>\n)',
                                  ]))
## Add simple hilighting information to code.OB
#
# Hilighting is performed per-line, i.e. multi-line comments or strings are
# tagged per line, so that a linebreak never occurs inside a tag.
#
# The argument 'data' is a list of lines, not including the lineberak character.
# The result is a list, where each entry is a line with added hilight
# information. Each line is a list, where each element is either a string or a
# pair (type,string), where the 'type' indicated what kind of token the string
# contains (e.g. keyword, operator, comment, string etc.).
# 
# Example: 
# data  :  ['# Some code...',
#                  'print "hello world!"']
# Result:  [ [('comment','# Some code...')],
#            [('keyword','print'),' ',('string','"hello world!"')] ]
#
# Example:
# data  :  ['""" Example of a',
#                Multiline string!"""' ]
# Result:  [ [('string','""" Example of a'],
#            [('string','    Multiline string!"""')] ]
kw_comment  = 'comment'
kw_string   = 'string'
kw_keyword  = 'keyword'
kw_language = 'language'


class CodeHilighter:
    def __init__(self,mimetype='text/plain'):
        self.__state = None
        if mimetype == 'source/python':
            self.process = self.process_Python
        elif mimetype == 'source/java':
            self.process = self.process_Java
        elif mimetype == 'text/xml':
            self.process = self.process_XML
        else:
            self.process = self.process_plaintext

    def process_Java(self,l):
        lres = []
        pos = 0

        for o in java_syntax.finditer(l):
            if self.__state is None:
                if pos < o.start(0):
                    lres.append(l[pos:o.start()])
                pos = o.end()
                if   o.group('cmnt') is not None:
                    lres.append((kw_comment,o.group(0)))
                elif o.group('str') is not None:
                    lres.append((kw_string,o.group(0)))
                elif o.group('mlcmntstart'):
                    self.__state = o.group(0)
                    lres.append((kw_comment,o.group(0)))
                elif o.group('newline'):
                    lres.append(u'\n')
                else:# o.group('word') is not None
                    w = o.group(0)
                    if   w in java_keywords:
                        lres.append((kw_keyword,w))
                    elif w in java_language:
                        lres.append((kw_language,w))
                    else:
                        lres.append(w)
            else:# inside multi-line string
                if o.group('mlcmntend') and o.group(0) == self.__state:
                    lres.append((kw_comment,l[pos:o.end(0)]))
                    pos = o.end(0)
                    self.__state = None                        
                elif o.group('newline'):
                    lres.append((kw_comment,l[pos:o.start(0)]))
                    lres.append(u'\n')
                    pos = o.end(0)
        if pos < len(l):
            if self.__state is None:
                lres.append(l[pos:])
            else:
                lres.append((kw_comment,l[pos:]))
        return lres
    def process_XML(self,l):
        # limited syntax support...
        lres = []
        pos = 0

        for o in xml_syntax.finditer(l):
            if self.__state is None:
                if o.group('tagstart'):                    
                    lres.append(l[pos:o.start(0)])
                    pos = o.end(0)
                    lres.append((kw_keyword,o.group('tagstart')))
                    self.__state = '<'
                elif o.group('comment'):
                    lres.append(l[pos:o.start(0)])
                    pos = o.end(0)
                    lres.append((kw_comment,o.group('comment')))
                elif o.group('directivestart'):
                    lres.append(l[pos:o.start(0)])
                    pos = o.start(0)
                    self.__state = '<?'
                elif o.group('doctypestart'):
                    lres.append(l[pos:o.start(0)])
                    pos = o.start(0)
                    self.__state = '<!'
                elif o.group('endtag'):                    
                    lres.append(l[pos:o.start(0)])
                    pos = o.end(0)
                    lres.append((kw_keyword,o.group('endtag')))
                else:
                    pass
            elif self.__state == '<!':
                if o.group('tagend') is not None:
                    lres.append((kw_comment,l[pos:o.end(0)]))
                    self.__state = None
                    pos = o.end(0)
                elif o.group('lf'):
                    if pos < o.start():
                        lres.append((kw_comment,l[pos:o.start(0)]))
                    lres.append('\n')
                    pos = o.end(0)
            elif self.__state == '<?':
                if o.group('directiveend') is not None:
                    lres.append((kw_comment, l[pos:o.end(0)]))
                    self.__state = None
                    pos = o.end(0)
                elif o.group('lf'):
                    if pos < o.start():
                        lres.append((kw_comment,l[pos:o.start(0)]))
                    lres.append('\n')
                    pos = o.end(0)
            else:# self.__state == '<':
                if o.group('tagend'): 
                    lres.append(l[pos:o.start(0)])
                    pos = o.end(0)
                    lres.append((kw_keyword,o.group('tagend')))
                    self.__state = None
                elif o.group('attrkey'):
                    lres.append(l[pos:o.start(0)])
                    pos = o.end(0)
                    try:
                        keyprfx,keyval = o.group('attrkey').split(':',1)
                        lres.append((kw_language,keyprfx + ':'))
                        lres.append((kw_keyword,keyval))
                    except ValueError:
                        lres.append((kw_keyword,o.group('attrkey')))
                    lres.append(o.group('attreq'))
                    lres.append((kw_string,o.group('attrval')))
                else:
                    pass
        if pos < len(l):
            if   self.__state == '<!':
                lres.append((kw_comment,l[pos:]))
            elif self.__state == '<?':
                lres.append((kw_comment, l[pos:]))
            else:
                lres.append(l[pos:])
        return lres
                


    def process_Python(self,l):
        lres = []
        pos = 0

        for o in python_syntax.finditer(l):
            if self.__state is None:
                if pos < o.start(0):
                    lres.append(l[pos:o.start()])
                pos = o.end()
                if   o.group('cmnt') is not None:
                    lres.append((kw_comment,o.group(0)))
                elif o.group('str') is not None:
                    lres.append((kw_string,o.group(0)))
                elif o.group('mlstr'):
                    self.__state = o.group(0)
                    lres.append((kw_string,o.group(0)))
                elif o.group('newline'):
                    lres.append(u'\n')
                else:# o.group('word') is not None
                    w = o.group(0)
                    if   w in python_keywords:
                        lres.append((kw_keyword,w))
                    elif w in python_language:
                        lres.append((kw_language,w))
                    else:
                        lres.append(w)
            else:# inside multi-line string
                if o.group('mlstr') and o.group(0) == self.__state:
                    lres.append((kw_string,l[pos:o.end(0)]))
                    pos = o.end(0)
                    self.__state = None                        
                elif o.group('newline'):
                    lres.append((kw_string,l[pos:o.start(0)]))
                    lres.append(u'\n')
                    pos = o.end(0)
        if pos < len(l):
            if self.__state is None:
                lres.append(l[pos:])
            else:
                lres.append((kw_string,l[pos:]))
        return lres
    def process_plaintext(self,data):
        return [data]
        

def hilightCode(data,mimetype='text/plain'):
    if mimetype == 'source/python':
        res = []
        
        state = None
        for l in data:
            lres = []
            pos = 0

            for o in python_syntax.finditer(l):
                if state is None:
                    if pos < o.start(0):
                        lres.append(l[pos:o.start()])
                    pos = o.end()
                    if   o.group('cmnt') is not None:
                        lres.append((kw_comment,o.group(0)))
                    elif o.group('str') is not None:
                        lres.append((kw_string,o.group(0)))
                    elif o.group('mlstr'):
                        state = o.group(0)
                        lres.append((kw_string,o.group(0)))
                    else:# o.group('word') is not None
                        w = o.group(0)
                        if   w in python_keywords:
                            lres.append((kw_keyword,w))
                        elif w in python_language:
                            lres.append((kw_language,w))
                        else:
                            lres.append(w)
                else:# inside multi-line string
                    if o.group('mlstr') and o.group(0) == state:
                        lres.append((kw_string,l[pos:o.end(0)]))
                        pos = o.end(0)
                        state = None                        
            if pos < len(l):
                if state is None:
                    lres.append(l[pos:])
                else:
                    lres.append((kw_string,l[pos:]))
            res.append(lres)

    else:
        res = [ [l] for l in data ]
    return res

if __name__ == '__main__':
    import sys
    lines = hilightCode(open(sys.argv[1],'rt').read().split('\n'),'source/python')
    for l in lines:
        for li in l:
            if isinstance(li,basestring):
                sys.stdout.write(li)
            else:
                t,data = li
                sys.stdout.write('{%s:%s}' % li)
        sys.stdout.write('\n')
    sys.stdout.flush()

