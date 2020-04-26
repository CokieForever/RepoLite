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

"""Git utility functions"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import copy
import os
import subprocess

from repolite.utilities.exceptions import FatalError


def getFirstRemote():
    return subprocess.run(["git", "remote"], stdout=subprocess.PIPE, encoding="latin-1",
                          check=True).stdout.strip().splitlines()[0]


def getCurrentBranch():
    return subprocess.run(["git", "branch", "--show-current"],
                          stdout=subprocess.PIPE,
                          encoding="latin-1", check=True).stdout.strip()


def cherryPick(sCommitId, xOnAbort=None):
    def onError():
        while True:
            sInput = input("You may have merge conflicts. Fix them and press enter, or enter 'abort' now to quit: ")
            if sInput == "abort":
                print("Aborting.")
                subprocess.run(["git", "cherry-pick", "--abort"])
                if xOnAbort is not None:
                    xOnAbort()
                raise FatalError("Process aborted.")
            elif not sInput:
                print("Continuing...")
                break

    try:
        subprocess.run(["git", "cherry-pick", sCommitId], check=True)
    except subprocess.CalledProcessError:
        onError()
        while True:
            try:
                dEnv = copy.deepcopy(os.environ)
                dEnv["GIT_EDITOR"] = "true"
                subprocess.run(["git", "cherry-pick", "--continue"], check=True, env=dEnv)
                break
            except subprocess.CalledProcessError:
                onError()
