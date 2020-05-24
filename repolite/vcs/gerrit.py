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

"""Gerrit utility functions"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import random
import re
import subprocess
from collections import OrderedDict

from repolite.vcs import git
from repolite.util.misc import FatalError


def push(sTopic=None, sTargetBranch="master"):
    sRemote = subprocess.run(["git", "remote"], stdout=subprocess.PIPE, encoding="utf-8",
                             check=True).stdout.strip().splitlines()[0]
    sCurrentBranch = subprocess.run(["git", "branch", "--show-current"], encoding="utf-8",
                                    stdout=subprocess.PIPE, check=True).stdout.strip()
    if sTopic is None and sCurrentBranch.startswith("crossrepo/"):
        sTopic = sCurrentBranch

    lArgs = ["git", "push", sRemote, "HEAD:refs/for/%s" % sTargetBranch]
    if sTopic:
        lArgs += ["-o", "topic=%s" % sTopic]
    subprocess.run(lArgs, check=True)


def download(sPatch, bDetach=False):
    oMatch = re.match(r"(\d+)/\d+", sPatch)
    if oMatch is None:
        raise FatalError("%s is not a valid patch ID" % sPatch)
    sPatchChecksum = "%02d" % int(oMatch.group(1)[-2:])

    sRemote = subprocess.run(["git", "remote"], stdout=subprocess.PIPE, encoding="utf-8",
                             check=True).stdout.strip().splitlines()[0]
    subprocess.run(["git", "fetch", sRemote, "refs/changes/%s/%s" % (sPatchChecksum, sPatch)],
                   check=True)
    if bDetach:
        subprocess.run(["git", "checkout", "FETCH_HEAD", "--detach"], check=True)
    else:
        rebase("FETCH_HEAD")


def cherry(sUpstream, sHead="HEAD"):
    dCommits = OrderedDict()
    for sCherry in subprocess.run(["git", "cherry", sUpstream, sHead], check=True,
                                  encoding="utf-8", stdout=subprocess.PIPE).stdout.strip().splitlines():
        sOperation, sCommitId = sCherry.strip().split(" ", maxsplit=1)
        if sOperation == "+":
            sCommitBody = subprocess.run(["git", "show", "-s", "--format=%b", sCommitId],
                                         check=True, encoding="utf-8", stdout=subprocess.PIPE).stdout.strip()
            for sBodyLine in sCommitBody.splitlines():
                if sBodyLine.startswith("Change-Id:"):
                    dCommits[sCommitId] = sBodyLine[len("Change-Id:"):].strip()
                    break
    return dCommits


def rebase(sTargetBranch, bIgnoreChangeIds=False):
    sCurrentBranch = git.getCurrentBranch()
    if not sCurrentBranch:
        sCurrentBranch = "tmp.%06d" % random.randrange(1e6)
        subprocess.run(["git", "checkout", "-b", sCurrentBranch], check=True)
        bDeleteBranch = True
    else:
        bDeleteBranch = False

    subprocess.run(["git", "checkout", "--detach", sTargetBranch], check=True)
    lChangeIds = cherry(sCurrentBranch).values() if not bIgnoreChangeIds else []
    for sCommitIdToPick, sChangeId in cherry("HEAD", sHead=sCurrentBranch).items():
        if sChangeId in lChangeIds:
            continue
        git.cherryPick(sCommitIdToPick,
                       xOnAbort=lambda: subprocess.run(["git", "checkout", sCurrentBranch], check=True))

    if bDeleteBranch:
        subprocess.run(["git", "branch", "-D", sCurrentBranch])
    else:
        subprocess.run(["git", "checkout", "-B", sCurrentBranch], check=True)