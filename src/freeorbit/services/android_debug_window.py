"""Android 调试子模块：独立窗口（ADB / Frida / 内存 dump）。

Frida 为可选依赖（`pip install frida`）；设备侧需匹配版本的 frida-server。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from freeorbit.dialogs.frida_android_risk_dialog import FridaAndroidInstallRiskDialog
from freeorbit.i18n import tr
from freeorbit.platform import android_adb
from freeorbit.platform import android_frida_install as frida_inst
from freeorbit.platform import android_settings as android_st

# 包名 / 应用进程表最多展示行数（超出部分提示）
_MAX_ADB_TABLE_ROWS = 5000
# 设备表与进程表第一列（序列号 / PID）统一宽度，筛选前后不变
_ADB_TABLE_COL0_WIDTH = 140

# 必须在用户脚本之前执行：快照 Frida 原生 Memory / ptr（用户脚本可能在后面改写全局 Memory）
_FRIDA_RPC_GUARD = """
(function () {
  var g = typeof globalThis !== "undefined" ? globalThis : this;
  if (g.__fob_frida) return;
  var mem0 = typeof Memory !== "undefined" ? Memory : null;
  var rb = null;
  try {
    if (mem0 && typeof mem0.readByteArray === "function") {
      rb = function (p, n) { return mem0.readByteArray(p, n); };
    }
  } catch (e) {}
  g.__fob_frida = {
    ptr: typeof ptr === "function" ? ptr : null,
    fobMemory: mem0,
    readByteArray: rb,
    NativePointer: typeof NativePointer === "function" ? NativePointer : null
  };
})();
"""

# 追加在用户脚本之后：合并 rpc.exports（避免用户整段 rpc.exports = {...} 覆盖内置读内存），
# 并提供 readMemoryBlock 返回 {ok,msg,bytes} 便于区分「不可读」与真实错误。
_FRIDA_RPC_BRIDGE = """
(function () {
  var g = typeof globalThis !== "undefined" ? globalThis : this;
  var F = g.__fob_frida;
  function fobParsePointer(addrStr) {
    if (F && typeof F.ptr === "function") return F.ptr(addrStr);
    if (typeof ptr === "function") return ptr(addrStr);
    if (F && typeof F.NativePointer === "function") return new F.NativePointer(addrStr);
    if (typeof NativePointer === "function") return new NativePointer(addrStr);
    throw new TypeError("ptr/NativePointer unavailable");
  }
  function fobBufferToBytes(buf) {
    var u8 = new Uint8Array(buf);
    var i, n = u8.length, out = [];
    for (i = 0; i < n; i++) out.push(u8[i] & 0xff);
    return out;
  }
  function fobReadMemoryBlock(addrStr, size) {
    var n = size | 0;
    if (n <= 0 || n > 0x100000) {
      return { ok: false, msg: "size out of range (1 .. 0x100000)" };
    }
    // 优先 Memory.readByteArray(ptr, n)；若全局 Memory 被破坏则回退 NativePointer#readByteArray(n)（Frida 文档）
    var readFn = null;
    if (F && typeof F.readByteArray === "function") {
      readFn = F.readByteArray;
    } else if (F && F.fobMemory && typeof F.fobMemory.readByteArray === "function") {
      readFn = function (p, n) { return F.fobMemory.readByteArray(p, n); };
    } else if (typeof Memory !== "undefined" && typeof Memory.readByteArray === "function") {
      readFn = function (p, n) { return Memory.readByteArray(p, n); };
    }
    try {
      var p = fobParsePointer(addrStr);
      var buf = null;
      if (readFn !== null) {
        buf = readFn(p, n);
      } else if (typeof p.readByteArray === "function") {
        buf = p.readByteArray(n);
      } else if (typeof p.readVolatile === "function") {
        buf = p.readVolatile(n);
      } else {
        return { ok: false, msg: "无法读内存：无 Memory.readByteArray 且 NativePointer 无 readByteArray/readVolatile" };
      }
      if (!buf) {
        return { ok: false, msg: "readByteArray null (unmapped or invalid ptr)" };
      }
      return { ok: true, bytes: fobBufferToBytes(buf) };
    } catch (e) {
      return { ok: false, msg: String(e) };
    }
  }
  function fobGetMainExecutableBase() {
    try {
      if (typeof Process !== "undefined" && Process.mainModule && Process.mainModule.base) {
        return Process.mainModule.base.toString();
      }
    } catch (e) {}
    try {
      var m = Process.enumerateModules();
      var i, path;
      for (i = 0; i < m.length; i++) {
        path = m[i].path || "";
        if (path.indexOf("/data/app/") !== -1 && path.indexOf(".so") !== -1) {
          return m[i].base.toString();
        }
      }
      if (m.length > 0) return m[0].base.toString();
    } catch (e) {}
    return "0";
  }
  var x = rpc.exports || {};
  rpc.exports = x;
  x.readMemoryBlock = fobReadMemoryBlock;
  x.readBytes = function (addrStr, size) {
    var r = fobReadMemoryBlock(addrStr, size);
    return r.ok ? r.bytes : [];
  };
  x.getMainExecutableBase = fobGetMainExecutableBase;
})();
"""


def _frida_available() -> bool:
    from freeorbit.platform import frida_loader

    frida_loader.ensure_frida_import_preference()
    try:
        import frida  # noqa: F401

        return True
    except ImportError:
        return False


class _FridaInstallServerThread(QThread):
    """后台下载并推送 frida-server，通过信号输出日志。"""

    log_line = Signal(str)
    finished_err = Signal(str)
    finished_ok = Signal()

    def __init__(
        self,
        serial: Optional[str],
        adb_exe: str,
        device_path: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._serial = serial
        self._adb_exe = adb_exe
        self._device_path = device_path

    def run(self) -> None:
        try:
            frida_inst.install_frida_server_to_device(
                self._serial,
                self._adb_exe,
                device_path=self._device_path,
                log=lambda s: self.log_line.emit(s),
            )
            self.finished_ok.emit()
        except Exception as e:  # noqa: BLE001
            self.finished_err.emit(str(e))


class _CallableThread(QThread):
    """在后台线程执行可调用对象，结果通过信号回到主线程。"""

    finished_ok = Signal(object)
    finished_err = Signal(str)

    def __init__(
        self,
        fn: Callable[[], object],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._fn())
        except Exception as e:  # noqa: BLE001
            self.finished_err.emit(str(e))


class _FridaAttachThread(QThread):
    """在后台线程执行 Frida 枚举设备、附加与脚本加载（避免阻塞 UI）。"""

    attached = Signal(object, object, object)  # session, script, device
    failed = Signal(str)

    def __init__(
        self,
        panel: "AndroidDebugPanel",
        remote_host: Optional[str],
        serial: Optional[str],
        target: str,
        full_js: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._panel = panel
        self._remote_host = remote_host
        self._serial = serial
        self._target = target
        self._full_js = full_js

    def run(self) -> None:
        from freeorbit.platform import frida_loader

        frida_loader.ensure_frida_import_preference()
        import frida

        try:
            dm = frida.get_device_manager()
            if self._remote_host:
                gr = getattr(frida, "get_remote_device", None)
                if callable(gr):
                    dev = gr(self._remote_host)
                else:
                    dev = dm.add_remote_device(self._remote_host)
            else:
                if self._serial:
                    dev = dm.get_device(self._serial, timeout=5)
                else:
                    try:
                        dev = frida.get_usb_device(timeout=5)
                    except Exception:
                        dev = None
                        for d in dm.enumerate_devices():
                            if getattr(d, "id", "") != "local":
                                dev = d
                                break
                        if dev is None:
                            raise RuntimeError(tr("android.frida_no_device"))

            def on_message(message: object, data: Optional[bytes]) -> None:
                # Frida 在独立线程回调，必须通过 Signal 投递到 Qt 主线程再写控件
                self._panel._dispatch_frida_message(message, data)

            # console.log 在 frida.core.Script._on_message 中单独走 _log_handler，
            # 不会进入 on("message")，必须 set_log_handler 才能显示到脚本输出框
            def on_console_log(level: str, text: str) -> None:
                self._panel._dispatch_frida_console_log(level, text)

            if self._target.isdigit():
                session = dev.attach(int(self._target))
            else:
                session = dev.attach(self._target)

            script = session.create_script(self._full_js)
            script.on("message", on_message)
            script.set_log_handler(on_console_log)
            script.load()
            self.attached.emit(session, script, dev)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class AndroidDebugPanel(QWidget):
    """ADB / Frida / 内存 dump 主面板（嵌入于 AndroidDebugWindow）。"""

    # Frida 回调在非主线程，必须通过 Signal 投递后再写 QTextEdit
    _sig_frida_sys_log = Signal(str)
    _sig_frida_script_log = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        open_buffer_tab: Optional[Callable[[str, bytes], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._open_buffer_tab = open_buffer_tab
        self._adb_exe = "adb"
        self._frida_session: Optional[object] = None
        self._frida_script: Optional[object] = None
        self._frida_device: Optional[object] = None
        self._adb_refresh_busy = False
        self._frida_probe_generation = 0
        self._frida_attach_thread: Optional[_FridaAttachThread] = None
        q = Qt.ConnectionType.QueuedConnection
        self._sig_frida_sys_log.connect(self._frida_log, q)
        self._sig_frida_script_log.connect(self._frida_log_script, q)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        self._legal_hint = QLabel(tr("android.hook_legal_hint"))
        self._legal_hint.setWordWrap(True)
        self._legal_hint.setStyleSheet("color: palette(mid);")

        self._tabs = QTabWidget()
        root.addWidget(self._tabs, 1)

        # —— Tab ADB ——
        tab_adb = QWidget()
        lay_adb = QVBoxLayout(tab_adb)
        row_exe = QHBoxLayout()
        row_exe.addWidget(QLabel(tr("android.adb_exe")))
        self._adb_path = QLineEdit("adb")
        row_exe.addWidget(self._adb_path, 1)
        lay_adb.addLayout(row_exe)

        row_dev = QHBoxLayout()
        row_dev.addWidget(QLabel(tr("android.device_serial")))
        self._serial = QComboBox()
        self._serial.setEditable(True)
        self._serial.setMinimumWidth(200)
        row_dev.addWidget(self._serial, 1)
        self._btn_refresh_dev = QPushButton(tr("android.refresh_devices"))
        self._btn_refresh_dev.clicked.connect(self._refresh_devices)
        row_dev.addWidget(self._btn_refresh_dev)
        lay_adb.addLayout(row_dev)

        row_act = QHBoxLayout()
        self._btn_pkgs = QPushButton(tr("android.list_packages"))
        self._btn_pkgs.clicked.connect(self._list_packages)
        self._btn_ps = QPushButton(tr("android.list_ps"))
        self._btn_ps.clicked.connect(self._list_ps)
        row_act.addWidget(self._btn_pkgs)
        row_act.addWidget(self._btn_ps)
        lay_adb.addLayout(row_act)

        row_filt = QHBoxLayout()
        self._lbl_adb_filter = QLabel()
        self._adb_filter_edit = QLineEdit()
        self._adb_filter_edit.setEnabled(False)
        self._adb_filter_edit.setClearButtonEnabled(True)
        self._adb_filter_edit.textChanged.connect(self._apply_adb_filter)
        row_filt.addWidget(self._lbl_adb_filter)
        row_filt.addWidget(self._adb_filter_edit, 1)
        lay_adb.addLayout(row_filt)

        # 包名 / 进程 / 设备列表共用表格；shell 输出单独一页；筛选框在表格上方
        self._adb_stack = QStackedWidget()
        self._adb_table = QTableWidget()
        self._adb_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._adb_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._adb_table.setAlternatingRowColors(True)
        self._adb_table.setMinimumHeight(120)
        self._adb_table.verticalHeader().setVisible(False)
        self._adb_shell_out = QPlainTextEdit()
        self._adb_shell_out.setReadOnly(True)
        self._adb_shell_out.setMinimumHeight(120)
        self._adb_stack.addWidget(self._adb_table)
        self._adb_stack.addWidget(self._adb_shell_out)
        lay_adb.addWidget(self._adb_stack, 1)

        self._adb_table_kind: str = "none"
        self._adb_pkgs_full: Optional[list[str]] = None
        self._adb_ps_full: Optional[list[tuple[int, str]]] = None

        row_sh = QHBoxLayout()
        self._shell_cmd = QLineEdit()
        self._shell_cmd.setPlaceholderText(tr("android.shell_placeholder"))
        row_sh.addWidget(self._shell_cmd, 1)
        self._btn_shell = QPushButton(tr("android.run_shell"))
        self._btn_shell.clicked.connect(self._run_shell)
        row_sh.addWidget(self._btn_shell)
        lay_adb.addLayout(row_sh)

        self._tabs.addTab(tab_adb, tr("android.tab_adb"))

        # —— Tab Frida ——
        tab_frida = QWidget()
        lay_f = QVBoxLayout(tab_frida)
        self._lbl_frida_win = QLabel()
        self._lbl_frida_root = QLabel()
        self._lbl_frida_srv = QLabel()
        for _w in (self._lbl_frida_win, self._lbl_frida_root, self._lbl_frida_srv):
            _w.setWordWrap(True)
            lay_f.addWidget(_w)
        row_frida_env = QHBoxLayout()
        self._btn_refresh_frida_env = QPushButton(tr("android.frida_refresh_env"))
        self._btn_refresh_frida_env.clicked.connect(self._refresh_frida_env_full)
        self._btn_install_frida_android = QPushButton(tr("android.frida_install_android"))
        self._btn_install_frida_android.clicked.connect(self._on_install_frida_android)
        self._btn_run_frida_server = QPushButton(tr("android.frida_run_on_device"))
        self._btn_run_frida_server.setToolTip(tr("android.frida_run_on_device_tip"))
        self._btn_run_frida_server.clicked.connect(self._on_run_frida_server_android)
        row_frida_env.addWidget(self._btn_refresh_frida_env)
        row_frida_env.addWidget(self._btn_install_frida_android)
        row_frida_env.addWidget(self._btn_run_frida_server)
        row_frida_env.addStretch(1)
        lay_f.addLayout(row_frida_env)
        self._frida_install_thread: Optional[_FridaInstallServerThread] = None

        form = QFormLayout()
        self._frida_target = QLineEdit()
        self._frida_target.setPlaceholderText(tr("android.frida_target_ph"))
        form.addRow(tr("android.frida_target"), self._frida_target)
        lay_f.addLayout(form)

        row_f = QHBoxLayout()
        self._btn_attach = QPushButton(tr("android.frida_attach"))
        self._btn_attach.clicked.connect(self._frida_attach)
        self._btn_detach = QPushButton(tr("android.frida_detach"))
        self._btn_detach.clicked.connect(self._frida_detach)
        self._btn_detach.setEnabled(False)
        row_f.addWidget(self._btn_attach)
        row_f.addWidget(self._btn_detach)
        row_f.addStretch(1)
        lay_f.addLayout(row_f)

        split_frida = QSplitter(Qt.Orientation.Vertical)
        self._frida_js = QPlainTextEdit()
        self._frida_js.setPlaceholderText(tr("android.frida_js_placeholder"))
        self._frida_js.setPlainText(
            '// 示例：Java.perform(() => { ... });\nconsole.log("Frida script loaded");\n'
        )
        w_js = QWidget()
        lay_js = QVBoxLayout(w_js)
        lay_js.setContentsMargins(0, 0, 0, 0)
        row_js_head = QHBoxLayout()
        row_js_head.addWidget(QLabel(tr("android.frida_script")))
        row_js_head.addStretch(1)
        self._btn_import_js = QPushButton(tr("android.frida_import_js"))
        self._btn_import_js.clicked.connect(self._import_frida_script_from_file)
        row_js_head.addWidget(self._btn_import_js)
        lay_js.addLayout(row_js_head)
        lay_js.addWidget(self._frida_js, 1)
        split_frida.addWidget(w_js)

        self._out_frida = QPlainTextEdit()
        self._out_frida.setReadOnly(True)
        self._out_frida.setMinimumHeight(100)
        self._out_frida_script = QPlainTextEdit()
        self._out_frida_script.setReadOnly(True)
        self._out_frida_script.setMinimumHeight(100)
        self._lbl_frida_log_title = QLabel()
        self._lbl_frida_script_title = QLabel()
        w_log_l = QWidget()
        lay_log_l = QVBoxLayout(w_log_l)
        lay_log_l.setContentsMargins(0, 0, 0, 0)
        lay_log_l.addWidget(self._lbl_frida_log_title)
        lay_log_l.addWidget(self._out_frida, 1)
        w_log_r = QWidget()
        lay_log_r = QVBoxLayout(w_log_r)
        lay_log_r.setContentsMargins(0, 0, 0, 0)
        row_script_out = QHBoxLayout()
        row_script_out.addWidget(self._lbl_frida_script_title)
        row_script_out.addStretch(1)
        self._btn_export_script_out = QPushButton(tr("android.frida_export_script_output"))
        self._btn_export_script_out.clicked.connect(self._export_frida_script_output_to_file)
        row_script_out.addWidget(self._btn_export_script_out)
        lay_log_r.addLayout(row_script_out)
        lay_log_r.addWidget(self._out_frida_script, 1)
        split_frida_log = QSplitter(Qt.Orientation.Horizontal)
        split_frida_log.addWidget(w_log_l)
        split_frida_log.addWidget(w_log_r)
        split_frida_log.setStretchFactor(0, 1)
        split_frida_log.setStretchFactor(1, 1)
        split_frida_log.setSizes([480, 480])
        split_frida.addWidget(split_frida_log)
        split_frida.setSizes([280, 220])
        lay_f.addWidget(split_frida, 1)

        self._tabs.addTab(tab_frida, tr("android.tab_frida"))

        # —— Tab Dump ——
        tab_dump = QWidget()
        lay_d = QVBoxLayout(tab_dump)
        lay_d.addWidget(QLabel(tr("android.dump_hint")))
        self._chk_dump_rva = QCheckBox()
        self._chk_dump_rva.setChecked(True)
        form_d = QFormLayout()
        form_d.addRow(self._chk_dump_rva)
        self._dump_addr = QLineEdit("0x0")
        form_d.addRow(tr("android.dump_addr"), self._dump_addr)
        self._dump_size = QSpinBox()
        self._dump_size.setRange(1, 16 * 1024 * 1024)
        self._dump_size.setValue(256)
        form_d.addRow(tr("android.dump_size"), self._dump_size)
        lay_d.addLayout(form_d)
        self._btn_dump = QPushButton(tr("android.dump_to_tab"))
        self._btn_dump.clicked.connect(self._dump_memory_to_tab)
        lay_d.addWidget(self._btn_dump)
        lay_d.addStretch(1)
        self._tabs.addTab(tab_dump, tr("android.tab_dump"))

        root.addWidget(self._legal_hint)

        self.retranslate_ui()
        self.sync_from_settings()
        self._refresh_frida_env_full()

    def sync_from_settings(self) -> None:
        """从 QSettings 同步 adb 等到界面（设置对话框保存后也会调用）。"""
        self._adb_path.setText(android_st.adb_path())

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.sync_from_settings()
        self._refresh_frida_env_full()

    def retranslate_ui(self) -> None:
        self._legal_hint.setText(tr("android.hook_legal_hint"))
        self._btn_refresh_dev.setText(tr("android.refresh_devices"))
        self._btn_pkgs.setText(tr("android.list_packages"))
        self._btn_ps.setText(tr("android.list_ps"))
        self._btn_ps.setToolTip(tr("android.list_ps_tooltip"))
        self._shell_cmd.setPlaceholderText(tr("android.shell_placeholder"))
        self._btn_shell.setText(tr("android.run_shell"))
        self._lbl_adb_filter.setText(tr("android.adb_filter_label"))
        self._adb_filter_edit.setPlaceholderText(tr("android.adb_filter_placeholder"))
        self._tabs.setTabText(0, tr("android.tab_adb"))
        self._tabs.setTabText(1, tr("android.tab_frida"))
        self._tabs.setTabText(2, tr("android.tab_dump"))
        self._frida_target.setPlaceholderText(tr("android.frida_target_ph"))
        self._frida_js.setPlaceholderText(tr("android.frida_js_placeholder"))
        self._btn_attach.setText(tr("android.frida_attach"))
        self._btn_detach.setText(tr("android.frida_detach"))
        self._btn_dump.setText(tr("android.dump_to_tab"))
        self._lbl_frida_log_title.setText(tr("android.frida_log"))
        self._lbl_frida_script_title.setText(tr("android.frida_script_output"))
        self._btn_import_js.setText(tr("android.frida_import_js"))
        self._btn_export_script_out.setText(tr("android.frida_export_script_output"))
        self._chk_dump_rva.setText(tr("android.dump_rva_mode"))
        self._btn_refresh_frida_env.setText(tr("android.frida_refresh_env"))
        self._btn_install_frida_android.setText(tr("android.frida_install_android"))
        self._btn_run_frida_server.setText(tr("android.frida_run_on_device"))
        self._btn_run_frida_server.setToolTip(tr("android.frida_run_on_device_tip"))
        if self._adb_table_kind == "packages" and self._adb_pkgs_full is not None:
            self._apply_adb_filter()
        elif self._adb_table_kind == "processes" and self._adb_ps_full is not None:
            self._apply_adb_filter()
        self._refresh_frida_env_full()

    def _serial_text(self) -> Optional[str]:
        """返回当前选中设备的序列号（供 adb -s）；下拉项展示为「序列号 (状态)」，数据在 UserRole。"""
        idx = self._serial.currentIndex()
        if idx >= 0:
            data = self._serial.itemData(idx, Qt.ItemDataRole.UserRole)
            if isinstance(data, str) and data.strip():
                return data.strip()
        t = self._serial.currentText().strip()
        if not t:
            return None
        # 兼容手动输入或旧格式：从「xxx (device)」取序列号
        if " (" in t and t.endswith(")"):
            return t.rsplit(" (", 1)[0].strip()
        return t

    def _adb_switch_to_table(self) -> None:
        self._adb_stack.setCurrentIndex(0)

    def _adb_switch_to_shell(self) -> None:
        self._adb_stack.setCurrentIndex(1)
        self._adb_filter_edit.setEnabled(False)

    def _apply_adb_table_two_column_layout(self) -> None:
        """设备列表与进程表：第一列固定宽度，第二列拉伸；筛选前后一致。"""
        t = self._adb_table
        h = t.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        t.setColumnWidth(0, _ADB_TABLE_COL0_WIDTH)

    def _apply_adb_table_one_column_layout(self) -> None:
        """包名表与单列消息：整列拉伸。"""
        t = self._adb_table
        h = t.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    def _adb_mark_non_filterable(self, kind: str) -> None:
        """设备列表、提示信息等模式不提供包名/进程筛选。"""
        self._adb_table_kind = kind
        self._adb_pkgs_full = None
        self._adb_ps_full = None
        self._adb_filter_edit.blockSignals(True)
        self._adb_filter_edit.clear()
        self._adb_filter_edit.blockSignals(False)
        self._adb_filter_edit.setEnabled(False)

    def _adb_table_set_message(self, header: str, body: str) -> None:
        """单列表格：加载提示、错误信息等。"""
        self._adb_mark_non_filterable("message")
        self._adb_switch_to_table()
        t = self._adb_table
        t.setSortingEnabled(False)
        t.setRowCount(0)
        t.setColumnCount(1)
        t.setHorizontalHeaderLabels([header])
        t.setRowCount(1)
        it = QTableWidgetItem(body)
        it.setToolTip(body)
        t.setItem(0, 0, it)
        self._apply_adb_table_one_column_layout()

    def _fill_adb_table_devices(self, rows: list[tuple[str, str]]) -> None:
        self._adb_mark_non_filterable("devices")
        self._adb_switch_to_table()
        t = self._adb_table
        t.setSortingEnabled(False)
        t.setRowCount(0)
        t.setColumnCount(2)
        t.setHorizontalHeaderLabels(
            [tr("android.col_serial"), tr("android.col_state")]
        )
        t.setRowCount(len(rows))
        for i, (serial, state) in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(serial))
            t.setItem(i, 1, QTableWidgetItem(state))
        self._apply_adb_table_two_column_layout()

    def _set_adb_packages_buffer(self, pkgs: list[str]) -> None:
        """保存完整包名列表并启用筛选框。"""
        self._adb_switch_to_table()
        self._adb_table_kind = "packages"
        self._adb_pkgs_full = list(pkgs)
        self._adb_ps_full = None
        self._adb_filter_edit.blockSignals(True)
        self._adb_filter_edit.clear()
        self._adb_filter_edit.blockSignals(False)
        self._adb_filter_edit.setEnabled(True)
        self._apply_adb_filter()

    def _set_adb_processes_buffer(self, rows: list[tuple[int, str]]) -> None:
        """保存完整进程列表并启用筛选框。"""
        self._adb_switch_to_table()
        self._adb_table_kind = "processes"
        self._adb_ps_full = list(rows)
        self._adb_pkgs_full = None
        self._adb_filter_edit.blockSignals(True)
        self._adb_filter_edit.clear()
        self._adb_filter_edit.blockSignals(False)
        self._adb_filter_edit.setEnabled(True)
        self._apply_adb_filter()

    def _apply_adb_filter(self) -> None:
        """按筛选框关键字过滤当前包名表或进程表（不区分大小写）。"""
        if self._adb_table_kind == "packages" and self._adb_pkgs_full is not None:
            needle = self._adb_filter_edit.text().strip().lower()
            if needle:
                filtered = [p for p in self._adb_pkgs_full if needle in p.lower()]
            else:
                filtered = list(self._adb_pkgs_full)
            self._render_packages_table(filtered)
        elif self._adb_table_kind == "processes" and self._adb_ps_full is not None:
            needle = self._adb_filter_edit.text().strip().lower()
            if needle:
                filtered = [
                    (pid, n)
                    for pid, n in self._adb_ps_full
                    if needle in n.lower() or needle in str(pid)
                ]
            else:
                filtered = list(self._adb_ps_full)
            self._render_processes_table(filtered)

    def _render_packages_table(self, pkgs: list[str]) -> None:
        self._adb_switch_to_table()
        t = self._adb_table
        t.setSortingEnabled(False)
        t.setRowCount(0)
        t.setColumnCount(1)
        t.setHorizontalHeaderLabels([tr("android.col_package")])
        max_show = _MAX_ADB_TABLE_ROWS
        chunk = pkgs[:max_show]
        extra = len(pkgs) > max_show
        t.setRowCount(len(chunk) + (1 if extra else 0))
        for i, p in enumerate(chunk):
            t.setItem(i, 0, QTableWidgetItem(p))
        if extra:
            t.setItem(
                len(chunk),
                0,
                QTableWidgetItem(
                    tr("android.table_truncated").format(
                        total=len(pkgs), shown=max_show
                    )
                ),
            )
        self._apply_adb_table_one_column_layout()

    def _render_processes_table(self, rows: list[tuple[int, str]]) -> None:
        self._adb_switch_to_table()
        t = self._adb_table
        t.setSortingEnabled(False)
        t.setRowCount(0)
        t.setColumnCount(2)
        t.setHorizontalHeaderLabels(
            [tr("android.col_pid"), tr("android.col_process_name")]
        )
        max_show = _MAX_ADB_TABLE_ROWS
        chunk = rows[:max_show]
        extra = len(rows) > max_show
        t.setRowCount(len(chunk) + (1 if extra else 0))
        for i, (pid, name) in enumerate(chunk):
            t.setItem(i, 0, QTableWidgetItem(str(pid)))
            t.setItem(i, 1, QTableWidgetItem(name))
        if extra:
            msg = tr("android.table_truncated").format(
                total=len(rows), shown=max_show
            )
            t.setItem(len(chunk), 0, QTableWidgetItem(msg))
            t.setSpan(len(chunk), 0, 1, 2)
        self._apply_adb_table_two_column_layout()

    def _finish_adb_refresh(self) -> None:
        self._adb_refresh_busy = False
        self._btn_refresh_dev.setEnabled(True)

    def _refresh_devices(self) -> None:
        if self._adb_refresh_busy:
            return
        self._adb_exe = self._adb_path.text().strip() or "adb"
        self._adb_refresh_busy = True
        self._btn_refresh_dev.setEnabled(False)
        self._adb_table_set_message(tr("android.col_message"), tr("android.adb_running"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        adb_exe = self._adb_exe

        def work() -> list[tuple[str, str]]:
            devs = android_adb.list_devices(adb_exe)
            return [(d.serial, d.state) for d in devs]

        th = _CallableThread(work, parent=self)
        th.finished_ok.connect(self._on_refresh_devices_ok)
        th.finished_err.connect(self._on_refresh_devices_err)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_refresh_devices_ok(self, rows: object) -> None:
        QApplication.restoreOverrideCursor()
        self._apply_adb_devices_to_ui(rows)  # type: ignore[arg-type]
        self._finish_adb_refresh()

    def _on_refresh_devices_err(self, err: str) -> None:
        QApplication.restoreOverrideCursor()
        self._adb_table_set_message(
            tr("android.col_message"),
            tr("android.adb_error").format(err=err),
        )
        self._finish_adb_refresh()

    def _apply_adb_devices_to_ui(self, rows: list[tuple[str, str]]) -> None:
        """在主线程更新设备下拉框与表格；序列号存 UserRole 供 adb -s 使用。"""
        self._serial.blockSignals(True)
        try:
            self._serial.clear()
            for serial, state in rows:
                label = f"{serial} ({state})"
                self._serial.addItem(label, serial)
            if rows:
                self._serial.setCurrentIndex(0)
            self._fill_adb_table_devices(rows)
        finally:
            self._serial.blockSignals(False)

    def _list_packages(self) -> None:
        self._adb_exe = self._adb_path.text().strip() or "adb"
        ser = self._serial_text()
        adb = self._adb_exe
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def work() -> list[str]:
            return android_adb.list_packages(ser, adb_exe=adb)

        th = _CallableThread(work, parent=self)
        th.finished_ok.connect(self._on_list_packages_ok)
        th.finished_err.connect(self._on_list_packages_err)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_list_packages_ok(self, pkgs: object) -> None:
        QApplication.restoreOverrideCursor()
        self._set_adb_packages_buffer(pkgs)  # type: ignore[arg-type]

    def _on_list_packages_err(self, err: str) -> None:
        QApplication.restoreOverrideCursor()
        self._adb_table_set_message(tr("android.col_message"), err)

    def _list_ps(self) -> None:
        self._adb_exe = self._adb_path.text().strip() or "adb"
        ser = self._serial_text()
        adb = self._adb_exe
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def work() -> list[tuple[int, str]]:
            return android_adb.list_app_processes_ps(ser, adb_exe=adb)

        th = _CallableThread(work, parent=self)
        th.finished_ok.connect(self._on_list_ps_ok)
        th.finished_err.connect(self._on_list_ps_err)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_list_ps_ok(self, rows: object) -> None:
        QApplication.restoreOverrideCursor()
        self._set_adb_processes_buffer(rows)  # type: ignore[arg-type]

    def _on_list_ps_err(self, err: str) -> None:
        QApplication.restoreOverrideCursor()
        self._adb_table_set_message(tr("android.col_message"), err)

    def _run_shell(self) -> None:
        cmd = self._shell_cmd.text().strip()
        if not cmd:
            return
        self._adb_exe = self._adb_path.text().strip() or "adb"
        self._adb_switch_to_shell()
        ser = self._serial_text()
        adb = self._adb_exe
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def work() -> str:
            return android_adb.shell(ser, cmd, adb_exe=adb)

        th = _CallableThread(work, parent=self)
        th.finished_ok.connect(self._on_run_shell_ok)
        th.finished_err.connect(self._on_run_shell_err)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_run_shell_ok(self, out: object) -> None:
        QApplication.restoreOverrideCursor()
        self._adb_shell_out.appendPlainText(str(out))

    def _on_run_shell_err(self, err: str) -> None:
        QApplication.restoreOverrideCursor()
        self._adb_shell_out.appendPlainText(err + "\n")

    def _refresh_frida_env_full(self) -> None:
        """Windows Frida / 设备 root / frida-server 状态摘要（ADB 探测在后台线程）。"""
        win_v = frida_inst.get_windows_frida_version()
        if win_v:
            self._lbl_frida_win.setText(tr("android.frida_env_win_ok").format(v=win_v))
            self._btn_attach.setEnabled(True)
            self._btn_install_frida_android.setEnabled(True)
        else:
            self._lbl_frida_win.setText(tr("android.frida_env_win_missing"))
            self._btn_attach.setEnabled(False)
            self._btn_install_frida_android.setEnabled(False)

        adb = self._adb_path.text().strip() or "adb"
        ser = self._serial_text()
        if not ser:
            self._lbl_frida_root.setText(tr("android.frida_env_no_device"))
            self._lbl_frida_srv.setText(tr("android.frida_env_skip_device"))
            return

        self._frida_probe_generation += 1
        gen = self._frida_probe_generation
        self._lbl_frida_root.setText(tr("android.adb_running"))
        self._lbl_frida_srv.setText(tr("android.adb_running"))

        def work() -> tuple[str, str, str, str]:
            rk, rd = frida_inst.probe_android_root(ser, adb)
            sk, sd = frida_inst.probe_frida_server_on_device(ser, adb)
            return rk, rd, sk, sd

        th = _CallableThread(work, parent=self)
        th.finished_ok.connect(
            lambda result: self._on_frida_probe_done(result, gen)
        )
        th.finished_err.connect(lambda err: self._on_frida_probe_err(err, gen))
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_frida_probe_done(
        self, result: object, gen: int
    ) -> None:
        if gen != self._frida_probe_generation:
            return
        rk, rd, sk, sd = result  # type: ignore[misc]
        if rk == "yes":
            self._lbl_frida_root.setText(tr("android.frida_root_yes").format(d=rd))
        else:
            self._lbl_frida_root.setText(tr("android.frida_root_no").format(d=rd))
        if sk == "running":
            self._lbl_frida_srv.setText(tr("android.frida_srv_running"))
        elif sk == "file_only":
            self._lbl_frida_srv.setText(tr("android.frida_srv_file").format(d=sd))
        elif sk == "none":
            self._lbl_frida_srv.setText(tr("android.frida_srv_none"))
        else:
            self._lbl_frida_srv.setText(tr("android.frida_srv_unknown").format(d=sd))

    def _on_frida_probe_err(self, err: str, gen: int) -> None:
        if gen != self._frida_probe_generation:
            return
        self._lbl_frida_root.setText(
            tr("android.frida_root_unknown").format(d=str(err))
        )
        self._lbl_frida_srv.setText(
            tr("android.frida_srv_unknown").format(d=str(err))
        )

    def _on_run_frida_server_android(self) -> None:
        ser = self._serial_text()
        if not ser:
            QMessageBox.warning(
                self,
                tr("android.debug_window_title"),
                tr("android.frida_install_no_device"),
            )
            return
        self._adb_exe = self._adb_path.text().strip() or "adb"
        path = android_st.frida_server_device_path()
        self._frida_log(tr("android.frida_run_log_start").format(path=path))
        adb = self._adb_exe
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def work() -> str:
            cmd = f'su -c "{path} &"'
            return android_adb.shell(ser, cmd, adb_exe=adb, timeout=25.0)

        th = _CallableThread(work, parent=self)
        th.finished_ok.connect(self._on_run_frida_server_ok)
        th.finished_err.connect(self._on_run_frida_server_err)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_run_frida_server_ok(self, out: object) -> None:
        QApplication.restoreOverrideCursor()
        s = str(out)
        self._frida_log(s if s.strip() else tr("android.frida_run_no_stdout"))
        self._refresh_frida_env_full()

    def _on_run_frida_server_err(self, err: str) -> None:
        QApplication.restoreOverrideCursor()
        self._frida_log(err)
        self._refresh_frida_env_full()

    def _on_install_frida_android(self) -> None:
        if not frida_inst.get_windows_frida_version():
            QMessageBox.warning(
                self,
                tr("android.debug_window_title"),
                tr("android.frida_install_no_pip"),
            )
            return
        ser = self._serial_text()
        if not ser:
            QMessageBox.warning(
                self,
                tr("android.debug_window_title"),
                tr("android.frida_install_no_device"),
            )
            return
        dlg = FridaAndroidInstallRiskDialog(self, wait_seconds=10)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._adb_exe = self._adb_path.text().strip() or "adb"
        dev_path = android_st.frida_server_device_path()
        self._frida_log(tr("android.frida_install_log_header"))
        self._btn_install_frida_android.setEnabled(False)
        self._btn_refresh_frida_env.setEnabled(False)
        th = _FridaInstallServerThread(
            ser,
            self._adb_exe,
            dev_path,
            parent=self,
        )
        self._frida_install_thread = th
        th.log_line.connect(self._frida_log)
        q = Qt.ConnectionType.QueuedConnection
        th.finished_ok.connect(self._on_frida_install_done, q)
        th.finished_err.connect(self._on_frida_install_failed, q)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_frida_install_done(self) -> None:
        self._btn_install_frida_android.setEnabled(True)
        self._btn_refresh_frida_env.setEnabled(True)
        self._frida_log(tr("android.frida_install_done"))
        self._refresh_frida_env_full()

    def _on_frida_install_failed(self, err: str) -> None:
        self._btn_install_frida_android.setEnabled(True)
        self._btn_refresh_frida_env.setEnabled(True)
        msg = err
        if err.startswith("HTTP_404:"):
            url = err[len("HTTP_404:") :]
            self._frida_log(tr("android.frida_install_err_404").format(url=url))
        elif err == "NO_FRIDA_PIP" or "NO_FRIDA_PIP" in err:
            self._frida_log(tr("android.frida_install_no_pip"))
        else:
            self._frida_log(tr("android.frida_install_failed").format(err=msg))
        self._refresh_frida_env_full()

    def _import_frida_script_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("android.frida_import_js_title"),
            "",
            tr("android.frida_import_js_filter"),
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            QMessageBox.warning(self, tr("android.debug_window_title"), str(e))
            return
        self._frida_js.setPlainText(text)

    def _export_frida_script_output_to_file(self) -> None:
        text = self._out_frida_script.toPlainText()
        if not text.strip():
            QMessageBox.information(
                self,
                tr("android.debug_window_title"),
                tr("android.frida_export_empty"),
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("android.frida_export_script_title"),
            "",
            tr("android.frida_export_script_filter"),
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8", newline="\n")
        except OSError as e:
            QMessageBox.warning(self, tr("android.debug_window_title"), str(e))
            return
        QMessageBox.information(
            self, tr("android.debug_window_title"), tr("android.frida_export_ok")
        )

    def _frida_log(self, text: str) -> None:
        self._out_frida.appendPlainText(text.rstrip() + "\n")

    def _frida_log_script(self, text: str) -> None:
        self._out_frida_script.appendPlainText(text.rstrip() + "\n")

    def _dispatch_frida_console_log(self, level: str, text: object) -> None:
        """console.log 经 Script.set_log_handler 回调；不在 on('message') 中。"""
        if isinstance(text, (list, tuple)):
            line = " ".join(str(x) for x in text)
        else:
            line = str(text) if text is not None else ""
        if level and level != "info":
            line = f"[{level}] {line}"
        self._sig_frida_script_log.emit(line)

    def _dispatch_frida_message(
        self, message: object, data: Optional[bytes]
    ) -> None:
        """由 Frida 线程调用：只发 Signal，禁止在此直接操作控件（不含 console.log）。"""
        if isinstance(message, dict):
            mtype = message.get("type")
            if isinstance(mtype, bytes):
                mtype = mtype.decode("utf-8", "replace")
            if mtype == "log":
                payload = message.get("payload")
                if isinstance(payload, (list, tuple)):
                    line = " ".join(str(x) for x in payload)
                elif payload is not None:
                    line = str(payload)
                else:
                    line = repr(message)
                lv = message.get("level", "")
                if lv:
                    line = f"[{lv}] {line}"
                self._sig_frida_script_log.emit(line)
            elif mtype == "send":
                self._sig_frida_script_log.emit(
                    tr("android.frida_send_prefix")
                    + repr(message.get("payload"))
                )
            elif mtype == "error":
                desc = message.get("description") or message.get("stack")
                line = str(desc) if desc is not None else repr(message)
                ln = message.get("lineNumber")
                if ln is not None:
                    line = f"{line} (line {ln})"
                self._sig_frida_script_log.emit(line)
            else:
                self._sig_frida_sys_log.emit(repr(message))
        else:
            self._sig_frida_sys_log.emit(str(message))
        if data:
            self._sig_frida_sys_log.emit(f"[binary] {data[:64]!r}…")

    @staticmethod
    def _frida_exports_call(exp: object, names: tuple[str, ...], *args: object):
        for n in names:
            fn = getattr(exp, n, None)
            if callable(fn):
                return fn(*args)
        return None

    def _frida_attach(self) -> None:
        if not _frida_available():
            QMessageBox.information(
                self, tr("android.debug_window_title"), tr("android.frida_install_hint")
            )
            return

        target = self._frida_target.text().strip()
        if not target:
            QMessageBox.warning(
                self, tr("android.debug_window_title"), tr("android.frida_need_target")
            )
            return

        if self._frida_attach_thread is not None and self._frida_attach_thread.isRunning():
            return

        user_js = self._frida_js.toPlainText().strip()
        # GUARD 在前保存原生 API；BRIDGE 在后合并 rpc.exports
        full_js = _FRIDA_RPC_GUARD + "\n" + user_js + "\n" + _FRIDA_RPC_BRIDGE

        self._frida_detach()
        self._btn_attach.setEnabled(False)
        self._btn_detach.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        remote_host = android_st.frida_remote_host()
        serial = self._serial_text()

        th = _FridaAttachThread(
            self,
            remote_host,
            serial,
            target,
            full_js,
            parent=self,
        )
        self._frida_attach_thread = th
        q = Qt.ConnectionType.QueuedConnection
        th.attached.connect(self._on_frida_attached_ok, q)
        th.failed.connect(self._on_frida_attached_fail, q)
        th.finished.connect(self._on_frida_attach_thread_finished)
        th.finished.connect(th.deleteLater)
        th.start()

    def _on_frida_attached_ok(
        self, session: object, script: object, dev: object
    ) -> None:
        self._frida_session = session
        self._frida_script = script
        self._frida_device = dev
        self._btn_detach.setEnabled(True)
        self._frida_log(tr("android.frida_attached"))
        exp = android_st.frida_expected_major()
        if exp and android_st.frida_warn_version_mismatch():
            pyv = android_st.python_frida_version()
            if pyv:
                py_major = pyv.split(".", 1)[0].strip()
                if py_major and py_major != exp.strip():
                    QMessageBox.warning(
                        self,
                        tr("android.debug_window_title"),
                        tr("android.frida_version_mismatch").format(
                            py=pyv, exp=exp.strip()
                        ),
                    )

    def _on_frida_attached_fail(self, err: str) -> None:
        self._frida_session = None
        self._frida_script = None
        self._frida_device = None
        self._btn_detach.setEnabled(False)
        self._frida_log(err)
        QMessageBox.warning(self, tr("android.debug_window_title"), err)

    def _on_frida_attach_thread_finished(self) -> None:
        QApplication.restoreOverrideCursor()
        self._btn_attach.setEnabled(True)
        self._frida_attach_thread = None

    def _frida_detach(self) -> None:
        if self._frida_script is not None:
            try:
                self._frida_script.unload()
            except Exception:
                pass
            self._frida_script = None
        if self._frida_session is not None:
            try:
                self._frida_session.detach()
            except Exception:
                pass
            self._frida_session = None
        self._frida_device = None
        self._btn_detach.setEnabled(False)

    def _dump_read_memory_impl(
        self,
        script: object,
        addr_val: int,
        size: int,
        chk_rva: bool,
    ) -> tuple[str, bytes]:
        """执行 Frida RPC 读内存（须在主线程调用，与 Frida Python 绑定一致）。"""
        exp = script.exports_sync
        base_hex = ""
        rva_hex = hex(addr_val)
        if chk_rva:
            base_s = self._frida_exports_call(
                exp,
                ("get_main_executable_base", "getMainExecutableBase"),
            )
            if base_s is None:
                raise RuntimeError(tr("android.dump_no_rpc_base"))
            base = int(str(base_s).strip(), 0)
            if base == 0:
                raise RuntimeError(tr("android.dump_base_zero"))
            va = base + addr_val
            addr_norm = hex(va)
            base_hex = hex(base)
        else:
            addr_norm = hex(addr_val)

        r = self._frida_exports_call(
            exp,
            ("read_memory_block", "readMemoryBlock"),
            addr_norm,
            size,
        )
        if isinstance(r, dict):
            if r.get("ok") is False:
                msg = r.get("msg") or ""
                raise RuntimeError(
                    tr("android.dump_read_detail").format(msg=msg)
                )
            raw = r.get("bytes")
            if raw is None:
                raise RuntimeError(tr("android.dump_rpc_missing"))
            data = bytes(raw) if not isinstance(raw, bytes) else raw
        else:
            arr = self._frida_exports_call(
                exp,
                ("read_bytes", "readBytes"),
                addr_norm,
                size,
            )
            if arr is None:
                raise RuntimeError(tr("android.dump_rpc_missing"))
            if not arr:
                raise RuntimeError(tr("android.dump_empty"))
            data = bytes(arr) if not isinstance(arr, bytes) else arr

        if chk_rva:
            title = tr("android.dump_tab_title_rva").format(
                base=base_hex,
                rva=rva_hex,
                va=addr_norm,
                n=len(data),
            )
        else:
            title = tr("android.dump_tab_title").format(addr=addr_norm, n=len(data))
        return title, data

    def _dump_memory_to_tab(self) -> None:
        if self._frida_script is None:
            QMessageBox.information(
                self, tr("android.debug_window_title"), tr("android.dump_need_attach")
            )
            return
        raw_addr = self._dump_addr.text().strip()
        if not raw_addr:
            return
        size = int(self._dump_size.value())
        try:
            addr_val = int(raw_addr, 0)
        except ValueError:
            QMessageBox.warning(self, tr("android.debug_window_title"), tr("android.bad_addr"))
            return

        script = self._frida_script
        chk_rva = self._chk_dump_rva.isChecked()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            title, data = self._dump_read_memory_impl(
                script, addr_val, size, chk_rva
            )
            if self._open_buffer_tab:
                # 推迟到下一事件循环，避免 load_bytes 与新建标签阻塞消息泵
                QTimer.singleShot(
                    0,
                    lambda t=title, d=data: self._open_buffer_tab_safe(t, d),
                )
            else:
                QMessageBox.information(
                    self,
                    tr("android.debug_window_title"),
                    tr("android.dump_no_tab").format(n=len(data)),
                )
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, tr("android.debug_window_title"), str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def _open_buffer_tab_safe(self, title: str, data: bytes) -> None:
        if self._open_buffer_tab:
            self._open_buffer_tab(title, data)


class AndroidDebugWindow(QMainWindow):
    """独立子窗口：Android 调试 / Hook（由「工具」菜单打开）。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        open_buffer_tab: Optional[Callable[[str, bytes], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._panel = AndroidDebugPanel(self, open_buffer_tab=open_buffer_tab)
        self.setCentralWidget(self._panel)
        self.setMinimumSize(900, 520)
        self.resize(1000, 680)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("android.debug_window_title"))
        self._panel.retranslate_ui()

    def sync_from_settings(self) -> None:
        self._panel.sync_from_settings()
