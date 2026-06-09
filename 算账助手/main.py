# -*- coding: utf-8 -*-
"""
算账助手 - PyQt5主窗口
Windows 11原生体验：圆角窗口、毛玻璃效果、系统托盘、原生通知
"""

import sys
import os

# Windows特定导入
if os.name == 'nt':
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        pass

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit, QStatusBar, QMenuBar, QMenu,
    QAction, QFileDialog, QMessageBox, QApplication, QSystemTrayIcon,
    QStyledItemDelegate, QToolButton, QSplitter, QScrollArea,
    QFrame, QGridLayout, QGroupBox, QDoubleSpinBox, QDialog,
    QProgressBar
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QBrush, QPainter, QLinearGradient

from database import Database
from parser import Importer, MessageParser
from adb_capture import ADBCapture


# ── QTableWidget 扩展方法 ──
def _table_set_columns(self, headers):
    """便捷方法：设置列标题"""
    self.setColumnCount(len(headers))
    self.setHorizontalHeaderLabels(headers)

def _table_set_column_widths(self, widths):
    """便捷方法：批量设置列宽"""
    for i, w in enumerate(widths):
        if i < self.columnCount():
            self.setColumnWidth(i, w)

QTableWidget.setColumns = _table_set_columns
QTableWidget.setColumnWidths = _table_set_column_widths

# ============== 样式表 ==============
DARK_STYLE = """
/* 全局样式 */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
}

/* 主窗口 */
QMainWindow {
    background-color: #1e1e2e;
}

/* 侧边栏按钮 */
QPushButton#nav_btn {
    background-color: transparent;
    border: none;
    text-align: left;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 14px;
    color: #6c7086;
}
QPushButton#nav_btn:hover {
    background-color: #313244;
    color: #cdd6f4;
}
QPushButton#nav_btn.selected {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
}

/* 圆角卡片 */
QFrame#card {
    background-color: #313244;
    border-radius: 12px;
    padding: 16px;
}

/* 主按钮 */
QPushButton#primary_btn {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-weight: bold;
}
QPushButton#primary_btn:hover {
    background-color: #b4befe;
}
QPushButton#primary_btn:pressed {
    background-color: #74c7ec;
}

/* 次要按钮 */
QPushButton#secondary_btn {
    background-color: #45475a;
    color: #cdd6f4;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
}
QPushButton#secondary_btn:hover {
    background-color: #585b70;
}

/* 输入框 */
QLineEdit, QTextEdit {
    background-color: #11111b;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 10px 14px;
    color: #cdd6f4;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
}

/* 下拉框 */
QComboBox {
    background-color: #11111b;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 14px;
    color: #cdd6f4;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #6c7086;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    selection-background-color: #89b4fa;
    outline: none;
}

/* 表格 */
QTableWidget {
    background-color: #11111b;
    border: 1px solid #45475a;
    border-radius: 8px;
    gridline-color: #313244;
    selection-background-color: #45475a;
}
QTableWidget::item {
    padding: 8px;
}
QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    padding: 10px;
    font-weight: bold;
}
QHeaderView::section:first {
    border-top-left-radius: 8px;
}
QHeaderView::section:last {
    border-top-right-radius: 8px;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

/* 状态栏 */
QStatusBar {
    background-color: #11111b;
    color: #6c7086;
    border-top: 1px solid #313244;
}

/* 分组框 */
QGroupBox {
    background-color: #313244;
    border-radius: 12px;
    padding: 16px;
    margin-top: 10px;
}
QGroupBox::title {
    color: #89b4fa;
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

/* 标签 */
QLabel {
    color: #cdd6f4;
}
QLabel#title {
    font-size: 24px;
    font-weight: bold;
    color: #cdd6f4;
}
QLabel#subtitle {
    font-size: 16px;
    color: #6c7086;
}
QLabel#stat_value {
    font-size: 28px;
    font-weight: bold;
    color: #89b4fa;
}
QLabel#stat_label {
    font-size: 12px;
    color: #6c7086;
}

/* 统计卡片 */
QFrame#stat_card {
    background-color: #313244;
    border-radius: 12px;
    padding: 20px;
}

/* 成功状态 */
QLabel#success {
    color: #a6e3a1;
    background-color: rgba(166, 227, 161, 0.1);
    padding: 4px 8px;
    border-radius: 4px;
}

/* 失败状态 */
QLabel#failed {
    color: #f38ba8;
    background-color: rgba(243, 139, 168, 0.1);
    padding: 4px 8px;
    border-radius: 4px;
}

/* 退码状态 */
QLabel#refund {
    color: #f9e2af;
    background-color: rgba(249, 226, 175, 0.1);
    padding: 4px 8px;
    border-radius: 4px;
}

/* 作废状态 */
QLabel#void {
    color: #6c7086;
    background-color: rgba(108, 112, 134, 0.1);
    padding: 4px 8px;
    border-radius: 4px;
    text-decoration: line-through;
}

/* 待处理状态 - v5新增 */
QLabel#pending {
    color: #89b4fa;
    background-color: rgba(137, 180, 250, 0.15);
    padding: 4px 8px;
    border-radius: 4px;
}

/* 部分成功状态 - v5新增 */
QLabel#partial {
    color: #cba6f7;
    background-color: rgba(203, 166, 247, 0.15);
    padding: 4px 8px;
    border-radius: 4px;
}

/* 托盘菜单 */
QMenu {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    padding: 8px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #45475a;
}
"""


# ============== Win11圆角支持 ==============
def set_window_rounded(hwnd, radius=15):
    """Windows 11 圆角窗口"""
    if os.name != 'nt':
        return
    
    try:
        # WS_POPUP | WS_VISIBLE
        GWL_STYLE = -16
        WS_POPUP = 0x800000
        WS_VISIBLE = 0x10000000
        
        # 设置窗口样式
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, WS_POPUP | WS_VISIBLE)
        
        # DWM圆角
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWCP_ROUND = 2
        
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, 
            ctypes.byref(ctypes.c_int(DWCP_ROUND)), 
            ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass


# ============== Windows通知 ==============
def show_windows_notification(title, message):
    """显示Windows原生通知"""
    try:
        from winotify import Notification
        toast = Notification(
            app_id="算账助手",
            title=title,
            msg=message,
            duration="short"
        )
        toast.show()
    except ImportError:
        pass
    except Exception:
        pass


# ============== 异步导入Worker ==============
class ImportWorker(QThread):
    """异步导入线程, 防止大文件导入时UI卡死"""
    progress = pyqtSignal(int, int, str)   # (current, total, message)
    finished = pyqtSignal(int, str)         # (count, group_name)
    error = pyqtSignal(str)                 # (error_message)

    def __init__(self, importer, text, group_name, is_file=False, file_path=None):
        super().__init__()
        self.importer = importer
        self.text = text
        self.group_name = group_name
        self.is_file = is_file
        self.file_path = file_path

    def run(self):
        try:
            if self.is_file and self.file_path:
                count, gname = self.importer.import_from_file(
                    self.file_path, self.group_name,
                    on_progress=lambda c, t, m: self.progress.emit(c, t, m)
                )
                self.finished.emit(count, gname)
            else:
                count = self.importer.import_from_text(
                    self.text, self.group_name,
                    on_progress=lambda c, t, m: self.progress.emit(c, t, m)
                )
                self.finished.emit(count, self.group_name)
        except Exception as e:
            self.error.emit(str(e))


# ============== 主窗口类 ==============
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化
        self.db = Database()
        self.parser = MessageParser()
        self.importer = Importer(self.db)
        self.adb = ADBCapture()
        
        # v5: 大额订单阈值
        self.large_order_threshold = 500
        
        # 界面
        self.init_ui()
        self.init_tray()
        
        # 刷新数据
        self.refresh_orders()
        self.update_status_bar()
        
        # 启动时从DB加载规则到引擎
        from lottery_engine import load_rules_from_db
        load_rules_from_db(self.db)
        
        # Win11圆角
        if os.name == 'nt':
            QTimer.singleShot(100, self._apply_round_corners)
    
    def _apply_round_corners(self):
        """应用Win11圆角"""
        try:
            hwnd = int(self.winId())
            set_window_rounded(hwnd)
        except Exception:
            pass
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("算账助手")
        self.setMinimumSize(1100, 700)
        self.resize(1200, 800)
        
        # 设置样式
        self.setStyleSheet(DARK_STYLE)
        
        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        
        # 主布局
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左侧导航
        nav_widget = self._create_nav_widget()
        main_layout.addWidget(nav_widget)
        
        # 右侧内容区
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)
        
        # 添加各页面
        self.content_stack.addWidget(self._create_import_page())    # 0
        self.content_stack.addWidget(self._create_orders_page())     # 1
        self.content_stack.addWidget(self._create_stats_page())      # 2
        self.content_stack.addWidget(self._create_period_page())     # 3
        self.content_stack.addWidget(self._create_adb_page())         # 4
        self.content_stack.addWidget(self._create_rules_page())      # 5
        self.content_stack.addWidget(self._create_settings_page())   # 6
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 默认显示导入页
        self.content_stack.setCurrentIndex(0)
        self.nav_buttons[0].setProperty("selected", True)
    
    def _create_nav_widget(self) -> QWidget:
        """创建侧边导航"""
        nav = QWidget()
        nav.setFixedWidth(220)
        nav.setStyleSheet("background-color: #11111b;")
        
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(5)
        
        # Logo/标题
        title = QLabel("算账助手")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa; padding: 15px;")
        layout.addWidget(title)
        
        # 导航按钮
        self.nav_buttons = []
        nav_items = [
            ("📥 导入数据", 0),
            ("📋 订单管理", 1),
            ("📊 统计分析", 2),
            ("🎯 期号管理", 3),
            ("📱 ADB监控", 4),
            ("📜 规则管理", 5),
            ("⚙️ 设置", 6),
        ]
        
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("nav_btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, i=index: self.switch_page(i))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        layout.addStretch()
        
        # 底部信息
        info = QLabel(f"数据: {self.db.db_path}")
        info.setStyleSheet("font-size: 10px; color: #6c7086; padding: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        return nav
    
    def switch_page(self, index: int):
        """切换页面"""
        self.content_stack.setCurrentIndex(index)
        
        # 更新导航按钮状态
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("selected", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        # 刷新数据
        if index == 1:
            self.refresh_orders()
        elif index == 2:
            self.refresh_stats()
        elif index == 3:
            self.refresh_periods()
        elif index == 4:
            self.update_adb_status()
    
    # ============== 导入页面 ==============
    def _create_import_page(self) -> QWidget:
        """导入页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("导入聊天记录")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # 群名输入
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("群名称:"))
        self.group_name_input = QLineEdit()
        self.group_name_input.setPlaceholderText("输入群名称，默认为'默认群'")
        self.group_name_input.setText("默认群")
        group_layout.addWidget(self.group_name_input)
        layout.addLayout(group_layout)
        
        # 文本框
        self.import_text = QTextEdit()
        self.import_text.setPlaceholderText(
            "粘贴微信聊天记录...\n\n"
            "支持格式:\n"
            "• [2024-01-15 12:30:45] 昵称: 内容\n"
            "• 2024-01-15 12:30:45 昵称 内容\n"
            "• 昵称: 内容"
        )
        self.import_text.setMinimumHeight(300)
        layout.addWidget(self.import_text)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        import_btn = QPushButton("📥 导入数据")
        import_btn.setObjectName("primary_btn")
        import_btn.clicked.connect(self.do_import)
        btn_layout.addWidget(import_btn)
        
        file_btn = QPushButton("📁 导入文件")
        file_btn.setObjectName("secondary_btn")
        file_btn.clicked.connect(self.import_file)
        btn_layout.addWidget(file_btn)
        
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setObjectName("secondary_btn")
        clear_btn.clicked.connect(self.import_text.clear)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 导入结果
        self.import_result = QLabel("")
        self.import_result.setStyleSheet("color: #a6e3a1; padding: 10px;")
        layout.addWidget(self.import_result)
        
        # 进度条
        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        self.import_progress.setTextVisible(True)
        self.import_progress.setStyleSheet("""
            QProgressBar { background: #313244; border: none; border-radius: 4px; height: 20px; color: #cdd6f4; }
            QProgressBar::chunk { background: #89b4fa; border-radius: 4px; }
        """)
        layout.addWidget(self.import_progress)
        
        layout.addStretch()
        return page
    
    def do_import(self):
        """执行导入(异步)"""
        text = self.import_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入聊天记录内容")
            return
        
        group_name = self.group_name_input.text().strip() or "默认群"
        
        # 显示进度条
        self.import_progress.setVisible(True)
        self.import_progress.setValue(0)
        self.import_result.setText("⏳ 正在导入...")
        
        # 启动异步导入
        self._import_worker = ImportWorker(self.importer, text, group_name)
        self._import_worker.progress.connect(self._on_import_progress)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.start()
    
    def _on_import_progress(self, current, total, message):
        """导入进度回调"""
        if total > 0:
            self.import_progress.setMaximum(total)
            self.import_progress.setValue(current)
        self.import_result.setText(f"⏳ {message}")
    
    def _on_import_finished(self, count, group_name):
        """导入完成回调"""
        self.import_progress.setVisible(False)
        
        # v5: 导入后自动标记大额订单
        if hasattr(self.db, 'mark_large_orders'):
            self.db.mark_large_orders(self.large_order_threshold)
        
        self.import_result.setText(f"✅ 成功导入 {count} 条记录")
        self.import_text.clear()
        self.update_status_bar()
        
        # Windows通知
        show_windows_notification("导入完成", f"成功导入 {count} 条记录到「{group_name}」")
        
        # 切换到订单页
        self.switch_page(1)
    
    def _on_import_error(self, error_msg):
        """导入出错回调"""
        self.import_progress.setVisible(False)
        self.import_result.setText(f"❌ 导入失败")
        QMessageBox.critical(self, "错误", f"导入失败: {error_msg}")
    
    def import_file(self):
        """从文件导入(异步)"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "文本文件 (*.txt *.log);;所有文件 (*)"
        )
        if file_path:
            group_name = self.group_name_input.text().strip() or None
            
            # 显示进度条
            self.import_progress.setVisible(True)
            self.import_progress.setValue(0)
            self.import_result.setText("⏳ 正在读取文件...")
            
            # 启动异步导入
            self._import_worker = ImportWorker(
                self.importer, "", group_name or "",
                is_file=True, file_path=file_path
            )
            self._import_worker.progress.connect(self._on_import_progress)
            self._import_worker.finished.connect(self._on_import_file_finished)
            self._import_worker.error.connect(self._on_import_error)
            self._import_worker.start()
    
    def _on_import_file_finished(self, count, group_name):
        """文件导入完成回调"""
        self.import_progress.setVisible(False)
        
        # v5: 导入后自动标记大额订单
        if hasattr(self.db, 'mark_large_orders'):
            self.db.mark_large_orders(self.large_order_threshold)
        
        self.import_result.setText(f"✅ 成功导入 {count} 条记录 (群: {group_name})")
        self.update_status_bar()
        show_windows_notification("导入完成", f"从文件导入 {count} 条记录")
    
    # ============== 订单页面 ==============
    def _create_orders_page(self) -> QWidget:
        """订单页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("订单管理")
        title.setObjectName("title")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        self.orders_count_label = QLabel("共 0 条")
        title_layout.addWidget(self.orders_count_label)
        layout.addLayout(title_layout)
        
        # 筛选栏
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("群组:"))
        self.order_group_filter = QComboBox()
        self.order_group_filter.currentIndexChanged.connect(self.refresh_orders)
        filter_layout.addWidget(self.order_group_filter)
        
        filter_layout.addWidget(QLabel("状态:"))
        self.order_status_filter = QComboBox()
        # v5: 新增待处理和部分成功状态
        self.order_status_filter.addItems(["全部", "待处理", "成功", "失败", "退码", "作废", "部分成功"])
        self.order_status_filter.currentIndexChanged.connect(self.refresh_orders)
        filter_layout.addWidget(self.order_status_filter)
        
        # v5: 大额筛选
        # v5: 类型筛选改为玩法筛选
        filter_layout.addWidget(QLabel("玩法:"))
        self.order_playtype_filter = QComboBox()
        self._refresh_playtype_filter()  # v7: 从数据库加载
        self.order_playtype_filter.currentIndexChanged.connect(self.refresh_orders)
        filter_layout.addWidget(self.order_playtype_filter)
        
        # v7: 玩法管理按钮(可自定义增删玩法分类)
        manage_pt_btn = QPushButton("⚙️")
        manage_pt_btn.setObjectName("secondary_btn")
        manage_pt_btn.setFixedSize(28, 28)
        manage_pt_btn.setToolTip("管理玩法分类")
        manage_pt_btn.clicked.connect(self.manage_play_types)
        filter_layout.addWidget(manage_pt_btn)

        filter_layout.addWidget(QLabel("类型:"))
        self.order_type_filter = QComboBox()
        self.order_type_filter.addItems(["全部", "大额"])
        self.order_type_filter.currentIndexChanged.connect(self.refresh_orders)
        filter_layout.addWidget(self.order_type_filter)
        
        filter_layout.addWidget(QLabel("搜索:"))
        self.order_search = QLineEdit()
        self.order_search.setPlaceholderText("搜索昵称/内容...")
        self.order_search.textChanged.connect(self.refresh_orders)
        filter_layout.addWidget(self.order_search)
        
        # v5: 确认下单按钮
        self.confirm_order_btn = QPushButton("✅ 确认下单")
        self.confirm_order_btn.setObjectName("secondary_btn")
        self.confirm_order_btn.clicked.connect(self.confirm_pending_orders)
        filter_layout.addWidget(self.confirm_order_btn)
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.clicked.connect(self.refresh_orders)
        filter_layout.addWidget(refresh_btn)
        
        # v6: 复制按钮 - 复制当前筛选结果到剪贴板
        copy_btn = QPushButton("📋 复制")
        copy_btn.setObjectName("secondary_btn")
        copy_btn.clicked.connect(self.copy_filtered_orders)
        filter_layout.addWidget(copy_btn)
        
        layout.addLayout(filter_layout)
        
        # v5: 表格新增💰列和实下列（列头和列宽调整）
        # v6: 表格新增玩法列
        self.orders_table = QTableWidget()
        self.orders_table.setColumns([
            "ID", "群组", "昵称", "时间", "彩种", "玩法", "💰", "金额", "实下", "状态", "内容"
        ])
        self.orders_table.setColumnWidths([50, 100, 80, 140, 50, 60, 35, 80, 80, 60, 280])
        self.orders_table.cellDoubleClicked.connect(self.on_order_cell_double_clicked)
        # v5: 右键菜单
        self.orders_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.orders_table.customContextMenuRequested.connect(self.show_order_context_menu)
        layout.addWidget(self.orders_table)
        
        return page
    
    def refresh_orders(self):
        """刷新订单列表"""
        # 更新群组筛选
        groups = self.db.get_groups()
        current = self.order_group_filter.currentText()
        self.order_group_filter.clear()
        self.order_group_filter.addItem("所有群")
        for _, name in groups:
            self.order_group_filter.addItem(name)
        
        idx = self.order_group_filter.findText(current)
        if idx >= 0:
            self.order_group_filter.setCurrentIndex(idx)
        
        # 获取筛选条件
        group_name = self.order_group_filter.currentText()
        if group_name == "所有群":
            group_name = None
        
        # v5: 扩展状态映射（含pending和partial）
        status_map = {
            "全部": "all", "待处理": "pending", "成功": "success",
            "失败": "failed", "退码": "refund", "作废": "void", "部分成功": "partial"
        }
        status = status_map.get(self.order_status_filter.currentText(), "all")
        keyword = self.order_search.text().strip() or None
        
        # v5: 大额筛选
        is_large = None
        if self.order_type_filter.currentText() == "大额":
            is_large = 1
        
        # v6: 玩法筛选 (v7: 支持多标签LIKE筛选)
        play_type_text = self.order_playtype_filter.currentText()
        play_type = None if play_type_text == "全部" else play_type_text
        if play_type_text == "未分类":
            play_type = "__uncategorized__"  # v7: 特殊标记
        
        # 查询
        if play_type == "__uncategorized__":
            # 未分类: play_type为空
            orders, total = self.db.get_orders(group_name=group_name, status=status, keyword=keyword, is_large=is_large, play_type=None)
            orders = [o for o in orders if not o.play_type]
            total = len(orders)
        else:
            orders, total = self.db.get_orders(group_name=group_name, status=status, keyword=keyword, is_large=is_large, play_type=play_type)
        
        # 更新表格（v6: 新增玩法列，索引调整）
        self.orders_table.setRowCount(len(orders))
        for i, order in enumerate(orders):
            self.orders_table.setItem(i, 0, QTableWidgetItem(str(order.id)))
            self.orders_table.setItem(i, 1, QTableWidgetItem(order.group_name))
            self.orders_table.setItem(i, 2, QTableWidgetItem(order.nickname))
            self.orders_table.setItem(i, 3, QTableWidgetItem(order.time))
            self.orders_table.setItem(i, 4, QTableWidgetItem(order.lottery_type))
            
            # v6→v7: 玩法列(多标签彩色显示)
            pt_display = order.play_type.replace(",", "·") if order.play_type else "—"
            pt_item = QTableWidgetItem(pt_display)
            if order.play_type:
                pt_item.setForeground(QColor(137, 180, 250))  # 蓝色高亮
                pt_item.setToolTip(order.play_type.replace(",", "\n"))  # hover显示每个标签
            else:
                pt_item.setForeground(QColor(108, 112, 134))  # 灰色
            self.orders_table.setItem(i, 5, pt_item)
            
            # v5: 💰列（大额标记）
            large_item = QTableWidgetItem("💰" if order.is_large == 1 else "")
            self.orders_table.setItem(i, 6, large_item)
            
            amt_item = QTableWidgetItem(f"¥{order.amount:.2f}" if order.amount > 0 else "-")
            self.orders_table.setItem(i, 7, amt_item)
            
            # v5: 实下列
            actual_text = f"¥{order.actual_amount:.2f}" if order.actual_amount > 0 else "-"
            actual_item = QTableWidgetItem(actual_text)
            actual_item.setData(Qt.UserRole, order.id)  # 存储order_id用于双击修改
            self.orders_table.setItem(i, 8, actual_item)
            
            # v5: 状态列（含pending和partial样式）
            status_item = QTableWidgetItem(order.status)
            if order.status == "success":
                status_item.setBackground(QColor(30, 60, 40))
                status_item.setForeground(QColor(166, 227, 161))  # 绿色
            elif order.status == "failed":
                status_item.setBackground(QColor(60, 30, 40))
                status_item.setForeground(QColor(243, 139, 168))  # 红色
            elif order.status == "refund":
                status_item.setBackground(QColor(60, 50, 20))
                status_item.setForeground(QColor(249, 226, 175))  # 橙黄色
            elif order.status == "void":
                status_item.setBackground(QColor(40, 40, 45))
                status_item.setForeground(QColor(108, 112, 134))  # 灰色
            elif order.status == "pending":  # v5: 待处理蓝色
                status_item.setBackground(QColor(30, 40, 60))
                status_item.setForeground(QColor(137, 180, 250))
            elif order.status == "partial":  # v5: 部分成功紫色
                status_item.setBackground(QColor(50, 30, 60))
                status_item.setForeground(QColor(203, 166, 247))
            self.orders_table.setItem(i, 9, status_item)
            
            self.orders_table.setItem(i, 10, QTableWidgetItem(order.content[:100]))
        
        self.orders_count_label.setText(f"共 {total} 条")
    
    # v5: 确认下单 - 批量将pending订单改为success或failed
    def _refresh_playtype_filter(self):
        """v7: 从数据库加载玩法分类到筛选下拉框"""
        current = self.order_playtype_filter.currentText() if hasattr(self, 'order_playtype_filter') else ""
        self.order_playtype_filter.clear()
        self.order_playtype_filter.addItem("全部")
        categories = self.db.get_play_type_categories() if self.db else Database.DEFAULT_PLAY_TYPES
        for pt in categories:
            self.order_playtype_filter.addItem(pt)
        self.order_playtype_filter.addItem("未分类")
        # 恢复之前选中
        idx = self.order_playtype_filter.findText(current)
        if idx >= 0:
            self.order_playtype_filter.setCurrentIndex(idx)

    def manage_play_types(self):
        """v7: 管理玩法分类对话框 - 用户可自定义增删玩法"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QHBoxLayout, \
            QPushButton, QLineEdit, QMessageBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("管理玩法分类")
        dialog.setMinimumSize(300, 400)
        layout = QVBoxLayout(dialog)
        
        # 说明
        layout.addWidget(QLabel("玩法分类列表（可增删，不锁死）："))
        
        # 列表
        list_widget = QListWidget()
        categories = self.db.get_play_type_categories()
        for pt in categories:
            list_widget.addItem(pt)
        layout.addWidget(list_widget)
        
        # 输入框 + 添加按钮
        add_layout = QHBoxLayout()
        input_field = QLineEdit()
        input_field.setPlaceholderText("输入新玩法名称...")
        add_layout.addWidget(input_field)
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(lambda: (
            list_widget.addItem(input_field.text()) if input_field.text().strip() else None,
            input_field.clear()
        ))
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)
        
        # 删除按钮
        del_btn = QPushButton("删除选中")
        def remove_selected():
            for item in list_widget.selectedItems():
                list_widget.takeItem(list_widget.row(item))
        del_btn.clicked.connect(remove_selected)
        layout.addWidget(del_btn)
        
        # 恢复默认
        reset_btn = QPushButton("恢复默认")
        def reset_default():
            list_widget.clear()
            for pt in Database.DEFAULT_PLAY_TYPES:
                list_widget.addItem(pt)
        reset_btn.clicked.connect(reset_default)
        layout.addWidget(reset_btn)
        
        # 保存/取消
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        def save_categories():
            cats = [list_widget.item(i).text() for i in range(list_widget.count())]
            self.db.save_play_type_categories(cats)
            self._refresh_playtype_filter()
            dialog.accept()
            QMessageBox.information(self, "已保存", f"玩法分类已更新，共{len(cats)}个")
        save_btn.clicked.connect(save_categories)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec_()

    def copy_filtered_orders(self):
        """v6: 复制当前筛选结果到剪贴板，按玩法分类复制"""
        from PyQt5.QtWidgets import QApplication
        
        # 获取当前筛选条件
        group_name = self.order_group_filter.currentText()
        if group_name == "所有群":
            group_name = None
        play_type_text = self.order_playtype_filter.currentText()
        play_type = None if play_type_text == "全部" else play_type_text
        
        # 查询当前筛选结果（不限条数）
        if play_type_text == "未分类":
            orders, total = self.db.get_orders(
                group_name=group_name, play_type=None, limit=10000)
            orders = [o for o in orders if not o.play_type]
            total = len(orders)
        else:
            orders, total = self.db.get_orders(
                group_name=group_name, play_type=play_type, limit=10000)
        
        if not orders:
            QMessageBox.information(self, "提示", "当前筛选无数据")
            return
        
        # 纯内容复制（适合粘贴到微信/QQ）
        content_lines = [o.content for o in orders if o.amount > 0]
        content_text = "\n".join(content_lines)
        
        # 格式化表格复制（适合粘贴到Excel）
        lines = []
        lines.append(f"{'ID':<6}{'群组':<12}{'昵称':<10}{'时间':<20}{'彩种':<5}{'玩法':<8}{'金额':<10}{'内容'}")
        lines.append("-" * 80)
        total_amt = 0
        for o in orders:
            total_amt += o.amount
            pt = o.play_type.replace(",", "·") if o.play_type else "—"
            line = f"{o.id:<6}{o.group_name:<12}{o.nickname:<10}{o.time:<20}{o.lottery_type:<5}{pt:<8}¥{o.amount:.0f}{'':<6}{o.content[:60]}"
            lines.append(line)
        lines.append("-" * 80)
        lines.append(f"共{total}条 | 合计¥{total_amt:.2f}")
        table_text = "\n".join(lines)
        
        # 默认复制纯内容（微信友好）
        QApplication.clipboard().setText(content_text)
        
        # 保存格式化文本供右键菜单用
        self._last_table_copy = table_text
        
        QMessageBox.information(self, "已复制", 
            f"已复制{total}条数据到剪贴板\n合计: ¥{total_amt:.2f}\n\n格式: 每行一条原始消息\n可直接粘贴到微信/QQ")

    def confirm_pending_orders(self):
        """弹出对话框选择成功/失败，批量更新选中的pending订单"""
        selected_rows = set(item.row() for item in self.orders_table.selectedItems())
        if not selected_rows:
            QMessageBox.warning(self, "提示", "请先选中要确认的订单行")
            return
        
        # 收集选中的pending订单ID
        pending_ids = []
        for row in selected_rows:
            status_item = self.orders_table.item(row, 9)  # v6: 状态列(索引9)
            if status_item and status_item.text() == "pending":
                id_item = self.orders_table.item(row, 0)
                if id_item:
                    pending_ids.append(int(id_item.text()))
        
        if not pending_ids:
            QMessageBox.warning(self, "提示", "选中的订单中没有待处理状态的订单")
            return
        
        # 弹出确认对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("确认下单")
        dialog.setMinimumWidth(300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f"确定将 {len(pending_ids)} 条待处理订单标记为:"))
        
        btn_layout = QHBoxLayout()
        success_btn = QPushButton("✅ 成功")
        success_btn.setObjectName("primary_btn")
        success_btn.clicked.connect(lambda: self._do_confirm_orders(pending_ids, "success", dialog))
        btn_layout.addWidget(success_btn)
        
        failed_btn = QPushButton("❌ 失败")
        failed_btn.setObjectName("secondary_btn")
        failed_btn.clicked.connect(lambda: self._do_confirm_orders(pending_ids, "failed", dialog))
        btn_layout.addWidget(failed_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        dialog.exec_()
    
    def _do_confirm_orders(self, order_ids, status, dialog):
        """执行批量更新订单状态"""
        count = self.db.batch_update_status(order_ids, status)
        dialog.accept()
        self.refresh_orders()
        self.update_status_bar()
        QMessageBox.information(self, "完成", f"✅ 已将 {count} 条订单标记为「{status}」")
    
    # v5: 双击单元格修改实下金额
    def on_order_cell_double_clicked(self, row, col):
        """双击实下列（第8列）弹出修改对话框"""
        if col != 8:  # v6: 实下列索引8
            return
        
        order_id_item = self.orders_table.item(row, 0)
        if not order_id_item:
            return
        order_id = int(order_id_item.text())
        
        # 获取当前实下金额
        current_item = self.orders_table.item(row, 8)
        current_val = current_item.text().replace("¥", "").replace("-", "0") if current_item else "0"
        
        # 弹出输入对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("修改实下金额")
        dialog.setMinimumWidth(300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f"订单ID: {order_id}"))
        layout.addWidget(QLabel("请输入实下金额:"))
        
        input_layout = QHBoxLayout()
        input_box = QLineEdit()
        input_box.setText(current_val)
        input_box.setPlaceholderText("请输入实下金额")
        input_layout.addWidget(input_box)
        layout.addLayout(input_layout)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确认")
        ok_btn.setObjectName("primary_btn")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec_() == QDialog.Accepted:
            try:
                new_amount = float(input_box.text())
                self.db.update_order(order_id, actual_amount=new_amount)
                self.refresh_orders()
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的金额")
    
    # v5: 右键菜单
    def show_order_context_menu(self, pos):
        """订单表格右键菜单"""
        row = self.orders_table.currentRow()
        if row < 0:
            return
        
        status_item = self.orders_table.item(row, 9)  # v6: 状态列索引9
        if not status_item:
            return
        
        menu = QMenu()
        
        # 标记部分成功
        if status_item.text() == "pending":
            partial_action = QAction("🎯 标记为部分成功", self)
            partial_action.triggered.connect(lambda: self.mark_partial_success(row))
            menu.addAction(partial_action)
        
        # 其他右键功能可继续扩展
        menu.exec_(self.orders_table.viewport().mapToGlobal(pos))
    
    def mark_partial_success(self, row):
        """标记订单为部分成功，弹出输入成功金额"""
        order_id_item = self.orders_table.item(row, 0)
        if not order_id_item:
            return
        order_id = int(order_id_item.text())
        
        dialog = QDialog(self)
        dialog.setWindowTitle("标记部分成功")
        dialog.setMinimumWidth(300)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f"订单ID: {order_id}"))
        layout.addWidget(QLabel("请输入实际成功的金额:"))
        
        input_layout = QHBoxLayout()
        input_box = QLineEdit()
        input_box.setPlaceholderText("请输入成功金额")
        input_layout.addWidget(input_box)
        layout.addLayout(input_layout)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确认")
        ok_btn.setObjectName("primary_btn")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec_() == QDialog.Accepted:
            try:
                success_amount = float(input_box.text())
                self.db.update_order(order_id, status="partial", actual_amount=success_amount)
                self.refresh_orders()
                self.update_status_bar()
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的金额")
    
    # ============== 统计页面 ==============
    def _create_stats_page(self) -> QWidget:
        """统计页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        title = QLabel("数据统计")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # 统计卡片区
        self.stats_cards = QGridLayout()
        self.stats_cards.setSpacing(15)
        layout.addLayout(self.stats_cards)
        
        # v5: 按群统计 - 动态创建，初始为空占位
        self.group_stats_box_widget = QGroupBox("按群统计")
        placeholder_layout = QVBoxLayout(self.group_stats_box_widget)
        placeholder_label = QLabel("加载中...")
        placeholder_label.setStyleSheet("color: #6c7086;")
        placeholder_layout.addWidget(placeholder_label)
        layout.addWidget(self.group_stats_box_widget)
        
        # 保存布局引用用于动态替换
        self.stats_page_layout = layout
        
        # 作废/退码明细
        void_box = QGroupBox("⚠️ 作废 / 退码明细（不计入统计）")
        void_box.setStyleSheet("QGroupBox { border: 1px solid #45475a; } QGroupBox::title { color: #f9e2af; }")
        void_layout = QVBoxLayout(void_box)
        self.void_table = QTableWidget()
        self.void_table.setColumns(["昵称", "群组", "状态", "金额", "条数"])
        self.void_table.setColumnWidths([100, 120, 60, 100, 60])
        void_layout.addWidget(self.void_table)
        layout.addWidget(void_box)
        
        # 作废/退码明细（初始为空，由refresh_stats填充）
        
        # 按人统计
        player_box = QGroupBox("按人统计（Top 20）")
        player_layout = QVBoxLayout(player_box)
        self.player_stats_table = QTableWidget()
        self.player_stats_table.setColumns(["昵称", "群组", "订单数", "总金额"])
        self.player_stats_table.setColumnWidths([100, 120, 80, 100])
        player_layout.addWidget(self.player_stats_table)
        layout.addWidget(player_box)
        
        layout.addStretch()
        return page
    
    def refresh_stats(self):
        """刷新统计数据"""
        # 获取统计
        stats = self.db.get_statistics()
        profit = self.db.get_profit_stats()
        
        # 清空并重建卡片
        while self.stats_cards.count():
            child = self.stats_cards.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # v5: 统计卡片（含pending和partial）
        cards_data = [
            ("总订单", str(stats["total"]), "#89b4fa"),
            ("有效订单", str(stats.get("effective", stats["total"])), "#74c7ec"),
            ("待处理", str(stats.get("pending", 0)), "#89b4fa"),  # v5新增
            ("成功", str(stats["success"]), "#a6e3a1"),
            ("失败", str(stats["failed"]), "#f38ba8"),
            ("部分成功", str(stats.get("partial", 0)), "#cba6f7"),  # v5新增
            ("退码", str(stats["refund"]), "#f9e2af"),
            ("作废", str(stats.get("void", 0)), "#6c7086"),
            # v5: 总下注优先用actual_amount计算（由db.get_statistics处理）
            ("总下注", f"¥{stats['success_amount']:.2f}", "#89b4fa"),
            ("总盈利", f"¥{stats.get('profit', 0):.2f}", "#a6e3a1" if stats.get('profit', 0) >= 0 else "#f38ba8"),
            ("参与人数", str(profit["player_count"]), "#cba6f7"),
            ("人均下注", f"¥{profit['total_bet']/max(profit['player_count'],1):.2f}", "#94e2d5"),
        ]
        
        for i, (label, value, color) in enumerate(cards_data):
            card = QFrame()
            card.setObjectName("stat_card")
            card_layout = QVBoxLayout(card)
            
            val_label = QLabel(value)
            val_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
            val_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(val_label)
            
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #6c7086; font-size: 12px;")
            lbl.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(lbl)
            
            self.stats_cards.addWidget(card, i // 4, i % 4)
        
        # v5: 按群统计 - 卡片式布局
        # 先清空旧容器
        if hasattr(self, 'group_stats_scroll'):
            self.group_stats_scroll.deleteLater()
        
        group_stats_box = QGroupBox("按群统计")
        group_stats_layout = QVBoxLayout(group_stats_box)
        
        # 使用QScrollArea横向滚动
        self.group_stats_scroll = QScrollArea()
        self.group_stats_scroll.setWidgetResizable(True)
        self.group_stats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.group_stats_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.group_stats_scroll.setMinimumHeight(160)
        self.group_stats_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        # 获取每个群的统计数据
        per_group_stats = self.db.get_per_group_statistics()
        
        # 横向卡片容器
        cards_container = QWidget()
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setSpacing(15)
        cards_layout.setContentsMargins(0, 10, 20, 10)
        
        for gstat in per_group_stats:
            # 每个群一个卡片
            card = QFrame()
            card.setFixedWidth(200)
            card.setStyleSheet("""
                QFrame {
                    background-color: #313244;
                    border-radius: 12px;
                    padding: 15px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(8)
            
            # 群名标题
            name_label = QLabel(gstat['group_name'])
            name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
            card_layout.addWidget(name_label)
            
            # 总订单
            total_label = QLabel(f"总订单: {gstat['total']}")
            total_label.setStyleSheet("color: #cdd6f4;")
            card_layout.addWidget(total_label)
            
            # 金额
            amount_label = QLabel(f"💰 总金额: ¥{gstat.get('amount', 0):.2f}")
            amount_label.setStyleSheet("color: #f9e2af;")
            card_layout.addWidget(amount_label)
            
            # 状态标签行
            tags_layout = QHBoxLayout()
            tags_layout.setSpacing(5)
            
            # 待处理（蓝色）
            pending_label = QLabel(f"⏳ {gstat.get('pending', 0)}")
            pending_label.setStyleSheet("color: #89b4fa; background-color: rgba(137,180,250,0.15); padding: 2px 6px; border-radius: 4px;")
            tags_layout.addWidget(pending_label)
            
            # 成功（绿色）
            success_label = QLabel(f"✅ {gstat.get('success', 0)}")
            success_label.setStyleSheet("color: #a6e3a1; background-color: rgba(166,227,161,0.15); padding: 2px 6px; border-radius: 4px;")
            tags_layout.addWidget(success_label)
            
            # 失败（红色）
            failed_label = QLabel(f"❌ {gstat.get('failed', 0)}")
            failed_label.setStyleSheet("color: #f38ba8; background-color: rgba(243,139,168,0.15); padding: 2px 6px; border-radius: 4px;")
            tags_layout.addWidget(failed_label)
            
            # 部分成功（紫色）
            partial_label = QLabel(f"🎯 {gstat.get('partial', 0)}")
            partial_label.setStyleSheet("color: #cba6f7; background-color: rgba(203,166,247,0.15); padding: 2px 6px; border-radius: 4px;")
            tags_layout.addWidget(partial_label)
            
            card_layout.addLayout(tags_layout)
            
            # 第二行标签
            tags_layout2 = QHBoxLayout()
            tags_layout2.setSpacing(5)
            
            # 退码（黄色）
            refund_label = QLabel(f"↩️ {gstat.get('refund', 0)}")
            refund_label.setStyleSheet("color: #f9e2af; background-color: rgba(249,226,175,0.15); padding: 2px 6px; border-radius: 4px;")
            tags_layout2.addWidget(refund_label)
            
            # 作废（灰色）
            void_label = QLabel(f"🚫 {gstat.get('void', 0)}")
            void_label.setStyleSheet("color: #6c7086; background-color: rgba(108,112,134,0.15); padding: 2px 6px; border-radius: 4px;")
            tags_layout2.addWidget(void_label)
            
            tags_layout2.addStretch()
            card_layout.addLayout(tags_layout2)
            
            card_layout.addStretch()
            cards_layout.addWidget(card)
        
        # 如果没有群数据，显示提示
        if not per_group_stats:
            no_data = QLabel("暂无群组数据")
            no_data.setStyleSheet("color: #6c7086; padding: 20px;")
            cards_layout.addWidget(no_data)
        
        cards_layout.addStretch()
        
        self.group_stats_scroll.setWidget(cards_container)
        group_stats_layout.addWidget(self.group_stats_scroll)
        
        # 替换旧的group_box
        if hasattr(self, 'group_stats_box_widget'):
            old_idx = self.stats_page_layout.indexOf(self.group_stats_box_widget)
            if old_idx >= 0:
                self.stats_page_layout.removeWidget(self.group_stats_box_widget)
                self.group_stats_box_widget.deleteLater()
        self.group_stats_box_widget = group_stats_box
        
        # 插入到统计卡片后面（index 2）
        self.stats_page_layout.insertWidget(2, group_stats_box)
        
        self.group_stats_table.setRowCount(len(group_stats))
        for i, row in enumerate(group_stats):
            for j, val in enumerate(row):
                self.group_stats_table.setItem(i, j, QTableWidgetItem(str(val)))
        
        # 按人统计
        players = profit["players"][:20]
        self.player_stats_table.setRowCount(len(players))
        for i, p in enumerate(players):
            self.player_stats_table.setItem(i, 0, QTableWidgetItem(p["nickname"]))
            self.player_stats_table.setItem(i, 1, QTableWidgetItem(p["group_name"] or ""))
            self.player_stats_table.setItem(i, 2, QTableWidgetItem(str(p["bet_count"])))
            self.player_stats_table.setItem(i, 3, QTableWidgetItem(f"¥{p['total_bet']:.2f}"))
    
    # ============== 期号管理页面 ==============
    def _create_period_page(self) -> QWidget:
        """期号管理页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        title = QLabel("期号管理")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # 录入区
        input_box = QGroupBox("录入开奖号码")
        input_layout = QHBoxLayout(input_box)
        
        input_layout.addWidget(QLabel("期号:"))
        self.period_input = QLineEdit()
        self.period_input.setPlaceholderText("如: 2024015")
        input_layout.addWidget(self.period_input)
        
        input_layout.addWidget(QLabel("彩种:"))
        self.period_lottery = QComboBox()
        self.period_lottery.addItems(["体", "福", "其他"])
        input_layout.addWidget(self.period_lottery)
        
        input_layout.addWidget(QLabel("开奖号:"))
        self.period_code = QLineEdit()
        self.period_code.setPlaceholderText("如: 12345")
        input_layout.addWidget(self.period_code)
        
        add_btn = QPushButton("➕ 添加")
        add_btn.setObjectName("primary_btn")
        add_btn.clicked.connect(self.add_period)
        input_layout.addWidget(add_btn)
        
        layout.addWidget(input_box)
        
        # 期号列表
        list_box = QGroupBox("期号列表")
        list_layout = QVBoxLayout(list_box)
        
        self.periods_table = QTableWidget()
        self.periods_table.setColumns(["期号", "彩种", "开奖号码", "添加时间", "操作"])
        self.periods_table.setColumnWidths([120, 60, 100, 150, 80])
        self.periods_table.cellClicked.connect(self.on_period_cell_clicked)
        list_layout.addWidget(self.periods_table)
        
        layout.addWidget(list_box)
        
        # 计算中奖
        calc_box = QGroupBox("计算中奖结果")
        calc_layout = QHBoxLayout(calc_box)
        
        self.calc_period_combo = QComboBox()
        calc_layout.addWidget(QLabel("选择期号:"))
        calc_layout.addWidget(self.calc_period_combo)
        
        calc_btn = QPushButton("📊 计算中奖")
        calc_btn.setObjectName("primary_btn")
        calc_btn.clicked.connect(self.calculate_winnings)
        calc_layout.addWidget(calc_btn)
        
        calc_layout.addStretch()
        layout.addWidget(calc_box)
        
        # 结果显示
        self.period_result = QLabel("")
        self.period_result.setStyleSheet("background-color: #313244; padding: 15px; border-radius: 8px;")
        self.period_result.setWordWrap(True)
        layout.addWidget(self.period_result)
        
        return page
    
    def refresh_periods(self):
        """刷新期号列表"""
        periods = self.db.get_all_periods()
        
        self.periods_table.setRowCount(len(periods))
        for i, p in enumerate(periods):
            self.periods_table.setItem(i, 0, QTableWidgetItem(p["period"]))
            self.periods_table.setItem(i, 1, QTableWidgetItem(p["lottery_type"]))
            self.periods_table.setItem(i, 2, QTableWidgetItem(p["open_code"]))
            self.periods_table.setItem(i, 3, QTableWidgetItem(p.get("open_time", "")[:19]))
            self.periods_table.setItem(i, 4, QTableWidgetItem("删除"))
            self.periods_table.item(i, 4).setForeground(QColor("#f38ba8"))
        
        # 更新计算下拉框
        self.calc_period_combo.clear()
        for p in periods:
            self.calc_period_combo.addItem(p["period"])
    
    def add_period(self):
        """添加期号"""
        period = self.period_input.text().strip()
        lottery = self.period_lottery.currentText()
        code = self.period_code.text().strip()
        
        if not period or not code:
            QMessageBox.warning(self, "提示", "请填写期号和开奖号码")
            return
        
        self.db.add_period(period, lottery, code)
        self.period_input.clear()
        self.period_code.clear()
        self.refresh_periods()
        show_windows_notification("添加成功", f"期号 {period} 开奖号码 {code}")
    
    def calculate_winnings(self):
        """计算中奖"""
        period = self.calc_period_combo.currentText()
        if not period:
            return
        
        result = self.db.calculate_winnings(period)
        
        if "error" in result:
            self.period_result.setText(f"❌ {result['error']}")
            return
        
        text = f"""
        <b>期号:</b> {result['period']} | <b>彩种:</b> {result['lottery_type']} | <b>开奖:</b> {result['open_code']}<br>
        <b>总订单:</b> {result['total_orders']} | <b>中奖:</b> {result['winners_count']} | <b>未中:</b> {result['losers_count']}<br>
        <b>总下注:</b> ¥{result['total_bet']:.2f} | <b>总奖金:</b> ¥{result.get('total_prize', 0):.2f} | <b>盈亏:</b> <span style="color: {'#a6e3a1' if result.get('net_result', 0) >= 0 else '#f38ba8'}">¥{result.get('net_result', 0):.2f}</span>
        """
        
        if result["winners"]:
            text += "<br><br><b>中奖名单:</b><br>"
            for w in result["winners"]:
                pt = w.get('play_type', '')
                win_prize = w.get('win_prize', 0)
                net = w.get('net_profit', 0)
                detail = w.get('win_detail', '')
                text += f"• {w['nickname']}: [{pt}] {w['content'][:40]} → {detail} | 奖金¥{win_prize:.0f} 盈亏¥{net:.0f}<br>"
        
        self.period_result.setText(text)
    
    def on_period_cell_clicked(self, row, col):
        """期号表格点击"""
        if col == 4:
            period = self.periods_table.item(row, 0).text()
            if QMessageBox.question(self, "确认", f"确定删除期号 {period}?") == QMessageBox.Yes:
                self.db.delete_period(period)
                self.refresh_periods()
    
    # ============== ADB页面 ==============
    def _create_adb_page(self) -> QWidget:
        """ADB监控页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        title = QLabel("ADB监控")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # 连接状态
        status_box = QGroupBox("设备连接")
        status_layout = QHBoxLayout(status_box)
        
        self.adb_status_label = QLabel("状态: 未检查")
        status_layout.addWidget(self.adb_status_label)
        
        self.adb_path_label = QLabel("ADB路径: 正在检测...")
        status_layout.addWidget(self.adb_path_label)
        
        connect_btn = QPushButton("🔗 连接设备")
        connect_btn.setObjectName("primary_btn")
        connect_btn.clicked.connect(self.adb_connect)
        status_layout.addWidget(connect_btn)
        
        layout.addWidget(status_box)
        
        # 监控控制
        control_box = QGroupBox("监控控制")
        control_layout = QHBoxLayout(control_box)
        
        control_layout.addWidget(QLabel("轮询间隔:"))
        self.adb_interval = QComboBox()
        self.adb_interval.addItems(["3秒", "5秒", "10秒", "30秒"])
        self.adb_interval.setCurrentIndex(1)
        control_layout.addWidget(self.adb_interval)
        
        self.adb_monitor_btn = QPushButton("▶️ 开始监控")
        self.adb_monitor_btn.setObjectName("primary_btn")
        self.adb_monitor_btn.clicked.connect(self.toggle_adb_monitor)
        control_layout.addWidget(self.adb_monitor_btn)
        
        self.adb_capture_count = QLabel("已捕获: 0 条")
        control_layout.addWidget(self.adb_capture_count)
        
        layout.addWidget(control_box)
        
        # 日志
        log_box = QGroupBox("捕获日志")
        log_layout = QVBoxLayout(log_box)
        
        self.adb_log = QTextEdit()
        self.adb_log.setReadOnly(True)
        self.adb_log.setMaximumHeight(200)
        log_layout.addWidget(self.adb_log)
        
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setObjectName("secondary_btn")
        clear_log_btn.clicked.connect(self.adb_log.clear)
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_box)
        
        # 说明
        info = QLabel(
            "使用说明:\n"
            "1. 手机开启USB调试模式\n"
            "2. 使用数据线连接电脑\n"
            "3. 在手机上授权USB调试\n"
            "4. 点击「连接设备」\n"
            "5. 点击「开始监控」自动捕获微信消息"
        )
        info.setStyleSheet("background-color: #313244; padding: 15px; border-radius: 8px; line-height: 1.8;")
        layout.addWidget(info)
        
        layout.addStretch()
        return page
    
    def update_adb_status(self):
        """更新ADB状态"""
        status = self.adb.get_connection_status()
        
        if status["adb_available"]:
            self.adb_path_label.setText(f"ADB路径: {status['adb_path']}")
        else:
            self.adb_path_label.setText("ADB: 未找到 (请安装Android SDK)")
        
        if status["connected"]:
            self.adb_status_label.setText(f"✅ 已连接: {status['device_id']}")
        else:
            self.adb_status_label.setText("❌ 未连接")
        
        self.adb_capture_count.setText(f"已捕获: {status['captured_count']} 条")
    
    def adb_connect(self):
        """连接设备"""
        success, msg = self.adb.connect()
        self.adb_log.append(msg)
        self.update_adb_status()
        
        if success:
            show_windows_notification("连接成功", msg)
        else:
            QMessageBox.warning(self, "连接失败", msg)
    
    def toggle_adb_monitor(self):
        """切换监控状态"""
        if self.adb.running:
            self.adb.stop_monitor()
            self.adb_monitor_btn.setText("▶️ 开始监控")
            self.adb_log.append("⏹️ 监控已停止")
        else:
            interval_map = {"3秒": 3, "5秒": 5, "10秒": 10, "30秒": 30}
            interval = interval_map.get(self.adb_interval.currentText(), 5)
            
            self.adb.start_monitor(callback=self.on_adb_message, interval=interval)
            self.adb_monitor_btn.setText("⏹️ 停止监控")
            self.adb_log.append("▶️ 开始监控微信消息...")
    
    def on_adb_message(self, msg: dict):
        """ADB捕获到消息"""
        self.adb_log.append(f"[{msg['time'][11:]}] {msg['nickname']}: {msg['content'][:60]}")
        
        # 自动导入
        try:
            count = self.importer.import_from_text(
                f"{msg['nickname']}: {msg['content']}",
                msg.get('group_name', 'ADB捕获')
            )
            self.update_status_bar()
        except Exception:
            pass
        
        self.adb_capture_count.setText(f"已捕获: {self.adb.captured_count} 条")
    
    # ============== 规则管理页面 ==============
    def _create_rules_page(self) -> QWidget:
        """规则管理页面"""
        from PyQt5.QtWidgets import (QDialog, QFormLayout, QDialogButtonBox,
                                      QSpinBox, QDoubleSpinBox, QCheckBox)
        import json

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        title = QLabel("规则管理")
        title.setObjectName("title")
        layout.addWidget(title)

        desc = QLabel("💡 所有玩法赔率/本金均可直接修改，修改后点击「应用规则」生效")
        desc.setStyleSheet("color: #6c7086; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ── 分类筛选 + 操作按钮 ──
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("分类:"))
        self.rules_cat_filter = QComboBox()
        self.rules_cat_filter.addItem("全部")
        self.rules_cat_filter.currentTextChanged.connect(self._filter_rules_table)
        top_bar.addWidget(self.rules_cat_filter)

        apply_btn = QPushButton("✅ 应用规则")
        apply_btn.setObjectName("primary_btn")
        apply_btn.clicked.connect(self._apply_rules)
        top_bar.addWidget(apply_btn)

        reset_btn = QPushButton("🔄 恢复默认")
        reset_btn.setObjectName("secondary_btn")
        reset_btn.clicked.connect(self._reset_rules)
        top_bar.addWidget(reset_btn)

        add_btn = QPushButton("➕ 新增规则")
        add_btn.setObjectName("secondary_btn")
        add_btn.clicked.connect(self._add_rule_dialog)
        top_bar.addWidget(add_btn)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # ── 规则表格 ──
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(8)
        self.rules_table.setHorizontalHeaderLabels([
            "玩法", "分类", "赔率类型", "赔率/倍数", "查表字段",
            "赔率表(JSON)", "奖金", "备注"
        ])
        header = self.rules_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        self.rules_table.setAlternatingRowColors(True)
        self.rules_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        layout.addWidget(self.rules_table)

        # ── 操作按钮行 ──
        btn_bar = QHBoxLayout()
        save_btn = QPushButton("💾 保存修改")
        save_btn.setObjectName("primary_btn")
        save_btn.clicked.connect(self._save_rules_edit)
        btn_bar.addWidget(save_btn)

        del_btn = QPushButton("🗑️ 删除选中")
        del_btn.setObjectName("secondary_btn")
        del_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e;")
        del_btn.clicked.connect(self._delete_selected_rule)
        btn_bar.addWidget(del_btn)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # 初始加载
        self._refresh_rules_table()
        return page

    def _refresh_rules_table(self):
        """刷新规则表格"""
        import json
        rules = self.db.get_all_rules()
        self.rules_table.setRowCount(len(rules))

        # 刷新分类筛选器
        cats = set(r["category"] for r in rules)
        current = self.rules_cat_filter.currentText()
        self.rules_cat_filter.blockSignals(True)
        self.rules_cat_filter.clear()
        self.rules_cat_filter.addItem("全部")
        for c in sorted(cats):
            self.rules_cat_filter.addItem(c)
        idx = self.rules_cat_filter.findText(current)
        if idx >= 0:
            self.rules_cat_filter.setCurrentIndex(idx)
        self.rules_cat_filter.blockSignals(False)

        # 颜色映射
        cat_colors = {
            "基础玩法": "#89b4fa",
            "包号/复式": "#a6e3a1",
            "查表玩法": "#f9e2af",
            "胆拖": "#cba6f7",
            "大小单双": "#fab387",
            "粘边赖": "#f38ba8",
            "直选复式": "#74c7ec",
            "自定义": "#6c7086",
        }

        for i, r in enumerate(rules):
            # 存play_type到行数据
            item0 = QTableWidgetItem(f"{r['display_name']}\n({r['play_type']})")
            item0.setData(Qt.UserRole, r["play_type"])
            item0.setFlags(item0.flags() & ~Qt.ItemIsEditable)
            self.rules_table.setItem(i, 0, item0)

            cat_item = QTableWidgetItem(r["category"])
            color = QColor(cat_colors.get(r["category"], "#6c7086"))
            cat_item.setForeground(color)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsEditable)
            self.rules_table.setItem(i, 1, cat_item)

            ot = r["odds_type"]
            ot_label = {"fixed": "固定赔率", "by_key": "按key查赔率", "principal_table": "本金表+奖金"}[ot]
            ot_item = QTableWidgetItem(ot_label)
            ot_item.setData(Qt.UserRole, ot)
            ot_item.setFlags(ot_item.flags() & ~Qt.ItemIsEditable)
            self.rules_table.setItem(i, 2, ot_item)

            # 赔率值
            odds_val = r["odds_value"] if ot == "fixed" else 0
            self.rules_table.setItem(i, 3, QTableWidgetItem(str(odds_val)))

            # key字段
            self.rules_table.setItem(i, 4, QTableWidgetItem(r.get("key_field", "")))

            # 赔率表/本金表JSON
            raw_json = r.get("odds_json", "") if ot == "by_key" else r.get("principal_json", "")
            try:
                display_json = json.dumps(json.loads(raw_json), ensure_ascii=False) if raw_json else ""
            except Exception:
                display_json = raw_json
            self.rules_table.setItem(i, 5, QTableWidgetItem(display_json))

            # 奖金
            prize_val = r.get("prize", 0)
            self.rules_table.setItem(i, 6, QTableWidgetItem(str(prize_val) if prize_val else "0"))

            # 备注
            self.rules_table.setItem(i, 7, QTableWidgetItem(r.get("remark", "")))

    def _filter_rules_table(self, category):
        """按分类筛选规则表格"""
        for i in range(self.rules_table.rowCount()):
            cat_item = self.rules_table.item(i, 1)
            if category == "全部" or (cat_item and cat_item.text() == category):
                self.rules_table.setRowHidden(i, False)
            else:
                self.rules_table.setRowHidden(i, True)

    def _apply_rules(self):
        """将数据库中的规则加载到引擎"""
        from lottery_engine import load_rules_from_db
        load_rules_from_db(self.db)
        QMessageBox.information(self, "规则已生效", "✅ 所有规则已从数据库加载到引擎，立即生效！")

    def _reset_rules(self):
        """重置为默认规则"""
        reply = QMessageBox.question(self, "确认重置",
            "将清除所有自定义规则，恢复为默认值。确定？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        conn = self.db._conn()
        conn.execute("DELETE FROM play_rules")
        conn.commit()
        conn.close()
        self.db._init_default_rules()
        self._refresh_rules_table()
        from lottery_engine import load_rules_from_db
        load_rules_from_db(self.db)
        QMessageBox.information(self, "已重置", "✅ 规则已恢复为默认值并生效！")

    def _save_rules_edit(self):
        """保存表格中的编辑到数据库"""
        import json
        changed = 0
        for i in range(self.rules_table.rowCount()):
            pt_item = self.rules_table.item(i, 0)
            if not pt_item:
                continue
            play_type = pt_item.data(Qt.UserRole)
            if not play_type:
                continue

            ot_item = self.rules_table.item(i, 2)
            ot = ot_item.data(Qt.UserRole) if ot_item else "fixed"

            updates = {}
            # 赔率值
            odds_item = self.rules_table.item(i, 3)
            if odds_item:
                try:
                    updates["odds_value"] = float(odds_item.text())
                except ValueError:
                    pass

            # 赔率表/本金表JSON
            json_item = self.rules_table.item(i, 5)
            if json_item:
                raw = json_item.text().strip()
                if raw:
                    try:
                        parsed = json.loads(raw)
                        if ot == "by_key":
                            updates["odds_json"] = {int(k): v for k, v in parsed.items()}
                        elif ot == "principal_table":
                            updates["principal_json"] = {int(k): v for k, v in parsed.items()}
                    except json.JSONDecodeError:
                        pass

            # 奖金
            prize_item = self.rules_table.item(i, 6)
            if prize_item:
                try:
                    updates["prize"] = float(prize_item.text())
                except ValueError:
                    pass

            # 备注
            remark_item = self.rules_table.item(i, 7)
            if remark_item:
                updates["remark"] = remark_item.text()

            if updates and self.db.update_rule(play_type, **updates):
                changed += 1

        if changed > 0:
            # 自动应用
            from lottery_engine import load_rules_from_db
            load_rules_from_db(self.db)
            QMessageBox.information(self, "保存成功", f"✅ 已更新 {changed} 条规则并生效！")
        else:
            QMessageBox.information(self, "无变更", "没有检测到修改。")

    def _delete_selected_rule(self):
        """删除选中的规则"""
        row = self.rules_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选中要删除的规则行")
            return
        pt_item = self.rules_table.item(row, 0)
        play_type = pt_item.data(Qt.UserRole) if pt_item else None
        if not play_type:
            return
        reply = QMessageBox.question(self, "确认删除",
            f"确定要删除玩法「{pt_item.text().split(chr(10))[0]}」的规则吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_rule(play_type)
            self._refresh_rules_table()

    def _add_rule_dialog(self):
        """新增规则对话框"""
        from PyQt5.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle("新增玩法规则")
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)

        pt_input = QLineEdit()
        pt_input.setPlaceholderText("英文大写+下划线，如 CUSTOM_PLAY")
        form.addRow("玩法标识:", pt_input)

        name_input = QLineEdit()
        name_input.setPlaceholderText("如：自定义玩法")
        form.addRow("显示名称:", name_input)

        cat_input = QComboBox()
        cat_input.addItems(["基础玩法", "包号/复式", "查表玩法", "胆拖", "大小单双", "粘边赖", "直选复式", "自定义"])
        form.addRow("分类:", cat_input)

        odds_type_input = QComboBox()
        odds_type_input.addItems(["fixed", "by_key", "principal_table"])
        form.addRow("赔率类型:", odds_type_input)

        odds_val_input = QDoubleSpinBox()
        odds_val_input.setRange(0, 99999)
        odds_val_input.setDecimals(2)
        form.addRow("固定赔率值:", odds_val_input)

        key_field_input = QLineEdit()
        key_field_input.setPlaceholderText("如：码数、拖码数、和值（by_key/principal_table时填写）")
        form.addRow("查表字段:", key_field_input)

        odds_json_input = QLineEdit()
        odds_json_input.setPlaceholderText('如: {"4": 37, "5": 15}')
        form.addRow("赔率表JSON:", odds_json_input)

        prize_input = QDoubleSpinBox()
        prize_input.setRange(0, 99999)
        prize_input.setDecimals(2)
        form.addRow("固定奖金:", prize_input)

        principal_input = QLineEdit()
        principal_input.setPlaceholderText('如: {"3": 12, "4": 48}（本金表时填写）')
        form.addRow("本金表JSON:", principal_input)

        remark_input = QLineEdit()
        form.addRow("备注:", remark_input)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        form.addRow(btns)

        if dialog.exec_() == QDialog.Accepted:
            pt = pt_input.text().strip()
            name = name_input.text().strip()
            if not pt or not name:
                QMessageBox.warning(self, "提示", "玩法标识和显示名称不能为空")
                return
            ok = self.db.add_rule(
                play_type=pt, display_name=name,
                category=cat_input.currentText(),
                odds_type=odds_type_input.currentText(),
                odds_value=odds_val_input.value(),
                key_field=key_field_input.text().strip(),
                odds_json=odds_json_input.text().strip(),
                prize=prize_input.value(),
                principal_json=principal_input.text().strip(),
                remark=remark_input.text().strip()
            )
            if ok:
                self._refresh_rules_table()
                QMessageBox.information(self, "成功", f"✅ 已添加规则「{name}」")
            else:
                QMessageBox.warning(self, "失败", "添加失败，玩法标识可能重复")

    # ============== 设置页面 ==============
    def _create_settings_page(self) -> QWidget:
        """设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        title = QLabel("设置")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # v5: 大额订单设置
        large_box = QGroupBox("💰 大额订单设置")
        large_layout = QVBoxLayout(large_box)
        
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("大额订单阈值:"))
        
        from PyQt5.QtWidgets import QDoubleSpinBox
        self.large_threshold_spin = QDoubleSpinBox()
        self.large_threshold_spin.setRange(0, 999999)
        self.large_threshold_spin.setDecimals(0)
        self.large_threshold_spin.setSuffix(" 元")
        self.large_threshold_spin.setValue(self.large_order_threshold)
        self.large_threshold_spin.valueChanged.connect(self.on_large_threshold_changed)
        threshold_layout.addWidget(self.large_threshold_spin)
        threshold_layout.addStretch()
        large_layout.addLayout(threshold_layout)
        
        scan_btn = QPushButton("🔍 扫描并标记大额订单")
        scan_btn.setObjectName("secondary_btn")
        scan_btn.clicked.connect(self.scan_large_orders)
        large_layout.addWidget(scan_btn)
        
        large_hint = QLabel("💡 金额大于等于阈值的订单将被标记为大额订单")
        large_hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        large_layout.addWidget(large_hint)
        
        layout.addWidget(large_box)
        
        # 数据目录
        data_box = QGroupBox("数据存储")
        data_layout = QVBoxLayout(data_box)
        
        data_layout.addWidget(QLabel(f"数据库路径: {self.db.db_path}"))
        
        export_btn = QPushButton("📤 导出数据库")
        export_btn.setObjectName("secondary_btn")
        export_btn.clicked.connect(self.export_database)
        data_layout.addWidget(export_btn)
        
        layout.addWidget(data_box)
        
        # 关于
        about_box = QGroupBox("关于")
        about_layout = QVBoxLayout(about_box)
        about_layout.addWidget(QLabel("算账助手 v1.0"))
        about_layout.addWidget(QLabel("微信群账目统计系统"))
        about_layout.addWidget(QLabel("基于PyQt5构建，Windows 11优化版"))
        layout.addWidget(about_box)
        
        layout.addStretch()
        return page
    
    # v5: 大额阈值变更
    def on_large_threshold_changed(self, value):
        """阈值变更时更新属性"""
        self.large_order_threshold = value
    
    # v5: 扫描并标记大额订单
    def scan_large_orders(self):
        """手动触发大额订单扫描"""
        if hasattr(self.db, 'mark_large_orders'):
            count = self.db.mark_large_orders(self.large_order_threshold)
            QMessageBox.information(self, "扫描完成", f"✅ 已扫描并标记 {count} 条大额订单")
            self.refresh_orders()
            self.update_status_bar()
        else:
            QMessageBox.warning(self, "提示", "当前数据库版本不支持此功能")
    
    def export_database(self):
        """导出数据库"""
        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出数据库", f"accounts_backup_{datetime.now().strftime('%Y%m%d')}.db",
            "SQLite数据库 (*.db)"
        )
        if save_path:
            import shutil
            shutil.copy2(self.db.db_path, save_path)
            show_windows_notification("导出成功", f"数据库已保存到: {save_path}")
    
    # ============== 系统托盘 ==============
    def init_tray(self):
        """初始化系统托盘"""
        self.tray = QSystemTrayIcon(self)
        
        # 创建托盘菜单
        menu = QMenu()
        
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)
        
        hide_action = QAction("最小化到托盘", self)
        hide_action.triggered.connect(self.hide_to_tray)
        menu.addAction(hide_action)
        
        menu.addSeparator()
        
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        
        # 设置提示
        self.tray.setToolTip("算账助手 - 运行中")
        self.tray.show()
    
    def hide_to_tray(self):
        """最小化到托盘"""
        self.hide()
        self.tray.showMessage("算账助手", "已最小化到系统托盘", QSystemTrayIcon.Information, 2000)
    
    def on_tray_activated(self, reason):
        """托盘图标点击"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止ADB监控
        if self.adb.running:
            self.adb.stop_monitor()
        
        # 最小化到托盘而不是退出
        event.ignore()
        self.hide_to_tray()
    
    def update_status_bar(self):
        """更新状态栏"""
        stats = self.db.get_statistics()
        void_info = ""
        if stats.get("void", 0) > 0:
            void_info += f" | 作废: {stats['void']}"
        if stats.get("refund", 0) > 0:
            void_info += f" | 退码: {stats['refund']}"
        # v5: 添加待处理和部分成功数量
        pending_info = ""
        if stats.get("pending", 0) > 0:
            pending_info = f" | ⏳待处理: {stats['pending']}"
        partial_info = ""
        if stats.get("partial", 0) > 0:
            partial_info = f" | 🎯部分成功: {stats['partial']}"
        msg = f"总订单: {stats['total']} | 有效: {stats.get('effective', stats['total'])} | 成功: {stats['success']} | 失败: {stats['failed']}{pending_info}{partial_info}{void_info} | 盈亏: ¥{stats.get('profit', 0):.2f}"
        self.status_bar.showMessage(msg)


if __name__ == "__main__":
    from datetime import datetime
    
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("算账助手")
    app.setOrganizationName("算账助手")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())
