Introduction
============

Building a document involves two steps:
* Compile everything into one XML file (excluding images etc.)
* Compile that XML file into the end-format (e.g. HTML or TeX)
The Python script
```
sdocml2xml.py
```
is used to perform the first step, and 
```
e2html.py
```
can convert the XML to multiple HTML files (written to a zip file).
and
```
 e2tex.py
```
can convert the XML to multiple HTML files (written to a zip file) and into a .TeX file that can be compiled with pdfLaTeX.


A ``bash`` script in included that builds the SDocML HTML manual - simply run
```
sh build.sh
```
Similarly,
```
sh build-pdf.sh
```
will build the PDF documentation.

Script: ``sdoc2xml.py``
-----------------------
Options for the script can be passed via the command line or via options files. Following options are available:

| *Command line arg*       | *Option file entry*         | *Description* |
|--------------------------|-----------------------------|---------------|
| `-o filename`            | `outfile : filename`        | Define the output file |
| `-config filename`       | N/A                         | Use a configuration file |
| `-d key=value`           | `define : key=value`        | Define a condition key; value is either "true" or "false" |
| `-dtdpath path`          | `dtdpath : path`            | Tells the parser to look here for he DTDs; multiple path entries are allowed.<br> If  none is defined, the parser will look in the path listed in the DOCTYPE tag of the document. |
| `-i`                     | `incpath : path`            | Add an search path. Tell the parser to look here for included sections and defines. |
| `-macroref`              | `macroref : filename`       | Generate a section file with a reference of all macros defined at the top-level section f the document.|
| `-makedoc filename`      | `makedoc : filename`        | Generate a section file with a reference of all tags. |
| `-macroreftitle TITLE`   | `macroreftitle : "TITLE"`   | Define the title used in the macro reference section |

Note that when specifying relative paths 
* on the command line, they are relative to the current directory,
* in a configuration file, they are relative to the path of the configuration file. 

Translation
-----------
The `sdoc2xml.py` script performs the following tasks:

* Read all external sections and collect them into one document tree.
* Expand macros and validate the resulting XML.
* Split text sections into paragraphs. 
* Verify that all internal references (links, references and cites) can be resolved.

The output document is pure XML (DTD validatable). It may contain external references to images and files (specifically, files included in pre-formatted elements) - these are not resolved in the expansion process.

Script: e2html.py
-----------------
This script converts an XML file as produced by ``sdocml2tex.py`` to HTML, copies dependencies (images and pre-formatted input files) and generates PNG images from the math tags.

The script assumes that following tools are available:
* pdflatex (used to generate a PDF document with one page per equation).
* ghostscript (used to convert the PDF document to individual PNGs).

Following options are recognized:

| *Command line arg*  | *Option file entry*   | *Description* | Note  |
|---------------------|-----------------------|---------------|-------|
| `-o filename`       | `outfile:filename`    | Output .zip file                                                          | Deprecated |
| `-style filename`   | `stylesheet:filename` | Include stylesheet in all HTML pages (multiple stylesheets are allowed).  | Deprecated |
| `-js filename`      | `javascript:filename` | Include javascript file in all HTML pages (multile file are allowed).     | Deprecated |
| `-config filename`  | N/A                   | Use options file. |
| `-i path`           | `incpath:filename`    | Add a search path for external files. |
| `-docdir dirname`   | `docdir:dirname`      |  Use `dirname` as root directory for the manual:<br> In the zip-file everything will be placed under the directory `/dirname`. |
| `-appicon filename  | `appicon:filename`    | Use this file as favicon.                     | Deprecated |
| `-icon key=filename | `icon:key=filename    | Defines which files to use for different icons. |
| N/A                 | `template:filename`   | Specifies an HTML template to use |
| `-tempdir dirname`  | `tempdir:filename`    | Defines a directory where all temporary files are placed. |
| `-gsbin name`       | `gsbin:name`          | Name of the GhostScript binary. |
| `-pdftexbin name`   | `pdflatex:name`       | Name of the pdfLaTeX binary. |

The deprecated entries should be written directly on the HTML template instead.

Currently following icon keys are used:

| *key*                  | *Description* |
|------------------------|--------------- |
| prev                   | Link button for previous document node. |
| next                   | Link button for next document node. |
| up                     | Link button for parent document node. |
| content                | Link button for top-level table-of-contents. |
| index                  | Link button for index. |
| passive                | Unused button. |
| error                  | Default image when the one wanted wasn't defined. |
| prev-passive           | Dead end button for previous node. |
| next-passive           | Dead end button for next node. |
| up-passive             | Dead end button for parent node. |
| content-expand-button  | Button for non-empty contents sub-tree in the sidebar |
| content-noexpand-button| Button for empty contents sub-tree in the sidebar |

Script: ``e2tex.py``
--------------------
This script converts an XML file as produced by `sdocml2tex.py` to TeX, which can in turn be converted to PDF using pdfLaTeX.

Following options are recognized:

| *Command line arg*       | *Option file entry* | *Description* | 
|--------------------------|---------------------|---------------|
| `-o filename`            | `outfile : filename`     | Output .zip file | 
| `-config filename`       | N/A | Use options file.  |
| `-i path`                | `incpath : filename`     | Add a search path for external files. |
| `-tempdir dirname`       | `tempdir : filename`     | Defines a directory where all temporary files are placed. |
| `-titlepagebg filename`  | `titlepagebg : filename` | A PDF file used for background on the title page |
| `-pagebg filename`       | `pagebg : filename`      | A PDF file used for background on all non-title pages.|
