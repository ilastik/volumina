#!/bin/sh

##
## Linking to PyQt4 manually
##
SITE_PACKAGES=$VIRTUAL_ENV/lib/python2.7/site-packages/

if [ ! -d "$SITE_PACKAGES/PyQt4" ]; then
    echo "linking PyQt4 to $SITE_PACKAGES..."
    ln -s /usr/lib/python2.7/dist-packages/PyQt4/ $SITE_PACKAGES
else
    echo "skip linking PyQt4: already exists in site-packages"
fi

linktofile() {
if [ ! -f "$SITE_PACKAGES/$1" ]; then
    echo "linking $1 to $SITE_PACKAGES..."
    ln -s /usr/lib/python2.7/dist-packages/$1 $SITE_PACKAGES
else
    echo "skip linking $1: already exists in site-packages"
fi
}

linktofile sip.so
linktofile sipdistutils.py
linktofile sipconfig.py
linktofile sipconfig_nd.py


##
## two stage install of requirements
##
pip install -r development-stage1.txt
pip install -r development-stage2.txt
