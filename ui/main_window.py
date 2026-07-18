from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QTimer
from PySide6.QtGui import QAction, QClipboard
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from core.scanner import LockHolder, kill_processes, probe_move, report_markdown, scan

logger = logging.getLogger(__name__)

COL_KILL = 0
COL_PID = 1
COL_NAME = 2
COL_VIA = 3
COL_PATH = 4
COL_STARTED = 5
COL_CMDLINE = 6


def _holders_key(holders: list[LockHolder]) -> tuple[LockHolder, ...]:
    return tuple(holders)


def _root_validation_error(root: Path) -> str | None:
    if str(root).replace("/", "\\").startswith("\\\\"):
        return "Network and device roots are refused"
    if not root.exists():
        return f"Root does not exist: {root}"
    if not root.is_dir():
        return f"Root is not a directory: {root}"
    return None


class MainWindow(QMainWindow):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config: Config = config
        self._holders: list[LockHolder] = []

        self._root_edit: QLineEdit
        self._table: QTableWidget
        self._status: QStatusBar
        self._act_live: QAction
        self._live_timer: QTimer

        self._init_ui()
        self._rescan()

    def _init_ui(self) -> None:
        self.setWindowTitle(self._config.app_name)
        self.resize(self._config.window_width, self._config.window_height)

        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        act_rescan = QAction("Rescan", self)
        act_rescan.setShortcut("F5")
        act_rescan.triggered.connect(self._rescan)
        toolbar.addAction(act_rescan)

        self._act_live = QAction("Live", self)
        self._act_live.setCheckable(True)
        self._act_live.setChecked(True)
        self._act_live.toggled.connect(self._on_live_toggled)
        toolbar.addAction(self._act_live)

        toolbar.addSeparator()

        act_kill_selected = QAction("Kill Selected", self)
        act_kill_selected.triggered.connect(self._on_kill_selected)
        toolbar.addAction(act_kill_selected)

        act_kill_all = QAction("Kill All Listed", self)
        act_kill_all.triggered.connect(self._on_kill_all)
        toolbar.addAction(act_kill_all)

        toolbar.addSeparator()

        act_probe = QAction("Probe Move", self)
        act_probe.triggered.connect(self._on_probe_move)
        toolbar.addAction(act_probe)

        act_copy_report = QAction("Copy Report", self)
        act_copy_report.triggered.connect(self._on_copy_report)
        toolbar.addAction(act_copy_report)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        root_row = QHBoxLayout()
        root_row.addWidget(QLabel("Root:"))
        self._root_edit = QLineEdit(self._config.default_root)
        self._root_edit.returnPressed.connect(self._rescan)
        root_row.addWidget(self._root_edit)
        rescan_btn = QPushButton("Scan")
        rescan_btn.clicked.connect(self._rescan)
        root_row.addWidget(rescan_btn)
        layout.addLayout(root_row)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Kill", "PID", "Name", "Locks via", "Locked path", "Started", "Command line"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_PATH, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_CMDLINE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_KILL, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(COL_KILL, 44)
        self._table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self._table)

        self.setCentralWidget(central)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._root_edit.textChanged.connect(self._on_root_edited)

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(self._config.live_interval_ms)
        self._live_timer.timeout.connect(self._live_tick)
        self._live_timer.start()

    def _root(self) -> Path:
        return Path(
            self._root_edit.text().strip() or self._config.default_root
        ).absolute()

    def _on_live_toggled(self, checked: bool) -> None:
        if checked:
            self._live_timer.start()
        else:
            self._live_timer.stop()
        logger.info("Live refresh %s", "on" if checked else "off")

    def _clear_holders(self) -> None:
        self._holders = []
        self._table.setRowCount(0)

    def _on_root_edited(self, _text: str) -> None:
        self._clear_holders()
        self._status.showMessage("Root changed: scan required")

    def _rescan(self) -> None:
        root = self._root()
        root_error = _root_validation_error(root)
        if root_error is not None:
            self._clear_holders()
            self._status.showMessage(root_error)
            return
        self._holders = scan(root)
        self._populate_table(preserve_checks=False)
        self._status.showMessage(f"{len(self._holders)} lock holder(s) under {root}")
        logger.info("Scan of %s found %d holder(s)", root, len(self._holders))

    def _live_tick(self) -> None:
        root = self._root()
        root_error = _root_validation_error(root)
        if root_error is not None:
            self._clear_holders()
            self._status.showMessage(root_error)
            return
        fresh = scan(root)
        if _holders_key(fresh) == _holders_key(self._holders):
            return
        checked_holders = set(self._checked_holders())
        self._holders = fresh
        self._populate_table(preserve_checks=False)
        for row, holder in enumerate(self._holders):
            if holder in checked_holders:
                item = self._table.item(row, COL_KILL)
                if item is not None:
                    item.setCheckState(Qt.CheckState.Checked)
        self._status.showMessage(
            f"live: {len(self._holders)} lock holder(s) under {root}"
        )

    def _populate_table(self, *, preserve_checks: bool) -> None:
        self._table.setRowCount(0)
        for holder in self._holders:
            row = self._table.rowCount()
            self._table.insertRow(row)

            check_item = QTableWidgetItem()
            # no ItemIsUserCheckable: Qt would only toggle on a direct hit of
            # the 14px indicator; _on_cell_clicked makes the whole cell the target
            check_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            check_item.setCheckState(Qt.CheckState.Unchecked)
            self._table.setItem(row, COL_KILL, check_item)

            started = holder.started.strftime("%m-%d %H:%M") if holder.started else "?"
            for col, text in (
                (COL_PID, str(holder.pid)),
                (COL_NAME, holder.name),
                (COL_VIA, holder.reason_summary),
                (COL_PATH, holder.locked_paths),
                (COL_STARTED, started),
                (COL_CMDLINE, holder.cmdline),
            ):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self._table.setItem(row, col, item)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col != COL_KILL:
            return
        item = self._table.item(row, COL_KILL)
        if item is None:
            return
        new_state = (
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        item.setCheckState(new_state)

    def _checked_holders(self) -> list[LockHolder]:
        checked: list[LockHolder] = []
        for row, holder in enumerate(self._holders):
            item = self._table.item(row, COL_KILL)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                checked.append(holder)
        return checked

    def _on_kill_selected(self) -> None:
        self._confirm_and_kill(self._checked_holders())

    def _on_kill_all(self) -> None:
        self._confirm_and_kill(list(self._holders))

    def _confirm_and_kill(self, targets: list[LockHolder]) -> None:
        if not targets:
            self._status.showMessage("Nothing selected")
            return
        was_live = self._live_timer.isActive()
        self._live_timer.stop()
        try:
            listing = "\n".join(
                f"  {h.pid}  {h.name}  ({h.reason_summary})" for h in targets
            )
            answer = QMessageBox.question(
                self,
                "Confirm kill",
                f"Kill {len(targets)} process(es)?\n\n{listing}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            results = kill_processes(targets)
            summary = ", ".join(f"{r.pid}:{r.outcome}" for r in results)
            logger.info("Kill results: %s", summary)
            denied = [r for r in results if r.outcome == "denied"]
            if denied:
                QMessageBox.warning(
                    self,
                    "Access denied",
                    "Could not kill (needs an elevated run):\n"
                    + "\n".join(f"  {r.pid}  {r.name}" for r in denied),
                )
            self._rescan()
            self._status.showMessage(f"Done: {summary}")
        finally:
            if was_live:
                self._live_timer.start()

    def _on_probe_move(self) -> None:
        root = self._root()
        root_error = _root_validation_error(root)
        if root_error is not None:
            self._status.showMessage(root_error)
            return
        was_live = self._live_timer.isActive()
        self._live_timer.stop()
        try:
            movable, message = probe_move(root)
            logger.info("Probe of %s: %s", root, message)
            self._status.showMessage(message)
            if movable:
                QMessageBox.information(self, "Probe Move", f"{root}\n\n{message}")
            else:
                QMessageBox.warning(
                    self,
                    "Probe Move",
                    f"{root}\n\n{message}",
                )
        finally:
            if was_live:
                self._live_timer.start()

    def _on_copy_report(self) -> None:
        report = report_markdown(self._root(), self._holders)
        mime = QMimeData()
        mime.setText(report)
        clipboard: QClipboard = QApplication.clipboard()
        clipboard.setMimeData(mime)
        self._status.showMessage("Report copied to clipboard")
        logger.info("Copied report for %d holder(s)", len(self._holders))
