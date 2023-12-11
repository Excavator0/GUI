from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMainWindow
from gui import Ui_MainWindow  # Import the generated module


class MyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create an instance of the generated UI class
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)


if __name__ == "__main__":
    app = QApplication([])
    app.setStyleSheet(Path('style.qss').read_text())
    window = MyMainWindow()
    window.showMaximized()
    app.exec_()

