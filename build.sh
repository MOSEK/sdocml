#!/bin/bash

RES=build/sdoc.tar.bz2
PYTHON=python

while [ -n "$1" ]; do
  case "$1" in
    --dir) 
        RES=build/sdoc
        ;;
    --python) 
        PYTHON=$2
        shift
        ;;
  esac
  shift
done

if  echo '** building reference sections ***************' && \
    $PYTHON sdoc/sdoc2xml.py manual/macrorefdoc.xml \
        -makedoc       build/output/tagsref.xml \
        -macroref      build/output/macroref.xml \
        -macroreftitle "Commonapi Macro Reference" \
        -dtdpath       dtd  \
        -dtdpath       dtd/external && \
    echo '** Building XML ******************************' && \
    $PYTHON sdoc/sdoc2xml.py manual/sdocml.xml \
        -i build/output \
        -o build/output/sdocml-expanded.xml \
        -dtdpath       dtd  \
        -dtdpath       dtd/external \
        -d final=true && \
    echo '** Building HTML *****************************' && \
    $PYTHON sdoc/e2html.py build/output/sdocml-expanded.xml \
      -config conf/sdoc-html.conf \
      -i . \
      -o $RES \
      -tempdir build/htmltemp
then
    echo > /dev/null
fi


