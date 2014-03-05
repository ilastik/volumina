import collections
from functools import partial
import logging
logger = logging.getLogger(__name__)

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QApplication, QKeySequence, QShortcut
from volumina.utility import Singleton, PreferencesManager, getMainWindow


class ShortcutManager2(object):
    __metaclass__ = Singleton

    class ActionInfo( collections.namedtuple('ActionInfo', 'group name description target_callable context_widget tooltip_widget') ):
        __slots__ = ()

        def __hash__(self):
            return ( self.group, self.name, self.context_widget ).__hash__()
        
        def __eq__(self, other):
            return ( (self.group == other.group)
                 and (self.name == other.name)
                 and (self.context_widget == other.context_widget) )

    def __init__(self):
        self._action_infos = collections.OrderedDict()    # { group : { name : [ActionInfo, ActionInfo, ...] } }
        self._keyseq_target_actions = {} # keyseq : [(group,name), (group,name), ...]
        self._global_shortcuts = {}  # keyseq : QShortcut

    def register(self, default_keyseq, action_info):
        default_keyseq = QKeySequence(default_keyseq)
        group, name, description, target_callable, context_widget, tooltip_widget = action_info
        assert context_widget is not None, "You must provide a context_widget"
        
        try:
            group_dict = self._action_infos[group]
        except KeyError:
            group_dict = self._action_infos[group] = collections.OrderedDict()
        
        try:
            action_list = group_dict[name]
        except KeyError:
            action_list = group_dict[name] = set()
        action_list.add( action_info )
        
        self.change_keyseq( group, name, None, default_keyseq )
        # TODO: If we have preferences for this action, update the keyseq

    def unregister(self, action_info):
        group, name, description, target_callable, context_widget, tooltip_widget = action_info
        action_list = self._action_infos[group][name]
        action_list.remove(action_info)
    
    def change_keyseq(self, group, name, old_keyseq, keyseq):
        if old_keyseq:
            old_keyseq = QKeySequence(old_keyseq)
            old_keytext = str(old_keyseq.toString())
            self._keyseq_target_actions[old_keytext].remove( (group, name) )        
        try:
            keyseq = QKeySequence(keyseq)
            keytext = str(keyseq.toString())
            target_name_list = self._keyseq_target_actions[keytext]
        except KeyError:
            target_name_list = self._keyseq_target_actions[keytext] = set()
            self._add_global_shortcut_listener( keyseq )
        
        target_name_list.add( (group, name) )
        self._update_tooltip( group, name, keyseq )
    
    def update_description(self, action_info, new_description):
        assert action_info in self._action_infos[action_info.group][action_info.name],\
            "Couldn't locate action_info for {}/{}".format( action_info.group, action_info.name )
        
        group, name, old_description, target_callable, context_widget, tooltip_widget = action_info
        new_action_info = ShortcutManager2.ActionInfo( group, name, new_description, target_callable, context_widget, tooltip_widget )
        self._action_infos[action_info.group][action_info.name].remove( action_info )
        self._action_infos[action_info.group][action_info.name].add( new_action_info )
        self._update_tooltip( new_action_info.group, new_action_info.name, None )
        return new_action_info
    
    def _add_global_shortcut_listener(self, keyseq):
        # Create a shortcut for this new key sequence
        # Note: We associate the shortcut with the ENTIRE WINDOW.
        #       We intercept the shortcut and decide which widget to direct it to.
        #       (We don't rely on Qt to do this for us.)
        # Note: This class assumes that all widgets using shortcuts belong to the SAME main window.
        assert keyseq not in self._global_shortcuts
        keyseq = QKeySequence(keyseq)
        keytext = str(keyseq.toString())
        self._global_shortcuts[keytext] = QShortcut( QKeySequence(keyseq), 
                                                     getMainWindow(), 
                                                     member=partial(self._handle_shortcut_pressed, keytext), 
                                                     context=Qt.ApplicationShortcut )

    def _handle_shortcut_pressed(self, keytext):
        # Resolve the target callable for this shortcut among the registered candidates
        # - Widget must be visible
        # - If multiple visible candidates, go with the one that has focus.
        # - Ignore deleted widgets
        target_name_list = self._keyseq_target_actions[keytext]
        candidate_actions = []
        for index, (group, name) in enumerate(list(target_name_list)):
            instance_list = self._action_infos[group][name]
            for action_info in instance_list:
                try:
                    if action_info.context_widget.isVisible():
                        candidate_actions.append( action_info )
                except RuntimeError as ex:
                    if 'has been deleted' in str(ex):
                        # This widget doesn't exist anymore.  
                        # Just remove it from our candidate list for next time.
                        target_name_list.pop(index)
                    else:
                        raise

        if len(candidate_actions) == 0:
            return
        if len(candidate_actions) == 1:
            logger.debug("Executing shortcut target for key sequence: {}".format( keytext ))
            candidate_actions[0].target_callable()
            return
        elif len( candidate_actions ) > 1:
            best_focus_candidates = []
            for action_info in candidate_actions:
                focused_child_depth = self._focused_widget_ancestor_index(action_info.context_widget)
                if focused_child_depth is not None:
                    best_focus_candidates.append( (focused_child_depth, action_info ) )

            if len(best_focus_candidates) == 0:
                logger.debug("Ignoring key sequence: {} because no targets have focus.".format( keytext ))
            elif len( best_focus_candidates ) == 1:
                logger.debug("Executing shortcut target for key sequence: {}".format( keytext ))
                best_focus_candidates[0][1].target_callable()
            else:
                best_focus_candidates = sorted(best_focus_candidates)
                if best_focus_candidates[0][0] != best_focus_candidates[1][0]:
                    # More than one of our targets owned the focus widget, but one was closer.
                    logger.debug("Executing shortcut target for key sequence: {}".format( keytext ))
                    best_focus_candidates[0][1].target_callable()
                else:
                    logger.debug( "Ignoring key sequence: {} due to multiple candidate targets:\n"
                                  "{}".format( keytext, best_focus_candidates ) )

    def _focused_widget_ancestor_index(self, widget):
        """
        If widget is an ancestor (parent, parent-parent, etc.) of the 
        currently focused widget, return the number of parent steps 
        between widget and the focused widget.  Otherwise, return None.
        """
        focused_widget = QApplication.focusWidget()
        ancestors = self._get_ancestors(focused_widget)
        try:
            return ancestors.index(widget)
        except ValueError:
            return None
        
    def _get_ancestors(self, widget):
        if widget is None:
            return []
        ancestors = [widget]
        parent = widget.parent()
        while parent is not None:
            ancestors.append(parent)
            parent = parent.parent()
        return ancestors

    def storeToPreferences(self):
        assert False, "TODO"
        # Auto-save after we're done setting prefs
        with PreferencesManager() as prefsMgr:
            for group, shortcutDict in self.shortcuts.items():
                groupKeys = {}
                for shortcut, (desc, obj) in shortcutDict.items():
                    groupKeys[desc] = shortcut.key() # QKeySequence is pickle-able
                prefsMgr.set( self.PreferencesGroup, group, groupKeys )

    def _update_tooltip(self, group, name, new_keyseq=None):
        """
        If this shortcut is associated with an object with tooltip text, 
            the tooltip text is updated to include the shortcut key.

        For example, a button with shortcut 'b' and tooltip "Make it happen!"
            is modified to have tooltip text "Make it happen! [B]"
        """
        action_list = self._action_infos[group][name]
        for action_info in action_list:
            widget = action_info.tooltip_widget
            if widget is None:
                continue
            try:
                old_text = str(widget.toolTip())
                if new_keyseq:
                    new_key = str(new_keyseq.toString())
                    if new_key == "":
                        new_key = "<no key>"
                    new_key_text = '[' + new_key + ']'
                else:
                    # No keyseq provided (it didn't change)
                    new_key_text = old_text
                
                if old_text == "":
                    old_text = action_info.description
        
                if '[' not in old_text:
                    new_text = old_text + ' ' + new_key_text
                else:
                    keyhelp_start = old_text.find('[')
                    new_text = old_text[:keyhelp_start] + new_key_text
                
                widget.setToolTip( new_text )
            except RuntimeError as ex:
                # Simply ignore 'XXX has been deleted' errors
                if 'has been deleted' in str(ex):
                    pass
                else:
                    raise

if __name__ == "__main__":
    from PyQt4.QtCore import Qt, QEvent, QTimer
    from PyQt4.QtGui import QApplication, QWidget, QLabel, QKeyEvent
    
    app = QApplication([])
    
    widget = QWidget()
    label = QLabel("<BLANK>", parent=widget)
    widget.show()

    counter = [0]
    def say_hello():
        counter[0] += 1
        print "changing label text ({})".format(counter[0])
        label.setText("Hello! {}".format( counter[0] ))

    mgr = ShortcutManager2()
    mgr.register( "h", ShortcutManager2.ActionInfo("greetings", "say hello", "Say Hello (with gusto)", say_hello, label, label) )

    def change_key():
        mgr.change_keyseq("greetings", "say hello", "h", "q")
    
    QTimer.singleShot(3000, change_key)
    app.exec_()
