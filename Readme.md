Volumina - Volume Slicing and Editing Library
=============================================

[![Build Status](https://secure.travis-ci.org/Ilastik/volumina.png)](http://travis-ci.org/Ilastik/volumina)


Developing with Volumina
========================

*In the following we assume an Ubuntu system.*

Virtual Python Environment
--------------------------

Make a new virtualenv for volumina

    $ virtualenv voluminave/

and activate it

    $ source voluminave/bin/activate


Linking to PyQt and Sip 
----------------------- 

Installing PyQt/Sip via pip is currently (May 2012) broken. Therefore
install the development versions of Qt4, Sip, and PyQt4 globally and
link them into the virtual environment: 

     $ cd voluminave/lib/python2.7/site-packages/ 
     $ ln -s /usr/lib/python2.7/dist-packages/PyQt4/
     $ ln -s /usr/lib/python2.7/dist-packages/sip.so
     $ ln -s /usr/lib/python2.7/dist-packages/sipdistutils.py
     $ ln -s /usr/lib/python2.7/dist-packages/sipconfig.py
     $ ln -s /usr/lib/python2.7/dist-packages/sipconfig_nd.py


Building the development requirements
-------------------------------------
Make sure that g++ is installed on your system besides the usual gcc C++/C development toolchain.
Install the dependencies using pip from the volumina repos root dir:

    $ pip install -r requirements/development.txt

