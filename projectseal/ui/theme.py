"""Единая визуальная тема ProjectSeal (QSS + палитра)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from ..runtime import resource_path

# Палитра
NAVY = "#0F1B2D"
NAVY_2 = "#162944"
INK = "#182230"
MUTED = "#667085"
MUTED_2 = "#98A2B3"
BG = "#F4F6FA"
CARD = "#FFFFFF"
BORDER = "#E4E9F2"
GREEN = "#0E9F6E"
GREEN_DARK = "#0B8A5F"
GREEN_SOFT = "#EAF8F2"
GREEN_LINE = "#BFE9D8"
RED = "#D92D20"
RED_SOFT = "#FEF3F2"
RED_LINE = "#FECDCA"
AMBER = "#B54708"
AMBER_SOFT = "#FFFAEB"
AMBER_LINE = "#FEDF89"
BLUE = "#175CD3"
BLUE_SOFT = "#EFF8FF"
BLUE_LINE = "#B2DDFF"
PURPLE = "#6941C6"

CATEGORY_COLORS = {
    "secret": RED,
    "junk": AMBER,
    "safe": GREEN,
}

CATEGORY_SOFT = {
    "secret": RED_SOFT,
    "junk": AMBER_SOFT,
    "safe": GREEN_SOFT,
}


def _font_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in (
        "SF Pro Text",
        "SF Pro Display",
        "Segoe UI",
        "Inter",
        "Helvetica Neue",
        "Arial",
    ):
        if candidate in families:
            return candidate
    return "Sans Serif"


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    family = _font_family()
    font = QFont(family)
    font.setPointSizeF(10.5)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.Base, QColor(CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#FAFBFD"))
    palette.setColor(QPalette.ColorRole.Text, QColor(INK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(INK))
    palette.setColor(QPalette.ColorRole.Button, QColor(CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(INK))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(GREEN))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(NAVY))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    app.setPalette(palette)

    check = resource_path("check.png").as_posix()
    app.setStyleSheet(_stylesheet(family, check))


def _stylesheet(family: str, check_png: str) -> str:
    return f"""
    * {{
        font-family: "{family}";
        outline: none;
    }}
    QWidget {{
        color: {INK};
        font-size: 10.5pt;
    }}
    QMainWindow, QWidget#Root {{
        background: {BG};
    }}
    QToolTip {{
        background: {NAVY};
        color: #FFFFFF;
        border: 1px solid #2A4160;
        border-radius: 6px;
        padding: 6px 8px;
        font-size: 9pt;
    }}

    /* ---------- Sidebar ---------- */
    QFrame#Sidebar {{
        background: {NAVY};
        border: none;
    }}
    QLabel#BrandTitle {{
        color: #FFFFFF;
        font-size: 19pt;
        font-weight: 700;
        letter-spacing: 0.2px;
    }}
    QLabel#BrandTagline {{
        color: #8FA3BF;
        font-size: 9pt;
    }}
    QLabel#SidebarSection {{
        color: #6D829E;
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 1.2px;
    }}
    QFrame[step="true"] {{
        background: transparent;
        border: none;
        border-radius: 11px;
    }}
    QFrame[step="true"][active="true"] {{
        background: {NAVY_2};
    }}
    QLabel[stepNumber="true"] {{
        min-width: 27px;
        max-width: 27px;
        min-height: 27px;
        max-height: 27px;
        border-radius: 13px;
        background: #1B2E49;
        color: #8FA3BF;
        font-size: 9pt;
        font-weight: 700;
        qproperty-alignment: AlignCenter;
    }}
    QLabel[stepNumber="true"][stepState="active"] {{
        background: {GREEN};
        color: #FFFFFF;
    }}
    QLabel[stepNumber="true"][stepState="done"] {{
        background: #143A30;
        color: #5FE0B0;
    }}
    QLabel[stepTitle="true"] {{
        color: #E7EDF6;
        font-size: 10pt;
        font-weight: 600;
    }}
    QLabel[stepSubtitle="true"] {{
        color: #7E93AE;
        font-size: 8.5pt;
    }}
    QFrame#PrivacyCard {{
        background: #14253D;
        border: 1px solid #1F3552;
        border-radius: 13px;
    }}
    QLabel#PrivacyTitle {{
        color: #D8E3F2;
        font-size: 9.5pt;
        font-weight: 600;
    }}
    QLabel#PrivacyText {{
        color: #8298B5;
        font-size: 8.5pt;
    }}
    QPushButton[role="sidebarLink"] {{
        color: #93A8C4;
        background: transparent;
        border: none;
        text-align: left;
        padding: 5px 2px;
        font-size: 9pt;
    }}
    QPushButton[role="sidebarLink"]:hover {{
        color: #FFFFFF;
    }}
    QLabel#VersionLabel {{
        color: #5E738F;
        font-size: 8pt;
    }}

    /* ---------- Typography ---------- */
    QLabel[role="h1"] {{
        color: {NAVY};
        font-size: 25pt;
        font-weight: 700;
        letter-spacing: -0.4px;
    }}
    QLabel[role="h2"] {{
        color: {NAVY};
        font-size: 16pt;
        font-weight: 700;
        letter-spacing: -0.2px;
    }}
    QLabel[role="h3"] {{
        color: {INK};
        font-size: 11.5pt;
        font-weight: 600;
    }}
    QLabel[role="subtitle"] {{
        color: {MUTED};
        font-size: 10.5pt;
    }}
    QLabel[role="muted"] {{
        color: {MUTED};
    }}
    QLabel[role="tiny"] {{
        color: {MUTED_2};
        font-size: 8.5pt;
    }}
    QLabel[role="path"] {{
        color: #344054;
        font-family: "SF Mono", "Menlo", "Consolas", "Courier New", monospace;
        font-size: 9pt;
        background: #F6F8FC;
        border: 1px solid #E8EDF5;
        border-radius: 8px;
        padding: 8px 10px;
    }}
    QLabel[role="badge"] {{
        border-radius: 10px;
        padding: 5px 10px;
        font-size: 8.5pt;
        font-weight: 600;
    }}
    QLabel[role="badge"][tone="green"] {{
        background: {GREEN_SOFT};
        color: #067647;
        border: 1px solid {GREEN_LINE};
    }}
    QLabel[role="badge"][tone="red"] {{
        background: {RED_SOFT};
        color: #B42318;
        border: 1px solid {RED_LINE};
    }}
    QLabel[role="badge"][tone="amber"] {{
        background: {AMBER_SOFT};
        color: {AMBER};
        border: 1px solid {AMBER_LINE};
    }}
    QLabel[role="badge"][tone="blue"] {{
        background: {BLUE_SOFT};
        color: {BLUE};
        border: 1px solid {BLUE_LINE};
    }}
    QLabel[role="badge"][tone="neutral"] {{
        background: #F2F4F7;
        color: #475467;
        border: 1px solid #E4E7EC;
    }}

    /* ---------- Cards ---------- */
    QFrame[card="true"] {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 16px;
    }}
    QFrame[card="true"][tone="green"] {{
        background: #F6FCF9;
        border: 1px solid {GREEN_LINE};
    }}
    QFrame[card="true"][tone="flat"] {{
        background: #FAFBFD;
        border: 1px solid #EDF1F7;
    }}
    QFrame[stat="true"] {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}
    QLabel[statValue="true"] {{
        font-size: 23pt;
        font-weight: 700;
        color: {INK};
    }}
    QLabel[statValue="true"][tone="red"] {{ color: {RED}; }}
    QLabel[statValue="true"][tone="amber"] {{ color: {AMBER}; }}
    QLabel[statValue="true"][tone="green"] {{ color: {GREEN}; }}
    QLabel[statLabel="true"] {{
        color: {MUTED};
        font-size: 8.8pt;
        font-weight: 600;
    }}
    QLabel[statHint="true"] {{
        color: {MUTED_2};
        font-size: 8pt;
    }}

    /* ---------- Drop zone ---------- */
    QFrame[dropzone="true"] {{
        background: #FFFFFF;
        border: 2px dashed #C9D4E4;
        border-radius: 18px;
    }}
    QFrame[dropzone="true"][hover="true"] {{
        background: #F7FDFA;
        border: 2px dashed {GREEN};
    }}
    QFrame[dropzone="true"][filled="true"] {{
        background: #F6FCF9;
        border: 1.5px solid {GREEN_LINE};
    }}
    QLabel[dropTitle="true"] {{
        color: {INK};
        font-size: 12pt;
        font-weight: 600;
    }}
    QLabel[dropSubtitle="true"] {{
        color: {MUTED};
        font-size: 9.5pt;
    }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        border-radius: 10px;
        padding: 10px 18px;
        font-weight: 600;
        font-size: 10pt;
    }}
    QPushButton[role="primary"] {{
        background: {GREEN};
        color: #FFFFFF;
        border: 1px solid {GREEN};
        min-height: 24px;
    }}
    QPushButton[role="primary"]:hover {{ background: {GREEN_DARK}; border-color: {GREEN_DARK}; }}
    QPushButton[role="primary"]:pressed {{ background: #097A54; }}
    QPushButton[role="primary"]:disabled {{
        background: #C7D2E0;
        border-color: #C7D2E0;
        color: #FFFFFF;
    }}
    QPushButton[role="secondary"] {{
        background: #FFFFFF;
        color: #344054;
        border: 1px solid #D5DCE7;
    }}
    QPushButton[role="secondary"]:hover {{
        background: #F8FAFD;
        border-color: #B9C4D4;
    }}
    QPushButton[role="ghost"] {{
        background: transparent;
        color: #5A6B82;
        border: 1px solid transparent;
        font-weight: 500;
    }}
    QPushButton[role="ghost"]:hover {{
        background: #EEF2F8;
        color: {INK};
    }}
    QPushButton[role="link"] {{
        background: transparent;
        color: {GREEN};
        border: none;
        padding: 4px 2px;
        font-weight: 600;
    }}
    QPushButton[role="link"]:hover {{ color: {GREEN_DARK}; text-decoration: underline; }}
    QPushButton[role="dangerGhost"] {{
        background: {RED_SOFT};
        color: #B42318;
        border: 1px solid {RED_LINE};
    }}
    QPushButton[role="dangerGhost"]:hover {{ background: #FEE4E2; }}
    QPushButton[role="icon"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 6px;
    }}
    QPushButton[role="icon"]:hover {{ background: #EEF2F8; }}
    QPushButton[role="big"] {{
        font-size: 11pt;
        padding: 13px 26px;
        border-radius: 11px;
    }}

    /* ---------- Inputs ---------- */
    QLineEdit {{
        background: #FFFFFF;
        border: 1px solid #DDE3EC;
        border-radius: 9px;
        padding: 9px 12px;
        color: {INK};
        selection-background-color: {GREEN_SOFT};
        selection-color: {INK};
    }}
    QLineEdit:focus {{ border: 1px solid {GREEN}; }}
    QLineEdit#Search {{
        background: #F9FBFD;
        padding-left: 34px;
    }}
    QComboBox {{
        background: #FFFFFF;
        border: 1px solid #DDE3EC;
        border-radius: 9px;
        padding: 8px 12px;
    }}

    /* ---------- Tabs ---------- */
    QTabWidget::pane {{
        border: none;
        background: transparent;
        top: -1px;
    }}
    QTabBar {{
        background: transparent;
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {MUTED};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 9px 14px;
        margin-right: 2px;
        min-width: 108px;
        font-size: 9.8pt;
        font-weight: 600;
    }}
    QTabBar::tab:hover {{ color: {INK}; }}
    QTabBar::tab:selected {{
        color: {GREEN};
        border-bottom: 2px solid {GREEN};
    }}

    /* ---------- Table ---------- */
    QTableView {{
        background: #FFFFFF;
        border: none;
        border-radius: 12px;
        selection-background-color: #F0FAF6;
        selection-color: {INK};
        gridline-color: transparent;
    }}
    QTableView::item {{
        border-bottom: 1px solid #F1F4F9;
        padding: 0px 6px;
    }}
    QTableView::item:selected {{
        background: #F0FAF6;
        color: {INK};
    }}
    QHeaderView::section {{
        background: #FAFBFD;
        color: #7A879A;
        border: none;
        border-bottom: 1px solid #E8EDF5;
        padding: 10px 8px;
        font-size: 8.5pt;
        font-weight: 700;
    }}
    QHeaderView::section:first {{ border-top-left-radius: 12px; }}
    QHeaderView::section:last {{ border-top-right-radius: 12px; }}
    QTableCornerButton::section {{ background: #FAFBFD; border: none; }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px 1px;
    }}
    QScrollBar::handle:vertical {{
        background: #D0D8E5;
        min-height: 28px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #B6C2D3; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 1px 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: #D0D8E5;
        min-width: 28px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ---------- Checkboxes ---------- */
    QCheckBox {{
        spacing: 8px;
        color: #475467;
    }}
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border: 1.5px solid #C9D3E2;
        border-radius: 5px;
        background: #FFFFFF;
    }}
    QCheckBox::indicator:hover {{ border-color: {GREEN}; }}
    QCheckBox::indicator:checked {{
        background: {GREEN};
        border-color: {GREEN};
        image: url("{check_png}");
    }}
    QCheckBox::indicator:disabled {{
        background: #F2F4F7;
        border-color: #E4E7EC;
    }}

    /* ---------- Progress ---------- */
    QProgressBar {{
        background: #E8EDF5;
        border: none;
        border-radius: 5px;
        height: 9px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {GREEN};
        border-radius: 5px;
    }}

    /* ---------- Banners ---------- */
    QFrame[banner="true"] {{
        border-radius: 11px;
        border: 1px solid {BORDER};
        background: #F8FAFC;
    }}
    QFrame[banner="true"][tone="error"] {{
        background: {RED_SOFT};
        border-color: {RED_LINE};
    }}
    QFrame[banner="true"][tone="warning"] {{
        background: {AMBER_SOFT};
        border-color: {AMBER_LINE};
    }}
    QFrame[banner="true"][tone="success"] {{
        background: {GREEN_SOFT};
        border-color: {GREEN_LINE};
    }}
    QFrame[banner="true"][tone="info"] {{
        background: {BLUE_SOFT};
        border-color: {BLUE_LINE};
    }}
    QLabel[bannerText="true"] {{
        color: #344054;
        font-size: 9.3pt;
    }}
    QLabel[bannerText="true"][tone="error"] {{ color: #912018; }}
    QLabel[bannerText="true"][tone="warning"] {{ color: #93370D; }}
    QLabel[bannerText="true"][tone="success"] {{ color: #067647; }}
    QLabel[bannerText="true"][tone="info"] {{ color: #1849A9; }}

    /* ---------- Dialogs ---------- */
    QDialog {{
        background: {CARD};
    }}
    QDialog QLabel[role="h2"] {{
        font-size: 17pt;
    }}
    QFrame[dialogHeader="true"] {{
        background: #F8FAFD;
        border-bottom: 1px solid {BORDER};
        border-top-left-radius: 16px;
        border-top-right-radius: 16px;
    }}
    QFrame#Toast {{
        background: {NAVY};
        border-radius: 10px;
    }}
    QLabel#ToastText {{ color: #FFFFFF; font-size: 9.5pt; }}

    /* ---------- Misc ---------- */
    QSplitter::handle {{ background: transparent; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QMenu {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {GREEN_SOFT}; color: #067647; }}
    """
