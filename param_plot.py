import pyqtgraph as pg
from collections import deque


class ParameterPlot(pg.PlotItem):
    def __init__(self, parent=None, name=None, labels=None, title=None,
                 viewBox=None, axisItems=None, enableMenu=True, stack_size=0):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.hideAxis(axis='bottom')
        self.stack_size = stack_size

        self.plot()
        self.y = deque(maxlen=self.stack_size)

    def update(self, conc):
        self.clear()
        self.y.append(conc)
        x = list(range(len(list(self.y))))
        param_data = pg.PlotDataItem(x, list(self.y), pen=(2, 80, 158))
        self.addItem(param_data)

    def change_size(self, new_size):
        self.y = deque(self.y, maxlen=new_size)
