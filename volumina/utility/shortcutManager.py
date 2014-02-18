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

import re
import abc
import collections

import sip
from PyQt4.QtCore import QStringList, Qt, QObject
from PyQt4.QtGui import QDialog, QScrollArea, QHBoxLayout, QVBoxLayout, QGroupBox, QGridLayout, \
                        QLabel, QLineEdit, QPushButton, QSpacerItem, QKeySequence, QWidget, QTreeWidget, QTreeWidgetItem, QSizePolicy

from volumina.utility import Singleton, PreferencesManager

def _has_attribute( cls, attr ):
    return any(attr in B.__dict__ for B in cls.__mro__)

def _has_attributes( cls, attrs ):
    return all(_has_attribute(cls, a) for a in attrs)

class ObjectWithToolTipABC(object):
    """
    Defines an ABC for objects that have toolTip() and setToolTip() members.
    Note: All QWidgets already implement this ABC.
    
    When a shortcut is registered with the shortcut manager, clients can (optionally) 
    provide an object that updates the tooltip text for the shortcut.
    That object must adhere to this interface.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def toolTip(self):
        raise NotImplementedError()
    
    @abc.abstractmethod
    def setToolTip(self, tip):
        raise NotImplementedError()
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is ObjectWithToolTipABC:
            return _has_attributes(C, ['toolTip', 'setToolTip'])
        return NotImplemented

class ShortcutManager(object):
    """
    Singleton object.
    Maintains a global list of shortcuts.
    If an object is provided when the shortcut is registered, the object's tooltip is updated to show the shortcut keys.
    """
    __metaclass__ = Singleton
    
    PreferencesGroup = "Keyboard Shortcuts"

    @property
    def shortcuts(self):
        return self._shortcuts

    def __init__(self):
        self._shortcuts = collections.OrderedDict()
        self.shortcutCollisions = set()
    
    def register(self, group, description, shortcut, objectWithToolTip=None):
        """
        Register a shortcut with the shortcut manager.
        
        Note: If the new shortcut uses the same key sequence as a shortcut that 
              already exists, the original shortcut is disabled, and this new 
              shortcut takes it's place.
        
        group - The GUI category of this shortcut
        description - A description of the shortcut action (shows up as default tooltip text)
        shortcut - A QShortcut
        objectWithToolTip - (optional) If provided, used to update the tooltip text with the shortcut keys. (See ABC above)
        """
        assert description is not None
        assert objectWithToolTip is None or isinstance(objectWithToolTip, ObjectWithToolTipABC)

        if not group in self._shortcuts:
            self._shortcuts[group] = collections.OrderedDict()
        
        # If we've got user preferences for this shortcut, apply them now.
        groupKeys = PreferencesManager().get( self.PreferencesGroup, group )
        if groupKeys is not None and description in groupKeys:
            keyseq = groupKeys[description]
            shortcut.setKey( keyseq )
        
        # Purge invalid shortcuts
        self._purgeDeletedShortcuts()
        
        # Before we add this shortcut to our dict, disable any other shortcuts it replaces
        conflicting_shortcuts = self._findExistingShortcuts( shortcut.key().toString() )
        for conflicted in conflicting_shortcuts:
            conflicted.setKey( QKeySequence("") )
            self.updateToolTip( conflicted )
        
        self._shortcuts[group][shortcut] = (description, objectWithToolTip)
        self.updateToolTip( shortcut )
        
    def _purgeDeletedShortcuts(self):
        for group in self._shortcuts.keys():
            for shortcut in self._shortcuts[group]:
                if sip.isdeleted(shortcut) or sip.isdeleted(shortcut.parentWidget()):
                    del self._shortcuts[group][shortcut]

    def _findExistingShortcuts(self, keyseq):
        existing_shortcuts = []
        for group, shortcutDict in self._shortcuts.items():
            for (shortcut, (desc, obj)) in shortcutDict.items():
                if str(shortcut.key().toString()).lower() == str(keyseq).lower():
                    existing_shortcuts.append( shortcut )
        return existing_shortcuts
    
    def unregister(self, shortcut):
        """
        Remove the shortcut from the manager.
        Note that this does NOT disable the shortcut.
        """
        for group in self._shortcuts:
            if shortcut in self._shortcuts[group]:
                del self._shortcuts[group][shortcut]
                break

    def setDescription(self, shortcut, description):
        for group in self._shortcuts:
            if shortcut in self._shortcuts[group]:
                (oldDescription, objectWithToolTip) = self._shortcuts[group][shortcut]
                self._shortcuts[group][shortcut] = (description, objectWithToolTip)
                self.updateToolTip(shortcut)

            # If we've got user preferences for this shortcut, apply now.
            groupKeys = PreferencesManager().get( self.PreferencesGroup, group )
            if groupKeys is not None and description in groupKeys:
                keyseq = groupKeys[description]
                shortcut.setKey( keyseq )

    def updateToolTip(self, shortcut):
        """
        If this shortcut is associated with an object with tooltip text, 
            the tooltip text is updated to include the shortcut key.

        For example, a button with shortcut 'b' and tooltip "Make it happen!"
            is modified to have tooltip text "Make it happen! [B]"
        """
        description = None
        for group in self._shortcuts:
            if shortcut in self._shortcuts[group]:
                (description, objectWithToolTip) = self._shortcuts[group][shortcut]
                break
            
        assert description is not None, "Couldn't find the shortcut you're trying to update."        
        if objectWithToolTip is None:
            return
        if isinstance(objectWithToolTip, QObject) and sip.isdeleted(objectWithToolTip):
            return

        oldText = str(objectWithToolTip.toolTip())
        newKey = str(shortcut.key().toString())
        if newKey == "":
            newKey = "<no key>"
        newKeyText = '[' + newKey + ']'
        
        if oldText == "":
            oldText = description

        if re.search("\[.*\]", oldText) is None:
            newText = oldText + ' ' + newKeyText
        else:
            newText = re.sub("\[.*\]", newKeyText, oldText)
        
        objectWithToolTip.setToolTip( newText )
    
    def storeToPreferences(self):
        # Auto-save after we're done setting prefs
        with PreferencesManager() as prefsMgr:
            for group, shortcutDict in self.shortcuts.items():
                groupKeys = {}
                for shortcut, (desc, obj) in shortcutDict.items():
                    groupKeys[desc] = shortcut.key() # QKeySequence is pickle-able
                prefsMgr.set( self.PreferencesGroup, group, groupKeys )

class ShortcutManagerDlg(QDialog):
    def __init__(self, *args, **kwargs):
        super(ShortcutManagerDlg, self).__init__(*args, **kwargs)
        self.setWindowTitle("Shortcut Preferences")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)

        mgr = ShortcutManager() # Singleton
        mgr._purgeDeletedShortcuts()

        scrollWidget = QWidget(parent=self)
        tempLayout = QVBoxLayout( scrollWidget )
        scrollWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        treeWidget = QTreeWidget(parent=scrollWidget)
        treeWidget.setHeaderLabels( ["Action", "Shortcut"] )
        treeWidget.setSizePolicy( QSizePolicy.Preferred, QSizePolicy.Preferred )
        treeWidget.setColumnWidth(0, 300)
        treeWidget.setColumnWidth(1, 50)

        # Create a LineEdit for each shortcut,
        # and keep track of them in a dict
        shortcutEdits = collections.OrderedDict()
        for group, shortcutDict in mgr.shortcuts.items():
            groupItem = QTreeWidgetItem( treeWidget, QStringList( group ) )
            ListOfActions = set()
            for i, (shortcut, (desc, obj)) in enumerate(shortcutDict.items()):
                if desc in ListOfActions:
                    continue
                edit = QLineEdit(str(shortcut.key().toString()))
                shortcutEdits[shortcut] = edit
                item = QTreeWidgetItem( groupItem, QStringList( desc ) )
                item.setText(0, desc)
                ListOfActions.add(desc)
                treeWidget.setItemWidget( item, 1, edit )

        tempLayout.addWidget( treeWidget )

        # Add ok and cancel buttons
        buttonLayout = QHBoxLayout()
        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect( self.reject )
        okButton = QPushButton("OK")
        okButton.clicked.connect( self.accept )
        okButton.setDefault(True)
        buttonLayout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Expanding))
        buttonLayout.addWidget(cancelButton)
        buttonLayout.addWidget(okButton)
        tempLayout.addLayout(buttonLayout)

        scroll = QScrollArea(parent=self)
        scroll.setWidget(scrollWidget)
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        dlgLayout = QVBoxLayout()
        dlgLayout.addWidget(scroll)
        self.setLayout(dlgLayout)
        
        # Show the window
        result = self.exec_()
        
        # If the user didn't hit "cancel", apply his changes to the manager's shortcuts
        if result == QDialog.Accepted:
            for shortcut, edit in shortcutEdits.items():
                oldKey = str(shortcut.key().toString()).lower()
                newKey = str(edit.text()).lower()
                
                if oldKey != newKey and newKey != "":
                    # Before we add this shortcut to our dict, disable any other shortcuts it replaces
                    conflicting_shortcuts = mgr._findExistingShortcuts( newKey )
                    for conflicted in conflicting_shortcuts:
                        conflicted.setKey( QKeySequence("") )
                        try:
                            shortcutEdits[conflicted].setText( "" )
                        except KeyError:
                            # There might not be an edit for this shortcut if 
                            #  it was skipped as a duplicate (see ListOfActions, above).
                            pass
                    shortcut.setKey( QKeySequence(newKey) )
                
                # Make sure the tooltips get updated.
                mgr.updateToolTip(shortcut)
            mgr.storeToPreferences()
                

if __name__ == "__main__":
    from PyQt4.QtGui import QShortcut, QKeySequence
    from functools import partial

    from PyQt4.QtGui import QApplication, QPushButton, QWidget
    app = QApplication([])

    mainWindow = QWidget()

    def showShortcuts():
        mgrDlg = ShortcutManagerDlg(mainWindow)
        
        for group, shortcutDict in mgr.shortcuts.items():
            print group + ":"
            for i, (shortcut, (desc, obj)) in enumerate(shortcutDict.items()):
                print desc + " : " + str(shortcut.key().toString())

    mainLayout = QVBoxLayout()
    btn = QPushButton("Show shortcuts")
    btn.clicked.connect( showShortcuts )
    mainLayout.addWidget(btn)
    mainWindow.setLayout(mainLayout)
    mainWindow.show()    

    def trigger(name):
        print "Shortcut triggered:",name
    
    def registerShortcuts(mgr):
        scA = QShortcut( QKeySequence("1"), mainWindow, member=partial(trigger, "A") )
        mgr.register( "Group 1",
                      "Shortcut 1A",
                      scA,
                      None )        
    
        scB = QShortcut( QKeySequence("2"), mainWindow, member=partial(trigger, "B") )
        mgr.register( "Group 1",
                      "Shortcut 1B",
                      scB,
                      None )        
    
        scC = QShortcut( QKeySequence("3"), mainWindow, member=partial(trigger, "C") )
        mgr.register( "Group 2",
                      "Shortcut 2C",
                      scC,
                      None )

    mgr = ShortcutManager()
    registerShortcuts(mgr)

    app.exec_()
    
    
    # Simulate a new session by making a new instance of the manager
    ShortcutManager.instance = None # Force the singleton to reset
    mgr2 = ShortcutManager()
    assert id(mgr) != id(mgr2), "Why didn't the singleton reset?"

    registerShortcuts(mgr2)

    # Check to make sure the shortcuts loaded from disc match those from the first "session"
    
    for group, shortcutDict in mgr.shortcuts.items():
        assert group in mgr2.shortcuts

    descriptionToKeys_1 = {}
    for group, shortcutDict in mgr.shortcuts.items():
        for shortcut, (desc, obj) in shortcutDict.items():
            descriptionToKeys_1[desc] = shortcut.key().toString()

    descriptionToKeys_2 = {}
    for group, shortcutDict in mgr2.shortcuts.items():
        for shortcut, (desc, obj) in shortcutDict.items():
            descriptionToKeys_2[desc] = shortcut.key().toString()
    
    assert descriptionToKeys_1 == descriptionToKeys_2
    print descriptionToKeys_1
    print descriptionToKeys_2









