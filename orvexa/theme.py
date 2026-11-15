STYLE = '''
QMainWindow { background:#080f1b; }
QWidget { color:#dbe8f6; font-family:'Golos Text','Segoe UI',sans-serif; font-size:12px; }
QFrame#Sidebar { background:#0a1422;border-right:1px solid #203043; }
QFrame#Topbar { background:#0a1320;border-bottom:1px solid #203043; }
QFrame#Card { background:#101c2c;border:1px solid #223246;border-radius:10px; }
QFrame#AI { background:#102532;border:1px solid #2a5865;border-radius:10px; }
QFrame#Notice { background:#1c222b;border:1px solid #4a4231;border-radius:8px; }
QScrollArea { border:none;background:transparent; }
QScrollArea > QWidget > QWidget { background:#080f1b; }
QPushButton { background:#172538;border:1px solid #2d4157;border-radius:6px;padding:8px 13px;font-size:10px;color:#c6d8e8; }
QPushButton:hover { background:#20364a;border-color:#42627d; }
QPushButton:pressed { background:#294459; }
QPushButton:disabled { color:#526b7e;background:#16212e;border-color:#253345; }
QPushButton[kind="primary"] { background:#51d4f0;border-color:#51d4f0;color:#092333;font-weight:600; }
QPushButton[kind="primary"]:hover { background:#85e7fa;border-color:#85e7fa; }
QPushButton[kind="primary"]:disabled { background:#245060;border-color:#245060;color:#688f9c; }
QPushButton[kind="secondary"] { background:transparent;border-color:transparent;color:#87a0b8; }
QPushButton[kind="secondary"]:hover { color:#59d5ef;background:#152a3a; }
QPushButton#Nav { background:transparent;border:1px solid transparent;border-radius:8px;padding:12px 15px;text-align:left;color:#8298b1;font-size:11px; }
QPushButton#Nav:hover { background:#132739;color:#c8dfef; }
QPushButton#Nav:checked { background:#153447;border-color:#2a5267;color:#5ddaf6; }
QPushButton#Tab { padding:5px 10px;font-size:9px;background:#0c1725;color:#748ba3;border:1px solid #24364a; }
QPushButton#Tab:checked { background:#203e51;color:#7ee4fa;border-color:#326379; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit { background:#0b1726;border:1px solid #30465d;border-radius:6px;padding:9px 10px;color:#e0eefb;selection-background-color:#256078; }
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus,QTextEdit:focus { border-color:#51d4f0; }
QSpinBox,QDoubleSpinBox { min-height:22px; }
QComboBox QAbstractItemView { background:#14263a;color:#d8e8f6;selection-background-color:#24536b; }
QCheckBox { color:#98adc3;spacing:9px;font-size:11px; }
QCheckBox::indicator { width:15px;height:15px;border:1px solid #39516b;border-radius:3px;background:#101d2b; }
QCheckBox::indicator:checked { background:#4dcde9;border-color:#4dcde9; }
QDialog { background:#101d2d; }
QMessageBox { background:#101d2d; }
QTextBrowser { background:#0b1827;border:1px solid #253d53;border-radius:8px;padding:14px;color:#b5cadd; }
QTableWidget { background:#101d2c;alternate-background-color:#132335;border:1px solid #273d53;gridline-color:#23384c;color:#bfd1e2;font-size:11px;selection-background-color:#234b63; }
QHeaderView::section { background:#14283b;color:#7f9db7;border:0;border-bottom:1px solid #2b455c;padding:10px;font-size:10px; }
QTableCornerButton::section { background:#14283b;border:0; }
QScrollBar:vertical { width:7px;background:#0c1623;margin:0; }
QScrollBar::handle:vertical { background:#2a4056;border-radius:3px;min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QToolTip { background:#1b3548;border:1px solid #38627c;color:#d7eafb;padding:6px; }
QStatusBar { background:#0a1522;color:#80a1b8;font-size:10px;border-top:1px solid #203346; }
'''
