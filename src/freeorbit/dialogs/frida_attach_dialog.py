"""Frida 附加前参数选择对话框（含高级设置）。"""

from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr


class FridaAttachDialog(QDialog):
    """选择 Frida 附加模式、设备、IL2CPP 与高级参数的模态对话框。"""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        default_target: str = "",
        default_serial: str = "",
        serials: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("android.frida_pre_attach_title"))
        self.setModal(True)
        self.setMinimumSize(420, 480)
        self.resize(460, 520)

        # 加载上次保存的参数
        from freeorbit.platform.android_settings import load_frida_params
        saved = load_frida_params()

        lay = QVBoxLayout(self)
        form = QFormLayout()

        # 模式
        self._mode_attach = QRadioButton(tr("android.frida_mode_attach"))
        self._mode_spawn = QRadioButton(tr("android.frida_mode_spawn"))
        self._mode_attach.setChecked(True)
        if saved.get("mode") == "spawn":
            self._mode_spawn.setChecked(True)
            self._mode_attach.setChecked(False)
        mode_row = QWidget()
        mode_lay = QVBoxLayout(mode_row)
        mode_lay.setContentsMargins(0, 0, 0, 0)
        mode_lay.addWidget(self._mode_attach)
        mode_lay.addWidget(self._mode_spawn)
        form.addRow(tr("android.frida_mode_label"), mode_row)

        # 设备
        self._device = QComboBox()
        self._device.setEditable(True)
        self._device.addItem(tr("android.frida_device_usb"), "")
        if serials:
            for s in serials:
                if s:
                    self._device.addItem(s, s)
        if default_serial:
            idx = self._device.findData(default_serial)
            if idx >= 0:
                self._device.setCurrentIndex(idx)
            else:
                self._device.setCurrentText(default_serial)
        form.addRow(tr("android.frida_device_label"), self._device)

        # 目标
        self._target = QLineEdit(default_target or saved.get("target", ""))
        form.addRow(tr("android.frida_target"), self._target)

        # IL2CPP
        self._il2cpp = QCheckBox(tr("android.frida_il2cpp_enable"))
        if saved.get("il2cpp"):
            self._il2cpp.setChecked(True)
        form.addRow(self._il2cpp)

        # 运行参数（仅 spawn 有效）
        self._args = QLineEdit()
        self._args.setPlaceholderText(tr("android.frida_args_ph"))
        self._args.setText(saved.get("spawn_args", ""))
        form.addRow(tr("android.frida_args_label"), self._args)

        # 高级设置
        self._adv_group = QGroupBox(tr("android.frida_advanced"))
        self._adv_group.setCheckable(True)
        self._adv_group.setChecked(False)
        adv_form = QFormLayout(self._adv_group)

        self._realm = QComboBox()
        self._realm.addItem(tr("android.frida_realm_default"), "")
        self._realm.addItem("Native", "native")
        self._realm.addItem("Emulated", "emulated")
        adv_form.addRow(tr("android.frida_realm_label"), self._realm)

        self._persist = QSpinBox()
        self._persist.setRange(0, 3600)
        self._persist.setSpecialValueText(tr("android.frida_persist_default"))
        self._persist.setSuffix(f" {tr('android.frida_persist_suffix')}")
        adv_form.addRow(tr("android.frida_persist_label"), self._persist)

        self._cwd = QLineEdit()
        self._cwd.setPlaceholderText(tr("android.frida_cwd_ph"))
        adv_form.addRow(tr("android.frida_cwd_label"), self._cwd)

        self._env = QPlainTextEdit()
        self._env.setPlaceholderText(tr("android.frida_env_ph"))
        self._env.setMaximumBlockCount(20)
        self._env.setFixedHeight(80)
        adv_form.addRow(tr("android.frida_env_label"), self._env)

        self._stdio = QComboBox()
        self._stdio.addItem(tr("android.frida_stdio_default"), "")
        self._stdio.addItem("inherit", "inherit")
        self._stdio.addItem("pipe", "pipe")
        self._stdio.addItem("null", "null")
        adv_form.addRow(tr("android.frida_stdio_label"), self._stdio)

        self._aux = QPlainTextEdit()
        self._aux.setPlaceholderText(tr("android.frida_aux_ph"))
        self._aux.setMaximumBlockCount(50)
        self._aux.setFixedHeight(80)
        adv_form.addRow(tr("android.frida_aux_label"), self._aux)

        # 从已保存参数恢复高级字段
        if saved.get("realm"):
            idx = self._realm.findData(saved["realm"])
            if idx >= 0:
                self._realm.setCurrentIndex(idx)
        if saved.get("persist", 0) > 0:
            self._persist.setValue(saved["persist"])
        if saved.get("cwd"):
            self._cwd.setText(saved["cwd"])
        if saved.get("env"):
            self._env.setPlainText(saved["env"])
        if saved.get("stdio"):
            idx = self._stdio.findData(saved["stdio"])
            if idx >= 0:
                self._stdio.setCurrentIndex(idx)
        if saved.get("aux"):
            self._aux.setPlainText(saved["aux"])
        # 如果有任何高级字段非默认，展开高级选项
        if any(saved.get(k) for k in ("realm", "cwd", "env", "stdio", "aux")) or saved.get("persist", 0) > 0:
            self._adv_group.setChecked(True)

        form.addRow(self._adv_group)
        lay.addLayout(form)

        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btn_box.accepted.connect(self.accept)
        self._btn_box.rejected.connect(self.reject)
        lay.addWidget(self._btn_box)

        self._mode_attach.toggled.connect(self._update_enabled)
        self._adv_group.toggled.connect(self._update_enabled)
        self._update_enabled()

    def _update_enabled(self) -> None:
        spawn = self._mode_spawn.isChecked()
        self._args.setEnabled(spawn)
        advanced = self._adv_group.isChecked()
        self._realm.setEnabled(advanced)
        self._persist.setEnabled(advanced)
        self._cwd.setEnabled(advanced and spawn)
        self._env.setEnabled(advanced and spawn)
        self._stdio.setEnabled(advanced and spawn)
        self._aux.setEnabled(advanced)

    def attach_mode(self) -> str:
        return "spawn" if self._mode_spawn.isChecked() else "attach"

    def device_id(self) -> str:
        return self._device.currentText().strip()

    def target(self) -> str:
        return self._target.text().strip()

    def il2cpp_enabled(self) -> bool:
        return self._il2cpp.isChecked()

    def spawn_args(self) -> list[str]:
        if not self._mode_spawn.isChecked():
            return []
        raw = self._args.text().strip()
        if not raw:
            return []
        return raw.split()

    def realm(self) -> str | None:
        if not self._adv_group.isChecked():
            return None
        v = self._realm.currentData()
        return v if isinstance(v, str) and v else None

    def persist_timeout(self) -> int | None:
        if not self._adv_group.isChecked():
            return None
        v = self._persist.value()
        return v if v > 0 else None

    def cwd(self) -> str | None:
        if not self._adv_group.isChecked() or not self._mode_spawn.isChecked():
            return None
        v = self._cwd.text().strip()
        return v if v else None

    def env(self) -> dict[str, str] | None:
        if not self._adv_group.isChecked() or not self._mode_spawn.isChecked():
            return None
        raw = self._env.toPlainText().strip()
        if not raw:
            return None
        result: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
        return result if result else None

    def stdio(self) -> str | None:
        if not self._adv_group.isChecked() or not self._mode_spawn.isChecked():
            return None
        v = self._stdio.currentData()
        return v if isinstance(v, str) and v else None

    def aux(self) -> dict | None:
        if not self._adv_group.isChecked():
            return None
        raw = self._aux.toPlainText().strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(tr("android.frida_aux_invalid").format(err=e)) from e
