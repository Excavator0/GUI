from datetime import datetime

import pyqtgraph as pg
from collections import deque


class ParameterPlot(pg.PlotItem):
    def __init__(self, parent=None, name=None, labels=None, title=None,
                 viewBox=None, axisItems=None, enableMenu=True, stack_size=0):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.stack_size = stack_size
        self.data = deque(maxlen=self.stack_size)
        self.plot = self.plot()
        self.y = deque(maxlen=self.stack_size)
        self.x = deque(maxlen=self.stack_size)
        self.counter = 0
        self.times = []

    def update(self, conc):
        self.clear()
        self.y.append(conc)
        self.counter += 1
        self.x.append(self.counter)
        self.time_now = datetime.now().strftime("%H:%M:%S")
        self.times.append((self.counter, self.time_now))
        param_data = pg.PlotDataItem(list(self.x), list(self.y), pen=None, symbol='o')

        self.addItem(param_data)
        ax = self.getAxis('bottom')
        ax.setTicks([self.times[-self.stack_size:]])

    def change_size(self, new_size):
        self.y = deque(self.y, maxlen=new_size)
        self.x = deque(self.x, maxlen=new_size)
        self.counter = 0
