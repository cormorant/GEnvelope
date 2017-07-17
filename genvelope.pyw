#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
import os
import sys
sys.stderr = open("genvelope_error.log", "a")
reload(sys)
sys.setdefaultencoding('utf8')
import datetime
import ConfigParser
import xlwt

from guidata.qt.QtGui import QMainWindow
from guidata.configtools import get_icon
from guidata.qthelpers import create_action, add_actions, get_std_icon

from PyQt4.QtCore import QSettings, QVariant, QSize, QDate, QTime, SIGNAL
from PyQt4.QtGui import (QApplication, QDialog, QFileDialog, QMessageBox,
    QPushButton, QToolButton, QVBoxLayout, QHBoxLayout, QWidget, QComboBox,
    QIcon, QDateEdit, QTimeEdit, QLabel, QFont)

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
plt.style.use('dark_background')

from baikal import BaikalFile
import numpy as np
from filter_design import butter_bandpass_filter, get_time


from obspy import UTCDateTime, Trace, Stream

__version__= u"0.0.1"
COMPANY_NAME = u'GIN SB RAS'
APP_NAME = u'G(raphical) Envelope calculation program'


# also read config file
def module_path():
    if hasattr(sys, "frozen"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)
# get current dir, may vary if run from EXE file
CurrDir = module_path()
# config filename
CONFIG_FILENAME = os.path.join(CurrDir, "genvelope.conf")
#!!! if not os.path.exists WHAT TO DO???

# frequencies
DEFAULT_FREQS = [(1.3, 0.3)]

# channels
CHANNEL_NAMES = ("N-S", "E-W", "Z")
CHANNELS = {
    "N-S": 0,
    "E-W": 1,
    "Z":   2,
}

# default stats
DEFAULT_STATS = {
    'network': "NT",
    'location': "LOC",
}

# 300 is 5 minutes (5 * 60)
Nsamples = 300


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowIcon(get_icon('settings.png'))
        self.setWindowTitle(APP_NAME)
        # menu
        self.create_menu()
        # resize to full screen
        self.showMaximized()
        # default settings
        self.Freqs = DEFAULT_FREQS
        self.data_dir = "data"
        # next create main frame order
        self.create_main_frame()
        # set dates
        self.Date = QDate(1990, 1, 1)
        self.Time = QTime(0, 0, 0, 0)
        # variables
        self.set_default_variables()
        # also connect clicking on plot with my func
        cid_down = self.figure.canvas.mpl_connect('button_release_event', self.OnRelease)
        # draw
        self.on_draw()

    def set_default_variables(self):
        """ default values """
        self.COLUMN_NUM = 0 # read first channel on load
        self.combo_box.setCurrentIndex(0)
        # baikal file etc
        self.bf = None # is BaikalFile object
        self.trace = None # ось Y
        self.freq = None
        # should we have variable for EventTime, if it is always = 0 ??? no...
        self.X_corr = 0
        # filter & amplitudes
        self.filtered = False
        self.button3.setChecked(False)
        self.button_apply.setEnabled(True)
        # dict for saving clicks and Points
        self.Points = {}

    def create_menu(self):
        file_menu = self.menuBar().addMenu(u"File")
        # load file
        load_xxfile_action = create_action(self, u"Load file (XX-5 format)",
            shortcut="Ctrl+O",
            icon=get_icon('fileimport.png'),
            triggered=self.load
        )
        #
        save_to_excel_action = create_action(self, u"Export to Excel",
            shortcut="Ctrl+S",
            icon=get_icon('filesave.png'),
            tip=u"Save",
            triggered=self.export_to_excel,
        )
        quit_action = create_action(self, u"Exit",
            shortcut="Ctrl+Q",
            icon=get_std_icon("DialogCloseButton"),
            tip=u"Quit application",
            triggered=self.close
        )
        # add all menu items
        add_actions(file_menu, (
            load_xxfile_action,
            #load_txtfile_action,
            None,
            save_to_excel_action,
            None,
            quit_action),
        )
        # about button
        # Edit menu
        about_menu = self.menuBar().addMenu(u"Help")
        about_action = create_action(self, u"About",
            triggered=self.about_action
        )
        add_actions(about_menu, (about_action,))

    def create_main_frame(self):
        font = QFont()
        font.setPointSize(14)
        self.main_frame = QWidget()
        #toolbar = self.addToolBar("Toolbar")
        self.statusBar().showMessage('Ready')
        # create Figure to draw on
        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        # Create the navigation toolbar, tied to the canvas 
        self.toolbar = NavigationToolbar(self.canvas, self)
 
        # Just some button 
        self.button = QPushButton(u'Open XX file')
        # add icon to button
        self.button.setIcon(QIcon(get_icon('fileimport.png')))
        self.button.setIconSize(QSize(24, 24))
        #
        self.button.clicked.connect(self.load)

        # load text file button
        self.button_text_file = QPushButton(u'Open ASCII file')
        self.button_text_file.setIcon(QIcon(get_icon('fileopen.png')))
        self.button_text_file.setIconSize(QSize(24, 24))
        self.button_text_file.clicked.connect(self.load_text_file)

        # change date/time
        self.date_edit = QDateEdit()
        self.date_edit.setEnabled(False)
        self.original_time_edit = QTimeEdit()
        self.original_time_edit.setEnabled(False)
        self.original_time_edit.setDisplayFormat("HH:mm:ss.zzz")
        self.time_edit = QTimeEdit()
        self.time_edit.setFont(font)
        self.time_edit.setDisplayFormat("HH:mm:ss.zzz")
        # set labels
        self.label_date = QLabel(u"Date:")
        self.label_date.setBuddy(self.date_edit)
        # --original time
        self.label_original_time = QLabel(u"Time (original):")
        self.label_original_time.setBuddy(self.original_time_edit)
        # change-able time
        self.label_time = QLabel(u"Time (0 on X-axis):")
        self.label_time.setBuddy(self.time_edit)
        # apply button
        self.button_apply = QPushButton(u"Apply")
        self.button_apply.setIcon(QIcon(get_icon('apply.png')))
        self.button_apply.setIconSize(QSize(24, 24))
        self.button_apply.clicked.connect(self.apply_time_shift)
        
        # choose channel button
        self.label_channels = QLabel(u"Channel:")
        self.select_channel = QPushButton(u"OK")
        self.select_channel.setIcon(QIcon(get_icon('apply.png')))
        self.select_channel.setIconSize(QSize(24, 24))
        # filtring...
        self.combo_box = QComboBox()
        self.label_channels.setBuddy(self.combo_box)
        # add items in comboBox
        for channel_name in CHANNEL_NAMES:
            self.combo_box.addItem(channel_name)
        self.combo_box.setFont(font)
        self.select_channel.clicked.connect(self.change_channel)
        
        self.button3 = QPushButton()
        self.button3.setText(u'Filter & amplitudes')
        self.button3.setCheckable(True)
        self.button3.setChecked(False)
        self.button3.setIcon(QIcon(get_icon('xmax.png')))
        self.button3.setIconSize(QSize(24, 24))
        #self.button3.clicked.connect(self.amplitudes)
        self.connect( self.button3, SIGNAL('clicked(bool)'), self.filter_data )

        # clear button
        self.clear_button = QPushButton(u"Clear")
        self.clear_button.setIcon(QIcon(get_icon('delete.png')))
        self.clear_button.setIconSize(QSize(24, 24))
        self.clear_button.clicked.connect(self.clear_points)

        # main layout is vertical
        main_layout = QVBoxLayout()
        
        buttons_layot = QHBoxLayout()
        buttons_layot.addWidget(self.button)
        buttons_layot.addWidget(self.button_text_file)
        buttons_layot.addStretch(1)
        # add date-time editor
        buttons_layot.addWidget(self.label_date)
        buttons_layot.addWidget(self.date_edit)
        buttons_layot.addWidget(self.label_original_time)
        buttons_layot.addWidget(self.original_time_edit)
        buttons_layot.addWidget(self.label_time)
        buttons_layot.addWidget(self.time_edit)
        buttons_layot.addWidget(self.button_apply)
        #
        buttons_layot.addWidget(self.label_channels)
        buttons_layot.addWidget(self.combo_box)
        buttons_layot.addWidget(self.select_channel)
        #layout.addWidget(self.button2)
        buttons_layot.addWidget(self.button3)
        buttons_layot.addWidget(self.clear_button)
        # main layot finally is
        main_layout.addLayout(buttons_layot)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)
        # final layout
        self.main_frame.setLayout(main_layout)
        self.setCentralWidget(self.main_frame)

    def toolbar_message(self, msg, delay=25000):
        self.statusBar().showMessage(msg, delay)

    def closeEvent(self, event):
        reply = QMessageBox.question(self, u'Message',
            u"Really exit?", QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # save settings
            settings = QSettings(COMPANY_NAME, APP_NAME)
            event.accept()
        else:
            event.ignore()

    def OnRelease(self, event):
        """ why doesnt work zoom, moving etc??? """
        #TODO: lets choose button in config file
        if not event.button == 1: return# middle button - forever (2)
        if event.inaxes:
            #print("%.4f\t%.4f" % (event.xdata, event.ydata))
            values = (event.xdata, event.ydata)
            try:
                self.Points[self.COLUMN_NUM] += [values]
            except KeyError:
                self.Points[self.COLUMN_NUM] = [values]
            (ymin, ymax) = self.ax.get_ylim()
            (xmin, xmax) = self.ax.get_xlim()
            #self.canvas.draw()
            self.on_draw(ymin, ymax, xmin, xmax)

    def showWarning(self, msg, header=u'Warning'):
        QMessageBox.question(self, header, msg, QMessageBox.Ok)

    #===========================
    def change_channel(self):
        text = self.combo_box.currentText()
        # save new channel
        self.COLUMN_NUM = CHANNELS[str(text)]
        # reload/redraw
        # also set not pressed filter button
        self.button3.setChecked(False)
        # reread
        self.trace = self.create_trace()
        self.filtered = False
        self.on_draw()
    
    def filter_data(self, pressed):
        """ filter data """
        self.trace = self.create_trace()
        if pressed:
            Freq, limit = self.Freqs[0]
            # limits
            low, high = Freq - limit, Freq + limit
            # filter
            self.trace.data = butter_bandpass_filter(self.trace.data, low, high,
                self.trace.stats.sampling_rate)
            self.trace.data = np.abs(self.trace.data)
            self.filtered = True
            self.freq = Freq
        else:
            self.freq = None
            self.filtered = False
        # draw
        self.on_draw()

    def create_trace(self, precision=3):
        """ create stream from header and data on given channel """
        header = self.bf.MainHeader
        date = datetime.datetime(*[header[k] for k in ("year", "month", "day")])
        delta = datetime.timedelta(seconds=header["to"])
        dt = date + delta
        # make utc datetime
        utcdatetime = UTCDateTime(dt, precision=precision)
        # get data
        data = (self.bf.traces[self.COLUMN_NUM].astype(float) *
            self.bf.ChannelHeaders[self.COLUMN_NUM]['koef_chan'])
        # demean
        data = data - data.mean()
        channel_name = self.bf.ChannelHeaders[self.COLUMN_NUM]['name_chan'][:3]
        # prepare header
        stats = DEFAULT_STATS.copy()
        stats.update({
            "station": header['station'].upper(),
            'channel': channel_name,
            'sampling_rate': int( round( 1. / header["dt"] ) ),
            "delta": float("%.4f" % header["dt"]),#header["dt"],
            "npts": data.size,
            'starttime': utcdatetime,
        })
        # make trace
        trace = Trace(header=stats, data=data)
        return trace
    
    def load(self):
        """ load XX file """
        # first set dafult values
        self.set_default_variables()
        # open file dialog
        filename = QFileDialog.getOpenFileName(self, "Open Baikal-5 file",
            self.data_dir, "Any file (*.*)")
        if not filename: return
        bf = BaikalFile(filename)
        if not bf.valid:
            QMessageBox.warning(self, "Error loading XX file", "File not in Baikal-5 format!")
            return
        self.toolbar_message("Opening file %s ..." % filename)
        # read Trace object from xx-file
        self.bf = bf
        self.trace = self.create_trace()
        # load date and time
        self.Date = QDate(*(bf.MainHeader[k] for k in ("year", "month", "day")))
        self.Time = QTime(*get_time(bf.MainHeader["to"]))
        self.original_time_edit.setTime(self.Time)
        # plot
        self.on_draw()

    def load_text_file(self):
        """ load text file """
        filename = QFileDialog.getOpenFileName(self, "Open text file", "",
            "Any file (*.*)")
        try:
            self.data = np.loadtxt(str(filename), usecols=(self.COLUMN_NUM,))
        except BaseException as e:
            self.toolbar_message("Error loading text file: {}".format(e))
        else:
            self.set_default_variables()
            # plot
            self.on_draw()

    def clear_points(self):
        """ clear (red) points on canvas on current freq """
        # clear for current channel
        cleared = self.Points.pop( self.COLUMN_NUM )
        # set message
        msg = "Cleared on channel {}: {}".format(CHANNEL_NAMES[self.COLUMN_NUM],
            cleared)
        self.toolbar_message(msg)
        self.on_draw()

    def about_action(self):
        """ show about message """
        msg = "Program '{}', \n version {}, \n developed by {}".format(APP_NAME,
            __version__, COMPANY_NAME)
        self.showWarning(msg, header=u"About")
    
    def on_draw(self, ymin=None, ymax=None, xmin=None, xmax=None):
        """ Redraws the figure """
        # set date-time's even if we have no data loaded
        self.date_edit.setDate(self.Date)
        self.time_edit.setTime(self.Time)
        if self.trace is None: return
        # clear the axes and to plot a new one
        self.ax.clear()
        # plot original seismogram
        x_time = self.trace.times()
        #print "Also moved X on_draw: corr = %s" % self.X_corr
        self.ax.plot(
            x_time + self.X_corr, # X
            self.trace.data,# Y
            "-", color="c", lw=1.75
        )
        # mark Event time by vertical line (Event time is ALWAYS == 0 !!!)
        self.ax.axvline(x=0, color="r", lw=1.5)
        #== Points: is there any points to plot?
        if self.Points:
            if self.filtered:
                try:
                    points = self.Points[self.COLUMN_NUM]
                except KeyError:
                    pass
                else:
                    x_points = [point[0] for point in points]
                    y_points = [point[1] for point in points]
                    self.ax.plot(x_points, y_points, "o-r", markersize=7)
        # set y limit (>0)
        self.ax.set_ylim(ymin, ymax)
        # set x limit (>0)
        if (xmin is None) and (xmax is None):
            self.ax.set_xlim(x_time.min()-10, x_time.max()+10)
        else:
            self.ax.set_xlim(xmin, xmax)
        # adjust canvas and show
        self.figure.tight_layout()
        self.ax.grid(True)
        self.canvas.draw()

    def apply_time_shift(self):
        """ shift seismogramm """
        # текущая дата
        date = self.Date.toPyDate()
        # current time is 0
        current_time = datetime.datetime.combine( date, self.original_time_edit.time().toPyTime() )
        # new time
        new_time = datetime.datetime.combine( date, self.time_edit.time().toPyTime() )
        # if more
        if new_time < current_time:
            # then merge
            delta = current_time - new_time# calc difference
            seconds = delta.total_seconds()
            self.X_corr = seconds
        elif new_time > current_time:
            seconds = (new_time - current_time).total_seconds()
            self.X_corr = -1 * seconds
        else: return
        # also save global Time
        self.Time = self.time_edit.time()
        # finally disable buuton
        self.button_apply.setEnabled(False)
        self.on_draw()

    def export_to_excel(self):
        """ exporting to excel"""
        WorkBook = xlwt.Workbook(encoding="utf8")
        # which freqs
        Freqs = [ self.Freqs[0][0] ]
        # add sheets with Freq as name
        sheets = [ WorkBook.add_sheet(channel) for channel in CHANNEL_NAMES ]
        #= writing values to sheets
        # write headers on each list
        for sheet in sheets:
            sheet.write(0, 0, "x")
            # also write not just y, but y_filename (from self.bf.filename)
            sheet.write(0, 1, "y")#_%s" % self.bf.filename.split('.')[0])
        # write values itself, but only where we have values
        for i_num, sheet in enumerate(sheets):
            row = 1
            # check whether we have there any values
            try:
                values = self.Points[i_num]
            except KeyError:
                continue
            if not values: continue
            # write X, Y
            for x, y in values:
                sheet.write(row, 0, x) # x
                sheet.write(row, 1, y) # y
                row += 1
        #=
        # finally save
        if hasattr(self.bf, "filename"):
            outfilename = "{}.xls".format(self.bf.filename)
        else:
            outfilename = "111.xls"
        try:
            WorkBook.save(outfilename)
        except IOError, e:
            self.showWarning(e, header=u"Ошибка")
        else:
        #===
            msg = u"File \"{}\"\n saved succesfully.".format(outfilename)
            self.showWarning(msg=msg)

if __name__ == '__main__':
    # create Main Window
    from guidata.qt.QtGui import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
