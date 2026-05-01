"""CompressedData

Handle compressed and cached data for FullTracePlot.
"""

import os
import sys
import json
import argparse
import ctypes as c
import numpy as np

from pathlib import Path
from datetime import datetime
from multiprocessing import Process, Array, set_start_method

from audioio import AudioLoader
from audioio import load_audio, write_audio
from audioio.audioconverter import parse_load_kwargs
from thunderlab.dataloader import DataLoader

from .version import __version__, __year__, audian_dirs


def down_sample_worker(proc_idx, num_proc, nblock, step, array,
                       file_paths, tbuffer, rate, channels, unit, amax,
                       end_indices, unwrap_thresh, unwrap_clips, load_kwargs):
    """ Worker for prepare() """
    if end_indices is None:
        data = DataLoader(file_paths, tbuffer, 0,
                          verbose=0, **load_kwargs)
    else:
        data = DataLoader(file_paths, tbuffer, 0,
                          verbose=0, rate=rate, channels=channels,
                          unit=unit, amax=amax, end_indices=end_indices,
                          **load_kwargs)
    data.set_unwrap(unwrap_thresh, unwrap_clips, False, data.unit)
    datas = np.frombuffer(array.get_obj()).reshape((-1, data.channels))
    buffer = np.zeros((nblock, data.channels))
    segments = np.arange(0, len(buffer), step)
    for index in range(proc_idx*nblock, data.frames, num_proc*nblock):
        if data.frames - index < nblock:
            nblock = data.frames - index
            buffer = buffer[:nblock, :]
            segments = np.arange(0, len(buffer), step)
        data.load_buffer(index, nblock, buffer)
        i = 2*index//step
        with array.get_lock():
            np.minimum.reduceat(buffer, segments,
                                out=datas[i + 0:i + 0 + 2*len(segments):2])
            np.maximum.reduceat(buffer, segments,
                                out=datas[i + 1:i + 1 + 2*len(segments):2])
    return None


class CompressedData:

    fulltraces_file = 'fulltraces.json'
    max_files = 1000
    
    def __init__(self, data): #, files, load_kwargs, unwrap, unwrap_clip):
        self.data = data
        self.procs = []
        self.shared_array = None
        self.times = None
        self.datas = None
        self.short_data = True

    def __del__(self):
        self.close()
        
    def close(self):
        for proc in self.procs:
            proc.terminate()
            proc.join()
            proc.close()
        self.procs = []

    def start(self, max_pixel, load_kwargs, do_short=True):
        if self.times is not None and self.datas is not None:
            return
        self.procs = []
        step = max(1, self.data.frames//max_pixel)
        nblock = max(step, int(30.0*self.data.rate//step)*step)
        end_indices = None
        if len(self.data.file_paths) > 1:
            end_indices = self.data.end_indices
        self.times = np.arange(0, self.data.frames + step - 1,
                               step/2)/self.data.rate
        if len(self.data.buffer) == self.data.frames:
            # short file, do not compress in background:
            self.short_data = True
            if do_short:
                segments = np.arange(0, self.data.frames, step)
                self.datas = np.zeros((1 + 2*len(segments),
                                       self.data.channels))
                np.minimum.reduceat(self.data.buffer, segments,
                                    out=self.datas[0:0 + 2*len(segments):2])
                np.maximum.reduceat(self.data.buffer, segments,
                                    out=self.datas[1:1 + 2*len(segments):2])
            return
        # compress in background:        
        self.short_data = False
        self.shared_array = Array(c.c_double, len(self.times)*self.data.channels)
        self.datas = np.frombuffer(self.shared_array.get_obj())
        self.datas = self.datas.reshape((len(self.times), self.data.channels))
        nprocs = os.cpu_count() - 1
        for i in range(max(1, nprocs)):
            p = Process(target=down_sample_worker,
                        args=(i, nprocs, nblock, step,
                              self.shared_array,
                              self.data.file_paths,
                              nblock/self.data.rate + 0.1,
                              self.data.rate, self.data.channels,
                              self.data.unit, self.data.ampl_max,
                              end_indices,
                              self.data.unwrap_thresh,
                              self.data.unwrap_clips,
                              load_kwargs))
            self.procs.append(p)
        for p in self.procs:
            p.start()

    def wait(self):
        for p in self.procs:
            p.join()
        for p in self.procs:
            p.close()
        self.procs = []
            
    def is_busy(self):
        busy = False
        for proc in self.procs:
            if proc.is_alive():
                busy = True
                break
        if not busy:
            for proc in self.procs:
                proc.close()
            self.procs = []
        return busy

    def get_lock(self):
        lock = self.shared_array.get_lock()
        return lock

    def save_data_local(self):
        if self.short_data:
            return
        ft_path = self.data.filepath.with_name(self.data.filepath.stem + '-fulltrace.wav')
        rate = 1/(self.times[1] - self.times[0])
        rate *= 1e6
        while rate > 2**31:
            rate /= 1e3
        write_audio(ft_path, self.datas, rate, format='WAV', encoding='DOUBLE')

    def save_data(self):
        if self.short_data:
            return
        audian_dirs.user_cache_path.mkdir(parents=True, exist_ok=True)
        files = {}
        ft_path = audian_dirs.user_cache_path / CompressedData.fulltraces_file
        if ft_path.exists():
            with ft_path.open() as sf:
                files = json.load(sf)
        # new filename:
        ft_name = f'{1:08X}-fulltrace.wav'
        for k in range(1, CompressedData.max_files + 10):
            ft_name = f'{k:08X}-fulltrace.wav'
            if not ft_name in files.keys():
                break
        # add to dictionary:
        first_file = Path(self.data.file_paths[0]).absolute()
        last_file = Path(self.data.file_paths[-1]).absolute()
        timestamp = datetime.now().isoformat()
        rate = 1/(self.times[1] - self.times[0])
        ft_props = dict(first=os.fspath(first_file),
                        last=os.fspath(last_file),
                        rate=rate,
                        created=timestamp,
                        used=timestamp)
        files[ft_name] = ft_props
        # remove old files:
        if len(files) > CompressedData.max_files:
            ft_files = list(files)
            timestamps = [files[ftf]['used'] for ftf in ft_files]
            idx = np.argsort(timestamps)
            for i in idx[:len(ft_files) - CompressedData.max_files]:
                try:
                    (audian_dirs.user_cache_path / ft_files[i]).unlink()
                except Exception as e:
                    print(e)
                files.pop(ft_files[i])
        # save json file:
        with ft_path.open('w') as df:
            json.dump(files, df, indent=4)
        # save file:
        rate *= 1e6
        while rate > 2**31:
            rate /= 1e3
        write_audio(audian_dirs.user_cache_path / ft_name,
                    self.datas, rate, format='WAV', encoding='DOUBLE')

    def load_data(self):
        self.times = None
        self.datas = None
        # load from folder of data file:
        ft_path = self.data.filepath.with_name(self.data.filepath.stem + '-fulltrace.wav')
        if ft_path.exists():
            self.datas, rate = load_audio(ft_path)
            rates = np.array([rate/1e6, rate/1e3, rate])
            durations = len(self.datas)/rates
            rate = rates[np.argmin(np.abs(durations - self.data.frames/self.data.rate))]
            self.times = np.arange(len(self.datas))/rate
            return
        # load from user cache:
        ft_path = audian_dirs.user_cache_path / CompressedData.fulltraces_file
        if audian_dirs.user_cache_path.exists() and ft_path.exists():
            # load json file:
            files = {}
            with ft_path.open() as sf:
                files = json.load(sf)
            # search for entry with matching source files:
            first_file = Path(self.data.file_paths[0]).absolute()
            last_file = Path(self.data.file_paths[-1]).absolute()
            for ft_file in files.keys():
                ft_props = files[ft_file]
                if ft_props['first'] == os.fspath(first_file) and \
                   ft_props['last'] == os.fspath(last_file):
                    # load full trace data:
                    ft_file_path = audian_dirs.user_cache_path / ft_file
                    if not ft_file_path.is_file() or \
                       ft_file_path.stat().st_size == 0:
                        # remove file from json file:
                        del files[ft_file]
                        with ft_path.open('w') as df:
                            json.dump(files, df, indent=4)
                        break
                    self.datas, rate = load_audio(ft_file_path)
                    rate = ft_props['rate']
                    self.times = np.arange(len(self.datas))/rate
                    # update timestamp:
                    timestamp = datetime.now().isoformat()
                    ft_props['used'] = timestamp
                    # save json file:
                    with ft_path.open('w') as df:
                        json.dump(files, df, indent=4)
                    break


def main(cargs):
    set_start_method('forkserver' if os.name == 'posix' else 'spawn')
    AudioLoader.max_open_files = os.cpu_count() + 2
    AudioLoader.max_open_loaders = 2*AudioLoader.max_open_files
    # command line arguments:
    parser = argparse.ArgumentParser(description='Compress timeseries data for audian.', epilog=f'version {__version__} by Jan Benda (2026-{__year__})')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('-i', dest='load_kwargs', default=[],
                        action='append', metavar='KWARGS',
                        help='key-word arguments for the data loader function')
    parser.add_argument('-u', dest='unwrap', default=0, type=float,
                        metavar='UNWRAP', const=1.5, nargs='?',
                        help='unwrap clipped data with threshold relative to maximum input range and divide by two using unwrap() from audioio package')
    parser.add_argument('-U', dest='unwrap_clip', default=0, type=float,
                        metavar='UNWRAP', const=1.5, nargs='?',
                        help='unwrap clipped data with threshold relative to maximum input range and clip using unwrap() from audioio package')
    parser.add_argument('files', nargs='+', default=[], type=str,
                        help='name of files with the time series data')
    args = parser.parse_args(cargs)

    # unwrap:
    if args.unwrap_clip > 1e-3:
        args.unwrap = args.unwrap_clip
        args.unwrap_clip = True
    else:
        args.unwrap_clip = False

    # kwargs for data loader:
    load_kwargs = parse_load_kwargs(args.load_kwargs)

    # expand wildcard patterns:
    files = []
    if os.name == 'nt':
        for fn in args.files:
            files.extend(sorted(glob.glob(fn)))
    else:
        files = args.files

    # compress:
    data = DataLoader(files, **load_kwargs)
    data.set_unwrap(args.unwrap, args.unwrap_clip, False, data.unit)
    compress = CompressedData(data)
    compress.start(6000, load_kwargs)
    compress.wait()
    compress.save_data_local()
    

def run():
    main(sys.argv[1:])
    return 0

    
if __name__ == '__main__':
    run()
