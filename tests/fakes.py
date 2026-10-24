"""Qt ウィジェットの偽物。実際の Qt クラスが持つメソッドだけを持たせる（ダックタイピング検証のため）。"""

from __future__ import annotations


class FakeRect:
    def __init__(self, x=0, y=0, w=100, h=20):
        self._v = (x, y, w, h)

    def x(self): return self._v[0]  # noqa: E704
    def y(self): return self._v[1]  # noqa: E704
    def width(self): return self._v[2]  # noqa: E704
    def height(self): return self._v[3]  # noqa: E704


class _MetaObject:
    def __init__(self, name): self._name = name  # noqa: E704
    def className(self): return self._name  # noqa: E704, N802


class FakeWidget:
    """QWidget 相当。"""

    def __init__(self, object_name="", *, visible=True, enabled=True, children=(), tooltip="", actions=()):
        self._actions = list(actions)
        self._object_name = object_name
        self._visible = visible
        self._enabled = enabled
        self._children = list(children)
        self._tooltip = tooltip
        self._title = ""
        self._modal = False

    def metaObject(self): return _MetaObject(type(self).__name__)  # noqa: E704, N802
    def objectName(self): return self._object_name  # noqa: E704, N802
    def isVisible(self): return self._visible  # noqa: E704, N802
    def isEnabled(self): return self._enabled  # noqa: E704, N802
    def isWidgetType(self): return True  # noqa: E704, N802
    def children(self): return list(self._children)  # noqa: E704
    def actions(self): return list(self._actions)  # noqa: E704
    def geometry(self): return FakeRect()  # noqa: E704
    def toolTip(self): return self._tooltip  # noqa: E704, N802
    def windowTitle(self): return self._title  # noqa: E704, N802
    def isModal(self): return self._modal  # noqa: E704, N802


class FakeAction:
    """QAction 相当。trigger() 呼び出し回数を数える。"""

    def __init__(self, object_name="", text="", *, enabled=True, visible=True, separator=False, menu=None,
                 checkable=False, checked=False):
        self._object_name, self._text = object_name, text
        self._enabled, self._visible, self._separator = enabled, visible, separator
        self._menu, self._checkable, self._checked = menu, checkable, checked
        self.triggered = 0

    def objectName(self): return self._object_name  # noqa: E704, N802
    def text(self): return self._text  # noqa: E704
    def toolTip(self): return self._text  # noqa: E704, N802
    def isEnabled(self): return self._enabled  # noqa: E704, N802
    def isVisible(self): return self._visible  # noqa: E704, N802
    def isSeparator(self): return self._separator  # noqa: E704, N802
    def isCheckable(self): return self._checkable  # noqa: E704, N802
    def isChecked(self): return self._checked  # noqa: E704, N802
    def menu(self): return self._menu  # noqa: E704

    def trigger(self): self.triggered += 1  # noqa: E704


class FakeQObjectNonWidget:
    """children() に混ざる、ウィジェットではない QObject（QTimer 等）。"""

    def isWidgetType(self): return False  # noqa: E704, N802
    def objectName(self): return "timer"  # noqa: E704, N802


class FakeDialog(FakeWidget):
    def __init__(self, object_name="", title="", *, modal=False, **kw):
        super().__init__(object_name, **kw)
        self._title = title
        self._modal = modal


class FakeLabel(FakeWidget):
    def __init__(self, object_name="", text="", **kw):
        super().__init__(object_name, **kw)
        self._text = text

    def text(self): return self._text  # noqa: E704


class FakeButton(FakeWidget):
    def __init__(self, object_name="", text="", *, checkable=False, **kw):
        super().__init__(object_name, **kw)
        self._text = text
        self._checkable = checkable
        self._checked = False
        self.clicks = 0

    def text(self): return self._text  # noqa: E704
    def isCheckable(self): return self._checkable  # noqa: E704, N802
    def isChecked(self): return self._checked  # noqa: E704, N802
    def setChecked(self, v): self._checked = bool(v)  # noqa: E704, N802

    def click(self):
        self.clicks += 1
        if self._checkable:
            self._checked = not self._checked


class FakeCheckBox(FakeButton):
    def __init__(self, object_name="", text="", **kw):
        super().__init__(object_name, text, checkable=True, **kw)


class FakeLineEdit(FakeWidget):
    def __init__(self, object_name="", text="", *, read_only=False, placeholder="", **kw):
        super().__init__(object_name, **kw)
        self._text = text
        self._read_only = read_only
        self._placeholder = placeholder

    def text(self): return self._text  # noqa: E704
    def setText(self, v): self._text = v  # noqa: E704, N802
    def isReadOnly(self): return self._read_only  # noqa: E704, N802
    def setReadOnly(self, v): self._read_only = v  # noqa: E704, N802
    def placeholderText(self): return self._placeholder  # noqa: E704, N802


class FakeFilterLineEdit(FakeLineEdit):
    """QgsFilterLineEdit 相当。QLineEdit なのに setValue(str) も持つ（実機で set_widget が誤拒否した）。"""

    def setValue(self, v): self._text = v  # noqa: E704, N802
    def value(self): return self._text  # noqa: E704


class FakePlainTextEdit(FakeWidget):
    def __init__(self, object_name="", text="", *, read_only=False, **kw):
        super().__init__(object_name, **kw)
        self._text = text
        self._read_only = read_only

    def toPlainText(self): return self._text  # noqa: E704, N802
    def setPlainText(self, v): self._text = v  # noqa: E704, N802
    def isReadOnly(self): return self._read_only  # noqa: E704, N802
    def setReadOnly(self, v): self._read_only = v  # noqa: E704, N802


class FakeComboBox(FakeWidget):
    def __init__(self, object_name="", items=(), *, data=None, **kw):
        super().__init__(object_name, **kw)
        self._items = list(items)
        self._data = list(data) if data is not None else [None] * len(self._items)
        self._index = 0 if self._items else -1

    def count(self): return len(self._items)  # noqa: E704
    def itemText(self, i): return self._items[i]  # noqa: E704, N802
    def currentText(self): return self._items[self._index] if self._index >= 0 else ""  # noqa: E704, N802
    def currentIndex(self): return self._index  # noqa: E704, N802
    def setCurrentIndex(self, i): self._index = i  # noqa: E704, N802

    def findData(self, value):  # noqa: N802
        return self._data.index(value) if value in self._data else -1


class FakeSpinBox(FakeWidget):
    def __init__(self, object_name="", value=0, minimum=0, maximum=100, **kw):
        super().__init__(object_name, **kw)
        self._v, self._min, self._max = value, minimum, maximum

    def text(self): return str(self._v)  # noqa: E704
    def value(self): return self._v  # noqa: E704

    def setValue(self, v):  # noqa: N802
        if not isinstance(v, int):
            raise TypeError("QSpinBox.setValue expects int")
        self._v = max(self._min, min(self._max, v))

    def minimum(self): return self._min  # noqa: E704
    def maximum(self): return self._max  # noqa: E704
    def isReadOnly(self): return False  # noqa: E704, N802
    def setReadOnly(self, v): pass  # noqa: E704, N802


class FakeDoubleSpinBox(FakeSpinBox):
    def decimals(self): return 2  # noqa: E704

    def setValue(self, v):  # noqa: N802
        if not isinstance(v, float):
            raise TypeError("QDoubleSpinBox.setValue expects float")
        self._v = v


class FakeFileWidget(FakeWidget):
    def __init__(self, object_name="", path="", **kw):
        super().__init__(object_name, **kw)
        self._path = path

    def filePath(self): return self._path  # noqa: E704, N802
    def setFilePath(self, v): self._path = v  # noqa: E704, N802


class FakeTabWidget(FakeWidget):
    def __init__(self, object_name="", tabs=(), **kw):
        super().__init__(object_name, **kw)
        self._tabs = list(tabs)
        self._index = 0

    def count(self): return len(self._tabs)  # noqa: E704
    def tabText(self, i): return self._tabs[i]  # noqa: E704, N802
    def currentIndex(self): return self._index  # noqa: E704, N802
    def setCurrentIndex(self, i): self._index = i  # noqa: E704, N802


class FakeGroupBox(FakeWidget):
    def __init__(self, object_name="", title="", **kw):
        super().__init__(object_name, **kw)
        self._title_text = title

    def title(self): return self._title_text  # noqa: E704


class FakePixmap:
    def __init__(self, ok=True): self.ok = ok; self.saved = []  # noqa: E702, E704
    def save(self, path, fmt): self.saved.append((path, fmt)); return self.ok  # noqa: E702, E704
    def width(self): return 640  # noqa: E704
    def height(self): return 480  # noqa: E704


class FakeGrabbable(FakeDialog):
    def __init__(self, *a, pixmap=None, **kw):
        super().__init__(*a, **kw)
        self.pixmap = pixmap or FakePixmap()

    def grab(self): return self.pixmap  # noqa: E704
