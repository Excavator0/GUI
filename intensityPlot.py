import pyqtgraph as pg


class IntensityPlot(pg.PlotItem):

    def __init__(self, parent=None, name=None, labels=None, title='Спектр интенсивности',
                 viewBox=None, axisItems=None, enableMenu=True):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.addLegend()
        self.showGrid(x=True, y=True, alpha=1)
        self.plot()
        self.getAxis("left").setTextPen("black")
        self.getAxis("bottom").setTextPen("black")
        self.transmission_data1 = None

    def update(self, x, y):
        self.clear()
        color1 = (158, 2, 2)
        self.transmission_data1 = pg.PlotDataItem(x, y, pen=color1)
        self.addItem(self.transmission_data1)


