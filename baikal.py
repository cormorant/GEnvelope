#!/usr/bin/env python
# coding: utf-8
from __future__ import division
"""
Описание формата Байкал-5
"""
APP_NAME = "BaikalLib"
__version__="0.0.1.2"
COMPANY_NAME = 'GIN'

import os
import sys
import struct
import numpy as np

# Краткое описание типов данных:
# имена
MainHeaderNames = ('nkan', 'test', 'vers', 'day', 'month', 'year',
    'satellit', 'valid', 'pri_synhr', 'razr', 'reserv_short1', 'reserv_short2',
    'reserv_short3', 'reserv_short4', 'reserv_short5', 'reserv_short6',
    'station', 'dt', 'to', 'deltas', 'latitude', 'longitude')
# заголовок файла
MainHeaderTypeStruct = '16h16s5d'
MainHeaderTypeStructSize = struct.calcsize(MainHeaderTypeStruct)

# имена
ChannelHeaderNames = ('phis_nom', 'reserv1', 'reserv2', 'reserv3',
    'name_chan', 'tip_dat', 'koef_chan', 'reserved')
# заголовок канала:
ChannelHeaderTypeStruct = '4h24s24s2d'
ChannelHeaderTypeStructSize = struct.calcsize(ChannelHeaderTypeStruct)

# адрес начала структур заголовка каналов (и размер главного заголовка)
CHANNEL_HEADER_START_OFFSET = 120


def stripnulls(s):
    """ очищает строку от символов пропуска и нулевых символов """
    s = s.strip()
    for sym in ("\00", "\01", ".st"): s = s.replace(sym, "")
    return s


def is_baikalfile(filename):
    """ Checks whether a file is Baykal XX waveform data or not """
    with open(filename, "rb") as _f:
        # количество каналов
        try:
            nkan, _test, version = struct.unpack("3h", _f.read(6))
        except struct.error:
            print("Error reading file {}".format(filename))
            return
    # должно быть вразумительное число каналов
    if not nkan in range(1, 7): return
    else:
        return True
    # проверка правильности даты, разрядности и тд
    # проверка версия формата
    #if 0 < version <= 60:
    #    return True
    #else:
    #    return False


class BaikalFile():
    """ Описание формата Байкал-5 """
    def __init__(self, filename):
        """ baikal-5 class init """
        # если файл является файлом формата Байкал - работаем с ним
        if not is_baikalfile(filename):
            self.valid = False
        else:
            self.filename = filename
            self.valid = True
            with open(self.filename, "rb") as _f:
                # считаем заголовок
                self.MainHeader = self._readMainHeader(_f)
                # заголовки каналов
                self.ChannelHeaders = self._readChannelHeaders(_f)
                # читать массивы с данными
                self.traces = self._readData(_f)

    def _readMainHeader(self, _f):
        """ считывание заголовка файла """
        # читать все записи из структуры или только обязательные
        _f.seek(0)
        size = MainHeaderTypeStructSize#120 if all
        data = struct.unpack(MainHeaderTypeStruct, _f.read(size))
        header = dict(zip(MainHeaderNames, data))
        # поправим станцию
        header["station"] = stripnulls(header["station"])
        # неправильный год кое-где
        if header["year"] < 1900: header["year"] += 2000
        return header

    def _readChannelHeaders(self, _f):
        """ считывание заголовков каналов, структура CHANNEL_HEADER """
        nkan = self.MainHeader['nkan']
        size = ChannelHeaderTypeStructSize
        headers = []
        _f.seek(CHANNEL_HEADER_START_OFFSET)
        for kan in range(nkan):
            # считывание очередного канала
            data = struct.unpack(ChannelHeaderTypeStruct, _f.read(size))
            result = dict(zip(ChannelHeaderNames, data))
            result["name_chan"] = stripnulls( result["name_chan"] )
            result['tip_dat'] = stripnulls( result['tip_dat'] )
            headers += [ result ]
        return headers
    
    def _readData(self, _f):
        """ считывание данных """
        nkan = self.MainHeader['nkan']
        razr = self.MainHeader['razr']
        razm = 2 if razr == 16 else 4 # размер одного замера
        typ = "h" if razr==16 else "i"# тип
        # dtype
        dtyp = np.int16 if razr==16 else np.int32
        # где начинать считывать данные (336)
        offset = CHANNEL_HEADER_START_OFFSET + nkan * 72
        # load&read
        _f.seek(offset)
        data = np.fromstring(_f.read(), dtype=dtyp)
        # обрезать массив с конца пока он не делится на число каналов
        while data.shape[0] % nkan != 0:
            data = data[:-1]
        # вернем демультиплексированные данные
        return data.reshape(int(data.shape[0]/nkan), nkan).T
