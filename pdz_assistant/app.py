from __future__ import annotations

import getpass
import os
import re
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .exporter import ExportCancelled, ExportService
from .models import ExportConfig, ExportResult, ProgressUpdate, ReaderState
from .reader import SsReaderController


class MainWindow(QMainWindow):
    progress_signal = Signal(object)
    export_finished = Signal(object)
    export_failed = Signal(str)
    missing_pages_prompt = Signal(int, int)

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.reader = SsReaderController()
        self.export_service = ExportService(self.reader)
        self.username = getpass.getuser()
        self.buffer_dir = Path.home() / "AppData" / "Local" / "Temp" / "buffer"
        self.export_thread: threading.Thread | None = None
        self.is_exporting = False
        self.current_reader_hwnd: int | None = None
        self.previous_png_dir: str | None = None
        self._pending_missing_pages_answer: bool | None = None
        self._pending_missing_pages_event: threading.Event | None = None

        self.setWindowTitle("pdz\u52a9\u624b Python\u7248")
        self.resize(1120, 760)
        self.setMinimumSize(860, 620)

        self._build_ui()
        self._apply_styles()
        self._wire_events()
        self._set_default_paths()

        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.refresh_reader_state)
        self.scan_timer.start(1000)
        self.refresh_reader_state()
        self._update_responsive_layout()

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll_area)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentRoot")
        self.scroll_area.setWidget(self.content_widget)

        root = QVBoxLayout(self.content_widget)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        self.hero_card = QFrame()
        self.hero_card.setObjectName("HeroCard")
        root.addWidget(self.hero_card)
        self._build_hero_card(self.hero_card)

        self.top_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.top_layout.setSpacing(16)
        root.addLayout(self.top_layout)

        self.status_card = self._create_panel_card()
        self.help_card = self._create_panel_card()
        self.top_layout.addWidget(self.status_card, 5)
        self.top_layout.addWidget(self.help_card, 4)

        self._build_status_card(self.status_card)
        self._build_help_card(self.help_card)

        self.export_card = self._create_panel_card()
        root.addWidget(self.export_card)
        self._build_export_card(self.export_card)

        self.progress_card = self._create_panel_card()
        root.addWidget(self.progress_card)
        self._build_progress_card(self.progress_card)

    def _build_hero_card(self, card: QFrame) -> None:
        self.hero_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, card)
        self.hero_layout.setContentsMargins(22, 20, 22, 20)
        self.hero_layout.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(6)

        eyebrow = QLabel("PDZ ASSISTANT")
        eyebrow.setObjectName("HeroEyebrow")
        left.addWidget(eyebrow)

        title = QLabel("ssReader PDZ \u5bfc\u51fa\u52a9\u624b")
        title.setObjectName("HeroTitle")
        left.addWidget(title)

        subtitle = QLabel(
            "\u4fdd\u7559\u5df2\u6709\u5bfc\u51fa\u80fd\u529b\uff0c\u7528\u66f4\u6e05\u6670\u7684\u72b6\u6001\u53cd\u9988\u548c\u66f4\u7ec6\u81f4\u7684\u684c\u9762 UI \u6765\u5b8c\u6210 PDZ \u8f6c PDF\u3002"
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)

        self.hero_layout.addLayout(left, 1)

        self.hero_right_layout = QVBoxLayout()
        self.hero_right_layout.setSpacing(10)
        self.hero_right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.hero_badge = QLabel("\u7b49\u5f85 ssReader")
        self.hero_badge.setObjectName("HeroBadge")
        self.hero_right_layout.addWidget(self.hero_badge, 0, Qt.AlignmentFlag.AlignRight)

        self.hero_detail = QLabel(r"D:\book")
        self.hero_detail.setObjectName("HeroDetail")
        self.hero_detail.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.hero_detail.setWordWrap(True)
        self.hero_right_layout.addWidget(self.hero_detail)

        self.hero_layout.addLayout(self.hero_right_layout)

    def _create_panel_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("PanelCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        card.setMinimumWidth(0)
        return card

    def _build_status_card(self, card: QFrame) -> None:
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._create_section_title("S", "ssReader \u72b6\u6001"))

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(14)
        metrics.setVerticalSpacing(12)

        metrics.addWidget(self._create_field_label("\u8fd0\u884c\u72b6\u6001"), 0, 0)
        self.reader_status_value = self._create_metric_value("\u672a\u542f\u52a8")
        metrics.addWidget(self.reader_status_value, 0, 1)

        metrics.addWidget(self._create_field_label("\u5f53\u524d\u7528\u6237"), 1, 0)
        self.username_value = self._create_metric_value(self.username)
        metrics.addWidget(self.username_value, 1, 1)
        metrics.addWidget(self._create_field_label("\u8bc6\u522b\u4e66\u540d"), 2, 0)
        self.book_name_value = self._create_metric_value("\u672a\u8bc6\u522b")
        self.book_name_value.setWordWrap(True)
        metrics.addWidget(self.book_name_value, 2, 1)
        metrics.addWidget(self._create_field_label("\u8f93\u51fa\u6587\u4ef6"), 3, 0)
        self.output_name_value = self._create_metric_value("1.pdf")
        self.output_name_value.setWordWrap(True)
        metrics.addWidget(self.output_name_value, 3, 1)
        layout.addLayout(metrics)

        self.window_position_title = QLabel("\u7a97\u53e3\u7126\u70b9")
        self.window_position_title.setObjectName("FieldLabel")
        layout.addWidget(self.window_position_title)

        self.window_position_row = self._create_chip_row()
        self.foreground_chip = self._create_status_chip("\u524d\u53f0")
        self.background_chip = self._create_status_chip("\u540e\u53f0")
        self.window_position_row.addWidget(self.foreground_chip)
        self.window_position_row.addWidget(self.background_chip)
        self.window_position_row.addStretch(1)
        layout.addLayout(self.window_position_row)

        self.window_state_title = QLabel("\u7a97\u53e3\u72b6\u6001")
        self.window_state_title.setObjectName("FieldLabel")
        layout.addWidget(self.window_state_title)

        self.window_state_row = self._create_chip_row()
        self.maximized_chip = self._create_status_chip("\u6700\u5927\u5316")
        self.normal_chip = self._create_status_chip("\u5e38\u89c4")
        self.minimized_chip = self._create_status_chip("\u6700\u5c0f\u5316")
        self.window_state_row.addWidget(self.maximized_chip)
        self.window_state_row.addWidget(self.normal_chip)
        self.window_state_row.addWidget(self.minimized_chip)
        self.window_state_row.addStretch(1)
        layout.addLayout(self.window_state_row)

        self.reader_note_label = QLabel("\u8bf7\u5148\u542f\u52a8 ssReader\u3002")
        self.reader_note_label.setObjectName("StatusNote")
        self.reader_note_label.setWordWrap(True)
        layout.addWidget(self.reader_note_label)

        self.reader_log_label = QLabel("")
        self.reader_log_label.setObjectName("PathCaption")
        self.reader_log_label.setWordWrap(True)
        layout.addWidget(self.reader_log_label)

    def _build_help_card(self, card: QFrame) -> None:
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._create_section_title("I", "\u4f7f\u7528\u8bf4\u660e"))

        steps = [
            "1. \u5728 ssReader \u4e2d\u6253\u5f00 pdz \u6587\u4ef6\uff0c\u7136\u540e\u5207\u5165\u9605\u8bfb\u754c\u9762\u3002",
            "2. \u5c06 ssReader \u7a97\u53e3\u6700\u5927\u5316\uff0c\u8fd9\u6837\u7ffb\u9875\u548c\u7f13\u5b58\u6293\u53d6\u4f1a\u66f4\u7a33\u5b9a\u3002",
            "3. \u5982\u679c\u81ea\u52a8\u8bfb\u53d6\u603b\u9875\u6570\u5931\u8d25\uff0c\u53ef\u4ee5\u624b\u52a8\u586b\u5199\u603b\u9875\u6570\u540e\u7ee7\u7eed\u5bfc\u51fa\u3002",
            "4. \u9ed8\u8ba4 PDF \u8f93\u51fa\u5230 D:\\book\uff0c\u5982\u679c\u7f13\u5b58\u91cc\u80fd\u8bc6\u522b\u4e66\u540d\uff0c\u4f1a\u81ea\u52a8\u751f\u6210\u540c\u540d\u6587\u4ef6\u3002",
        ]

        for index, step in enumerate(steps):
            label = QLabel(step)
            label.setObjectName("HintLabel")
            label.setWordWrap(True)
            layout.addWidget(label)
            if index < len(steps) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setObjectName("DividerLine")
                layout.addWidget(line)

        help_footer = QLabel(
            "\u5982\u679c\u9875\u6570\u8bfb\u53d6\u5931\u8d25\uff0c\u53ef\u4ee5\u4f18\u5148\u67e5\u770b\u5de6\u4fa7\u72b6\u6001\u63d0\u793a\u548c\u65e5\u5fd7\u4fe1\u606f\u3002"
        )
        help_footer.setObjectName("HelpFooter")
        help_footer.setWordWrap(True)
        layout.addWidget(help_footer)

    def _build_export_card(self, card: QFrame) -> None:
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._create_section_title("E", "\u5bfc\u51fa\u8bbe\u7f6e"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        self.total_pages_edit = QLineEdit()
        self.total_pages_edit.setObjectName("PrimaryInput")
        self.total_pages_edit.setPlaceholderText("\u8bf7\u8f93\u5165\u603b\u9875\u6570\uff0c\u4f8b\u5982 328")

        self.manual_pages_hint = QLabel(
            "\u53ef\u81ea\u52a8\u8bc6\u522b\u65f6\u4f1a\u81ea\u52a8\u586b\u5145\uff0c\u5982\u672a\u8bc6\u522b\u53ef\u624b\u52a8\u8f93\u5165\u3002"
        )
        self.manual_pages_hint.setObjectName("InlineHint")
        self.manual_pages_hint.setWordWrap(True)

        self.png_dir_edit = QLineEdit()
        self.png_dir_edit.setObjectName("PrimaryInput")

        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setObjectName("PrimaryInput")

        self.browse_png_button = self._create_action_button("\u9009\u62e9 PNG \u76ee\u5f55", primary=False)
        self.browse_pdf_button = self._create_action_button("\u9009\u62e9 PDF \u6587\u4ef6", primary=False)
        self.open_buffer_button = self._create_action_button("\u6253\u5f00\u7f13\u5b58\u76ee\u5f55", primary=False)
        self.convert_button = self._create_action_button("\u4e00\u952e\u8f6c\u6362", primary=True)
        self.cancel_button = self._create_action_button("\u53d6\u6d88\u8f6c\u6362", primary=False)
        self.cancel_button.setEnabled(False)

        self.delete_png_checkbox = QCheckBox("\u751f\u6210 PDF \u540e\u81ea\u52a8\u5220\u9664 PNG")
        self.delete_png_checkbox.setObjectName("CleanCheck")

        grid.addWidget(self._create_field_label("\u603b\u9875\u6570"), 0, 0)
        grid.addWidget(self.total_pages_edit, 0, 1, 1, 3)
        grid.addWidget(self.manual_pages_hint, 1, 1, 1, 3)

        grid.addWidget(self._create_field_label("PNG \u76ee\u5f55"), 2, 0)
        grid.addWidget(self.png_dir_edit, 2, 1, 1, 2)
        grid.addWidget(self.browse_png_button, 2, 3)

        grid.addWidget(self._create_field_label("PDF \u8def\u5f84"), 3, 0)
        grid.addWidget(self.pdf_path_edit, 3, 1, 1, 2)
        grid.addWidget(self.browse_pdf_button, 3, 3)

        self.output_path_hint = QLabel("")
        self.output_path_hint.setObjectName("PathCaption")
        self.output_path_hint.setWordWrap(True)
        grid.addWidget(self.output_path_hint, 4, 1, 1, 3)

        layout.addLayout(grid)

        self.export_actions_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.export_actions_layout.setSpacing(12)
        self.export_actions_layout.addWidget(self.delete_png_checkbox)
        self.export_actions_layout.addStretch(1)
        self.export_actions_layout.addWidget(self.open_buffer_button)
        self.export_actions_layout.addWidget(self.convert_button)
        self.export_actions_layout.addWidget(self.cancel_button)
        layout.addLayout(self.export_actions_layout)

    def _build_progress_card(self, card: QFrame) -> None:
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._create_section_title("P", "\u8fdb\u5ea6\u9762\u677f"))

        self.progress_message = QLabel("[*] \u7b49\u5f85\u5c31\u7eea")
        self.progress_message.setObjectName("AlertBanner")
        self.progress_message.setWordWrap(True)
        layout.addWidget(self.progress_message)

        total_row = QHBoxLayout()
        total_row.setSpacing(12)
        total_row.addWidget(self._create_field_label("\u603b\u4f53\u8fdb\u5ea6"))
        total_row.addStretch(1)
        self.progress_label = QLabel("\u603b\u8fdb\u5ea6\uff1a0%")
        self.progress_label.setObjectName("SubtleValue")
        total_row.addWidget(self.progress_label)
        layout.addLayout(total_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("ModernProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_footer = QLabel(
            "\u8f6c\u6362\u8fc7\u7a0b\u4f1a\u81ea\u52a8\u6e05\u7a7a\u7f13\u5b58\u5e76\u91cd\u5efa\u8f93\u51fa\u76ee\u5f55\uff0c\u8bf7\u907f\u514d\u5c06\u4e24\u8005\u8bbe\u4e3a\u540c\u4e00\u4e2a\u8def\u5f84\u3002"
        )
        self.progress_footer.setObjectName("HelpFooter")
        self.progress_footer.setWordWrap(True)
        layout.addWidget(self.progress_footer)

    def _create_section_title(self, icon: str, text: str) -> QWidget:
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        icon_label = QLabel(icon)
        icon_label.setObjectName("SectionIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label = QLabel(text)
        text_label.setObjectName("SectionTitle")

        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch(1)
        return wrap

    def _create_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _create_metric_value(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("MetricValue")
        return label

    def _create_chip_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)
        return layout

    def _create_status_chip(self, text: str) -> QLabel:
        chip = QLabel(text)
        chip.setObjectName("StatusChip")
        chip.setProperty("active", False)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setMinimumHeight(36)
        return chip

    def _create_action_button(self, text: str, primary: bool) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("PrimaryButton" if primary else "SecondaryButton")
        button.setMinimumHeight(42)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self) -> None:
        width = self.width()

        if width < 1260:
            self.top_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.status_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.help_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        else:
            self.top_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.status_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.help_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        if width < 980:
            self.hero_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.hero_right_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.hero_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.hero_detail.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.hero_badge.setMaximumWidth(16777215)
        else:
            self.hero_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.hero_right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.hero_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.hero_detail.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.hero_badge.setMaximumWidth(220)

        if width < 1160:
            self.export_actions_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.export_actions_layout.setSpacing(10)
            self.open_buffer_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.convert_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.cancel_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.export_actions_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.export_actions_layout.setSpacing(12)
            self.open_buffer_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self.convert_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self.cancel_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#AppRoot {
                background: qradialgradient(cx:0.12, cy:0.06, radius:1.15,
                    fx:0.12, fy:0.06, stop:0 #223149, stop:0.38 #162131, stop:1 #101723);
                color: #eef4ff;
                font-family: 'Microsoft YaHei UI';
                font-size: 14px;
            }
            QWidget#ContentRoot {
                background: transparent;
            }
            QScrollArea {
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(16, 23, 35, 0.35);
                width: 10px;
                margin: 8px 4px 8px 0;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(112, 145, 188, 0.65);
                min-height: 28px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QFrame#HeroCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #24354c, stop:0.55 #1a2738, stop:1 #121c29);
                border: 1px solid #405068;
                border-radius: 24px;
            }
            QFrame#PanelCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1b2534, stop:1 #202c3d);
                border: 1px solid #2e3b50;
                border-radius: 20px;
            }
            QLabel#HeroEyebrow {
                color: #9ebce7;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 2px;
            }
            QLabel#HeroTitle {
                color: #f7fbff;
                font-size: 30px;
                font-weight: 900;
            }
            QLabel#HeroSubtitle {
                color: #d7e3f4;
                font-size: 14px;
            }
            QLabel#HeroBadge {
                min-width: 132px;
                padding: 8px 14px;
                border-radius: 16px;
                background: rgba(106, 147, 203, 0.18);
                color: #eef6ff;
                border: 1px solid #7fa4d1;
                font-size: 13px;
                font-weight: 800;
            }
            QLabel#HeroDetail {
                color: #bac9dc;
                font-size: 13px;
                font-weight: 600;
                min-width: 220px;
            }
            QLabel#SectionIcon {
                min-width: 28px;
                min-height: 28px;
                max-width: 28px;
                max-height: 28px;
                border-radius: 14px;
                background: rgba(97, 137, 190, 0.2);
                color: #9dc0f3;
                font-size: 13px;
                font-weight: 900;
            }
            QLabel#SectionTitle {
                color: #f7fbff;
                font-size: 16px;
                font-weight: 900;
            }
            QLabel#FieldLabel {
                color: #b8c7da;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#MetricValue {
                color: #ffffff;
                font-size: 18px;
                font-weight: 900;
            }
            QLabel#HintLabel {
                color: #eef3fb;
                font-size: 14px;
            }
            QLabel#HelpFooter {
                color: #aac0dc;
                font-size: 13px;
                padding: 10px 12px;
                border-radius: 12px;
                background: rgba(92, 121, 165, 0.12);
                border: 1px solid rgba(97, 126, 170, 0.35);
            }
            QLabel#SubtleValue {
                color: #d9e2ee;
                font-size: 13px;
                font-weight: 800;
            }
            QLabel#InlineHint {
                color: #9fb3ca;
                font-size: 12px;
                padding-top: 2px;
            }
            QLabel#PathCaption {
                color: #93abc8;
                font-size: 12px;
            }
            QLabel#StatusNote {
                border-radius: 12px;
                padding: 12px 14px;
                font-weight: 700;
                background: rgba(78, 110, 154, 0.18);
                color: #e6f0ff;
                border: 1px solid rgba(104, 139, 186, 0.55);
            }
            QFrame#DividerLine {
                background: #314154;
                min-height: 1px;
                max-height: 1px;
                border: none;
            }
            QLineEdit#PrimaryInput {
                min-height: 42px;
                background: #273345;
                color: #ffffff;
                border: 1px solid #586b85;
                border-radius: 12px;
                padding: 0 14px;
                selection-background-color: #6ea6ff;
            }
            QLineEdit#PrimaryInput[compact='true'] {
                min-height: 38px;
            }
            QLineEdit#PrimaryInput:focus {
                border: 1px solid #96c0ff;
                background: #2a3950;
            }
            QLabel#StatusChip {
                min-width: 96px;
                padding: 0 16px;
                border-radius: 18px;
                background: rgba(53, 68, 90, 0.72);
                color: #aebcd1;
                border: 1px solid #4d627e;
                font-size: 13px;
                font-weight: 800;
            }
            QLabel#StatusChip[active='true'] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(92, 133, 188, 0.95), stop:1 rgba(57, 92, 137, 0.95));
                color: #ffffff;
                border: 1px solid #9cc0eb;
            }
            QPushButton#PrimaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a79ae, stop:1 #2e5379);
                border: 1px solid #89b0df;
                border-radius: 12px;
                color: #ffffff;
                font-weight: 900;
                padding: 0 20px;
                min-width: 126px;
            }
            QPushButton#PrimaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5688c0, stop:1 #355e89);
            }
            QPushButton#PrimaryButton:disabled {
                background: #2a3646;
                border-color: #415062;
                color: #8c97a7;
            }
            QPushButton#SecondaryButton {
                background: #1d2837;
                border: 1px solid #677b95;
                border-radius: 12px;
                color: #eef4ff;
                font-weight: 800;
                padding: 0 18px;
                min-width: 126px;
            }
            QPushButton#SecondaryButton:hover {
                background: #253243;
            }
            QPushButton#SecondaryButton:disabled {
                background: #182230;
                border-color: #3b495a;
                color: #7e8898;
            }
            QCheckBox#CleanCheck {
                color: #edf4ff;
                font-weight: 700;
                spacing: 10px;
            }
            QCheckBox#CleanCheck::indicator {
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1px solid #7c93b0;
                background: #1e2837;
            }
            QCheckBox#CleanCheck::indicator:checked {
                background: #4b7cb8;
                border-color: #9dc1f5;
            }
            QLabel#AlertBanner {
                border-radius: 14px;
                padding: 13px 15px;
                font-weight: 800;
                background: rgba(73, 111, 153, 0.22);
                color: #e4f0ff;
                border: 1px solid #55779e;
            }
            QProgressBar#ModernProgress {
                min-height: 12px;
                max-height: 12px;
                border-radius: 6px;
                border: 1px solid #53657c;
                background: #182230;
            }
            QProgressBar#ModernProgress::chunk {
                border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6b8eb7, stop:1 #d5e0ec);
            }
            """
        )

    def _wire_events(self) -> None:
        self.browse_png_button.clicked.connect(self.choose_png_dir)
        self.browse_pdf_button.clicked.connect(self.choose_pdf_path)
        self.open_buffer_button.clicked.connect(self.open_buffer_dir)
        self.convert_button.clicked.connect(self.start_export)
        self.cancel_button.clicked.connect(self.cancel_export)
        self.delete_png_checkbox.stateChanged.connect(self.on_delete_png_changed)
        self.total_pages_edit.textChanged.connect(self.refresh_reader_state)
        self.png_dir_edit.textChanged.connect(self.refresh_reader_state)
        self.pdf_path_edit.textChanged.connect(self.refresh_reader_state)
        self.progress_signal.connect(self.apply_progress)
        self.export_finished.connect(self.on_export_finished)
        self.export_failed.connect(self.on_export_failed)
        self.missing_pages_prompt.connect(self._show_missing_pages_prompt)

    def _set_default_paths(self) -> None:
        pdf_dir = Path(r"D:\book")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        png_dir = Path.home() / "Desktop" / "png_output"
        png_dir.mkdir(parents=True, exist_ok=True)
        self.png_dir_edit.setText(str(png_dir))
        self.pdf_path_edit.setText(str(pdf_dir / self._build_default_pdf_name()))

    def _build_default_pdf_name(self) -> str:
        title = self._guess_current_book_title()
        if not title:
            return "1.pdf"
        safe_title = self._sanitize_filename(title)
        return f"{safe_title}.pdf" if safe_title else "1.pdf"

    def _guess_current_book_title(self) -> str:
        candidates: list[Path] = []
        if self.buffer_dir.exists():
            for child in self.buffer_dir.iterdir():
                if child.is_dir():
                    candidates.append(child)

        if not candidates:
            return ""

        candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for candidate in candidates:
            name = candidate.name.strip()
            if name and name.lower() != "buffer":
                return name
        return ""

    def _sanitize_filename(self, name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*]+', '_', name).strip()
        cleaned = cleaned.rstrip('.')
        return cleaned[:120]

    def _refresh_static_labels(self, state: ReaderState) -> None:
        book_title = self._guess_current_book_title() or "\u672a\u8bc6\u522b"
        self.book_name_value.setText(book_title)

        self.reader_status_value.setText("\u8fd0\u884c\u4e2d" if state.is_running else "\u672a\u542f\u52a8")

        pdf_text = self.pdf_path_edit.text().strip()
        if pdf_text:
            pdf_path = Path(pdf_text)
            self.output_name_value.setText(pdf_path.name)
            self.output_path_hint.setText(f"\u8f93\u51fa\u8def\u5f84\uff1a{pdf_path}")
        else:
            self.output_name_value.setText("\u672a\u8bbe\u7f6e")
            self.output_path_hint.setText("\u8bf7\u8bbe\u7f6e PDF \u8f93\u51fa\u8def\u5f84\u3002")

    def _build_status_note(self, state: ReaderState, blockers: list[str]) -> str:
        if not state.is_running:
            return "\u8bf7\u5148\u542f\u52a8 ssReader\uff0c\u7136\u540e\u518d\u8fdb\u884c\u72b6\u6001\u8bc6\u522b\u548c\u5bfc\u51fa\u3002"
        if state.diagnostic_message:
            return f"{state.diagnostic_message}\u3002\u5982\u679c\u4f60\u5df2\u7ecf\u77e5\u9053\u603b\u9875\u6570\uff0c\u4ecd\u53ef\u4ee5\u624b\u52a8\u586b\u5199\u540e\u7ee7\u7eed\u3002"
        if blockers:
            return blockers[0]
        return "\u5f53\u524d\u72b6\u6001\u5df2\u5c31\u7eea\uff0c\u53ef\u4ee5\u76f4\u63a5\u5f00\u59cb\u8f6c\u6362\u3002"

    def _build_log_text(self, state: ReaderState) -> str:
        if state.diagnostic_log_path is None:
            return f"\u7f13\u5b58\u76ee\u5f55\uff1a{self.buffer_dir}"
        return f"\u8bca\u65ad\u65e5\u5fd7\uff1a{state.diagnostic_log_path.name}"

    def _build_manual_pages_hint(self, state: ReaderState) -> str:
        if state.total_pages:
            return f"\u5df2\u81ea\u52a8\u8bc6\u522b\u603b\u9875\u6570\uff1a{state.total_pages}\u3002\u4f60\u4e5f\u53ef\u4ee5\u624b\u52a8\u4fee\u6539\u3002"
        if state.diagnostic_message:
            return "\u672a\u8bfb\u53d6\u5230\u9875\u6570\uff0c\u8bf7\u624b\u52a8\u586b\u5199\u603b\u9875\u6570\uff0c\u6216\u5148\u67e5\u770b\u4e0a\u65b9\u72b6\u6001\u63d0\u793a\u3002"
        return "\u53ef\u81ea\u52a8\u8bc6\u522b\u65f6\u4f1a\u81ea\u52a8\u586b\u5145\uff0c\u5982\u672a\u8bc6\u522b\u53ef\u624b\u52a8\u8f93\u5165\u3002"

    def _build_idle_progress_message(self, state: ReaderState, blockers: list[str]) -> tuple[str, bool]:
        if not state.is_running:
            return "\u8bf7\u5148\u542f\u52a8 ssReader\u3002", True
        if state.diagnostic_message:
            return state.diagnostic_message, True
        if blockers:
            return blockers[0], True
        if state.is_reading_mode:
            return "\u9605\u8bfb\u5668\u5df2\u5c31\u7eea\uff0c\u53ef\u4ee5\u5f00\u59cb\u5bfc\u51fa\u3002", False
        return "\u8bf7\u8fdb\u5165 ssReader \u9605\u8bfb\u754c\u9762\uff0c\u6216\u624b\u52a8\u586b\u5199\u603b\u9875\u6570\u540e\u7ee7\u7eed\u3002", False

    def _set_hero_state(self, state: ReaderState, blockers: list[str]) -> None:
        if not state.is_running:
            badge_text = "\u7b49\u5f85 ssReader"
        elif blockers:
            badge_text = "\u9700\u8981\u68c0\u67e5"
        else:
            badge_text = "\u5df2\u5c31\u7eea"

        self.hero_badge.setText(badge_text)

        pdf_text = self.pdf_path_edit.text().strip() or r"D:\book"
        if state.diagnostic_log_path is not None:
            detail = f"\u65e5\u5fd7\uff1a{state.diagnostic_log_path.name}\n\u8f93\u51fa\uff1a{pdf_text}"
        else:
            detail = f"\u9ed8\u8ba4\u8f93\u51fa\uff1a{pdf_text}"
        self.hero_detail.setText(detail)

    def _set_chip_active(self, chip: QLabel, active: bool) -> None:
        chip.setProperty("active", active)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
        chip.update()

    def refresh_reader_state(self) -> None:
        state = self.reader.get_state()
        self.current_reader_hwnd = state.hwnd

        self._refresh_pdf_name_if_default()
        self._refresh_static_labels(state)

        self._set_chip_active(self.foreground_chip, state.is_foreground)
        self._set_chip_active(self.background_chip, state.is_running and not state.is_foreground)
        self._set_chip_active(self.maximized_chip, state.is_maximized)
        self._set_chip_active(self.normal_chip, state.is_running and not state.is_maximized and not state.is_minimized)
        self._set_chip_active(self.minimized_chip, state.is_minimized)

        if state.total_pages and not self.total_pages_edit.text().strip():
            self.total_pages_edit.setText(str(state.total_pages))

        blockers = self._get_start_export_blockers(state)
        self.open_buffer_button.setEnabled(self.buffer_dir.exists())
        self.convert_button.setEnabled(not blockers)
        self.reader_note_label.setText(self._build_status_note(state, blockers))
        self.reader_log_label.setText(self._build_log_text(state))
        self.manual_pages_hint.setText(self._build_manual_pages_hint(state))
        self._set_hero_state(state, blockers)

        if not self.is_exporting:
            banner_message, is_error = self._build_idle_progress_message(state, blockers)
            self.apply_progress(ProgressUpdate(banner_message, 0, is_error))

    def _refresh_pdf_name_if_default(self) -> None:
        current_pdf = self.pdf_path_edit.text().strip()
        if not current_pdf:
            return
        current_path = Path(current_pdf)
        if current_path.parent != Path(r"D:\book"):
            return
        if current_path.name == "1.pdf":
            self.pdf_path_edit.setText(str(Path(r"D:\book") / self._build_default_pdf_name()))

    def _get_start_export_blockers(self, state: ReaderState) -> list[str]:
        blockers: list[str] = []
        if self.is_exporting:
            blockers.append("\u6b63\u5728\u5bfc\u51fa\uff0c\u8bf7\u52ff\u91cd\u590d\u70b9\u51fb\u3002")
            return blockers

        png_text = self.png_dir_edit.text().strip()
        pdf_text = self.pdf_path_edit.text().strip()
        total_pages_text = self.total_pages_edit.text().strip()

        if not state.is_running:
            blockers.append("ssReader \u672a\u542f\u52a8")
        if state.is_running and not state.is_maximized:
            blockers.append("\u8bf7\u5c06 ssReader \u7a97\u53e3\u6700\u5927\u5316")

        if not png_text:
            blockers.append("\u8bf7\u8bbe\u7f6e PNG \u8f93\u51fa\u76ee\u5f55")
        if not pdf_text:
            blockers.append("\u8bf7\u8bbe\u7f6e PDF \u8f93\u51fa\u8def\u5f84")
        if not total_pages_text:
            blockers.append("\u8bf7\u5148\u586b\u5199\u603b\u9875\u6570")

        pdf_path: Path | None = None
        if pdf_text:
            pdf_path = Path(pdf_text)
            if pdf_path.suffix.lower() != ".pdf":
                blockers.append("PDF \u8f93\u51fa\u6587\u4ef6\u5fc5\u987b\u4ee5 .pdf \u7ed3\u5c3e")
            if not pdf_path.parent.exists():
                blockers.append("PDF \u6240\u5728\u76ee\u5f55\u4e0d\u5b58\u5728")

        png_dir: Path | None = None
        if png_text:
            png_dir = Path(png_text)
            if not png_dir.exists():
                blockers.append("PNG \u8f93\u51fa\u76ee\u5f55\u4e0d\u5b58\u5728")

        if png_dir is not None and pdf_path is not None and png_dir == pdf_path.parent:
            blockers.append("PNG \u8f93\u51fa\u76ee\u5f55\u4e0d\u80fd\u4e0e PDF \u76ee\u5f55\u5b8c\u5168\u76f8\u540c")

        if total_pages_text and (not total_pages_text.isdigit() or int(total_pages_text) <= 0):
            blockers.append("\u603b\u9875\u6570\u5fc5\u987b\u662f\u5927\u4e8e 0 \u7684\u6574\u6570")

        return blockers

    def choose_png_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "\u9009\u62e9 PNG \u76ee\u5f55", self.png_dir_edit.text())
        if directory:
            self.png_dir_edit.setText(directory)

    def choose_pdf_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "\u9009\u62e9 PDF \u6587\u4ef6", self.pdf_path_edit.text(), "PDF Files (*.pdf)")
        if path:
            self.pdf_path_edit.setText(path)

    def open_buffer_dir(self) -> None:
        if not self.buffer_dir.exists():
            QMessageBox.information(self, "\u63d0\u793a", "\u7f13\u5b58\u76ee\u5f55\u6682\u4e0d\u5b58\u5728\u3002")
            return
        os.startfile(self.buffer_dir)

    def on_delete_png_changed(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / "pdz_png_temp"
        if self.delete_png_checkbox.isChecked():
            self.previous_png_dir = self.png_dir_edit.text().strip() or self.previous_png_dir
            temp_dir.mkdir(parents=True, exist_ok=True)
            self.png_dir_edit.setText(str(temp_dir))
            self.png_dir_edit.setEnabled(False)
            self.browse_png_button.setEnabled(False)
        else:
            self.png_dir_edit.setEnabled(True)
            self.browse_png_button.setEnabled(True)
            if self.previous_png_dir:
                self.png_dir_edit.setText(self.previous_png_dir)
        self.refresh_reader_state()

    def start_export(self) -> None:
        if self.current_reader_hwnd is None:
            QMessageBox.warning(self, "\u8b66\u544a", "\u672a\u68c0\u6d4b\u5230 ssReader \u7a97\u53e3\u3002")
            return

        blockers = self._get_start_export_blockers(self.reader.get_state())
        if blockers:
            QMessageBox.warning(self, "\u8b66\u544a", blockers[0])
            return

        png_dir = Path(self.png_dir_edit.text().strip())
        pdf_path = Path(self.pdf_path_edit.text().strip())
        config = ExportConfig(
            png_dir=png_dir,
            pdf_path=pdf_path,
            temp_buffer_dir=self.buffer_dir,
            total_pages=int(self.total_pages_edit.text().strip()),
            delete_png_after_pdf=self.delete_png_checkbox.isChecked(),
        )

        self.is_exporting = True
        self.convert_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.apply_progress(ProgressUpdate("\u6b63\u5728\u51c6\u5907\u5bfc\u51fa\u4efb\u52a1\u2026", 1))

        def worker() -> None:
            try:
                result = self.export_service.run_export(
                    hwnd=self.current_reader_hwnd,
                    config=config,
                    progress=self.progress_signal.emit,
                    ask_continue=self.ask_continue_on_missing_pages,
                )
                self.export_finished.emit(result)
            except ExportCancelled:
                self.export_failed.emit("\u5bfc\u51fa\u5df2\u53d6\u6d88")
            except Exception as exc:
                self.export_failed.emit(str(exc))

        self.export_thread = threading.Thread(target=worker, daemon=True)
        self.export_thread.start()

    def cancel_export(self) -> None:
        self.export_service.cancel()
        self.cancel_button.setEnabled(False)

    def ask_continue_on_missing_pages(self, total_pages: int, missing_pages: int) -> bool:
        if threading.current_thread() is threading.main_thread():
            return self._prompt_missing_pages_on_main_thread(total_pages, missing_pages)

        wait_event = threading.Event()
        self._pending_missing_pages_event = wait_event
        self._pending_missing_pages_answer = None
        self.missing_pages_prompt.emit(total_pages, missing_pages)
        wait_event.wait()
        answer = bool(self._pending_missing_pages_answer)
        self._pending_missing_pages_answer = None
        self._pending_missing_pages_event = None
        return answer

    def _show_missing_pages_prompt(self, total_pages: int, missing_pages: int) -> None:
        answer = self._prompt_missing_pages_on_main_thread(total_pages, missing_pages)
        self._pending_missing_pages_answer = answer
        if self._pending_missing_pages_event is not None:
            self._pending_missing_pages_event.set()

    def _prompt_missing_pages_on_main_thread(self, total_pages: int, missing_pages: int) -> bool:
        dialog_result = QMessageBox.question(
            self,
            "\u9875\u6570\u63d0\u793a",
            f"\u9884\u8ba1\u603b\u9875\u6570\u4e3a {total_pages}\uff0c\u4f46\u5f53\u524d\u4ecd\u7f3a\u5c11 {missing_pages} \u9875\u3002\u662f\u5426\u4ecd\u7136\u5408\u6210 PDF\uff1f",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return dialog_result == QMessageBox.StandardButton.Yes

    def apply_progress(self, update: ProgressUpdate) -> None:
        total_percent = max(0, min(update.percent, 100))

        self.progress_message.setText(f"[*] {update.message}")
        self.progress_bar.setValue(total_percent)
        self.progress_label.setText(f"\u603b\u8fdb\u5ea6\uff1a{total_percent}%")

        if update.is_error:
            self.progress_message.setStyleSheet(
                "background: rgba(138, 74, 88, 0.28); color: #ffc4d1; border: 1px solid #91586a; border-radius: 14px; padding: 13px 15px; font-weight: 800;"
            )
        else:
            self.progress_message.setStyleSheet(
                "background: rgba(73, 111, 153, 0.22); color: #e4f0ff; border: 1px solid #55779e; border-radius: 14px; padding: 13px 15px; font-weight: 800;"
            )

    def on_export_finished(self, result: ExportResult) -> None:
        self.is_exporting = False
        self.cancel_button.setEnabled(False)
        self.refresh_reader_state()
        if result.success:
            self.apply_progress(ProgressUpdate(result.message, 100))
            QMessageBox.information(self, "\u5bfc\u51fa\u5b8c\u6210", f"\u5df2\u751f\u6210\uff1a{result.output_pdf}")
        else:
            self.apply_progress(ProgressUpdate(result.message, 0, True))

    def on_export_failed(self, message: str) -> None:
        self.is_exporting = False
        self.cancel_button.setEnabled(False)
        self.refresh_reader_state()
        self.apply_progress(ProgressUpdate(message, 0, True))
        QMessageBox.warning(self, "\u5bfc\u51fa\u5931\u8d25", message)
