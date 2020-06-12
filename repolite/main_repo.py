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
import json
import os
import shlex
import subprocess
from collections import OrderedDict, Counter
from configparser import ConfigParser
from urllib.parse import urlparse, unquote

import requests

from repolite.util.log import error, warning, highlight, fatalError, success, fullSuccess, oTerminal
from repolite.util.misc import strOrDefault, FatalError, changeWorkingDir, hideFile
from repolite.vcs import gerrit, git


def KeepInvalid(xFunction):
    xFunction.bKeepInvalid = True
    return xFunction


def ForAll(xFunction):
    xFunction.bForAll = True
    return xFunction


class RepoData:
    def __init__(self):
        self.dRaw = {}

    def load(self, sFile):
        try:
            with open(sFile, "r") as oFile:
                self.dRaw = json.load(oFile)
        except (ValueError, OSError) as e:
            raise FatalError(e)

    def save(self, sFile):
        try:
            with open(sFile, "w") as oFile:
                json.dump(self.dRaw, oFile)
        except (ValueError, OSError) as e:
            raise FatalError(e)

    def getLastPushedCommit(self, sProject, sChangeId):
        return self.dRaw.get(sProject, {}).get(sChangeId, {}).get("last-pushed-commit")

    def setLastPushedCommit(self, sProject, sChangeId, sCommit):
        self.dRaw.setdefault(sProject, {}).setdefault(sChangeId, {})["last-pushed-commit"] = sCommit


class RepoLite:
    def __init__(self, oArgs):
        self.oArgs = oArgs
        self.oApiClient = None
        self.sRootFolder = os.path.abspath(os.getcwd())
        self.sRepoDataFile = os.path.join(self.sRootFolder, ".repolite", "data")

    def getApiClient(self):
        sConfigFilePath = os.path.join(os.path.expanduser("~"), ".repolite")
        if not os.path.isfile(sConfigFilePath):
            raise FatalError("The config file %s does not exist." % sConfigFilePath)

        sWorkingDir = os.path.normcase(os.path.abspath(os.path.dirname(os.getcwd())))
        oConfig = ConfigParser()
        oConfig.read(sConfigFilePath)
        dSection = oConfig["DEFAULT"]
        for sSection in oConfig.sections():
            sTarget = oConfig.get(sSection, "target", fallback=None)
            if sTarget:
                sTarget = os.path.normcase(os.path.abspath(os.path.join(os.path.dirname(sConfigFilePath), sTarget)))
                if sWorkingDir == sTarget:
                    dSection = oConfig[sSection]
                    break

        def getNotEmpty(sKey):
            sValue = dSection.get(sKey, fallback=None)
            if sValue is None:
                raise FatalError("No value provided for %s in the config file" % sKey)
            return sValue

        self.oApiClient = gerrit.ApiClient(getNotEmpty("url"), getNotEmpty("username"), getNotEmpty("password"))
        return self.oApiClient

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
                error("[%s] %s" % (sRepoName, e))
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
                        sDirPath = os.path.join(self.sRootFolder, sDirPath)
                        if not bKeepInvalid and not os.path.isdir(sDirPath):
                            warning("Directory %s does not exist, skipped." % sDirPath)
                        else:
                            dRepos[sRepoUrl] = sDirPath
        except OSError as e:
            raise FatalError(e)
        return dRepos

    def getRepoData(self):
        oRepoData = RepoData()
        if os.path.isfile(self.sRepoDataFile):
            oRepoData.load(self.sRepoDataFile)
        return oRepoData

    def saveRepoData(self, oRepoData):
        sDir = os.path.dirname(self.sRepoDataFile)
        os.makedirs(sDir, exist_ok=True)
        hideFile(sDir)
        oRepoData.save(self.sRepoDataFile)

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

        def topic():
            sRepoName = os.path.basename(os.getcwd())
            dTopics[sRepoName] = strOrDefault(git.getCurrentBranch(), "(none)")

        lErrorRepos = self.runInRepos(dRepos, lambda _: topic())
        if lErrorRepos:
            return lErrorRepos

        lTopics = list(set(dTopics.values()))
        if len(lTopics) == 1:
            print(oTerminal.green(lTopics[0]))
        else:
            iMaxLen = max(len(s) for s in lTopics)
            sMainTopic = Counter(dTopics.values()).most_common(1)[0][0]
            for sRepoName, sTopic in dTopics.items():
                print("%s %s %s" % (sRepoName, "".join(["."] * (iMaxLen - len(sTopic) + 4)),
                                    oTerminal.green(sTopic) if sTopic == sMainTopic else oTerminal.red(sTopic)))

        return []

    def PULL(self, sRepoUrl):
        sChangeId = gerrit.getChangeId()
        if not sChangeId:
            raise FatalError("Unable to extract Change-Id")
        sProject = gerrit.getProjectName()
        try:
            dChangeData = self.getApiClient().getChangeData(sChangeId, sProject, lAdditionalData=["ALL_REVISIONS"])
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                warning("No remote patch")
                return
            raise e
        sRemoteCommit = dChangeData["current_revision"]
        sLocalCommit = git.getLastCommit()
        sLastPushedCommit = self.getRepoData().getLastPushedCommit(sProject, sChangeId)
        if sRemoteCommit == sLocalCommit:
            print("Already up-to-date.")
            return
        elif sRemoteCommit == sLastPushedCommit:
            print("You are ahead of Gerrit.")
            return
        elif sLocalCommit in dChangeData["revisions"]:
            print("Pulling changes from %s" % sRepoUrl)
            sBranch = git.getCurrentBranch()
            dFetchData = dChangeData["revisions"][sRemoteCommit]["fetch"]["ssh"]
            subprocess.run(["git", "fetch", dFetchData["url"], dFetchData["ref"]], check=True)
            subprocess.run(["git", "checkout", "FETCH_HEAD"], check=True)
            if sBranch:
                subprocess.run(["git", "branch", "-D", sBranch], check=True)
                subprocess.run(["git", "checkout", "-b", sBranch], check=True)
        else:
            raise FatalError("You have local commits unknown to Gerrit")

    def PUSH(self, sRepoUrl):
        sChangeId = gerrit.getChangeId()
        if not sChangeId:
            raise FatalError("Unable to extract Change-Id")
        sProject = gerrit.getProjectName()
        oRepoData = self.getRepoData()
        sLocalCommit = git.getLastCommit()
        try:
            dChangeData = self.getApiClient().getChangeData(sChangeId, sProject, lAdditionalData=["CURRENT_REVISION"])
        except requests.HTTPError as e:
            if e.response.status_code != 404:
                raise
        else:
            sRemoteCommit = dChangeData["current_revision"]
            sLastPushedCommit = oRepoData.getLastPushedCommit(sProject, sChangeId)
            if sRemoteCommit == sLocalCommit:
                warning("No new changes")
                return
            elif sRemoteCommit != sLastPushedCommit:
                warning("You are about to overwrite unknown changes.")
                sInput = input("Continue? (y/n): ")
                if sInput != "y":
                    raise FatalError("Operation aborted")
        print("Pushing changes to %s" % sRepoUrl)
        gerrit.push()
        oRepoData.setLastPushedCommit(sProject, sChangeId, sLocalCommit)
        self.saveRepoData(oRepoData)

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
            raise FatalError("There is no topic")

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

    oSubparsers.add_parser("pull", help="Pull all repos")

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

    oArgs = oParser.parse_args()
    oArgs.manifest = os.path.abspath(oArgs.manifest)
    return oArgs


if __name__ == "__main__":
    main()
