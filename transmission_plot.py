import pyqtgraph as pg


class TransmissionPlot(pg.PlotItem):

    def __init__(self, parent=None, name=None, labels=None, title='Спектр пропускания',
                 viewBox=None, axisItems=None, enableMenu=True):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.addLegend()
        self.showGrid(x=True, y=True, alpha=1)
        self.plot()
        self.getAxis("left").setTextPen("black")
        self.getAxis("bottom").setTextPen("black")


        self.transmission_data1 = None
        self.transmission_data2 = None
        self.transmission_data3 = None
        self.transmission_data4 = None
        self.transmission_data5 = None

        self.counter = 0

    def update(self, x, y):
        color1 = (158, 2, 2)
        color2 = (2, 44, 158)
        color3 = (1, 122, 23)
        color4 = (90, 1, 112)
        color5 = (150, 86, 2)
        if self.counter == 0:
            self.transmission_data1 = pg.PlotDataItem(x, y, pen=color1)
            self.addItem(self.transmission_data1)
            self.counter += 1
        elif self.counter == 1:
            self.transmission_data2 = pg.PlotDataItem(x, y, pen=color2)
            self.addItem(self.transmission_data2)
            self.counter += 1
        elif self.counter == 2:
            self.transmission_data3 = pg.PlotDataItem(x, y, pen=color3)
            self.addItem(self.transmission_data3)
            self.counter += 1
        elif self.counter == 3:
            self.transmission_data4 = pg.PlotDataItem(x, y, pen=color4)
            self.addItem(self.transmission_data4)
            self.counter += 1
        elif self.counter == 4:
            self.transmission_data5 = pg.PlotDataItem(x, y, pen=color5)
            self.addItem(self.transmission_data5)
            self.counter += 1
        else:
            self.clear()
            self.transmission_data1 = self.transmission_data2
            self.transmission_data2 = self.transmission_data3
            self.transmission_data3 = self.transmission_data4
            self.transmission_data4 = self.transmission_data5
            self.transmission_data1.setPen(color1)
            self.transmission_data2.setPen(color2)
            self.transmission_data3.setPen(color3)
            self.transmission_data4.setPen(color4)

            self.transmission_data5 = pg.PlotDataItem(x, y, pen=color5)
            self.addItem(self.transmission_data1)
            self.addItem(self.transmission_data2)
            self.addItem(self.transmission_data3)
            self.addItem(self.transmission_data4)
            self.addItem(self.transmission_data5)
            self.counter += 1

