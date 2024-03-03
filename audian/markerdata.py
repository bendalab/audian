import os
import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QVariant
from PyQt5.QtCore import QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QKeySequence, QIcon, QIconEngine, QColor
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QTableView
from PyQt5.QtWidgets import QPushButton, QDialog, QDialogButtonBox, QFileDialog
from PyQt5.QtWidgets import QStyledItemDelegate, QComboBox, QAction, QMessageBox
try:
    from PyQt5.QtWidgets import QKeySequenceEditor
    has_key_editor = True
except ImportError:
    has_key_editor = False


""" Colors from https://github.com/bendalab/plottools/colors.py """
colors_vivid = dict()
colors_vivid['red'] = '#D71000'
colors_vivid['orange'] = '#FF9000'
colors_vivid['yellow'] = '#FFF700'
colors_vivid['lightgreen'] = '#B0FF00'
colors_vivid['green'] = '#30D700'
colors_vivid['darkgreen'] = '#00A050'
colors_vivid['cyan'] = '#00D0B0'
colors_vivid['lightblue'] = '#00B0C7'
colors_vivid['blue'] = '#1040C0'
colors_vivid['purple'] = '#8000C0'
colors_vivid['magenta'] = '#B000B0'
colors_vivid['pink'] = '#E00080'

colors = colors_vivid


if has_key_editor:

    class KeySequenceDelegate(QStyledItemDelegate):

        def __init__(self, parent=None):
            super().__init__(parent)


        def createEditor(self, parent, option, index):
            editor = QKeySequenceEditor(parent)
            return editor


        def setEditorData(self, editor, index):
            value = index.model().data(index, Qt.EditRole)
            editor.setKeySequence(value)


        def setModelData(self, editor, model, index):
            value = editor.keySequence()
            model.setData(index, value.toString(), Qt.EditRole)


        def updateEditorGeometry(self, editor, option, index):
            editor.setGeometry(option.rect)


class ColorIconEngine(QIconEngine):

    def __init__(self, color):
        super().__init__()
        self.color = colors[color]


    def paint(self, painter, rect, mode=QIcon.Normal, state=QIcon.Off):
        painter.setBrush(QColor('black'))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)
        painter.setBrush(QColor(self.color))
        painter.setPen(Qt.NoPen)
        d = rect.width()//5
        painter.drawEllipse(rect.adjusted(d, d, -d, -d))


class ColorDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        super().__init__(parent)


    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        for c in colors:
            editor.addItem(index.model().icons[c], c)
        editor.setEditable(False)
        return editor


    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        editor.setCurrentText(value)


    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.EditRole)


    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


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
    
    def __init__(self, labels, acts, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.orig_labels = labels
        self.labels = [x.copy() for x in labels]
        self.header = ['label', 'key', 'color']
        self.dialog = None
        self.view = None
        self.key_delegate = None
        self.acts = acts
        self.icons = {}
        for c in colors:
            self.icons[c] = QIcon(ColorIconEngine(c))

        
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

        # icons:
        if role == Qt.DecorationRole:
            label = self.labels[index.row()]
            if index.column() == 2:
                return self.icons[label.color]
                
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
            act = self.find_action(value)
            if not act is None:
                act_text = act.text().replace('&', '')
                QMessageBox.information(self.parent(), "Audian key shortcut",
                                        f'Key shortcut <b>{value}</b> for label <b>{self.labels[index.row()].label}</b> disables <b>{act_text}</b>')
        elif index.column() == 2:
            self.labels[index.row()].color = value
        else:
            return False
        self.dataChanged.emit(index, index)
        return True


    def find_action(self, key_shortcut):
        ks = QKeySequence(key_shortcut)
        for a in dir(self.acts):
            act = getattr(self.acts, a)
            if isinstance(act, QAction) and act.shortcut() == ks:
                return act
        return None

                
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
            color = list(colors.keys())[(row+k)%len(colors)]
            self.labels.insert(row+k, MarkerLabel(chr(ord('A')+row+k),
                                                  '', color))
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
            rows = [r.row() for r in selection.selectedRows()]
            for r in reversed(sorted(rows)):
                self.removeRow(r)

    
    def edit(self, parent):
        if not self.dialog is None:
            return
        xwidth = parent.fontMetrics().averageCharWidth()
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
        self.view.setColumnWidth(0, max(8*xwidth,
                                        self.view.columnWidth(0)) +
                                 4*xwidth)
        self.view.setColumnWidth(2, max(12*xwidth,
                                        self.view.columnWidth(2)))
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setSelectionBehavior(self.view.SelectRows)
        if has_key_editor:
            self.key_delegate = KeySequenceDelegate(self.dialog)
            self.view.setItemDelegateForColumn(1, self.key_delegate)
        color_delegate = ColorDelegate(self.dialog)
        self.view.setItemDelegateForColumn(2, color_delegate)
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
        width = 50 + delb.sizeHint().width()
        width += self.view.verticalHeader().width()
        for c in range(self.columnCount()):
            width += self.view.columnWidth(c)
        self.dialog.setMaximumWidth(width)
        self.dialog.resize(width, 30*xwidth)
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
        self.texts = []
        self.keys = ['channels', 'times', 'amplitudes',
                     'frequencies', 'powers',
                     'delta_times', 'delta_amplitudes',
                     'delta_frequencies', 'delta_powers', 'labels', 'texts']
        self.headers = ['channel', 'time/s', 'amplitude',
                       'frequency/Hz', 'power/dB',
                       'time-diff/s', 'ampl-diff',
                        'freq-diff/Hz', 'power-diff/dB', 'label', 'text']

        
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
        self.texts = []


    def add_data(self, channel, time, amplitude=None,
                 frequency=None, power=None,
                 delta_time=None, delta_amplitude=None,
                 delta_frequency=None, delta_power=None,
                 label='', text=''):
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
        self.texts.append(text)

        
    def set_label(self, index, label):
        self.labels[index] = label

        
    def set_text(self, index, text):
        self.texts[index] = text


    def data_frame(self):
        table_dict = {}
        for key, header in zip(self.keys, self.headers):
            table_dict[header] = getattr(self, key)
        return pd.DataFrame(table_dict)


    def set_markers(self, locs, labels, rate):
        for i in range(len(locs)):
            l = ''
            t = ''
            if i < len(labels):
                l = labels[i,0]
                t = labels[i,1]
            tstart = float(locs[i,0])/rate
            tspan = float(locs[i,1])/rate
            self.add_data(0, tstart + tspan, delta_time=tspan,
                          label=l, text=t)

            
    def get_markers(self, rate):
        n = len(self.times)
        locs = np.zeros((n, 2), dtype=int)
        labels = np.zeros((n, 3), dtype=object)
        for k in range(n):
            ispan = int(np.round(self.delta_times[k]*rate))
            i1 = int(np.round(self.times[k]*rate))
            locs[k,0] = i1 - ispan
            locs[k,1] = ispan
            labels[k,0] = self.labels[k]
            labels[k,1] = self.texts[k]
        return locs, labels
    
            
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
            if key == 'labels' or key == 'texts':
                return item
            else:
                if item is np.nan:
                    return '-'
                else:
                    return f'{item:.5g}'
                
        # alignment:
        if role == Qt.TextAlignmentRole:
            if key == 'labels' or key == 'texts':
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
