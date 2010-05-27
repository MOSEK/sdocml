#!/bin/bash



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
    python sdoc/e2tex.py \
    build/output/sdocml-expanded.xml \
    -i . \
    -tempdir build/textemp \
    -o build/textemp/sdoc.tex \
    -template tex/template.tex
then
    if [ -z "$1" ]; then
        cd build/textemp &&
        pdflatex sdoc.tex
        cd ../../
    fi
fi

    

