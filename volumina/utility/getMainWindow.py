from PyQt4.QtGui import QApplication, QWidget, QMainWindow

def getMainWindow():
    """
    Attempt to return the main window for the app.
    Since any QWidget could be the main window, we have to use some heuristics:
    - If there's just one top-level widget, bingo.
    - If one of the top-level widgets happens to be a QMainWindow, use that.
    - If not, select the largets top-level widget
    """
    top_level_widgets = list(QApplication.instance().topLevelWidgets())
    
    # If there's just one, return it.
    if len(top_level_widgets) == 1:
        return top_level_widgets[0]
    
    # If there's more than one, check for a QMainWindow
    for widget in top_level_widgets:
        if isinstance(widget, QMainWindow):
            return widget
    
    # Otherwise, return the biggest one
    top_level_widgets = filter( lambda w: isinstance(w, QWidget), top_level_widgets )
    if len(top_level_widgets) == 0:
        return None

    biggest_size = top_level_widgets[0].size()
    biggest_widget = top_level_widgets[0]
    for widget in top_level_widgets[1:]:
        if widget.size() > biggest_size:
            biggest_size = widget.size()
            biggest_widget = widget

    return biggest_widget
