#!/bin/bash



if  python sdoc/e2tex.py \
    build/output/sdocml-expanded.xml \
    -i . \
    -tempdir build/textemp \
    -o build/textemp/sdoc.tex \
    -template tex/template.tex
then
    cd build/textemp &&
    pdflatex sdoc.tex
    cd ../../
fi

    

