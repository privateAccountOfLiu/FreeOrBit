"""设置对话框：左侧树 + 右侧堆叠页（参考 IDE 设置布局）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import _LANG_EN, _LANG_ZH, current_language, set_language, tr

if TYPE_CHECKING:
    pass


class SettingsDialog(QDialog):
    """语言等选项；确定/取消/应用。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        on_apply_lang: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._on_apply_lang = on_apply_lang
        self._lang_combo: Optional[QComboBox] = None
        self._breadcrumb: Optional[QLabel] = None
        self._tree: Optional[QTreeWidget] = None
        self._stack: Optional[QStackedWidget] = None
        self._page_lang: Optional[QWidget] = None
        self._btn_box: Optional[QDialogButtonBox] = None
        self._build_ui()
        self._apply_retranslate()

    def _build_ui(self) -> None:
        self.setMinimumSize(640, 420)
        root = QVBoxLayout(self)

        body = QHBoxLayout()
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumWidth(200)
        self._tree.setMaximumWidth(280)

        self._stack = QStackedWidget()
        self._page_lang = QWidget()
        fl = QFormLayout(self._page_lang)
        self._breadcrumb = QLabel()
        self._breadcrumb.setWordWrap(True)
        self._breadcrumb.setStyleSheet("color: palette(mid); padding-bottom: 8px;")
        fl.addRow(self._breadcrumb)
        self._lang_combo = QComboBox()
        self._lang_combo.addItem(tr("settings.lang.zh"), _LANG_ZH)
        self._lang_combo.addItem(tr("settings.lang.en"), _LANG_EN)
        ix = self._lang_combo.findData(current_language())
        if ix >= 0:
            self._lang_combo.setCurrentIndex(ix)
        self._lang_field_label = QLabel()
        fl.addRow(self._lang_field_label, self._lang_combo)
        self._stack.addWidget(self._page_lang)

        body.addWidget(self._tree)
        body.addWidget(self._stack, 1)

        root.addLayout(body)

        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self._btn_box.accepted.connect(self._on_ok)
        self._btn_box.rejected.connect(self.reject)
        apply_btn = self._btn_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn is not None:
            apply_btn.clicked.connect(self._on_apply_clicked)
        root.addWidget(self._btn_box)

        self._populate_tree()

    def _populate_tree(self) -> None:
        assert self._tree is not None
        try:
            self._tree.currentItemChanged.disconnect()
        except TypeError:
            pass
        self._tree.clear()
        root_item = QTreeWidgetItem([tr("settings.tree.appearance")])
        sys_item = QTreeWidgetItem([tr("settings.tree.system")])
        lang_item = QTreeWidgetItem([tr("settings.tree.language")])
        lang_item.setData(0, Qt.ItemDataRole.UserRole, 0)
        sys_item.addChild(lang_item)
        root_item.addChild(sys_item)
        self._tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        sys_item.setExpanded(True)
        self._tree.setCurrentItem(lang_item)
        self._tree.currentItemChanged.connect(self._on_tree_change)

    def _on_tree_change(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is None or self._stack is None:
            return
        idx = current.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(idx, int) and idx >= 0:
            self._stack.setCurrentIndex(idx)

    def _apply_retranslate(self) -> None:
        self.setWindowTitle(tr("settings.title"))
        if self._breadcrumb is not None:
            self._breadcrumb.setText(tr("settings.breadcrumb"))
        if self._btn_box is not None:
            ok = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
            cancel = self._btn_box.button(QDialogButtonBox.StandardButton.Cancel)
            apply = self._btn_box.button(QDialogButtonBox.StandardButton.Apply)
            if ok is not None:
                ok.setText(tr("btn.ok"))
            if cancel is not None:
                cancel.setText(tr("btn.cancel"))
            if apply is not None:
                apply.setText(tr("btn.apply"))
        self._populate_tree()
        if self._lang_combo is not None:
            cur = self._lang_combo.currentData()
            self._lang_combo.blockSignals(True)
            self._lang_combo.clear()
            self._lang_combo.addItem(tr("settings.lang.zh"), _LANG_ZH)
            self._lang_combo.addItem(tr("settings.lang.en"), _LANG_EN)
            ix = self._lang_combo.findData(cur if cur else current_language())
            self._lang_combo.setCurrentIndex(max(0, ix))
            self._lang_combo.blockSignals(False)
        if hasattr(self, "_lang_field_label"):
            self._lang_field_label.setText(tr("settings.lang.label"))

    def _apply_language_from_ui(self) -> None:
        if self._lang_combo is None:
            return
        lang = self._lang_combo.currentData()
        if lang in (_LANG_ZH, _LANG_EN):
            set_language(str(lang))
            if self._on_apply_lang:
                self._on_apply_lang()

    def _on_apply_clicked(self) -> None:
        self._apply_language_from_ui()
        self._apply_retranslate()

    def _on_ok(self) -> None:
        self._apply_language_from_ui()
        self.accept()
