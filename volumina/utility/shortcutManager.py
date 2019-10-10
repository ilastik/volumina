from __future__ import print_function
import collections
from functools import partial
import logging
from future.utils import with_metaclass

logger = logging.getLogger(__name__)

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QShortcut
from PyQt5.QtGui import QKeySequence
from volumina.utility import Singleton, preferences, getMainWindow


class ShortcutManager(with_metaclass(Singleton, object)):
    """
    A singleton class that serves as a registry for all keyboard shortcuts in the app.
    All shortcuts should be configured using this class, not using the plain Qt shortcut API.
    This class handles details of directing a shortcut trigger to the intended target,
    even if the normal Qt shortcut API would get confused about whether or not the shortcut
    is active based on the current 'context'.

    See __init__ for implementation details.
    """

    # Each shortcut target is registered using this ActionInfo class.
    #
    # group (str): A user-friendly category name that this shortcut belongs to.
    # name (str): A (non-user-friendly) id for this action
    # description (str): A user-friendly description of what this shortcut does
    # target_callable (callable): A Python callable that serves as the target for the shortcut when it is activated
    # context_widget (QWidget): A widget that can be used as a reference for deciding when the shortcut is enabled.
    #                           The shortcut is enabled if this widget is visible and enabled.
    # tooltip_widget (ObjectWithToolTipABC): (optional) Any object that fulfills the ObjectWithToolTipABC (see below).
    #                                        If provided, this object's tooltip will be updated to reflect the current shortcut key sequence.
    #                                        To omit this field, simply provide None
    ActionInfo = collections.namedtuple(
        "ActionInfo", "group name description target_callable context_widget tooltip_widget"
    )
    # for sorting: make sure only to compare comparable member
    ActionInfo.__lt__ = lambda self, other: self[:2] < other[:2]

    def __init__(self):
        """
        Implementation details:

        - All shortcuts are tracked by an id consisting of 2 strings: (group, name). (The description field is used for displaying to the user.)
        - In _keyseq_target_actions, all known shortcut key sequences are mapped to a set of (group, name) pairs, i.e. the possible targets for the key sequence
        - For a given (group, name) id, the associated action(s) can be looked up using _action_infos
        - We register a single, universal shortcut handler with Qt (_handle_shortcut_pressed) for every shortcut key sequence we are aware of.
          In that handler, we determine which target action (if any) should be triggered in response to the shortcut, and trigger it by calling its target_callable.
        """
        self._keyseq_target_actions = {}  # { keyseq : set([(group,name), (group,name), ...]) }
        self._action_infos = collections.OrderedDict()  # { group : { name : set([ActionInfo, ActionInfo, ...]) } }
        self._global_shortcuts = {}  # { keyseq : QShortcut }

        self._preferences_reversemap = self._load_from_preferences()

    def register(self, default_keyseq, action_info):
        """
        Register a new shortcut.

        :param default_keyseq: A string specifying the shortcut key, e.g. 's' or 'Ctrl+P'
        :param action_info: The details of the shortcut's target action.  Must be of type ActionInfo (see above).
        """
        default_keyseq = QKeySequence(default_keyseq)
        group, name, description, target_callable, context_widget, tooltip_widget = action_info
        assert context_widget is not None, "You must provide a context_widget"

        try:
            group_dict = self._action_infos[group]
        except KeyError:
            group_dict = self._action_infos[group] = collections.OrderedDict()

        try:
            action_set = group_dict[name]
        except KeyError:
            action_set = group_dict[name] = set()
        action_set.add(action_info)

        self.change_keyseq(group, name, None, default_keyseq)

        # If there was a preference for this keyseq, update our map to use it.
        try:
            stored_keyseq = self._preferences_reversemap[(group, name)]
            self.change_keyseq(group, name, default_keyseq, stored_keyseq)
        except KeyError:
            pass

    def unregister(self, action_info):
        """
        Remove an action from the managed shortcut targets.
        """
        group, name, description, target_callable, context_widget, tooltip_widget = action_info
        action_set = self._action_infos[group][name]
        action_set.remove(action_info)

    def get_all_action_descriptions(self):
        """
        Return a dict of { group : [(name, description), (name, description),...] }
        Used by the ShortcutManagerDlg
        """
        all_descriptions = collections.OrderedDict()
        for group, group_dict in list(self._action_infos.items()):
            all_descriptions[group] = []
            for name, action_set in list(group_dict.items()):
                if action_set:
                    all_descriptions[group].append((name, next(iter(action_set)).description))
        return all_descriptions

    def get_keyseq_reversemap(self, _d=None):
        """
        Construct the reverse-map of { (group, name) : keyseq }
        :param _d: Internal use only.
        """
        _d = _d or self._keyseq_target_actions
        reversemap = {}
        for keyseq, targets in list(_d.items()):
            for (group, name) in targets:
                reversemap[(group, name)] = keyseq
        return reversemap

    def change_keyseq(self, group, name, old_keyseq, keyseq):
        """
        Customize a shortcut's activating key sequence.
        """
        if old_keyseq:
            old_keyseq = QKeySequence(old_keyseq)
            old_keytext = str(old_keyseq.toString())
            self._keyseq_target_actions[old_keytext].remove((group, name))
        try:
            keyseq = QKeySequence(keyseq)
            keytext = str(keyseq.toString())
            target_name_set = self._keyseq_target_actions[keytext]
        except KeyError:
            target_name_set = self._keyseq_target_actions[keytext] = set()
            self._add_global_shortcut_listener(keyseq)

        target_name_set.add((group, name))
        self._update_tooltip(group, name, keyseq)

    def update_description(self, action_info, new_description):
        """
        Locate the given action_info and replace it with a copy except for the new description text.
        """
        assert (
            action_info in self._action_infos[action_info.group][action_info.name]
        ), "Couldn't locate action_info for {}/{}".format(action_info.group, action_info.name)

        group, name, old_description, target_callable, context_widget, tooltip_widget = action_info
        new_action_info = ShortcutManager.ActionInfo(
            group, name, new_description, target_callable, context_widget, tooltip_widget
        )
        self._action_infos[action_info.group][action_info.name].remove(action_info)
        self._action_infos[action_info.group][action_info.name].add(new_action_info)
        self._update_tooltip(new_action_info.group, new_action_info.name, None)
        return new_action_info

    PreferencesGroup = "Shortcut Preferences v2"

    def store_to_preferences(self):
        """
        Immediately serialize the current set of shortcuts to the preferences file.
        """
        # Auto-save after we're done setting prefs
        # Just save the entire shortcut dict as a single pickle value
        reversemap = self.get_keyseq_reversemap(self._keyseq_target_actions)
        preferences.set(self.PreferencesGroup, "all_shortcuts", reversemap)

    def _load_from_preferences(self):
        """
        Read previously-saved preferences file and return the dict of shortcut keys -> targets (a 'reversemap').
        Called during initialization only.
        """
        return preferences.get(self.PreferencesGroup, "all_shortcuts", default={})

    def _add_global_shortcut_listener(self, keyseq):
        # Create a shortcut for this new key sequence
        # Note: We associate the shortcut with the ENTIRE WINDOW.
        #       We intercept the shortcut and decide which widget to direct it to.
        #       (We don't rely on Qt to do this for us.)
        # Note: This class assumes that all widgets using shortcuts belong to the SAME main window.
        assert keyseq not in self._global_shortcuts
        keyseq = QKeySequence(keyseq)
        keytext = str(keyseq.toString())
        self._global_shortcuts[keytext] = QShortcut(
            QKeySequence(keyseq),
            getMainWindow(),
            member=partial(self._handle_shortcut_pressed, keytext),
            context=Qt.ApplicationShortcut,
        )

    def _handle_shortcut_pressed(self, keytext):
        # Resolve the target callable for this shortcut among the registered candidates
        # - Widget must be visible
        # - If multiple visible candidates, go with the one that has focus.
        # - Ignore deleted widgets
        target_name_set = self._keyseq_target_actions[keytext]
        candidate_actions = []
        for index, (group, name) in enumerate(list(target_name_set)):
            instance_list = self._action_infos[group][name]
            for action_info in list(instance_list):  # copy the list so we can modify it in the loop if necessary
                try:
                    if action_info.context_widget.isVisible() and action_info.context_widget.isEnabled():
                        candidate_actions.append(action_info)
                except RuntimeError as ex:
                    if "has been deleted" in str(ex):
                        # This widget doesn't exist anymore.
                        # Just remove it from our candidate list for next time.
                        instance_list.remove(action_info)
                    else:
                        raise

        if len(candidate_actions) == 0:
            return
        if len(candidate_actions) == 1:
            logger.debug("Executing shortcut target for key sequence: {}".format(keytext))
            candidate_actions[0].target_callable()
            return
        elif len(candidate_actions) > 1:
            best_focus_candidates = []
            for action_info in candidate_actions:
                focused_child_depth = self._focused_widget_ancestor_index(action_info.context_widget)
                if focused_child_depth is not None:
                    best_focus_candidates.append((focused_child_depth, action_info))

            if len(best_focus_candidates) == 0:
                logger.warning(
                    "Ignoring key sequence: {} due to multiple candidate targets, none of which have keyboard focus: {}".format(
                        keytext, [action_info.group + ": " + action_info.name for action_info in candidate_actions]
                    )
                )
            elif len(best_focus_candidates) == 1:
                logger.debug("Executing shortcut target for key sequence: {}".format(keytext))
                best_focus_candidates[0][1].target_callable()
            else:
                best_focus_candidates.sort()
                if best_focus_candidates[0][0] != best_focus_candidates[1][0]:
                    # More than one of our targets owned the focus widget, but one was closer.
                    logger.debug("Executing shortcut target for key sequence: {}".format(keytext))
                    best_focus_candidates[0][1].target_callable()
                else:
                    logger.warning(
                        "Ignoring key sequence: {} due to multiple candidate targets:\n"
                        "{}".format(keytext, best_focus_candidates)
                    )

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
        """
        Return all 'ancestors' (i.e. parent widgets) of the given widget, INCLUDING the widget itself.
        """
        if widget is None:
            return []
        ancestors = [widget]
        parent = widget.parent()
        while parent is not None:
            ancestors.append(parent)
            parent = parent.parent()
        return ancestors

    def _update_tooltip(self, group, name, new_keyseq=None):
        """
        If this shortcut is associated with an object with tooltip text,
            the tooltip text is updated to include the shortcut key.

        For example, a button with shortcut 'b' and tooltip "Make it happen!"
            is modified to have tooltip text "Make it happen! [B]"
        """
        action_set = self._action_infos[group][name]
        for action_info in action_set:
            widget = action_info.tooltip_widget
            if widget is None:
                continue
            try:
                old_text = str(widget.toolTip())
                new_key_text = ""
                if new_keyseq:
                    new_key = str(new_keyseq.toString())
                    if new_key == "":
                        new_key = "<no key>"
                    new_key_text = "[" + new_key + "]"
                elif "[" in old_text and "]" in old_text:
                    # No keyseq provided (it didn't change, so just extract the old keyseq)
                    start = old_text.find("[")
                    stop = old_text.find("]")
                    new_key_text = old_text[start : stop + 1]

                if old_text == "":
                    old_text = action_info.description

                if "[" not in old_text:
                    new_text = old_text + " " + new_key_text
                else:
                    keyhelp_start = old_text.find("[")
                    new_text = old_text[:keyhelp_start] + new_key_text

                widget.setToolTip(new_text)
            except RuntimeError as ex:
                # Simply ignore 'XXX has been deleted' errors
                if "has been deleted" in str(ex):
                    pass
                else:
                    raise


def _has_attribute(cls, attr):
    return any(attr in B.__dict__ for B in cls.__mro__)


def _has_attributes(cls, attrs):
    return all(_has_attribute(cls, a) for a in attrs)


import abc


class ObjectWithToolTipABC(with_metaclass(abc.ABCMeta, object)):
    """
    Defines an ABC for objects that have toolTip() and setToolTip() members.
    Note: All QWidgets already implement this ABC.

    When a shortcut is registered with the shortcut manager, clients can (optionally)
    provide an object that updates the tooltip text for the shortcut.
    That object must adhere to this interface.
    """

    @abc.abstractmethod
    def toolTip(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def setToolTip(self, tip):
        raise NotImplementedError()

    @classmethod
    def __subclasshook__(cls, C):
        if cls is ObjectWithToolTipABC:
            return _has_attributes(C, ["toolTip", "setToolTip"])
        return NotImplemented


if __name__ == "__main__":
    from PyQt5.QtCore import Qt, QEvent, QTimer
    from PyQt5.QtWidgets import QApplication, QWidget, QLabel
    from PyQt5.QtGui import QKeyEvent

    app = QApplication([])

    widget = QWidget()
    label = QLabel("<BLANK>", parent=widget)
    widget.show()

    counter = [0]

    def say_hello():
        counter[0] += 1
        print("changing label text ({})".format(counter[0]))
        label.setText("Hello! {}".format(counter[0]))

    mgr = ShortcutManager()
    mgr.register(
        "h", ShortcutManager.ActionInfo("greetings", "say hello", "Say Hello (with gusto)", say_hello, label, label)
    )

    def change_key():
        mgr.change_keyseq("greetings", "say hello", "h", "q")

    QTimer.singleShot(3000, change_key)
    app.exec_()
