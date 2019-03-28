from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow


def getMainWindow() -> QMainWindow:
    """
    Attempt to return the main window for the app.
    There's no guaranteed way to find *the* main window, 
    so we use some heuristics and make a guess:
    - Prefer instances of QMainWindow
    - Prefer the biggest window without a parent.
    """
    top_level_widgets = list(QApplication.instance().topLevelWidgets())

    # Real widgets only.
    top_level_widgets = [w for w in top_level_widgets if isinstance(w, QWidget)]

    if not top_level_widgets:
        # Couldn't find any
        raise Exception("Failed to determine main widget")

    # We prefer QMainWindow instances.  If we have any, drop all the other widgets.
    main_windows = [w for w in top_level_widgets if isinstance(w, QMainWindow)]
    if main_windows:
        top_level_widgets = main_windows

    # Now return the biggest widget we found.
    sizes = [w.width() * w.height() for w in top_level_widgets]

    max_area = 0
    main_widget = None

    for w in top_level_widgets:
        area = w.width() * w.height()
        if area > max_area:
            max_area = area
            main_widget = w

    return main_widget
