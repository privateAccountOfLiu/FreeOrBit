"""设置对话框：左侧树 + 右侧堆叠页（参考 IDE 设置布局）。"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from freeorbit.template.auto_template import parse_rules_text

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
        self._page_struct: Optional[QWidget] = None
        self._breadcrumb_struct: Optional[QLabel] = None
        self._chk_auto_apply: Optional[QCheckBox] = None
        self._chk_auto_rules: Optional[QCheckBox] = None
        self._lbl_rules_hint: Optional[QLabel] = None
        self._rules_edit: Optional[QPlainTextEdit] = None
        self._page_perm: Optional[QWidget] = None
        self._breadcrumb_perm: Optional[QLabel] = None
        self._chk_admin_launch: Optional[QCheckBox] = None
        self._lbl_perm_hint: Optional[QLabel] = None
        self._btn_box: Optional[QDialogButtonBox] = None
        self._build_ui()
        self._apply_retranslate()

    def _build_ui(self) -> None:
        self.setMinimumSize(720, 560)
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

        self._page_struct = QWidget()
        lay_struct = QVBoxLayout(self._page_struct)
        self._breadcrumb_struct = QLabel()
        self._breadcrumb_struct.setWordWrap(True)
        self._breadcrumb_struct.setStyleSheet("color: palette(mid); padding-bottom: 8px;")
        lay_struct.addWidget(self._breadcrumb_struct)
        self._chk_auto_apply = QCheckBox()
        self._chk_auto_apply.setChecked(
            QSettings().value("structure/auto_apply_on_open", True, type=bool)
        )
        lay_struct.addWidget(self._chk_auto_apply)
        self._chk_auto_rules = QCheckBox()
        self._chk_auto_rules.setChecked(
            QSettings().value("structure/auto_rules_enabled", True, type=bool)
        )
        lay_struct.addWidget(self._chk_auto_rules)
        self._lbl_rules_hint = QLabel()
        self._lbl_rules_hint.setWordWrap(True)
        self._lbl_rules_hint.setStyleSheet("color: palette(mid);")
        lay_struct.addWidget(self._lbl_rules_hint)
        self._rules_edit = QPlainTextEdit()
        self._rules_edit.setMinimumHeight(140)
        rf = QFont("Consolas", 10)
        rf.setStyleHint(QFont.StyleHint.Monospace)
        self._rules_edit.setFont(rf)
        _rt = QSettings().value("structure/auto_rules_text", "")
        self._rules_edit.setPlainText(_rt if isinstance(_rt, str) else "")
        self._rules_edit.setPlaceholderText(tr("settings.struct.auto_rules_placeholder"))
        lay_struct.addWidget(self._rules_edit)
        lay_struct.addStretch(1)
        self._stack.addWidget(self._page_struct)

        self._page_perm = QWidget()
        lay_perm = QVBoxLayout(self._page_perm)
        self._breadcrumb_perm = QLabel()
        self._breadcrumb_perm.setWordWrap(True)
        self._breadcrumb_perm.setStyleSheet("color: palette(mid); padding-bottom: 8px;")
        lay_perm.addWidget(self._breadcrumb_perm)
        self._chk_admin_launch = QCheckBox()
        self._chk_admin_launch.setChecked(
            QSettings().value("elevation/request_admin_on_launch", False, type=bool)
        )
        lay_perm.addWidget(self._chk_admin_launch)
        self._lbl_perm_hint = QLabel()
        self._lbl_perm_hint.setWordWrap(True)
        self._lbl_perm_hint.setStyleSheet("color: palette(mid);")
        lay_perm.addWidget(self._lbl_perm_hint)
        lay_perm.addStretch(1)
        self._stack.addWidget(self._page_perm)
        self._apply_perm_platform_state()

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
        self._tree.currentItemChanged.connect(self._on_tree_change)

    def _apply_perm_platform_state(self) -> None:
        """非 Windows 下禁用提权选项。"""
        win = sys.platform == "win32"
        if self._chk_admin_launch is not None:
            self._chk_admin_launch.setEnabled(win)
            if not win:
                self._chk_admin_launch.setChecked(False)

    def _populate_tree(self) -> None:
        assert self._tree is not None
        self._tree.blockSignals(True)
        try:
            self._tree.clear()
            root_item = QTreeWidgetItem([tr("settings.tree.appearance")])
            struct_item = QTreeWidgetItem([tr("settings.tree.structure")])
            struct_item.setData(0, Qt.ItemDataRole.UserRole, 1)
            root_item.addChild(struct_item)
            sys_item = QTreeWidgetItem([tr("settings.tree.system")])
            lang_item = QTreeWidgetItem([tr("settings.tree.language")])
            lang_item.setData(0, Qt.ItemDataRole.UserRole, 0)
            sys_item.addChild(lang_item)
            perm_item = QTreeWidgetItem([tr("settings.tree.elevation")])
            perm_item.setData(0, Qt.ItemDataRole.UserRole, 2)
            sys_item.addChild(perm_item)
            root_item.addChild(sys_item)
            self._tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)
            sys_item.setExpanded(True)
            self._tree.setCurrentItem(lang_item)
        finally:
            self._tree.blockSignals(False)

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
        if self._breadcrumb_struct is not None:
            self._breadcrumb_struct.setText(tr("settings.struct.breadcrumb"))
        if self._chk_auto_apply is not None:
            self._chk_auto_apply.setText(tr("settings.struct.auto_apply"))
        if self._chk_auto_rules is not None:
            self._chk_auto_rules.setText(tr("settings.struct.auto_rules"))
        if self._lbl_rules_hint is not None:
            self._lbl_rules_hint.setText(tr("settings.struct.auto_rules_hint"))
        if self._rules_edit is not None:
            self._rules_edit.setPlaceholderText(tr("settings.struct.auto_rules_placeholder"))
        if self._breadcrumb_perm is not None:
            self._breadcrumb_perm.setText(tr("settings.elevation.breadcrumb"))
        if self._chk_admin_launch is not None:
            self._chk_admin_launch.setText(tr("settings.elevation.admin_launch"))
        if self._lbl_perm_hint is not None:
            if sys.platform == "win32":
                self._lbl_perm_hint.setText(tr("settings.elevation.hint"))
            else:
                self._lbl_perm_hint.setText(tr("settings.elevation.unix_hint"))
        self._apply_perm_platform_state()

    def _save_elevation_settings(self) -> None:
        if self._chk_admin_launch is not None and sys.platform == "win32":
            QSettings().setValue(
                "elevation/request_admin_on_launch",
                self._chk_admin_launch.isChecked(),
            )

    def _validate_structure_rules(self) -> bool:
        if self._rules_edit is None:
            return True
        _, errs = parse_rules_text(self._rules_edit.toPlainText())
        if errs:
            QMessageBox.warning(
                self,
                tr("settings.struct.rules_warn"),
                "\n".join(errs[:24]),
            )
            return False
        return True

    def _save_structure_settings(self) -> None:
        if self._chk_auto_apply is not None:
            QSettings().setValue(
                "structure/auto_apply_on_open",
                self._chk_auto_apply.isChecked(),
            )
        if self._chk_auto_rules is not None:
            QSettings().setValue(
                "structure/auto_rules_enabled",
                self._chk_auto_rules.isChecked(),
            )
        if self._rules_edit is not None:
            QSettings().setValue(
                "structure/auto_rules_text",
                self._rules_edit.toPlainText(),
            )

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
        if not self._validate_structure_rules():
            return
        self._save_structure_settings()
        self._save_elevation_settings()
        self._apply_retranslate()

    def _on_ok(self) -> None:
        self._apply_language_from_ui()
        if not self._validate_structure_rules():
            return
        self._save_structure_settings()
        self._save_elevation_settings()
        self.accept()
