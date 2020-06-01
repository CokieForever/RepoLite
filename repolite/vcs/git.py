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

import os
import subprocess

from repolite.util.misc import FatalError


def getFirstRemote():
    return subprocess.run(["git", "remote"], capture_output=True,
                          encoding="utf-8", check=True).stdout.strip().splitlines()[0]


def getCurrentBranch():
    return subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                          encoding="utf-8", check=True).stdout.strip()


def getLastCommitMsg():
    return subprocess.run(["git", "log", "-1", "--format=full"], capture_output=True,
                          encoding="utf-8", check=True).stdout.strip()


def getAllBranches():
    return [s[2:] for s in subprocess.run(["git", "branch"], capture_output=True,
                                          encoding="utf-8", check=True).stdout.splitlines()]


def getGitMessages():
    return subprocess.run(["git", "log", "--format=format:%s"], capture_output=True,
                          encoding="utf-8", check=True).stdout.splitlines()


def getRemoteUrl():
    sRemote = getFirstRemote()
    return subprocess.run(["git", "config", "--get", "remote.%s.url" % sRemote], capture_output=True,
                          encoding="utf-8", check=True).stdout.strip()


def getLastCommit():
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                          encoding="utf-8", check=True).stdout.strip()


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
                dEnv = os.environ.copy()
                dEnv["GIT_EDITOR"] = "true"
                subprocess.run(["git", "cherry-pick", "--continue"], check=True, env=dEnv)
                break
            except subprocess.CalledProcessError:
                onError()
