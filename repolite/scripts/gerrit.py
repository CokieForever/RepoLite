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

"""Command line tool to manage a single repository"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import argparse
import subprocess

from repolite.utilities import gerrit
from repolite.utilities.exceptions import FatalError


class Gerrit:
    def __init__(self, oArgs):
        self.oArgs = oArgs

    def run(self):
        oMethod = getattr(self, self.oArgs.command.upper())
        if oMethod is not None and callable(oMethod):
            try:
                return oMethod()
            except (subprocess.CalledProcessError, OSError) as e:
                raise FatalError(e)
        raise FatalError("Command %s is not implemented." % self.oArgs.command)

    def PUSH(self):
        gerrit.push(sTopic=self.oArgs.topic, sTargetBranch=self.oArgs.branch)

    def DOWNLOAD(self):
        gerrit.download(self.oArgs.patch, bDetach=self.oArgs.detach)

    def REBASE(self):
        gerrit.rebase(self.oArgs.branch)


def main():
    oGerrit = Gerrit(parseArgs())
    try:
        oGerrit.run()
    except FatalError as e:
        print("FATAL ERROR: %s" % e)
    except KeyboardInterrupt:
        print("Program interrupted.")


def parseArgs():
    oParser = argparse.ArgumentParser(description="Gerrit utility")
    oSubparsers = oParser.add_subparsers(dest="command", required=True)

    oPushParser = oSubparsers.add_parser("push", help="Push your work to gerrit")
    oPushParser.add_argument("branch", help="Target branch", nargs="?", default="master")
    oPushParser.add_argument("topic", help="Target topic", nargs="?")

    oDownloadParser = oSubparsers.add_parser("download", help="Download a patch and rebase on it")
    oDownloadParser.add_argument("patch", help="Patch ID")
    oDownloadParser.add_argument("-d", "--detach", help="Detaches HEAD instead of rebasing", action="store_true")

    oRebaseParser = oSubparsers.add_parser("rebase", help="Rebase the current branch on another (local) one")
    oRebaseParser.add_argument("branch", help="Branch to rebase onto")

    return oParser.parse_args()


if __name__ == "__main__":
    main()
