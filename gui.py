import configparser
import threading
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QHBoxLayout, QDialog, QFileDialog

import fetch_data
import intensity_plot
import transmission_plot
import param_plot
import ctypes
import numpy as np
import pyqtgraph as pg

first_start = True
int_max = 100000
simulation = 1
method_path = "test-2.mtg"
fspec_path = "Не выбран"
trans_interval = 10
fon_interval = 60
stop_threads = True
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
    method = b"test-2.mtg"
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


class ModalPopup(QDialog):
    def rb_chosen(self):
        global simulation
        rb = self.sender()
        if rb.text() == "Выкл.":
            simulation = 0
        else:
            simulation = 1
        print(simulation)
        config = configparser.ConfigParser()
        config.read("./Device.ini")
        config.set('FSM', 'simulation', str(simulation))
        with open('./Device.ini', 'w') as configfile:
            config.write(configfile)

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

    def change_trans_interval(self, s):
        global trans_interval
        trans_interval = s[0:2]

    def change_fon_interval(self, s):
        global fon_interval
        if s == "1 мин":
            fon_interval = 60
        elif s == "1 час":
            fon_interval = 3600
        elif s == "24 часа":
            fon_interval = 3600 * 24
        elif s == "Неделя":
            fon_interval = 3600 * 24 * 7
        elif s == "2 недели":
            fon_interval = 3600 * 24 * 14
        else:
            fon_interval = 3600 * 24 * 30
        print(fon_interval)

    def __init__(self):
        super().__init__()
        self.setFixedSize(400, 600)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        layout = QVBoxLayout(self)
        label1 = QtWidgets.QLabel()
        label1.setText("Симуляция")
        layout.addWidget(label1)

        radio_layout = QHBoxLayout()
        rb_on = QtWidgets.QRadioButton('Вкл.', self)
        rb_on.toggled.connect(self.rb_chosen)
        rb_on.setChecked(True)
        radio_layout.addWidget(rb_on)

        rb_off = QtWidgets.QRadioButton('Выкл.', self)
        rb_off.toggled.connect(self.rb_chosen)
        radio_layout.addWidget(rb_off)
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
        self.path1_label.setText(method_path)
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
        label4.setText("Период обновления спектра пропускания")
        layout.addWidget(label4)
        combo1 = QtWidgets.QComboBox()
        combo1.addItems(["10 с", "20 с", "30 с", "40 с", "50 с", "60 с"])
        combo1.currentTextChanged.connect(self.change_trans_interval)
        layout.addWidget(combo1)

        label5 = QtWidgets.QLabel()
        label5.setText("Период обновления спектра интенсивности")
        layout.addWidget(label5)
        combo2 = QtWidgets.QComboBox()
        combo2.addItems(["1 мин", "1 ч", "24 ч", "Неделя", "2 недели", "Месяц"])
        combo2.currentTextChanged.connect(self.change_fon_interval)
        layout.addWidget(combo2)

        spacer = QtWidgets.QSpacerItem(20, 200, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        layout.addItem(spacer)


class Ui_MainWindow(object):
    def run_thread(self):
        global stop_threads
        stop_threads = False
        self.thread = threading.Thread(target=self.update_trans_plot, daemon=True)
        self.thread.start()
        self.start_button.setText("Стоп")
        self.start_button.clicked.connect(self.stop_thread)

    def stop_thread(self):
        global stop_threads
        stop_threads = True
        self.start_button.setText("Старт")
        self.start_button.clicked.connect(self.run_thread)

    def dummy(self, conc):
        self.param_plots(conc, True)


    def update_trans_plot(self):
        global first_start
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
                            res, x, y = get_spectr_func()
                            if res == 0:
                                self.plot1.update(x, y)
                first_start = False
                self.timer1.start()
                self.timer2.start()
            else:
                if self.timer1.hasExpired(trans_interval * 1000):
                    res, warn, conc = get_value_func()
                    if res == 0:
                        conc = [number for number in conc if number != 0]
                        self.param_plots(conc, False)
                        res, x, y = get_spectr_func()
                        if res == 0:
                            self.plot1.update(x, y)
                    self.timer1.restart()
                if self.timer2.hasExpired(fon_interval * 1000):
                    self.update_intensity_plot()
                    self.timer2.restart()

    def update_intensity_plot(self):
        res, warn = init_func()
        if res == 0:
            x, y = read_fon_spe()
            self.plot2.update(x, y)
        print("Fon updated")

    def param_plots(self, conc, build):
        print("params are build")
        conc = [number for number in conc if int_max > number > -int_max]
        if build:
            layout = QGridLayout(self.scrollAreaWidgetContents)
            for i in range(len(conc)):
                param_label = QtWidgets.QLabel()
                param_label.setAlignment(QtCore.Qt.AlignCenter)
                param_label.setText(f"Параметр {i + 1}")
                print(i)
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
                plot = param_plot.ParameterPlot(stack_size=20)
                self.parameter.append(plot)
                widget.addItem(plot)
                widget.setBackground("w")
                plot.update(conc[i])
                layout.addLayout(param_layout, i, 0)
                layout.addWidget(widget, i, 1)
        else:
            for i in range(len(conc)):
                self.param_values[i].setText("{:.2f}".format(conc[i]))
                self.parameter[i].update(conc[i])

    def open_settings(self, MainWindow):
        self.modal_popup = ModalPopup()
        self.modal_popup.show()

    def setupUi(self, MainWindow):
        self.thread = None
        self.timer1 = QtCore.QElapsedTimer()
        self.timer2 = QtCore.QElapsedTimer()
        MainWindow.setObjectName("MainWindow")
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.main_layout = QVBoxLayout(self.centralwidget)

        self.settings = QHBoxLayout()
        self.settings.setObjectName("settings")

        self.start_button = QtWidgets.QPushButton()
        self.start_button.setFixedSize(160, 80)
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self.run_thread)

        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setFixedSize(160, 80)
        self.settings_button.clicked.connect(self.open_settings)

        self.res_layout = QVBoxLayout()

        self.res_label = QtWidgets.QLabel()
        self.res_label.setAlignment(QtCore.Qt.AlignCenter)

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)

        self.label_2 = QtWidgets.QLabel()
        font = QtGui.QFont()
        font.setPointSize(26)
        font.setBold(False)
        font.setWeight(50)
        self.label_2.setFont(font)
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)

        self.res_layout.addWidget(self.res_label)
        self.res_layout.addWidget(self.label_2)
        self.res_layout.addWidget(self.label)

        self.scans_layout = QVBoxLayout()
        self.scans_label = QtWidgets.QLabel()
        self.scans_label.setAlignment(QtCore.Qt.AlignCenter)

        self.label_3 = QtWidgets.QLabel()
        font = QtGui.QFont()
        font.setPointSize(26)
        font.setBold(False)
        font.setWeight(50)
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
        font = QtGui.QFont()
        font.setPointSize(26)
        font.setBold(False)
        font.setWeight(50)
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

        self.parameter = []
        self.param_values = []

        self.plots_layout = QVBoxLayout()

        self.transmission = pg.GraphicsLayoutWidget()
        self.transmission.setBackground("w")
        self.transmission.setFixedWidth(MainWindow.width() * 1.8)
        self.plot1 = transmission_plot.TransmissionPlot()
        self.transmission.addItem(self.plot1)
        self.plots_layout.addWidget(self.transmission)

        self.intensity = pg.GraphicsLayoutWidget()
        self.intensity.setBackground("w")
        self.plot2 = intensity_plot.IntensityPlot()
        self.intensity.addItem(self.plot2)
        self.plots_layout.addWidget(self.intensity)

        self.graphs.addLayout(self.params_layout)
        self.graphs.addLayout(self.plots_layout)

        self.settings.addWidget(self.start_button)
        self.settings.addLayout(self.res_layout)
        self.settings.addLayout(self.scans_layout)
        self.settings.addLayout(self.cuv_layout)
        self.settings.addWidget(self.settings_button)

        self.main_layout.addLayout(self.settings)
        self.main_layout.addLayout(self.graphs)
        self.param_plots([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], True)
        MainWindow.setCentralWidget(self.centralwidget)

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
