import configparser
import csv
import glob
import serial.tools.list_ports
import os
import subprocess
import threading
import time
import serial
import modbus_tk
import modbus_tk.defines as cst
from PyQt5.QtCore import QTime
from modbus_tk import modbus_rtu
from datetime import datetime

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
plots_interval = 10
params_interval = "1 ч"
stop_threads = True
parameter = []
days_threshold = 0
modbus_connected = False
device_num = 0
port = ''
timeout = 0
zoom = True

master = None
logger = modbus_tk.utils.create_logger("console")


def send_conc(device, conc):
    data_format = ">"
    for i in range(len(conc)):
        data_format = data_format + "f"
    logger.info(master.execute(device, cst.WRITE_MULTIPLE_REGISTERS, 0, output_value=conc, data_format=data_format))
    logger.info(master.execute(device, cst.READ_HOLDING_REGISTERS, 0, 2, data_format='>f'))


def send_res(device, res, warn):
    logger.info(master.execute(device, cst.WRITE_MULTIPLE_REGISTERS, 100, output_value=[res, warn]))
    logger.info(master.execute(device, cst.READ_HOLDING_REGISTERS, 100, 102))


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
    x_values = []
    binary_data = b""
    with open('./Spectra/original.spe', 'rb') as file:
        data = file.readlines()
        for line in data[36:-1]:
            binary_data = binary_data + line
    newFile = open("./Spectra/values_bin.txt", "wb")
    newFile.write(binary_data)

    second_arr = np.fromfile("./Spectra/values_bin.txt", dtype=np.single)
    for i in range(len(arr)):
        x_values.append(x_first + (i * ((x_last - x_first) / len(arr))))
    return x_values, arr, second_arr



def start_func():
    start_function = my_dll.Start
    start_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
    start_function.restypes = [ctypes.c_int]
    warning = (ctypes.c_int * 1)()
    result = start_function(warning)
    return result, warning[0]


def init_func():
    init_function = my_dll.Init
    init_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
    init_function.restypes = [ctypes.c_int]
    warning = (ctypes.c_int * 1)()
    result = init_function(warning)
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
    return result, warning[0], list(conc)


def get_spectr_func():
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
    x_values = []
    binary_data = b""
    with open('./Spectra/original.spe', 'rb') as file:
        data = file.readlines()
        for line in data[36:-1]:
            binary_data = binary_data + line
    newFile = open("./Spectra/values_bin.txt", "wb")
    newFile.write(binary_data)

    second_arr = np.fromfile("./Spectra/values_bin.txt", dtype=np.single)
    for i in range(len(arr)):
        arr[i] = arr[i] - second_arr[i]
    for i in range(len(arr)):
        x_values.append(x_first + (i * ((x_last - x_first) / len(arr))))
    return x_values, list(arr)


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
        global simulation, plots_interval, params_interval, days_threshold
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

        plots_interval = int(self.combo1.currentText()[0:2])
        params_interval = self.combo2.currentText()
        max_val = "8000"
        min_val = "0"
        if self.max_entry.text() != '':
            if self.min_entry.text() != '':
                self.parent.plot2.setXRange(int(self.min_entry.text()), int(self.max_entry.text()))
                self.parent.plot1.setXRange(int(self.min_entry.text()), int(self.max_entry.text()))
                max_val = self.max_entry.text()
                min_val = self.min_entry.text()
            else:
                self.parent.plot2.setXRange(0, int(self.max_entry.text()))
                self.parent.plot1.setXRange(0, int(self.max_entry.text()))
                max_val = self.max_entry.text()
        elif self.min_entry.text() != '':
            self.parent.plot2.setXRange(int(self.min_entry.text()), 8000)
            self.parent.plot1.setXRange(int(self.min_entry.text()), 8000)
            min_val = self.min_entry.text()
        if self.save_entry != '':
            days_threshold = int(self.save_entry.text())
        else:
            days_threshold = 5
        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        json_data["simulation"] = str(simulation)
        json_data["method_path"] = method_path
        json_data["fspec_path"] = fspec_path
        json_data["params_period"] = self.combo2.currentText()
        json_data["plots_period"] = self.combo1.currentText()
        json_data["days_threshold"] = days_threshold
        json_data["limits"]["min"] = min_val
        json_data["limits"]["max"] = max_val
        with open('./config.json', 'w') as f:
            json.dump(json_data, f)

    def load(self):
        global method_path, fspec_path, params_interval, plots_interval, simulation, days_threshold
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
        self.combo1.setCurrentText(json_data["plots_period"])
        plots_interval = int(json_data["plots_period"][0:2])
        self.combo2.setCurrentText(json_data["params_period"])
        params_interval = json_data["params_period"]
        days_threshold = int(json_data["days_threshold"])
        self.save_entry.setText(str(days_threshold))
        self.min_entry.setText(json_data["limits"]["min"])
        self.max_entry.setText(json_data["limits"]["max"])
        self.parent.plot2.setXRange(int(json_data["limits"]["min"]), int(json_data["limits"]["max"]))
        self.parent.plot1.setXRange(int(json_data["limits"]["min"]), int(json_data["limits"]["max"]))

    def modbus_settings(self):
        self.modbus_popup = ModbusWindow(self)
        self.modbus_popup.show()

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
        label4.setText("Период обновления графиков")
        layout.addWidget(label4)
        self.combo1 = QtWidgets.QComboBox()
        self.combo1.addItems(["10 с", "20 с", "30 с", "40 с", "50 с", "60 с"])
        layout.addWidget(self.combo1)

        label5 = QtWidgets.QLabel()
        label5.setText("Период обновления параметров")
        layout.addWidget(label5)
        self.combo2 = QtWidgets.QComboBox()
        self.combo2.addItems(["1 ч", "12 ч", "24 ч"])
        layout.addWidget(self.combo2)

        label7 = QtWidgets.QLabel()
        label7.setText("Границы спектров по оси Х")
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

        label10 = QtWidgets.QLabel()
        label10.setText("Удалять архивы старше чем, дней")
        layout.addWidget(label10)
        self.save_entry = QtWidgets.QLineEdit()
        self.save_entry.setValidator(QtGui.QIntValidator())
        layout.addWidget(self.save_entry)
        self.load()

        modbus_button = QtWidgets.QPushButton()
        modbus_button.setText("Настройки ModBus")
        modbus_button.clicked.connect(self.modbus_settings)
        layout.addWidget(modbus_button)
        spacer = QtWidgets.QSpacerItem(20, 200, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        layout.addItem(spacer)
        save_button = QtWidgets.QPushButton()
        save_button.setText("Сохранить")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)

        if not stop_threads:
            button1.setEnabled(False)
            self.rb_on.setEnabled(False)
            self.rb_off.setEnabled(False)


class ModbusWindow(QDialog):
    def stop_client(self):
        global master, modbus_connected
        master = None
        modbus_connected = False
        self.error_label.setText("")
        self.connect_button.setText("Соединение")

    def start_client(self, device, PORT, baudrate, timeoutentry):
        global master, modbus_connected, device_num, port, timeout
        port = PORT
        if device == "" or timeout == "":
            modbus_connected = False
            self.error_label.setText("Соединение НЕ установлено")
        else:
            device_num = int(device)
            timeout = int(timeoutentry)
            try:
                try:
                    master = modbus_rtu.RtuMaster(
                        serial.Serial(port=PORT, baudrate=baudrate, bytesize=8, parity='N', stopbits=1, xonxoff=0)
                    )
                    master.set_timeout(int(timeout))
                    logger.info("connected")
                    modbus_connected = True
                    self.error_label.setText("Соединение установлено")
                    self.connect_button.setText("Отключиться")
                except serial.serialutil.SerialException:
                    modbus_connected = False
                    self.error_label.setText("Соединение НЕ установлено")
            except modbus_tk.modbus.ModbusError as exc:
                modbus_connected = False
                logger.error("%s- Code=%d", exc, exc.get_exception_code())
                self.error_label.setText("Соединение НЕ установлено")

    def toggle_label_and_function(self, device, PORT, baudrate, timeoutentry):
        if self.connect_button.text() == "Соединение":
            self.start_client(device, PORT, baudrate, timeoutentry)
        else:
            self.stop_client()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setFixedSize(400, 400)
        self.setWindowTitle("Настройки ModBus")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        layout = QVBoxLayout(self)
        available_ports = [i.device for i in serial.tools.list_ports.comports()]
        label1 = QtWidgets.QLabel()
        label1.setText("Адрес устройства")
        layout.addWidget(label1)
        self.device_entry = QtWidgets.QLineEdit()
        self.device_entry.setValidator(QtGui.QIntValidator())
        if device_num != 0:
            self.device_entry.setText(str(device_num))
        layout.addWidget(self.device_entry)

        label4 = QtWidgets.QLabel()
        label4.setText("Порт")
        layout.addWidget(label4)
        self.ports = QtWidgets.QComboBox()
        self.ports.addItems(available_ports)
        if port != '':
            self.ports.setCurrentText(port)
        layout.addWidget(self.ports)

        label2 = QtWidgets.QLabel()
        label2.setText("Скорость обмена, бит/с")
        layout.addWidget(label2)
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
        self.combo.setCurrentText("9600")
        layout.addWidget(self.combo)

        label3 = QtWidgets.QLabel()
        label3.setText("Таймаут, с")
        layout.addWidget(label3)
        self.timeout_entry = QtWidgets.QLineEdit()
        self.timeout_entry.setValidator(QtGui.QIntValidator())
        if timeout != 0:
            self.timeout_entry.setText(str(timeout))
        layout.addWidget(self.timeout_entry)

        label5 = QtWidgets.QLabel()
        label5.setText(
            "Карта регистров:\nПараметры записываются начиная с адреса 0\nКоды ошибок и предупреждений с 100 по 102")
        layout.addWidget(label5)
        self.connect_button = QtWidgets.QPushButton()
        self.error_label = QtWidgets.QLabel()
        self.error_label.setText("")
        if modbus_connected:
            self.connect_button.setText("Отключиться")
            self.error_label.setText("Соединение установлено")
        else:
            self.connect_button.setText("Соединение")
        self.connect_button.clicked.connect(lambda: self.toggle_label_and_function(self.device_entry.text(),
                                                                                   self.ports.currentText(),
                                                                                   self.combo.currentText(),
                                                                                   self.timeout_entry.text()))
        layout.addWidget(self.connect_button)

        layout.addWidget(self.error_label)


class Ui_MainWindow(object):
    def save_to_archive(self, conc, y):
        global days_threshold
        date_now = datetime.today().strftime('%y_%m_%d')
        archive_name = f'./Archive/{date_now}.csv'
        if os.path.exists(archive_name):
            mode = 'a'
        else:
            mode = 'w'
        with open(archive_name, mode=mode) as employee_file:
            employee_writer = csv.writer(employee_file, delimiter=';', quotechar='"',
                                         quoting=csv.QUOTE_MINIMAL)
            result_to_write = [datetime.today().strftime('%y_%m_%d_%H_%M_%S')] + conc + y
            employee_writer.writerow(result_to_write)

        current_time = datetime.now()
        directories = ["./Archive/", "./Reports/", "./Spectra/"]
        extensions = [".csv", ".txt", ".spe"]
        for i in range(len(directories)):
            for filename in os.listdir(directories[i]):
                file_path = os.path.join(directories[i], filename)
                if filename.endswith(extensions[i]):
                    try:
                        date_str = filename[0:8]
                        file_date = datetime.strptime(date_str, '%y_%m_%d')
                        days_difference = (current_time - file_date).days
                        if days_difference > days_threshold:
                            os.remove(file_path)
                    except ValueError:
                        pass
        for filename in os.listdir("./Log/"):
            file_path = os.path.join("./Log/", filename)
            if filename.endswith(".log"):
                try:
                    date_str = filename[11:19]
                    file_date = datetime.strptime(date_str, '%y_%m_%d')
                    days_difference = (current_time - file_date).days
                    if days_difference > days_threshold:
                        os.remove(file_path)
                except ValueError:
                    pass

    def run_thread(self):
        global stop_threads
        stop_threads = False
        if self.thread is not None:
            self.thread.join(0.01)
        self.thread = threading.Thread(target=self.update_trans_plot, daemon=True)
        self.thread.start()
        self.start_button.setText("Стоп")
        self.start_button.clicked.connect(self.stop_thread)
        self.fon_update.setEnabled(False)

    def run_fix_fon_thread(self):
        self.thread = threading.Thread(target=self.set_fixed_fon, daemon=True)
        self.thread.start()

    def stop_thread(self):
        global stop_threads
        stop_threads = True
        self.start_button.setText("Старт")
        self.start_button.clicked.connect(self.run_thread)
        self.fon_update.setEnabled(True)
        self.plot1.clear()
        self.plot2.clear()

    def generate_warnings(self, warning):
        self.warnings_box.clear()
        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        warnings = str(bin(warning))
        warnings = warnings[::-1]
        for i in range(len(warnings)):
            if warnings[i] == '1':
                self.warnings_box.addItem(str(json_data["warnings"].get(str(i))))

    def error_out(self, res):
        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        if res > 0:
            res = -500
        self.fspec_error.setText("Ошибка! " + str(json_data["errors"].get(str(res))))
        self.icon_label.show()
        self.stop_thread()

    def update_trans_plot(self):
        global first_start, zoom
        self.icon_label.hide()
        self.fspec_error.setText("")
        while not stop_threads:
            self.label_2.setText(str(fetch_data.res))
            self.label_3.setText(str(fetch_data.scans))
            self.label_4.setText(str(fetch_data.cuv_length))
            if first_start:
                self.plot1.enableAutoRange(axis=pg.ViewBox.YAxis)
                self.plot2.enableAutoRange(axis=pg.ViewBox.YAxis)
                res, warn = start_func()
                if res == 0:
                    res, warn = init_func()
                    if res == 0:
                        x, y, y2 = read_fon_spe()
                        self.plot1.update(x, y, y2)
                        res, warn, conc = get_value_func()
                        if res == 0:
                            conc = [number for number in conc if number != 0]
                            self.param_plots(conc, False)
                            if modbus_connected:
                                send_conc(device_num, conc)
                                send_res(device_num, res, warn)
                            self.generate_warnings(warn)
                            x, y = get_spectr_func()
                            self.save_to_archive(conc, y)
                            self.plot2.update(x, y)
                        else:
                            self.error_out(res)
                            if modbus_connected:
                                send_res(device_num, res, warn)
                            break
                    else:
                        self.error_out(res)
                        if modbus_connected:
                            send_res(device_num, res, warn)
                        break
                else:
                    self.error_out(res)
                    if modbus_connected:
                        send_res(device_num, res, warn)
                    break
                zoom = False
                first_start = False
                self.timer1.start()
            else:
                if self.timer1.hasExpired(plots_interval * 1000):
                    if not zoom:
                        self.plot1.disableAutoRange(axis=pg.ViewBox.YAxis)
                        self.plot2.disableAutoRange(axis=pg.ViewBox.YAxis)
                        zoom = False
                    res, warn = init_func()
                    if res == 0:
                        x, y, y2 = read_fon_spe()
                        self.plot1.update(x, y, y2)
                        res, warn, conc = get_value_func()
                        if res == 0:
                            conc = [number for number in conc if number != 0]
                            self.param_plots(conc, False)
                            if modbus_connected:
                                send_conc(device_num, conc)
                                send_res(device_num, res, warn)
                            self.generate_warnings(warn)
                            x, y = get_spectr_func()
                            self.save_to_archive(conc, y)
                            self.plot2.update(x, y)
                        else:
                            self.error_out(res)
                            if modbus_connected:
                                send_res(device_num, res, warn)
                            break
                    else:
                        self.error_out(res)
                        if modbus_connected:
                            send_res(device_num, res, warn)
                        break
                    self.timer1.restart()

    def set_fixed_fon(self):
        global first_start
        self.start_button.setEnabled(False)
        if first_start:
            res, warn = start_func()
            if res == 0:
                res, warn = init_func()
                if res == 0:
                    if os.path.exists("./Spectra/original.spe"):
                        os.remove("./Spectra/original.spe")
                    os.rename("./Spectra/fon.spe", "./Spectra/original.spe")
                    first_start = False
                    date = datetime.today().strftime('%d.%m.%y %H:%M:%S')
                    self.last_updated.setText("Дата обновления:\n" + date)
                    with open('./config.json', 'r', encoding="utf-8") as file:
                        json_data = json.load(file)
                    json_data["fon_updated"] = date
                    with open('./config.json', 'w') as f:
                        json.dump(json_data, f)
                else:
                    self.error_out(res)
                    if modbus_connected:
                        send_res(device_num, res, warn)
            else:
                self.error_out(res)
                if modbus_connected:
                    send_res(device_num, res, warn)
        else:
            res, warn = init_func()
            if res == 0:
                date = datetime.today().strftime('%d.%m.%y %H:%M:%S')
                self.last_updated.setText("Дата обновления:\n" + date)
                with open('./config.json', 'r', encoding="utf-8") as file:
                    json_data = json.load(file)
                json_data["fon_updated"] = date
                with open('./config.json', 'w') as f:
                    json.dump(json_data, f)
                if os.path.exists("./Spectra/original.spe"):
                    os.remove("./Spectra/original.spe")
                os.rename("./Spectra/fon.spe", "./Spectra/original.spe")
            else:
                self.error_out(res)
                if modbus_connected:
                    send_res(device_num, res, warn)
        self.start_button.setEnabled(True)

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
                plot = param_plot.ParameterPlot()
                plot.disableAutoRange(pg.ViewBox.XAxis)
                parameter.append(plot)
                widget.addItem(plot)
                widget.setBackground("w")
                layout.addLayout(param_layout, i, 0)
                layout.addWidget(widget, i, 1)
        else:
            for i in range(len(conc)):
                self.param_values[i].setText("{:.2f}".format(conc[i]))
                parameter[i].update(conc[i], params_interval)
                parameter[i].show()

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
        button_font.setPointSize(9)
        button_font.setBold(False)

        start_layout = QGridLayout()
        self.start_button = QtWidgets.QPushButton()
        self.start_button.setFixedSize(160, 100)
        self.start_button.setFont(button_font)
        self.start_button.setObjectName("start_button")
        self.start_button.clicked.connect(self.run_thread)
        if not os.path.exists("./Spectra/original.spe"):
            self.start_button.setEnabled(False)
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
        self.icon_label.setPixmap(
            QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning).pixmap(32))
        self.icon_label.hide()
        self.label_layout.addStretch()

        self.label_layout.addWidget(self.icon_label)
        self.fspec_error = QtWidgets.QLabel()
        self.fspec_error.setText("")
        self.fspec_error.setFont(error_font)
        self.fspec_error.setAlignment(QtCore.Qt.AlignCenter)
        self.label_layout.addWidget(self.fspec_error)

        self.fon_update = QtWidgets.QPushButton()
        self.fon_update.setFixedSize(160, 100)
        self.fon_update.setText("Взять спектр\nпустой кюветы")
        self.fon_update.setFont(button_font)
        self.fon_update.clicked.connect(self.run_fix_fon_thread)
        start_layout.addWidget(self.fon_update, 0, 3)
        self.last_updated = QtWidgets.QLabel()
        self.last_updated.setAlignment(QtCore.Qt.AlignCenter)
        with open('./config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        self.last_updated.setText("Дата обновления:\n" + json_data["fon_updated"])
        start_layout.addWidget(self.last_updated, 1, 3)
        start_layout.addLayout(self.label_layout, 1, 0, 1, 3)

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

        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setFixedSize(160, 100)
        self.settings_button.setFont(button_font)
        self.settings_button.clicked.connect(self.open_settings)
        set_layout = QVBoxLayout()
        set_layout.addWidget(self.settings_button)
        spacer = QtWidgets.QSpacerItem(0, 40, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        set_layout.addItem(spacer)
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
        self.settings.addLayout(set_layout)

        self.main_layout.addLayout(self.settings)
        self.main_layout.addLayout(self.graphs)
        ModalPopup(self).load()

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
