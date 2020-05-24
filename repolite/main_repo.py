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

"""Command line tool to manage multiple Gerrit repositories"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import argparse
import inspect
import os
import shlex
import subprocess
from collections import OrderedDict, Counter
from urllib.parse import urlparse, unquote

from repolite.util.log import error, warning, highlight, fatalError, success, fullSuccess, oTerminal
from repolite.util.misc import strOrDefault, FatalError, changeWorkingDir
from repolite.vcs import gerrit, git


def KeepInvalid(xFunction):
    xFunction.bKeepInvalid = True
    return xFunction


def ForAll(xFunction):
    xFunction.bForAll = True
    return xFunction


class RepoLite:
    def __init__(self, oArgs):
        self.oArgs = oArgs

    def run(self):
        oMethod = getattr(self, self.oArgs.command.upper())
        if oMethod is not None and callable(oMethod):
            return self.executeForAll(oMethod)
        raise FatalError("Command %s is not implemented." % self.oArgs.command)

    def executeForAll(self, xFunction):
        dRepos = self.readManifest(bKeepInvalid=getattr(xFunction, "bKeepInvalid", False))
        if not dRepos:
            raise FatalError("There is no valid repository defined.")
        if getattr(xFunction, "bForAll", False):
            return xFunction(dRepos)
        else:
            def doCallFunction(sRepoUrl):
                highlight("\n### %s ###" % os.path.basename(os.getcwd()))
                if len(inspect.getfullargspec(xFunction)[0]) > 1:
                    xFunction(sRepoUrl)
                else:
                    xFunction()
                success("Done")

            return self.runInRepos(dRepos, doCallFunction)

    def runInRepos(self, dRepos, xFunction):
        lErrorRepos = []
        for sRepoUrl, sDirPath in dRepos.items():
            sRepoName = os.path.basename(sDirPath)
            try:
                os.makedirs(sDirPath, exist_ok=True)
                with changeWorkingDir(sDirPath):
                    xFunction(sRepoUrl)
            except (subprocess.CalledProcessError, FatalError, OSError) as e:
                error("[%s] %s" % (sRepoName, e), bRaise=False)
                lErrorRepos.append(sDirPath)
        return lErrorRepos

    def readManifest(self, bKeepInvalid=False):
        if not os.path.isfile(self.oArgs.manifest):
            raise FatalError("The manifest file %s does not exist." % self.oArgs.manifest)
        dRepos = OrderedDict()
        try:
            with open(self.oArgs.manifest) as oFile:
                for sLine in oFile:
                    sLine = sLine.strip()
                    if sLine:
                        lElements = sLine.split(" ")
                        (sRepoUrl, sDirPath) = lElements[0], " ".join(lElements[1:])
                        if not sDirPath:
                            sDirPath = unquote(urlparse(sRepoUrl, allow_fragments=True).path.split("/")[-1])
                        sDirPath = os.path.abspath(sDirPath)
                        if not bKeepInvalid and not os.path.isdir(sDirPath):
                            warning("Directory %s does not exist, skipped." % sDirPath)
                        else:
                            dRepos[sRepoUrl] = sDirPath
        except OSError as e:
            raise FatalError(e)
        return dRepos

    @KeepInvalid
    def SYNC(self, sRepoUrl):
        if not os.path.isdir(".git"):
            print("Cloning from %s" % sRepoUrl)
            subprocess.run(["git", "clone", sRepoUrl, "."], check=True)
            sCurrentBranch = git.getCurrentBranch()
            subprocess.run(["git", "checkout", "HEAD", "--detach"], check=True)
            subprocess.run(["git", "branch", "-d", sCurrentBranch], check=True)
        else:
            print("Syncing from %s" % sRepoUrl)
            subprocess.run(["git", "fetch", git.getFirstRemote(), "HEAD"], check=True)
            if self.oArgs.detach:
                subprocess.run(["git", "checkout", "FETCH_HEAD", "--detach"], check=True)
            else:
                gerrit.rebase("FETCH_HEAD", bIgnoreChangeIds=True)

    def START(self):
        print("Creating new topic: %s -> %s" % (strOrDefault(git.getCurrentBranch(), "(none)"), self.oArgs.topic))
        subprocess.run(["git", "checkout", "-b", self.oArgs.topic], check=True)

    def SWITCH(self):
        print("Switching topic: %s -> %s" % (strOrDefault(git.getCurrentBranch(), "(none)"), self.oArgs.topic))
        subprocess.run(["git", "checkout", self.oArgs.topic], check=True)

    def END(self):
        if git.getCurrentBranch() == self.oArgs.topic:
            print("Detaching HEAD")
            subprocess.run(["git", "fetch", git.getFirstRemote(), "HEAD"], check=True)
            subprocess.run(["git", "checkout", "FETCH_HEAD", "--detach"], check=True)
        print("Deleting topic %s" % self.oArgs.topic)
        subprocess.run(["git", "branch", "-D", self.oArgs.topic], check=True)

    def FORALL(self):
        print("Running command")
        subprocess.run(shlex.split(self.oArgs.command_line), check=True)

    @ForAll
    def TOPIC(self, dRepos):
        dTopics = OrderedDict()

        def topic(sRepoUrl):
            sRepoName = os.path.basename(os.getcwd())
            dTopics[sRepoName] = strOrDefault(git.getCurrentBranch(), "(none)")

        lErrorRepos = self.runInRepos(dRepos, topic)

        lTopics = list(set(dTopics.values()))
        if len(lTopics) == 1:
            print(oTerminal.green(lTopics[0]))
        else:
            iMaxLen = max(len(s) for s in lTopics)
            sMainTopic = Counter(dTopics.values()).most_common(1)[0][0]
            for sRepoName, sTopic in dTopics.items():
                print("%s %s %s" % (sRepoName, "".join(["."] * (iMaxLen - len(sTopic) + 4)),
                                    oTerminal.green(sTopic) if sTopic == sMainTopic else oTerminal.red(sTopic)))

        return lErrorRepos

    def PUSH(self, sRepoUrl):
        print("Pushing changes to %s" % sRepoUrl)
        gerrit.push()

    def DOWNLOAD(self, sRepoUrl):
        if self.oArgs.repo == urlparse(sRepoUrl, allow_fragments=True).path[1:]:
            print("Downloading patch %s from %s" % (self.oArgs.patch, sRepoUrl))
            gerrit.download(self.oArgs.patch, bDetach=self.oArgs.detach)
        else:
            print("Skipped")

    def REBASE(self):
        print("Rebasing current state on %s" % self.oArgs.topic)
        gerrit.rebase(self.oArgs.topic)

    def RENAME(self):
        sCurrentBranch = git.getCurrentBranch()
        if sCurrentBranch:
            print("Renaming topic: %s -> %s" % (sCurrentBranch, self.oArgs.topic))
            subprocess.run(["git", "branch", "-m", self.oArgs.topic], check=True)
        else:
            error("There is no topic")

    def STASH(self):
        print("Stashing content")
        subprocess.run(["git", "stash"], check=True)

    def POP(self):
        print("Retrieving stashed content")
        sOutput = subprocess.run(["git", "stash", "list"], check=True, capture_output=True, encoding="utf-8").stdout
        if list(filter(bool, sOutput.splitlines())):
            subprocess.run(["git", "stash", "pop"], check=True)
        else:
            warning("No content to retrieve")


def main():
    oRepoLite = RepoLite(parseArgs())
    try:
        lErrorRepos = [os.path.basename(s) for s in oRepoLite.run()]
        print("")
        if lErrorRepos:
            fatalError("The command failed in the following repos: %s. Please check the log for details."
                       % ", ".join(lErrorRepos))
        else:
            fullSuccess("Execution successfully completed.")
    except FatalError as e:
        print("")
        fatalError("%s" % e)
    except KeyboardInterrupt:
        print("")
        fatalError("Program interrupted.")


def parseArgs():
    oParser = argparse.ArgumentParser(description="Lite version of repo")
    oParser.add_argument("-m", "--manifest", help="Manifest file", default="manifest.txt")
    oSubparsers = oParser.add_subparsers(dest="command", required=True)

    oSyncParser = oSubparsers.add_parser("sync", help="Sync and rebase")
    oSyncParser.add_argument("-d", "--detach", help="Detaches HEAD instead of rebasing", action="store_true")

    oStartParser = oSubparsers.add_parser("start", help="Start topic")
    oStartParser.add_argument("topic", help="Topic name")

    oSwitchParser = oSubparsers.add_parser("switch", help="Switch topic")
    oSwitchParser.add_argument("topic", help="Topic name")

    oEndParser = oSubparsers.add_parser("end", help="End and delete topic")
    oEndParser.add_argument("topic", help="Topic name")

    oForAllParser = oSubparsers.add_parser("forall", help="Execute a command on all repos")
    oForAllParser.add_argument("command_line", help="Command to execute")

    oSubparsers.add_parser("topic", help="Show current topics")

    oSubparsers.add_parser("push", help="Push all repos")

    oDownloadParser = oSubparsers.add_parser("download", help="Download a patch and rebase on it")
    oDownloadParser.add_argument("repo", help="Patch repository")
    oDownloadParser.add_argument("patch", help="Patch ID")
    oDownloadParser.add_argument("-d", "--detach", help="Detaches HEAD instead of rebasing", action="store_true")

    oRebaseParser = oSubparsers.add_parser("rebase", help="Rebase the current topic on another (local) one")
    oRebaseParser.add_argument("topic", help="Topic to rebase onto")

    oRenameParser = oSubparsers.add_parser("rename", help="Rename the current topic")
    oRenameParser.add_argument("topic", help="New topic name")

    oSubparsers.add_parser("stash", help="Stashes changes of all repos")

    oSubparsers.add_parser("pop", help="Pops stash list of all repos")

    return oParser.parse_args()


if __name__ == "__main__":
    main()
