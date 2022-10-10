import os
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QVariant
from PyQt5.QtCore import QAbstractTableModel, QModelIndex
from PyQt5.QtWidgets import QFileDialog


class MarkerData:

    def __init__(self):
        self.file_path = None
        self.channels = []
        self.times = []
        self.amplitudes = []
        self.frequencies = []
        self.powers = []
        self.delta_times = []
        self.delta_amplitudes = []
        self.delta_frequencies = []
        self.delta_powers = []
        self.comments = []
        self.keys = ['channels', 'times', 'amplitudes',
                     'frequencies', 'powers',
                     'delta_times', 'delta_amplitudes',
                     'delta_frequencies', 'delta_powers', 'comments']
        self.labels = ['channel', 'time/s', 'amplitude',
                       'frequency/Hz', 'power/dB',
                       'time-diff/s', 'ampl-diff',
                       'freq-diff/Hz', 'power-diff/dB', 'comment']

        
    def clear(self):
        self.channels = []
        self.times = []
        self.amplitudes = []
        self.frequencies = []
        self.powers = []
        self.delta_times = []
        self.delta_amplitudes = []
        self.delta_frequencies = []
        self.delta_powers = []
        self.comments = []


    def add_data(self, channel, time, amplitude, frequency, power):
        self.channels.append(channel)
        self.times.append(time if not time is None else np.nan)
        self.amplitudes.append(amplitude if not amplitude is None else np.nan)
        self.frequencies.append(frequency if not frequency is None else np.nan)
        self.powers.append(power if not power is None else np.nan)
        self.delta_times.append(np.nan)
        self.delta_amplitudes.append(np.nan)
        self.delta_frequencies.append(np.nan)
        self.delta_powers.append(np.nan)
        self.comments.append('')


    def set_delta(self, delta_time, delta_amplitude,
                  delta_frequency, delta_power):
        self.delta_times[-1] = delta_time if not delta_time is None else np.nan
        self.delta_amplitudes[-1] = delta_amplitude if not delta_amplitude is None else np.nan
        self.delta_frequencies[-1] = delta_frequency if not delta_frequency is None else np.nan
        self.delta_powers[-1] = delta_power if not delta_power is None else np.nan

        
    def set_comment(self, index, comment):
        self.comments[index] = comment


    def data_frame(self):
        table_dict = {}
        for key, label in zip(self.keys, self.labels):
            table_dict[label] = getattr(self, key)
        return pd.DataFrame(table_dict)


    
class MarkerDataModel(QAbstractTableModel):
    
    def __init__(self, data, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.data = data

        
    def rowCount(self, parent=None):
        return len(self.data.channels)

    
    def columnCount(self, parent=None):
        return len(self.data.keys)


    def headerData(self, index, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.data.labels[index]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return f'{index}'
        return QVariant()

    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        
        key = self.data.keys[index.column()]
        item = getattr(self.data, key)[index.row()]
        
        # data:
        if role == Qt.DisplayRole:
            if key == 'comments':
                return item
            else:
                if item is np.nan:
                    return '-'
                else:
                    return f'{item:.5g}'
                
        # alignment:
        if role == Qt.TextAlignmentRole:
            if key == 'comments':
                return Qt.AlignLeft
            else:
                if item is np.nan:
                    return Qt.AlignCenter
                else:
                    return Qt.AlignRight


    def clear(self):
        self.beginResetModel()
        self.data.clear()
        self.endResetModel()


    def save(self, parent):
        name = os.path.splitext(os.path.basename(self.data.file_path))[0]
        file_name = f'{name}-marker.csv'
        filters = 'All files (*);;Comma separated values (*.csv)'
        has_excel = False
        try:
            import openpyxl
            has_excel = True
            filters += ';;Excel spreadsheet (*.xlsx)'
        except ImportError:
            pass
        file_path = os.path.join(os.path.dirname(self.data.file_path),
                                 file_name)
        file_path = QFileDialog.getSaveFileName(parent, 'Save marker data',
                                                file_path, filters)[0]
        if file_path:
            df = self.data.data_frame()
            ext = os.path.splitext(file_path)[1]
            if has_excel and ext.lower() == '.xlsx':
                df.to_excel(file_path, index=False)
            else:
                df.to_csv(file_path, index=False)
            

    def add_data(self, channel, time, amplitude, frequency, power):
        self.beginInsertRows(QModelIndex(),
                             len(self.data.channels), len(self.data.channels))
        self.data.add_data(channel, time, amplitude, frequency, power)
        self.endInsertRows()

        
    def set_delta(self, delta_time, delta_amplitude,
                  delta_frequency, delta_power):
        self.data.set_delta(delta_time, delta_amplitude,
                            delta_frequency, delta_power)
        self.dataChanged.emit(self.index(len(self.data.channels)-1, 0),
                              self.index(len(self.data.channels)-1,
                                         len(self.data.keys)))
