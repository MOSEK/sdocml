#!/bin/bash

if [ "$1" == dir ]; then
    RES=build/sdoc
else
    RES=build/sdoc.tar.bz2
fi

if  echo '** building reference sections ***************' && \
    python sdoc/sdoc2xml.py manual/macrorefdoc.xml \
        -makedoc       build/output/tagsref.xml \
        -macroref      build/output/macroref.xml \
        -macroreftitle "Commonapi Macro Reference" \
        -dtdpath       dtd  \
        -dtdpath       dtd/external && \
    echo '** Building XML ******************************' && \
    python sdoc/sdoc2xml.py manual/sdocml.xml \
        -i build/output \
        -o build/output/sdocml-expanded.xml \
        -dtdpath       dtd  \
        -dtdpath       dtd/external \
        -d final=true && \
    echo '** Building HTML *****************************' && \
    python sdoc/e2html.py build/output/sdocml-expanded.xml \
      -config conf/sdoc-html.conf \
      -i . \
      -o $RES \
      -tempdir build/htmltemp
then
    echo > /dev/null
fi


