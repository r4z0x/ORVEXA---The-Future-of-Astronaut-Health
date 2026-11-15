"""ORVEXA desktop entry point. No web server or browser is involved."""
import sys
import sqlite3
from PySide6.QtWidgets import QApplication, QMessageBox
from orvexa.ui import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('ORVEXA')
    app.setOrganizationName('ORVEXA')
    try:
        window = MainWindow()
    except (sqlite3.Error, OSError, ValueError, KeyError) as exc:
        QMessageBox.critical(None, 'ORVEXA — Unable to Open Data',
            'Check the data folder and disk access. The database has not been deleted or overwritten.\n\n'+str(exc))
        return 1
    window.show()
    return app.exec()

if __name__ == '__main__':
    raise SystemExit(main())
