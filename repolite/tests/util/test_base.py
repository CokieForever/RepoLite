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

"""test_base.py"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import os
import shlex
import subprocess
import sys
from collections import OrderedDict
from urllib.parse import urlparse, quote_plus

from repolite.tests.util.test_setup import Setup, getExecutablePath, configureGit, withRetry, removeFolder
from repolite.util.misc import changeWorkingDir
# noinspection PyAttributeOutsideInit
from repolite.vcs import git, gerrit


class TestBase:
    oTestSetup = Setup()

    @classmethod
    def setup_class(cls):
        try:
            cls.oTestSetup.setup()
        except:  # noqa: E722
            cls.teardown_class()
            raise

    @classmethod
    def teardown_class(cls):
        cls.oTestSetup.teardown()

    @property
    def oApiClient(self):
        return self.oTestSetup.oApiClient

    def setup_method(self, _):
        self.sRepoFolder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "repo"))
        self.cleanRepoFolder()
        self.runRepo(["sync"])
        dJson = self.oApiClient.get("config/server/info")
        sGetMsgHookCommand = dJson["download"]["schemes"]["ssh"]["clone_commands"]["Clone with commit-msg hook"] \
            .split("&&")[1].strip()
        if os.name == "nt":
            sScpExe = getExecutablePath("scp.exe")
            if sScpExe:
                sGetMsgHookCommand = sGetMsgHookCommand.replace("scp", '"%s"' % sScpExe)
        for sProjectFolder in self.dProjectFolders:
            configureGit(sProjectFolder)
            subprocess.run(shlex.split(sGetMsgHookCommand.replace("${project-base-name}", sProjectFolder)), check=True)

    def teardown_method(self, _):
        self.oTestSetup.resetProjects()

    def cleanRepoFolder(self):
        withRetry(lambda: removeFolder(self.sRepoFolder))
        withRetry(lambda: os.makedirs(self.sRepoFolder))
        self.dProjectFolders = OrderedDict()
        with open(os.path.join(self.sRepoFolder, "manifest.txt"), "w") as oFile:
            for sUrl in self.oTestSetup.lProjectUrls:
                oFile.write(sUrl)
                sProjectName = urlparse(sUrl).path[1:]
                if "/" in sProjectName:
                    sProjectDir = sProjectName.replace("/", "_")
                    oFile.write(" %s" % sProjectDir)
                else:
                    sProjectDir = sProjectName
                oFile.write("\n")
                self.dProjectFolders[os.path.join(self.sRepoFolder, sProjectDir)] = sProjectName

    def runGit(self, lArgs, **kwargs):
        if "check" not in kwargs:
            kwargs["check"] = True
        if "capture_output" not in kwargs:
            kwargs["capture_output"] = True
        if kwargs["capture_output"] and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        return subprocess.run(["git"] + lArgs, **kwargs)

    def runRepo(self, lArgs, **kwargs):
        kwargs["cwd"] = self.sRepoFolder
        if "check" not in kwargs:
            kwargs["check"] = True
        if "capture_output" not in kwargs:
            kwargs["capture_output"] = True
        if kwargs["capture_output"] and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        dEnv = os.environ.copy()
        dEnv["PYTHONPATH"] = os.pathsep.join(sys.path)
        dEnv["USERPROFILE"] = self.oTestSetup.sRepoConfigFolder
        dEnv["HOME"] = self.oTestSetup.sRepoConfigFolder
        sRepoScript = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main_repo.py"))
        return subprocess.run([sys.executable, sRepoScript] + lArgs, env=dEnv, **kwargs)

    def createCommit(self, sId="1", bAmend=False):
        dCommits = {}
        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            with changeWorkingDir(sProjectFolder):
                sTestFileName = "test_%s.txt" % sId
                with open(sTestFileName, "w") as oFile:
                    if bAmend:
                        oFile.write("This is an amended test (%s)." % sId)
                    else:
                        oFile.write("This is a test (%s)." % sId)
                self.runGit(["add", sTestFileName])
                if bAmend:
                    sLastCommitMsg = self.runGit(["log", "-1", "--format=format:%B"]).stdout
                    sNewCommitMsg = "\n".join(["Amended test commit (%s)" % sId] + sLastCommitMsg.splitlines()[1:])
                    self.runGit(["commit", "--amend", "-m", sNewCommitMsg])
                else:
                    self.runGit(["commit", "-m", "Test commit (%s)" % sId])
                dCommits[sProjectName] = git.getLastCommit()
        return dCommits

    def createChange(self, sId="1", bAmend=False):
        dCommits = {}
        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            with changeWorkingDir(sProjectFolder):
                if bAmend:
                    sChangeId = gerrit.getChangeId()
                    dJson = {"message": "Amended test commit (%s)" % sId}
                    self.oApiClient.put("changes/%s~master~%s/message"
                                        % (quote_plus(sProjectName), sChangeId), json=dJson)
                else:
                    dJson = {"project": sProjectName, "branch": "master", "subject": "Test commit (%s)" % sId}
                    sChangeId = self.oApiClient.post("changes/", json=dJson)["change_id"]
                dJson = self.oApiClient.getChangeData(sChangeId, sProjectName, lAdditionalData=["CURRENT_REVISION"])
                dCommits[sProjectName] = dJson["current_revision"]
        return dCommits

    def push(self):
        self.runRepo(["push"])
        lChangeNumbers = []
        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            with changeWorkingDir(sProjectFolder):
                dJson = self.oApiClient.getChangeData(gerrit.getChangeId(), sProjectName)
                lChangeNumbers.append(dJson["_number"])
        return lChangeNumbers

    def merge(self, iChangeNumber):
        self.oApiClient.post("changes/%d/revisions/current/review" % iChangeNumber,
                             json={"labels": {"Code-Review": "+2"}})
        self.oApiClient.post("changes/%d/submit" % iChangeNumber)
