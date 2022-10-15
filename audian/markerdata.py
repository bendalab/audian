import os
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QVariant
from PyQt5.QtCore import QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QTableView
from PyQt5.QtWidgets import QPushButton, QDialog, QDialogButtonBox, QFileDialog


class MarkerLabel:

    def __init__(self, label, key_shortcut, color, action=None):
        self.label = label
        self.key_shortcut = key_shortcut
        self.color = color
        self.action = action


    def copy(self):
        ml = MarkerLabel(self.label, self.key_shortcut, self.color, self.action)
        return ml

    
class MarkerLabelsModel(QAbstractTableModel):
    
    def __init__(self, labels, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.orig_labels = labels
        self.labels = [x.copy() for x in labels]
        self.header = ['label', 'key', 'color']
        self.dialog = None
        self.view = None

        
    def rowCount(self, parent=None):
        return len(self.labels)

    
    def columnCount(self, parent=None):
        return 3


    def headerData(self, index, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[index]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return f'{index}'
        return QVariant()

    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        
        # data:
        if role == Qt.DisplayRole or role == Qt.EditRole:
            label = self.labels[index.row()]
            if index.column() == 0:
                return label.label
            elif index.column() == 1:
                return label.key_shortcut
            elif index.column() == 2:
                return label.color
            else:
                return QVariant()
                
        # alignment:
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter

        return QVariant()

    
    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlag
        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled | Qt.ItemIsEditable
        return flags


    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        if index.column() == 0:
            self.labels[index.row()].label = value
        elif index.column() == 1:
            self.labels[index.row()].key_shortcut = value
        elif index.column() == 2:
            self.labels[index.row()].color = value
        else:
            return False
        self.dataChanged.emit(index, index)
        return True


    def store(self):
        for k in range(len(self.labels)):
            if k < len(self.orig_labels):
                self.orig_labels[k] = self.labels[k]
            else:
                self.orig_labels.append(self.labels[k])

                
    def set(self, labels):
        self.beginResetModel()
        self.orig_labels = labels
        self.labels = [x.copy() for x in labels]
        self.endResetModel()


    def insertRows(self, row, count, parent=QModelIndex()):
        if row > len(self.labels):
            return False
        self.beginInsertRows(parent, row, row+count-1)
        for k in range(count):
            self.labels.insert(row+k, MarkerLabel(f'events{row+k+1}', '', ''))
        self.endInsertRows()
        return True

        
    def add_row(self):
        self.insertRows(len(self.labels), 1)


    def removeRows(self, row, count, parent=QModelIndex()):
        if row >= len(self.labels):
            return False
        self.beginRemoveRows(parent, row, row+count-1)
        for k in range(count):
            self.labels.pop(row)
        self.endRemoveRows()
        return True

        
    def remove_rows(self):
        selection = self.view.selectionModel()
        if selection.hasSelection():
            for r in selection.selectedRows():
                self.removeRow(r.row())

    
    def edit(self, parent):
        if not self.dialog is None:
            return
        xheight = parent.fontMetrics().ascent()
        self.dialog = QDialog(parent)
        self.dialog.setWindowTitle('Audian label editor')
        vbox = QVBoxLayout()
        vbox.setContentsMargins(10, 10, 10, 10)
        self.dialog.setLayout(vbox)
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        vbox.addLayout(hbox)
        self.view = QTableView()
        self.view.setModel(self)
        self.view.resizeColumnsToContents()
        self.view.setColumnWidth(0, max(8*xheight, self.view.columnWidth(0)) + 4*xheight)
        hbox.addWidget(self.view)
        bbox = QVBoxLayout()
        bbox.setContentsMargins(0, 0, 0, 0)
        hbox.addLayout(bbox)
        addb = QPushButton('&Add')
        addb.clicked.connect(self.add_row)
        bbox.addWidget(addb)
        delb = QPushButton('&Remove')
        delb.clicked.connect(self.remove_rows)
        bbox.addWidget(delb)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel |
                                   QDialogButtonBox.Ok)
        buttons.rejected.connect(self.dialog.reject)
        buttons.accepted.connect(self.dialog.accept)
        vbox.addWidget(buttons)
        width = 20 + delb.sizeHint().width()
        width += self.view.verticalHeader().width() + 24
        for c in range(self.columnCount()):
            width += self.view.columnWidth(c)
        self.dialog.setMaximumWidth(width)
        self.dialog.resize(width, 20*xheight)
        self.dialog.finished.connect(self.finished)
        self.dialog.show()


    def finished(self, result=0):
        if result == QDialog.Accepted:
            self.store()
        self.dialog = None


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
        self.labels = []
        self.keys = ['channels', 'times', 'amplitudes',
                     'frequencies', 'powers',
                     'delta_times', 'delta_amplitudes',
                     'delta_frequencies', 'delta_powers', 'labels']
        self.headers = ['channel', 'time/s', 'amplitude',
                       'frequency/Hz', 'power/dB',
                       'time-diff/s', 'ampl-diff',
                       'freq-diff/Hz', 'power-diff/dB', 'label']

        
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
        self.labels = []


    def add_data(self, channel, time, amplitude, frequency, power,
                 delta_time=None, delta_amplitude=None,
                 delta_frequency=None, delta_power=None, label=''):
        self.channels.append(channel)
        self.times.append(time if not time is None else np.nan)
        self.amplitudes.append(amplitude if not amplitude is None else np.nan)
        self.frequencies.append(frequency if not frequency is None else np.nan)
        self.powers.append(power if not power is None else np.nan)
        self.delta_times.append(delta_time if not delta_time is None else np.nan)
        self.delta_amplitudes.append(delta_amplitude if not delta_amplitude is None else np.nan)
        self.delta_frequencies.append(delta_frequency if not delta_frequency is None else np.nan)
        self.delta_powers.append(delta_power if not delta_power is None else np.nan)
        self.labels.append(label)

        
    def set_label(self, index, label):
        self.labels[index] = label


    def data_frame(self):
        table_dict = {}
        for key, header in zip(self.keys, self.headers):
            table_dict[header] = getattr(self, key)
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
            return self.data.headers[index]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return f'{index}'
        return QVariant()

    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        
        key = self.data.keys[index.column()]
        item = getattr(self.data, key)[index.row()]
        
        # data:
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if key == 'labels':
                return item
            else:
                if item is np.nan:
                    return '-'
                else:
                    return f'{item:.5g}'
                
        # alignment:
        if role == Qt.TextAlignmentRole:
            if key == 'labels':
                return Qt.AlignLeft | Qt.AlignVCenter
            else:
                if item is np.nan:
                    return Qt.AlignHCenter | Qt.AlignVCenter
                else:
                    return Qt.AlignRight | Qt.AlignVCenter

        return QVariant()

    
    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlag
        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        key = self.data.keys[index.column()]
        if key == 'labels':
            return flags | Qt.ItemIsEditable
        else:
            return flags


    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        key = self.data.keys[index.column()]
        if key == 'labels':
            self.data.labels[index.row()] = value
            self.dataChanged.emit(index, index)
            return True
        else:
            return False
        

    def clear(self):
        self.beginResetModel()
        self.data.clear()
        self.endResetModel()


    def save(self, parent):
        name = os.path.splitext(os.path.basename(self.data.file_path))[0]
        file_name = f'{name}-events.csv'
        filters = 'All files (*);;Comma separated values CSV (*.csv)'
        has_excel = False
        try:
            import openpyxl
            has_excel = True
            filters += ';;Excel spreadsheet XLSX (*.xlsx)'
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
            

    def add_data(self, channel, time, amplitude, frequency, power,
                 delta_time=None, delta_amplitude=None,
                 delta_frequency=None, delta_power=None, label=''):
        self.beginInsertRows(QModelIndex(),
                             len(self.data.channels), len(self.data.channels))
        self.data.add_data(channel, time, amplitude, frequency, power,
                           delta_time, delta_amplitude,
                           delta_frequency, delta_power, label)
        self.endInsertRows()
