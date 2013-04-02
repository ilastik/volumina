**Volumina** - Volume Slicing and Editing Library
=============================================

[![Build Status](https://travis-ci.org/ilastik/volumina.png?branch=master)](https://travis-ci.org/ilastik/volumina)

[Code coverage](http://ilastik.github.com/volumina/cover/index.html)

Installing
==========
First, test volumina

    $ python setup.py nosetests

and then install:

    $ python setup.py install

Developing with Volumina
========================

*In the following we assume an Ubuntu system.*

After you entered a virtual environment you can automatically execute all the steps documented below by calling

    $ ./install-development-reqs-virtualenv-ubuntu.sh

from the "requirements" directory in the volumina repository. Note, that we use distribute instead of setuptools.
So, create your virtualenvs using `mkvirtualenv --distribute`.

1. Virtual Python Environment
-----------------------------

Make a new virtualenv for volumina

    $ virtualenv --distribute voluminave/

and activate it

    $ source voluminave/bin/activate


2. Linking to PyQt and Sip 
--------------------------

Installing PyQt/Sip via pip is currently (May 2012) broken. Therefore
install the development versions of Qt4, Sip, and PyQt4 globally and
link them into the virtual environment: 

     $ cd voluminave/lib/python2.7/site-packages/ 
     $ ln -s /usr/lib/python2.7/dist-packages/PyQt4/
     $ ln -s /usr/lib/python2.7/dist-packages/sip.so
     $ ln -s /usr/lib/python2.7/dist-packages/sipdistutils.py
     $ ln -s /usr/lib/python2.7/dist-packages/sipconfig.py
     $ ln -s /usr/lib/python2.7/dist-packages/sipconfig_nd.py


3. Building the development requirements
----------------------------------------
Make sure that g++ is installed on your system besides the usual gcc C++/C development toolchain. qimage2ndarray depends on numpy without requiring the dependency (as of June 2012). Therefore we need to install our requirements in a two stage procedure:

    $ pip install -r requirements/development-stage1.txt
    $ pip install -r requirements/development-stage2.txt

