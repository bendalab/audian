import numpy as np
import pandas as pd


class MarkerData:

    def __init__(self):
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


    def print(self):
        table_dict = {}
        keys = ['channels', 'times', 'amplitudes', 'frequencies', 'powers',
                'delta_times', 'delta_amplitudes',
                'delta_frequencies', 'delta_powers', 'comments']
        labels = ['channel', 'time/s', 'amplitude', 'frequency/Hz', 'power/dB',
                  'd-time/s', 'd-amplitude',
                  'd-frequency/Hz', 'd-power/dB', 'comment']
        for key, label in zip(keys, labels):
            table_dict[label] = getattr(self, key)
        table = pd.DataFrame(table_dict)
        print(table)

