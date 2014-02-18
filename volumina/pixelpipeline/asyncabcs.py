# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers

from abc import ABCMeta, abstractmethod, abstractproperty
from PyQt4.QtCore import pyqtSignal

def _has_attribute( cls, attr ):
    return True if any(attr in B.__dict__ for B in cls.__mro__) else False

def _has_attributes( cls, attrs ):
    return True if all(_has_attribute(cls, a) for a in attrs) else False

    

#*******************************************************************************
# R e q u e s t A B C                                                          *
#*******************************************************************************

class RequestABC:
    __metaclass__ = ABCMeta

    @abstractmethod
    def wait( self ):
        ''' doc '''

    @abstractmethod
    def notify( self, callback, **kwargs ):
        pass

    @classmethod
    def __subclasshook__(cls, C):
        if cls is RequestABC:
            return True if _has_attributes(C, ['wait', 'notify']) else False
        return NotImplemented



#*******************************************************************************
# S o u r c e A B C                                                            *
#*******************************************************************************

class SourceABC:
    __metaclass__ = ABCMeta
    
    numberOfChannelsChanged = pyqtSignal(int)

    @abstractproperty
    def numberOfChannels(self):
        raise NotImplementedError

    @abstractmethod
    def request( self, slicing ):
        pass

    @abstractmethod
    def setDirty( self, slicing ):
        pass

    @classmethod
    def __subclasshook__(cls, C):
        if cls is SourceABC:
            return True if _has_attributes(C, ['request', 'setDirty']) else False
        return NotImplemented

    @abstractmethod
    def __eq__( self, other ):
        raise NotImplementedError

    @abstractmethod
    def __ne__( self, other ):
        raise NotImplementedError
    
    @abstractmethod
    def clean_up(self):
        pass
