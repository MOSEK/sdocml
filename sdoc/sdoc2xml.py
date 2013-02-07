"""
    This file os part of the sdocml project:
        http://code.google.com/p/sdocml/
    The project is distributed under GPLv3:
        http://www.gnu.org/licenses/gpl-3.0.html
    
    Copyright (c) 2009,2010 Mosek ApS 
"""

import xml.sax
import re
import sys,os,time
import urlparse
from EvHandler import dtdhandler, handler, Pos, AlternativeSAXHandler, ReParsingSAXHandler
import inspect
import math
import config
import logging
import Nodes
from Nodes import Node,NodeError,unescape,escape,xescape,MotexException,msg
import re

def makemacroref(outfile,docRoot,title):
    msg('Writing Macro reference to "%s"' % outfile)
    f = open(outfile,'wt')
    f.write('<?xml version="1.0" encoding="utf-8" ?>\n')
    f.write('<!DOCTYPE section>\n')
    f.write('<section id="chapter:macro-reference">')
    #f.write('  <head><title>Global macro reference</title></head>\n')
    f.write('  <head><title>%s</title></head>\n' % title)


    defitems = docRoot.documentElement.getMacroDefs()
    defs = [ d for k,d in defitems if isinstance(d,Nodes.DefNode) ]
    envs = [ d for k,d in defitems if isinstance(d,Nodes.DefEnvNode) ]
    defs.sort(lambda lhs,rhs: cmp(lhs.getAttr('m'),rhs.getAttr('m')))
    envs.sort(lambda lhs,rhs: cmp(lhs.getAttr('m'),rhs.getAttr('m')))
    defs = zip(defs,range(len(defs)))
    envs = zip(envs,range(len(envs)))
    if defs: 
        deftabw = min(len(defs),8)
         
        f.write('<center>\n')
        f.write('  <table class="macro-ref-overview" cellhalign="%s">\n' % ' '.join(['left'] * deftabw))
        collen = int(math.ceil(float(len(defs)) / deftabw))
        cols = [ defs[i*collen:(i+1)*collen] for i in range(deftabw) ]
        if len(cols[-1]) < len(cols[0]):
            cols[-1] = cols[-1] + [None] * (len(cols[0]) - len(cols[-1]))
        
        for ds in zip(*cols):
            f.write('    <tr>')
            for d in ds:
                if d is not None:
                    f.write('<td><ref ref="macro-ref:%d"><nx>\\%s</nx></ref></td>' % (d[1],d[0].macroName()))
                else:
                    f.write('<td/>')
            f.write('</tr>\n')
        f.write('  </table>\n')
        f.write('</center>\n')
    
    if envs: 
        deftabw = min(len(envs),8)
         
        f.write('<center>\n')
        f.write('  <table class="macro-ref-overview" cellhalign="%s">\n' % ' '.join(['left'] * deftabw))
        collen = len(envs) / deftabw
        cols = [ envs[i*collen:(i+1)*collen] for i in range(deftabw) ]
        
        if len(cols[-1]) < len(cols[0]):
            cols[-1] = cols[-1] + [None] * (len(cols[0]) - len(cols[-1]))
        
        for ds in zip(*cols):
            f.write('    <tr>')
            for d in ds:
                if d is not None:
                    f.write('<td><ref ref="macro-ref:%d"><nx>%s</nx></ref></td>' % (d[1],d[0].macroName()))
                else:
                    f.write('<td/>')
            f.write('</tr>\n')
        f.write('  </table>\n')
        f.write('</center>\n')

    if defs:
        f.write('  <section id="section:macro-defs">\n') 
        f.write('    <head><title>Macros</title></head>')
        f.write('    <dlist class="macro-ref-list">\n')
        for d,idx in defs:
            desc = d.getDescr()
            f.write('<dt class="macro-def-label" id="macro-ref:%d"><nx>\\%s</nx></dt>\n\n' % (idx,d.macroName())) 
            f.write('<dd>\n')
            f.write('  <dlist class="macro-def-entry">\n')
            if desc:
                f.write('    <dt>Description:</dt><dd><nx>%s</nx> </dd>\n' % desc)

            filename,line = d.pos.filename,d.pos.line
            filename = os.path.basename(filename)
            f.write('    <dt>Defined at:</dt><dd>%s:%d</dd>\n' % (filename,line))
            f.write('    <dt>Number of arguments:</dt> <dd>%d</dd>\n' % d.nArgs())
            f.write('    <dt>Expands to:</dt><dd><pre>')
            
             
            
            f.write(xescape(d.docExpandMacro()))
            
            f.write('</pre></dd>')

            f.write('  </dlist>\n')
            f.write('</dd>\n')
            
            
        f.write('    </dlist>\n')
        f.write('  </section>\n')

    if envs:
        f.write('  <section id="section:macro-envs">\n') 
        f.write('    <head><title>Macro Environments</title></head>')
        f.write('    <dlist class="macro-env-ref-list">\n')
        for d,idx in envs:
            desc = d.getDescr()
            f.write('<dt class="macro-def-label" id="env-ref:%d"><nx>\\begin{%s} ... \\end{%s}</nx></dt>\n\n' % (idx,d.macroName(),d.macroName()) )
            f.write('<dd>\n')
            f.write('  <dlist class="macro-env-entry">\n')
            if desc:
                f.write('    <dt>Description:</dt><dd><nx> %s </nx></dd>\n' % desc)
            filename,line = d.pos.filename,d.pos.line
            filename = os.path.basename(filename)
            f.write('    <dt> Defined at:</dt><dd>%s:%d</dd>\n' % (filename,line))
            f.write('    <dt> Number of arguments:</dt><dd> %d</dd>\n' % d.nArgs())
            f.write('    <dt> Expands to:</dt><dd><pre>\n')
            f.write(escape(d.docExpandMacro()))
            
            f.write('</pre></dd>')

            f.write('  </dlist>\n')
            f.write('</dd>\n')
            
            
        f.write('    </dlist>\n')
        f.write('  </section>\n')

    f.write('</section>')
    f.close()


def decodeString(s):
    o = re.match(r'[ ]*(?:"(?P<dqstr>[^"\\]|(?:\\"))*"|\'(?P<sqstr>[^\'\\]|(?:\\\'))*\'|(?P<unqstr>\S+))[ ]*$', s)
    assert o
    return o.group('dqstr') or o.group('sqstr') or o.group('unqstr')
def decodeDefineString(s):
    o = re.match(r'[ ]*(?P<key>[a-zA-Z09_]+)\s*=\s*(?:"(?P<dqstr>[^"\\]|(?:\\"))*"|\'(?P<sqstr>[^\'\\]|(?:\\\'))*\'|(?P<unqstr>\S+))[ ]*$', s)
    assert o
    return o.group('key'),o.group('dqstr') or o.group('sqstr') or o.group('unqstr')

if __name__ == "__main__":
    P = xml.sax.make_parser()
    logging.basicConfig(level=logging.INFO)

    sdocbase = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]),'..'))

    args  = sys.argv[1:]

    conf = config.Configuration({   'infile'       : config.UniqueEntry('infile'),
                                    'outfile'      : config.UniqueEntry('outfile'),
                                    'incpath'      : config.DirListEntry('incpath'),
                                    'dtdpath'      : config.DirListEntry('dtdpath'),
                                    'trace'        : config.UniqueBoolEntry('trace',default=False),
                                    'makedoc'      : config.UniqueEntry('makedoc',  default=None),
                                    'macroref'     : config.UniqueEntry('macroref',default=None),
                                    'macroreftitle' : config.UniqueEntry('macroreftitle',default="Macro reference"),
                                    'define'       : config.BoolDefListEntry('define'),
                                    'error:refs'   : config.UniqueBoolEntry('error:refs',default=True),
                                    #'nodefaultinc' : config.UniqueEntry('nodefaultinc'),
                                    'maxsectiondepth' : config.UniqueIntEntry('macsectiondepth','4'),
                                    'erroronmissingrefs' : config.UniqueBoolEntry('erroronmissigrefs',default=True)
                                })
    # add a couple of default paths
    conf.update('dtdpath',os.path.join(sdocbase,'dtd'))
    conf.update('dtdpath',os.path.join(sdocbase,'dtd','external'))

    while args:
        arg = args.pop(0)
        if   arg == '-o':
            conf.update('outfile',args.pop(0))
        elif arg == '-config':
            conf.updateFile(args.pop(0))
        elif arg == '-d':
            conf.update('define',args.pop(0))
        elif arg == '-defaultinclude':
            conf.update('incpath',os.path.join(sdocbase,'manual','include'))
        elif arg == '-i':
            conf.update('incpath',args.pop(0))
        elif arg == '-dtdpath':
            conf.update('dtdpath',args.pop(0))
        elif arg == '-makedoc':
            conf.update('makedoc',args.pop(0))
        elif arg == '-trace':
            conf.update('trace','on')
        elif arg == '-macroref':
            conf.update('macroref',args.pop(0))
        elif arg == '-error:refs':
            conf.update('error:refs',args.pop(0))
        elif arg == '-macroreftitle':
            conf.update('macroreftitle','"%s"' % args.pop(0))
        elif arg == '-noerroronmissingrefs':
            conf.update('erroronmissingrefs',False)
        #elif arg == '-nodefaultinc':
        #    conf.update('nodefaultinc',args.pop(0))
        else:
            conf.update('infile',arg)

    outputfile = conf['outfile']
    inputfile  = conf['infile']  

    msg('Configuration:')
    msg('+--------------------')
    msg('| Output file:          %s' % outputfile)
    msg('| Input file:           %s' % inputfile)
    msg('| Reference doc file:   %s' % conf['makedoc'])
    msg('| Macro reference file: %s' % conf['macroref'])
    msg('| Show error trace:     %s' % conf['trace'])
    msg('| Include paths:')
    for p in conf['incpath']:
        msg('|\t%s' % p)
    msg('| Conditions:')
    for k,v in conf['define'].items():
        msg('|\t%s = %s' % (k,v))
    msg('+--------------------')


    manager = Nodes.Manager(conds=conf['define'],
                            incpaths=conf['incpath'],
                            maxsectdepth=conf['maxsectiondepth'],
                            dtdpaths=conf['dtdpath'])
    #manager = Nodes.Manager({ 'capi'    : True,
    #                          'pyapi'   : False,
    #                          'dnetapi' : False,
    #                          'javaapi' : False,
    #                          'mexapi'  : False })
    
    time0 = time.time()

    try:
        makedoc         = conf['makedoc']
        macroref        = conf['macroref']
        macrorefsecname = conf['macroreftitle']
        showtrace       = conf['trace'] 
        if makedoc is not None:
            r = []
            r.extend(['<?xml version="1.0" ?>',
                      '<!DOCTYPE section SYSTEM "sdocml.dtd">',
                      '<section id="chapter:tag-reference" class="split:yes">',
                      '  <head>',
                      '     <defines>',
                      '         <def m="tagref" n="1"><e n="ref"><attr n="ref">section:tagref:element:{{0}}</attr><e n="tt"><d>&lt;{{0}}&gt;</d></e></e></def>',
                      '         <def m="tag" n="1"><d>&lt;{{0}}&gt;</d></def>',
                      '         <def m="taga" n="2"><d>&lt;{{0}} {{1}}&gt;</d></def>',
                      '         <def m="emptytag" n="1"><d>&lt;{{0}}/&gt;</d></def>',
                      '         <def m="emptytaga" n="2"><d>&lt;{{0}} {{1}}/&gt;</d></def>',
                      '         <def m="endtag" n="1"><d>&lt;/{{0}}&gt;</d></def>',
                      '     </defines>',
                      '     <title>TexML tag reference</title>',
                      '  </head>',
                      '  Reference of all tags allowed in the TexML format.'])

            keys = Nodes.globalNodeDict.keys()
            keys.sort()
            d = {}
            d.update(Nodes.globalNodeDict)
            d['section'] = Nodes._SectionNode
            d['sdocml:conditional'] = Nodes.SDocMLConditionalNode

            for k,n in d.items():
                if inspect.isclass(n) and (issubclass(n,Nodes.GenericNode)):
                    del d[k]
 

            backrefs = {}
            for k,n in d.items():
                ci = [ o.group(1) for o in re.finditer(r'<([a-z]+)>',n.contIter) ]
                for v in ci:
                    if not backrefs.has_key(v): backrefs[v] = []
                    backrefs[v].append(k)
            for v in backrefs.values():
                v.sort()

            itemkeys = d.keys()
            itemkeys.sort()
            for k in itemkeys:
                n = d[k]
                if True:
                    r.append('<section id="section:tagref:element:%s">' % n.nodeName)
                    r.append('  <head><title>Element: <tt>&lt;%s&gt;</tt></title></head>' % n.nodeName) 
                    if n.comment is not None:
                        r.append(n.comment)
                    r.append('  <dlist>')
                    if n.acceptAttrs:
                        r.append('    <dt>Attributes:</dt>')
                        r.append('    <dd><dlist>')
                        attrkeys = n.acceptAttrs.keys()
                        attrkeys.sort()
                        for attrname in attrkeys:
                            attr = n.acceptAttrs[attrname]
                            r.append('<dt>%s</dt>' % attrname)
                            if attr.descr is not None:
                                r.append('<dd>%s</dd>' % attr.descr)

                        r.append('    </dlist></dd>')
                    r.append('    <dt>Content mode:</dt>')
                    if   n.macroMode == Nodes.MacroMode.Invalid:
                        r.append('<dd>Text and macros are not allowed.</dd>')
                    elif n.macroMode == Nodes.MacroMode.NoExpand:
                        r.append('<dd>Macro-expansion is not performed on text.</dd>')
                    elif n.macroMode == Nodes.MacroMode.Text:
                        r.append('<dd>Text mode macro-expansion is performed on the content.</dd>')
                    elif n.macroMode == Nodes.MacroMode.Math:
                        r.append('<dd>Math mode macro-expansion is performed in the content.</dd>')
                    elif n.macroMode == Nodes.MacroMode.Inherit:
                        r.append('<dd>The macro expansion mode is inherited from the parent.</dd>')
                    elif n.macroMode == Nodes.MacroMode.SimpleMath:
                        r.append('<dd>Simple math macros are expanded.</dd>')
                    else:
                        print n,n.macroMode

                    if backrefs.has_key(k):
                        r.append('  <dt>Element appears in:</dt>')
                        r.append('  <dd>%s</dd>' % ', '.join([ '<ref ref="section:tagref:element:%s">%s</ref>' % (name,name) for name in backrefs[k]]))

                    r.append('    <dt>Content syntax:</dt>')
                    if n.contIter.strip():                
                        syntax = []
                        for o in re.finditer(r'([^<]+)|<([a-z]*)>',n.contIter.strip()):
                            if o.group(1):
                                syntax.append(o.group(1))
                            else:
                                elm = o.group(2)
                                syntax.append('&lt;<ref ref="section:tagref:element:%s">%s</ref>&gt;' % (elm,elm))
                    else:
                        syntax = [ 'EMPTY' ]

                    r.append('    <dd><tt>%s</tt></dd>' % ''.join(syntax))

                    for desc,e in n.examples:
                        r.append('    <dt>Example:</dt>\n')
                        r.append('    <dd>%s\n<pre>' % desc)
                        r.append(escape(e))
                        r.append('</pre> </dd>')
                        

            

                    r.append('  </dlist>')
                    r.append('</section>')
            r.append('</section>')
            P.setEntityResolver(manager.getEntityResolver())
            P.setDTDHandler(dtdhandler())
            msg('Writing MoTeX reference to "%s"' % makedoc)
            
            try:
                os.makedirs(os.path.dirname(makedoc))
            except OSError:
                pass
            
            outf = open(makedoc,'wt')

            outf.write('\n'.join(r))

            outf.close()


        assert inputfile
        if inputfile is not None:
            docRoot = Nodes.DocumentRoot(manager,None,None,Nodes.globalNodeDict,Pos('<root>',0)) 
            h = AlternativeSAXHandler(inputfile,docRoot,manager) 
            P.setContentHandler(h)
            P.setEntityResolver(manager.getEntityResolver())
            
            msg('Parse %s' % inputfile)
            P.parse(sys.argv[1])
            time1 = time.time()
            msg('Parse and expand: %.1f sec.' % (time1-time0))
            time0 = time1


            msg('Convert to XML')
            doc = docRoot.toXMLLite()

            if macroref is not None:
                try:
                    os.makedirs(os.path.dirname(macroref))
                except OSError:
                    pass
                makemacroref(macroref,docRoot,macrorefsecname) 
                
            if not Nodes.ERROR_OCCURRED:
                if outputfile  is not None:
                    try:
                        os.makedirs(os.path.dirname(outputfile))
                    except OSError:
                        pass
                    f = open(outputfile,'w')
                    f.write('<?xml version="1.0" encoding="utf-8" ?>\n')
                    f.write('<!DOCTYPE sdocmlx>\n')
                    msg('Write output file')
                    # check tree
                    if False:
                        # debugging: Verify that all nodes are unicode.
                        stack = [doc]
                        while stack:
                            n = stack.pop()
                            stack.extend(n.childNodes)
                            if n.nodeType == n.TEXT_NODE:
                                if not isinstance(n.data,basestring):
                                    print "parent =",n.parentNode.nodeName
                                    print "data =",repr(n.data)
                                    assert isinstance(n.data, unicode)
                            elif n.nodeType == n.ELEMENT_NODE:
                                for i in range(n.attributes.length):
                                    a = n.attributes.item(i)
                                    if not isinstance(a.value,basestring):
                                        print "node =",n.nodeName
                                        print "attr %s = %s" % (a.name,a.value)
                                        assert isinstance(a.value,basestring) 

                    #f.write(unescape(doc.toxml('utf-8')) )
                    msg('Reparsing document')
                    doc = docRoot.toXMLLite()
                    doc = doc.toxml('utf-8')
                    doc = unescape(doc)
                    print doc
                    tmpmanager = Nodes.Manager(conds=conf['define'],
                                            incpaths=conf['incpath'],
                                            maxsectdepth=conf['maxsectiondepth'],
                                            dtdpaths=conf['dtdpath'])
                    docRoot = Nodes.MetaDocumentRoot(tmpmanager,None,None,Nodes.metaNodeDict,Pos('<root>',0))
                    pars = ReParsingSAXHandler(Nodes.metaNodeDict,tmpmanager,docRoot)
                    xml.sax.parseString(doc,pars)
                    doc = docRoot.toXML()
                    f.write(doc.toxml('utf-8'))
                    f.close()
                    
                    time1 = time.time()
                    msg('Write output file: %.1f sec.' % (time1-time0))
                    time0 = time1
            
                if conf['erroronmissingrefs']:
                  msg('Checking cross-references')
                  errs = []
                  errs.extend(manager.checkIdRefs())
                  if conf['error:refs'] and errs:
                      msg('FAILED: Missing references.')
                      sys.exit(1)
            else:
                msg('Errors were encountered.')
                sys.exit(1)

        msg('Fini!')
    except MotexException,e:
        if showtrace:
            import traceback
            traceback.print_exc()
        print e
        sys.exit(1)        

