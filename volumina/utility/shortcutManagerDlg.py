from __future__ import print_function
from __future__ import absolute_import
import collections

from PyQt5.QtWidgets import QDialog, QScrollArea, QHBoxLayout, QVBoxLayout, \
                        QLineEdit, QPushButton, QSpacerItem, QWidget, QTreeWidget, QTreeWidgetItem, QSizePolicy

from .shortcutManager import ShortcutManager

class ShortcutManagerDlg(QDialog):
    def __init__(self, *args, **kwargs):
        super(ShortcutManagerDlg, self).__init__(*args, **kwargs)
        self.setWindowTitle("Shortcut Preferences")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)

        mgr = ShortcutManager() # Singleton

        scrollWidget = QWidget(parent=self)
        tempLayout = QVBoxLayout( scrollWidget )
        scrollWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        treeWidget = QTreeWidget(parent=scrollWidget)
        treeWidget.setHeaderLabels( ["Action", "Shortcut"] )
        treeWidget.setSizePolicy( QSizePolicy.Preferred, QSizePolicy.Preferred )
        treeWidget.setColumnWidth(0, 300)
        treeWidget.setColumnWidth(1, 50)

        action_descriptions = mgr.get_all_action_descriptions()
        target_keyseqs = mgr.get_keyseq_reversemap()
        
        # Create a LineEdit for each shortcut,
        # and keep track of them in a dict
        shortcutEdits = collections.OrderedDict()
        for group, targets in list(action_descriptions.items()):
            groupItem = QTreeWidgetItem( treeWidget, [group] )
            for (name, description) in targets:
                edit = QLineEdit( target_keyseqs[(group,name)] )
                shortcutEdits[(group, name)] = edit
                item = QTreeWidgetItem( groupItem, [description] )
                item.setText(0, description)
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

        # Did the user hit 'cancel'?        
        if result != QDialog.Accepted:
            return
        
        for (group, name), edit in list(shortcutEdits.items()):
            oldKey = target_keyseqs[(group, name)]
            newKey = str(edit.text())
            
            if oldKey.lower() != newKey.lower() and newKey != "":
                mgr.change_keyseq(group, name, oldKey, newKey)
        
        mgr.store_to_preferences()
                
if __name__ == "__main__":
    from PyQt5.QtWidgets import QShortcut
    from PyQt5.QtGui import QKeySequence
    from functools import partial

    from PyQt5.QtWidgets import QApplication, QPushButton, QWidget
    app = QApplication([])

    mainWindow = QWidget()

    def showShortcuts():
        mgrDlg = ShortcutManagerDlg(mainWindow)
        for (group, name), keyseq in sorted(mgr.get_keyseq_reversemap().items()):
            print(group + "." + name + " : " + keyseq)

    mainLayout = QVBoxLayout()
    btn = QPushButton("Show shortcuts")
    btn.clicked.connect( showShortcuts )
    mainLayout.addWidget(btn)
    mainWindow.setLayout(mainLayout)
    mainWindow.show()
    mainWindow.raise_()    

    def trigger(name):
        print("Shortcut triggered:",name)
    
    ActionInfo = ShortcutManager.ActionInfo
    def registerShortcuts(mgr):
        mgr.register( "1", ActionInfo( "Group 1",
                                       "Shortcut 1A",
                                       "Shortcut 1A",
                                       partial(trigger, "A"),
                                       mainWindow,
                                       None ) )
    
        mgr.register( "2", ActionInfo( "Group 1",
                                       "Shortcut 1B",
                                       "Shortcut 1B",
                                       partial(trigger, "B"),
                                       mainWindow,
                                       None ) )

        mgr.register( "3", ActionInfo( "Group 2",
                                       "Shortcut 2C",
                                       "Shortcut 2C",
                                       partial(trigger, "C"),
                                       mainWindow,
                                       None ) )

    
    mgr = ShortcutManager()
    registerShortcuts(mgr)

    app.exec_()

    # Simulate a new session by making a new instance of the manager
    ShortcutManager.instance = None # Force the singleton to reset
    mgr2 = ShortcutManager()
    assert id(mgr) != id(mgr2), "Why didn't the singleton reset?"
 
    registerShortcuts(mgr2)
 
    # Check to make sure the shortcuts loaded from disc match those from the first "session"
    #print mgr.get_keyseq_reversemap()
    #print mgr2.get_keyseq_reversemap()
    assert mgr.get_keyseq_reversemap() == mgr2.get_keyseq_reversemap()
