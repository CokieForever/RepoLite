#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2020 Quoc-Nam Dessoulles
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""misc.py"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import os
import signal
import threading
from contextlib import contextmanager


class FatalError(ValueError):
    pass


def strOrDefault(sString, sDefault):
    return sString if sString else sDefault


@contextmanager
def changeWorkingDir(sNewWorkingDir):
    sOldWorkingDir = os.path.abspath(os.getcwd())
    os.chdir(os.path.abspath(sNewWorkingDir))
    try:
        yield sNewWorkingDir
    finally:
        os.chdir(sOldWorkingDir)


# See https://stackoverflow.com/a/35792192
def kill(iPid, iSignum):
    if os.name == "nt":
        dSigMap = {
            signal.SIGINT: signal.CTRL_C_EVENT,
            signal.SIGBREAK: signal.CTRL_BREAK_EVENT
        }
        if iSignum in dSigMap:
            iPid = 0

        oPrevHandler = signal.getsignal(iSignum)
        if iSignum in dSigMap and iPid == 0:
            event = threading.Event()

            # noinspection PyUnusedLocal
            def handler(iSigNum, oFrame):
                event.set()

            signal.signal(iSignum, handler)
            try:
                os.kill(iPid, dSigMap[iSignum])
                while not event.is_set():
                    pass
            finally:
                signal.signal(iSignum, oPrevHandler)
        else:
            os.kill(iPid, dSigMap.get(iSignum, iSignum))
    else:
        os.kill(iPid, iSignum)
