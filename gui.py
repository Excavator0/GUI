import configparser
import os
import subprocess
import threading
import time

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QHBoxLayout, QDialog, QFileDialog
import json
import ctypes
import numpy as np
import pyqtgraph as pg

import fetch_data
import transmissionPlot
import intensityPlot
import param_plot


first_start = True
int_max = 100000
simulation = 1
method_path = "test-2.mtg"
fspec_path = "Не выбран"
trans_interval = 60
int_interval = 10
stop_threads = True
parameter = []

# GAS.dll functions below
dll_path = "./GAS.dll"
my_dll = ctypes.WinDLL(dll_path)


def read_fon_spe():
    binary_data = b""
    with open('./Spectra/fon.spe', 'rb') as file:
        data = file.readlines()
        for line in data[36:-1]:
            binary_data = binary_data + line
        x_first = float(data[32].decode("utf-8")[data[32].decode("utf-8").find("=") + 1:])
        x_last = float(data[33].decode("utf-8")[data[33].decode("utf-8").find("=") + 1:])
    newFile = open("./Spectra/values_bin.txt", "wb")
    newFile.write(binary_data)

    arr = np.fromfile("./Spectra/values_bin.txt", dtype=np.single)
    print(len(arr))
    x_values = []
    for i in range(len(arr)):
        x_values.append(x_first + (i * ((x_last - x_first) / len(arr))))
    return x_values, arr


def start_func():
    start_function = my_dll.Start
    start_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
    start_function.restypes = [ctypes.c_int]
    warning = (ctypes.c_int * 1)()
    result = start_function(warning)
    print("Result of start:", result)
    print(warning[0])
    return result, warning[0]


def init_func():
    init_function = my_dll.Init
    init_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
    init_function.restypes = [ctypes.c_int]
    warning = (ctypes.c_int * 1)()
    result = init_function(warning)
    print("Result of init:", result)
    print(warning[0])
    return result, warning[0]


def get_value_func():
    getValue_function = my_dll.GetValue
    getValue_function.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int),
                                  ctypes.c_char_p]
    getValue_function.restypes = [ctypes.c_int]
    warning = (ctypes.c_int * 1)()
    method = ctypes.c_char_p(method_path.encode('utf-8'))
    conc = (ctypes.c_double * 16)()
    password = b""
    result = getValue_function(method, conc, warning, password)
    print("Result of getValue:", result)
    print(list(conc))
    return result, warning[0], list(conc)


def get_size_func():
    get_size_function = my_dll.GetSize
    get_size_function.restypes = [ctypes.c_int]
    result = get_size_function()
    print("Result of getSize:", result)
    return result


def get_spectr_func():
    length = get_size_func()
    get_spectr_function = my_dll.GetSpectr
    get_spectr_function.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float),
                                    ctypes.POINTER(ctypes.c_float)]
    get_spectr_function.restypes = [ctypes.c_int]
    x_o = (ctypes.c_float * 1)()
    x_s = (ctypes.c_float * 1)()
    y = (ctypes.c_float * length)()
    result = get_spectr_function(x_o, x_s, y)
    print("Result of getSpectr:", result)
    x = []
    for i in range(length):
        x.append(x_o[0] + (i * x_s[0]))
    return result, x, list(y)


def change_param_size(text):
    new_size = int(text)
    for i in range(16):
        parameter[i].change_size(new_size)


class ModalPopup(QDialog):

    def choose_method(self):
        global method_path
        dlg = QFileDialog()
        method_path, _ = dlg.getOpenFileName(self, 'Открыть файл', './', "Файл метода (*.mtg *.mtz *.mtd)")
        self.path1_label.setText(method_path)

    def choose_fspec(self):
        global fspec_path
        dlg = QFileDialog()
        fspec_path, _ = dlg.getOpenFileName(self, 'Открыть файл', './', "Файл программы FSpec (*.exe)")
        self.path2_label.setText(fspec_path)

    def save(self):
        global simulation, trans_interval, int_interval
        self.close()

        if self.rb_off.isChecked():
            simulation = 0
        else:
            simulation = 1
        config = configparser.ConfigParser()
        config.read("./Device.ini")
        config.set('FSM', 'simulation', str(simulation))
        with open('./Device.ini', 'w') as configfile:
            config.write(configfile)

        int_interval = int(self.combo1.currentText()[0:2])
        s = self.combo2.currentText()
        if s == "1 мин":
            trans_interval = 60
        elif s == "1 час":
            trans_interval = 3600
        elif s == "24 часа":
            trans_interval = 3600 * 24
        elif s == "Неделя":
            trans_interval = 3600 * 24 * 7
        elif s == "2 недели":
            trans_interval = 3600 * 24 * 14
        else:
            trans_interval = 3600 * 24 * 30
        stack_size = "5"
        if self.entry1.text() != '':
            change_param_size(int(self.entry1.text()))
            stack_size = self.entry1.text()
        max_val = "8000"
        min_val = "0"
        if self.max_entry.text() != '':
            if self.min_entry.text() != '':
                self.parent.plot1.setXRange(int(self.min_entry.text()), int(self.max_entry.text()))
                max_val = self.max_entry.text()
                min_val = self.min_entry.text()
            else:
                self.parent.plot1.setXRange(0, int(self.max_entry.text()))
                max_val = self.max_entry.text()
        elif self.min_entry.text() != '':
            self.parent.plot1.setXRange(int(self.min_entry.text()), 8000)
            min_val = self.min_entry.text()

        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        json_data["simulation"] = str(simulation)
        json_data["method_path"] = method_path
        json_data["fspec_path"] = fspec_path
        json_data["int_period"] = self.combo1.currentText()
        json_data["trans_period"] = self.combo2.currentText()
        json_data["param_size"] = stack_size
        json_data["limits"]["min"] = min_val
        json_data["limits"]["max"] = max_val
        with open('./config.json', 'w') as f:
            json.dump(json_data, f)

    def load(self):
        global method_path, fspec_path, int_interval, trans_interval, simulation
        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        if json_data["simulation"] == "1":
            self.rb_on.setChecked(True)
            simulation = 1
        else:
            self.rb_off.setChecked(True)
            simulation = 0
        self.path1_label.setText(json_data["method_path"])
        method_path = json_data["method_path"]
        self.path2_label.setText(json_data["fspec_path"])
        fspec_path = json_data["fspec_path"]
        self.combo1.setCurrentText(json_data["int_period"])
        int_interval = int(json_data["int_period"][0:2])
        self.combo2.setCurrentText(json_data["trans_period"])
        s = json_data["trans_period"]
        if s == "1 мин":
            trans_interval = 60
        elif s == "1 час":
            trans_interval = 3600
        elif s == "24 часа":
            trans_interval = 3600 * 24
        elif s == "Неделя":
            trans_interval = 3600 * 24 * 7
        elif s == "2 недели":
            trans_interval = 3600 * 24 * 14
        else:
            trans_interval = 3600 * 24 * 30
        self.entry1.setText(json_data["param_size"])
        change_param_size(json_data["param_size"])
        self.min_entry.setText(json_data["limits"]["min"])
        self.max_entry.setText(json_data["limits"]["max"])
        self.parent.plot1.setXRange(int(json_data["limits"]["min"]), int(json_data["limits"]["max"]))

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setFixedSize(400, 600)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        layout = QVBoxLayout(self)
        label1 = QtWidgets.QLabel()
        label1.setText("Симуляция")
        layout.addWidget(label1)
        radio_layout = QHBoxLayout()
        self.rb_on = QtWidgets.QRadioButton('Вкл.', self)
        radio_layout.addWidget(self.rb_on)
        self.rb_off = QtWidgets.QRadioButton('Выкл.', self)
        radio_layout.addWidget(self.rb_off)
        spacer = QtWidgets.QSpacerItem(250, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        radio_layout.addItem(spacer)
        layout.addLayout(radio_layout)

        label2 = QtWidgets.QLabel()
        label2.setText("Путь к файлу метода")
        layout.addWidget(label2)

        path1_layout = QHBoxLayout()
        button1 = QtWidgets.QPushButton()
        button1.setText("Выбрать")
        button1.clicked.connect(self.choose_method)
        self.path1_label = QtWidgets.QLabel()
        path1_layout.addWidget(button1)
        path1_layout.addWidget(self.path1_label)
        layout.addLayout(path1_layout)

        label3 = QtWidgets.QLabel()
        label3.setText("Путь к файлу FSpec")
        layout.addWidget(label3)

        path2_layout = QHBoxLayout()
        button2 = QtWidgets.QPushButton()
        button2.setText("Выбрать")
        button2.clicked.connect(self.choose_fspec)
        self.path2_label = QtWidgets.QLabel()
        self.path2_label.setText(fspec_path)
        path2_layout.addWidget(button2)
        path2_layout.addWidget(self.path2_label)
        layout.addLayout(path2_layout)

        label4 = QtWidgets.QLabel()
        label4.setText("Период обновления спектра интенсивности")
        layout.addWidget(label4)
        self.combo1 = QtWidgets.QComboBox()
        self.combo1.addItems(["10 с", "20 с", "30 с", "40 с", "50 с", "60 с"])
        layout.addWidget(self.combo1)

        label5 = QtWidgets.QLabel()
        label5.setText("Период обновления спектра пропускания")
        layout.addWidget(label5)
        self.combo2 = QtWidgets.QComboBox()
        self.combo2.addItems(["1 мин", "1 ч", "24 ч", "Неделя", "2 недели", "Месяц"])
        layout.addWidget(self.combo2)

        label6 = QtWidgets.QLabel()
        label6.setText("Размер стека параметров")
        layout.addWidget(label6)
        self.entry1 = QtWidgets.QLineEdit()
        self.entry1.setValidator(QtGui.QIntValidator(1, 999, self))
        layout.addWidget(self.entry1)

        label7 = QtWidgets.QLabel()
        label7.setText("Границы спектра интенсивности по оси Х")
        layout.addWidget(label7)
        limits_layout = QGridLayout()
        label8 = QtWidgets.QLabel()
        label8.setText("Левая граница")
        limits_layout.addWidget(label8, 0, 0)
        label9 = QtWidgets.QLabel()
        label9.setText("Правая граница")
        limits_layout.addWidget(label9, 0, 1)
        self.min_entry = QtWidgets.QLineEdit()
        self.min_entry.setValidator(QtGui.QIntValidator())
        limits_layout.addWidget(self.min_entry, 1, 0)
        self.max_entry = QtWidgets.QLineEdit()
        self.max_entry.setValidator(QtGui.QIntValidator())
        limits_layout.addWidget(self.max_entry, 1, 1)
        layout.addLayout(limits_layout)
        self.load()
        spacer = QtWidgets.QSpacerItem(20, 200, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        layout.addItem(spacer)
        save_button = QtWidgets.QPushButton()
        save_button.setText("Сохранить")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)




class Ui_MainWindow(object):
    def run_thread(self):
        global stop_threads
        stop_threads = False
        self.thread = threading.Thread(target=self.update_intensity_plot, daemon=True)
        self.thread.start()
        self.start_button.setText("Стоп")
        self.start_button.clicked.connect(self.stop_thread)

    def stop_thread(self):
        global stop_threads
        stop_threads = True
        self.start_button.setText("Старт")
        self.start_button.clicked.connect(self.run_thread)

    def generate_warnings(self, warning):
        self.warnings_box.clear()
        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        warnings = str(bin(warning))
        warnings = warnings[::-1]
        for i in range(len(warnings)):
            if warnings[i] == '1':
                self.warnings_box.addItem(str(json_data["warnings"].get(str(i))))

    # def error_window(self, res):
    #     window = QDialog(self.centralwidget)
    #     window.setFixedSize(400, 200)
    #     window.setWindowTitle("Ошибка!")
    #     window.setModal(True)
    #     window.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
    #
    #     with open('./config.json', 'r', encoding="utf-8") as file:
    #         json_data = json.load(file)
    #
    #     layout = QHBoxLayout(window)
    #     label = QtWidgets.QLabel()
    #     label.setText(str(json_data["errors"].get(str(res))))
    #     layout.addWidget(label)
    #     window.exec_()

    def error_out(self, res):
        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        if res > 0:
            res = -500
        self.fspec_error.setText("Ошибка! " + str(json_data["errors"].get(str(res))))
        self.icon_label.show()
        self.stop_thread()

    def update_intensity_plot(self):
        global first_start
        self.icon_label.hide()
        self.fspec_error.setText("")
        while not stop_threads:
            self.label_2.setText(str(fetch_data.res))
            self.label_3.setText(str(fetch_data.scans))
            self.label_4.setText(str(fetch_data.cuv_length))
            if first_start:
                res, warn = start_func()
                if res == 0:
                    res, warn = init_func()
                    if res == 0:
                        x, y = read_fon_spe()
                        self.plot2.update(x, y)
                        res, warn, conc = get_value_func()
                        if res == 0:
                            conc = [number for number in conc if number != 0]
                            self.param_plots(conc, False)
                            self.generate_warnings(warn)
                            res, x, y = get_spectr_func()
                            if res == 0:
                                self.plot1.update(x, y)
                            else:
                                self.error_out(res)
                                break
                        else:
                            self.error_out(res)
                            break
                    else:
                        self.error_out(res)
                        break
                else:
                    self.error_out(res)
                    break
                first_start = False
                self.timer1.start()
                self.timer2.start()
            else:
                if self.timer1.hasExpired(int_interval * 1000):
                    res, warn, conc = get_value_func()
                    if res == 0:
                        conc = [number for number in conc if number != 0]
                        self.param_plots(conc, False)
                        self.generate_warnings(warn)
                        res, x, y = get_spectr_func()
                        if res == 0:
                            self.plot1.update(x, y)
                        else:
                            self.error_out(res)
                            break
                    else:
                        self.error_out(res)
                        break
                    self.timer1.restart()
                if self.timer2.hasExpired(trans_interval * 1000):
                    self.update_trans_plot()
                    self.timer2.restart()

    def update_trans_plot(self):
        res, warn = init_func()
        if res == 0:
            x, y = read_fon_spe()
            self.plot2.update(x, y)
        print("Fon updated")

    def param_plots(self, conc, build):
        global parameter
        conc = [number for number in conc if int_max > number > -int_max]
        if build:
            layout = QGridLayout(self.scrollAreaWidgetContents)
            for i in range(len(conc)):
                param_label = QtWidgets.QLabel()
                param_label.setAlignment(QtCore.Qt.AlignCenter)
                param_label.setText(f"Параметр {i + 1}")
                param_value = QtWidgets.QLabel()
                self.param_values.append(param_value)
                font = QtGui.QFont()
                font.setPointSize(26)
                font.setBold(False)
                font.setWeight(50)
                param_value.setFont(font)
                param_value.setAlignment(QtCore.Qt.AlignCenter)
                param_value.setText("{:.2f}".format(conc[i]))

                param_layout = QGridLayout()
                param_layout.addWidget(param_label, 0, 0)
                param_layout.addWidget(param_value, 1, 0)

                widget = pg.GraphicsLayoutWidget()
                widget.setFixedHeight(150)
                plot = param_plot.ParameterPlot(stack_size=5)
                parameter.append(plot)
                widget.addItem(plot)
                widget.setBackground("w")
                plot.update(conc[i])
                layout.addLayout(param_layout, i, 0)
                layout.addWidget(widget, i, 1)
        else:
            for i in range(len(conc)):
                self.param_values[i].setText("{:.2f}".format(conc[i]))
                parameter[i].update(conc[i])

    def open_settings(self):
        self.modal_popup = ModalPopup(self)
        self.modal_popup.show()

    def start_fspec(self):
        if os.path.exists(fspec_path):
            result = subprocess.run([fspec_path])
        else:
            self.fspec_error.setText("Неверный путь")

    def setupUi(self, MainWindow):
        self.thread = None
        self.timer1 = QtCore.QElapsedTimer()
        self.timer2 = QtCore.QElapsedTimer()
        MainWindow.setObjectName("MainWindow")
        font = QtGui.QFont()
        font.setPointSize(26)
        font.setBold(False)
        font.setWeight(50)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.main_layout = QVBoxLayout(self.centralwidget)
        self.settings = QHBoxLayout()
        self.settings.setObjectName("settings")

        button_font = QtGui.QFont()
        button_font.setPointSize(10)
        button_font.setBold(False)

        start_layout = QGridLayout()
        self.start_button = QtWidgets.QPushButton()
        self.start_button.setFixedSize(160, 100)
        self.start_button.setFont(button_font)
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self.run_thread)
        start_layout.addWidget(self.start_button, 0, 0)

        group_box = QtWidgets.QGroupBox("Окно предупреждений")
        group_box.setFixedWidth(400)
        group_box.setFixedHeight(120)
        self.warnings_box = QtWidgets.QListWidget()
        self.warnings_box.setFixedWidth(380)
        self.warnings_box.setFixedHeight(80)
        group_layout = QVBoxLayout(group_box)
        group_layout.addWidget(self.warnings_box)
        start_layout.addWidget(group_box, 0, 2)

        start_fspec = QtWidgets.QPushButton()
        start_fspec.setFixedSize(160, 100)
        start_fspec.setText("Запуск FFSpec")
        start_fspec.setFont(button_font)
        start_fspec.clicked.connect(self.start_fspec)
        start_layout.addWidget(start_fspec, 0, 1)

        error_font = QtGui.QFont()
        error_font.setPointSize(10)
        error_font.setBold(True)
        self.label_layout = QHBoxLayout()
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setPixmap(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning).pixmap(32))
        self.icon_label.hide()
        self.label_layout.addStretch()

        self.label_layout.addWidget(self.icon_label)
        self.fspec_error = QtWidgets.QLabel()
        self.fspec_error.setText("")
        self.fspec_error.setFont(error_font)
        self.fspec_error.setAlignment(QtCore.Qt.AlignCenter)
        self.label_layout.addWidget(self.fspec_error)
        start_layout.addLayout(self.label_layout, 1, 0, 1, 3)

        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setFixedSize(160, 100)
        self.settings_button.setFont(button_font)
        self.settings_button.clicked.connect(self.open_settings)

        self.res_layout = QVBoxLayout()

        self.res_label = QtWidgets.QLabel()
        self.res_label.setAlignment(QtCore.Qt.AlignCenter)

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)

        self.label_2 = QtWidgets.QLabel()
        self.label_2.setFont(font)
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)

        self.res_layout.addWidget(self.res_label)
        self.res_layout.addWidget(self.label_2)
        self.res_layout.addWidget(self.label)

        self.scans_layout = QVBoxLayout()
        self.scans_label = QtWidgets.QLabel()
        self.scans_label.setAlignment(QtCore.Qt.AlignCenter)

        self.label_3 = QtWidgets.QLabel()
        self.label_3.setFont(font)
        self.label_3.setAlignment(QtCore.Qt.AlignCenter)

        self.dummy_label = QtWidgets.QLabel()
        self.scans_layout.addWidget(self.scans_label)
        self.scans_layout.addWidget(self.label_3)
        self.scans_layout.addWidget(self.dummy_label)

        self.cuv_layout = QVBoxLayout()

        self.cuv_label = QtWidgets.QLabel()
        self.cuv_label.setAlignment(QtCore.Qt.AlignCenter)

        self.label_4 = QtWidgets.QLabel()
        self.label_4.setFont(font)
        self.label_4.setAlignment(QtCore.Qt.AlignCenter)

        self.label_5 = QtWidgets.QLabel()
        self.label_5.setAlignment(QtCore.Qt.AlignCenter)

        self.cuv_layout.addWidget(self.cuv_label)
        self.cuv_layout.addWidget(self.label_4)
        self.cuv_layout.addWidget(self.label_5)

        self.graphs = QHBoxLayout()

        self.params_layout = QHBoxLayout()

        self.scrollArea = QtWidgets.QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.params_layout.addWidget(self.scrollArea)

        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.param_values = []

        self.plots_layout = QVBoxLayout()

        self.transmission = pg.GraphicsLayoutWidget()
        self.transmission.setBackground("w")
        self.transmission.setFixedWidth(MainWindow.width() * 1.8)
        self.plot1 = intensityPlot.IntensityPlot()
        self.transmission.addItem(self.plot1)
        self.plots_layout.addWidget(self.transmission)

        self.intensity = pg.GraphicsLayoutWidget()
        self.intensity.setBackground("w")
        self.plot2 = transmissionPlot.TransmissionPlot()
        self.intensity.addItem(self.plot2)
        self.plots_layout.addWidget(self.intensity)

        self.graphs.addLayout(self.params_layout)
        self.graphs.addLayout(self.plots_layout)

        self.settings.addLayout(start_layout)
        self.settings.addLayout(self.res_layout)
        self.settings.addLayout(self.scans_layout)
        self.settings.addLayout(self.cuv_layout)
        self.settings.addWidget(self.settings_button)

        self.main_layout.addLayout(self.settings)
        self.main_layout.addLayout(self.graphs)
        self.param_plots([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], True)
        MainWindow.setCentralWidget(self.centralwidget)

        ModalPopup(self).load()

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)


    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Приложение"))
        self.start_button.setText(_translate("MainWindow", "Старт"))
        self.settings_button.setText(_translate("MainWindow", "Настройки"))
        self.res_label.setText(_translate("MainWindow", "Разрешение"))
        self.label.setText(_translate("MainWindow", "см⁻¹"))
        self.label_2.setText(_translate("MainWindow", "0"))
        self.scans_label.setText(_translate("MainWindow", "Число сканов"))
        self.label_3.setText(_translate("MainWindow", "0"))
        self.cuv_label.setText(_translate("MainWindow", "Толщина кюветы"))
        self.label_4.setText(_translate("MainWindow", "0"))
        self.label_5.setText(_translate("MainWindow", "мм"))
