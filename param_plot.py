from datetime import datetime

import pyqtgraph as pg
from collections import deque

import pytz

UNIX_EPOCH_naive = datetime(1970, 1, 1, 0, 0)  # offset-naive datetime
UNIX_EPOCH_offset_aware = datetime(1970, 1, 1, 0, 0, tzinfo=pytz.utc)  # offset-aware datetime
UNIX_EPOCH = UNIX_EPOCH_naive

TS_MULT_us = 1e6


def now_timestamp(ts_mult=TS_MULT_us, epoch=UNIX_EPOCH):
    return int((datetime.now() - epoch).total_seconds() * ts_mult)


def int2dt(ts, ts_mult=TS_MULT_us):
    return datetime.utcfromtimestamp(float(ts) / ts_mult)


class TimeAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [int2dt(value).strftime("%H:%M:%S") for value in values]


class ParameterPlot(pg.PlotItem):
    def __init__(self, parent=None, name=None, labels=None, title=None,
                 viewBox=None, axisItems=None, enableMenu=True, stack_size=0):
        super().__init__(parent, name, labels, title, viewBox, axisItems, enableMenu)
        self.stack_size = stack_size
        self.data = deque(maxlen=self.stack_size)
        self.plot = self.plot()
        self.y = deque(maxlen=self.stack_size)
        self.x = deque(maxlen=self.stack_size)

    def update(self, conc):
        self.clear()
        self.y.append(conc)
        self.x.append(now_timestamp())
        param_data = pg.PlotDataItem(list(self.x), list(self.y), pen=None, symbol='o', symbolSize=6)
        date_axis = TimeAxisItem(orientation='bottom')
        self.setAxisItems(axisItems={'bottom': date_axis})

        self.addItem(param_data)

    def change_size(self, new_size):
        self.y = deque(self.y, maxlen=new_size)
        self.x = deque(self.x, maxlen=new_size)
        self.stack_size = new_size
