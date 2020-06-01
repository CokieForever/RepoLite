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

"""Log utilities"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import sys

from blessed import Terminal

oTerminal = Terminal()


def highlight(sMsg):
    print(oTerminal.blue(sMsg))


def success(sMsg):
    print(oTerminal.green(sMsg))


def fullSuccess(sMsg, bExit=True):
    print(oTerminal.white_on_green(sMsg))
    if bExit:
        sys.exit(0)


def fatalError(sMsg, bExit=True):
    print(oTerminal.white_on_red("ERROR: %s" % sMsg))
    if bExit:
        sys.exit(1)


def error(sMsg):
    print(oTerminal.red("ERROR: %s" % sMsg))


def warning(sMsg):
    print(oTerminal.orange("WARN: %s" % sMsg))
