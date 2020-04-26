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

"""Tests of the repo tool"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import os
import re
import shlex
import subprocess
import sys
from collections import Counter

import requests

from repolite.tests.utilities.test_setup import Setup, removeFolder, withRetry, getExecutablePath

INITIAL_COMMIT_MSG = "Initial empty repository"


# noinspection PyAttributeOutsideInit
class TestRepo:
    oTestSetup = Setup()

    @classmethod
    def setup_class(cls):
        try:
            cls.oTestSetup.setup()
        except:  # noqa: E723
            cls.teardown_class()
            raise

    @classmethod
    def teardown_class(cls):
        cls.oTestSetup.teardown()

    def setup_method(self, _):
        self.sRepoFolder = os.path.join(os.path.abspath(os.path.dirname(__file__)), "repo")
        self.runRepo(["sync"])
        self.lProjectFolders = [os.path.join(self.sRepoFolder, sUrl.split("/")[-1])
                                for sUrl in self.oTestSetup.lProjectUrls]
        dJson = self.oTestSetup.oGerritClient.get("config/server/info", bGetJson=True)
        sGetMsgHookCommand = dJson["download"]["schemes"]["ssh"]["clone_commands"]["Clone with commit-msg hook"] \
            .split("&&")[1].strip()
        if os.name == "nt":
            sScpExe = getExecutablePath("scp.exe")
            if sScpExe:
                sGetMsgHookCommand = sGetMsgHookCommand.replace("scp", '"%s"' % sScpExe)
        for sProjectFolder in self.lProjectFolders:
            sProjectName = os.path.basename(sProjectFolder)
            subprocess.run(shlex.split(sGetMsgHookCommand.replace("${project-base-name}", sProjectName)),
                           check=True, cwd=os.path.dirname(sProjectFolder))

    def teardown_method(self, _):
        self.oTestSetup.resetProjects()
        self.cleanRepoFolder()

    def cleanRepoFolder(self):
        withRetry(lambda: removeFolder(self.sRepoFolder))
        withRetry(lambda: os.makedirs(self.sRepoFolder))
        with open(os.path.join(self.sRepoFolder, "manifest.txt"), "w") as oFile:
            for sUrl in self.oTestSetup.lProjectUrls:
                oFile.write(sUrl + "\n")

    def runRepo(self, lArgs, **kwargs):
        kwargs["cwd"] = self.sRepoFolder
        if "check" not in kwargs:
            kwargs["check"] = True
        if "capture_output" not in kwargs:
            kwargs["capture_output"] = True
        if kwargs["capture_output"] and "encoding" not in kwargs:
            kwargs["encoding"] = "latin-1"
        sRepoScript = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "repo.py"))
        return subprocess.run([sys.executable, sRepoScript] + lArgs, **kwargs)

    def runGit(self, lArgs, sCwd, **kwargs):
        kwargs["cwd"] = sCwd
        if "check" not in kwargs:
            kwargs["check"] = True
        if "capture_output" not in kwargs:
            kwargs["capture_output"] = True
        if kwargs["capture_output"] and "encoding" not in kwargs:
            kwargs["encoding"] = "latin-1"
        return subprocess.run(["git"] + lArgs, **kwargs)

    def getCurrentBranch(self, sProjectFolder):
        return self.runGit(["branch", "--show-current"], sProjectFolder).stdout.strip()

    def getAllBranches(self, sProjectFolder):
        return [s[2:] for s in self.runGit(["branch"], sProjectFolder).stdout.splitlines()]

    def getGitMessages(self, sProjectFolder):
        return self.runGit(["log", "--format=format:%s"], sProjectFolder).stdout.splitlines()

    def createCommit(self, sId="1", bAmend=False):
        for sProjectFolder in self.lProjectFolders:
            sTestFileName = "test_%s.txt" % sId
            with open(os.path.join(sProjectFolder, sTestFileName), "w") as oFile:
                if bAmend:
                    oFile.write("This is an amended test (%s)." % sId)
                else:
                    oFile.write("This is a test (%s)." % sId)
            self.runGit(["add", sTestFileName], sProjectFolder)
            if bAmend:
                sLastCommitMsg = self.runGit(["log", "-1", "--format=format:%B"], sProjectFolder).stdout
                sNewCommitMsg = "\n".join(["Amended test commit (%s)" % sId] + sLastCommitMsg.splitlines()[1:])
                self.runGit(["commit", "--amend", "-m", sNewCommitMsg], sProjectFolder)
            else:
                self.runGit(["commit", "-m", "Test commit (%s)" % sId], sProjectFolder)

    def push(self):
        self.runRepo(["push"])
        lChangeNumbers = []
        for sProjectFolder in self.lProjectFolders:
            sProjectName = os.path.basename(sProjectFolder)
            dJson = self.oTestSetup.oGerritClient.get("changes/?q=%s"
                                                      % requests.utils.quote("p:%s" % sProjectName), bGetJson=True)
            lChangeNumbers.append(dJson[0]["_number"])
        return lChangeNumbers

    def merge(self, iChangeNumber):
        self.oTestSetup.oGerritClient.post("changes/%d/revisions/current/review" % iChangeNumber,
                                           json={"labels": {"Code-Review": "+2"}})
        self.oTestSetup.oGerritClient.post("changes/%d/submit" % iChangeNumber)

    def test_repoSync_checkout(self):
        for sProjectFolder in self.lProjectFolders:
            lBranches = self.getAllBranches(sProjectFolder)
            assert len(lBranches) == 1
            assert re.match(r"\(HEAD detached at .*\)", lBranches[0], re.IGNORECASE) is not None
            assert self.getCurrentBranch(sProjectFolder) == ""
            assert self.getGitMessages(sProjectFolder) == [INITIAL_COMMIT_MSG]

    def test_repoStart_onDetached(self):
        self.runRepo(["start", "topic"])

        for sProjectFolder in self.lProjectFolders:
            assert self.getCurrentBranch(sProjectFolder) == "topic"
            assert self.getGitMessages(sProjectFolder) == [INITIAL_COMMIT_MSG]

    def test_repoStart_onOtherTopic(self):
        self.runRepo(["start", "topic_1"])
        self.createCommit()
        self.runRepo(["start", "topic_2"])

        for sProjectFolder in self.lProjectFolders:
            assert self.getCurrentBranch(sProjectFolder) == "topic_2"
            assert self.getGitMessages(sProjectFolder) == ["Test commit (1)", INITIAL_COMMIT_MSG]
            assert os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))

    def test_repoSync_detach(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.runRepo(["sync", "-d"])

        for sProjectFolder in self.lProjectFolders:
            assert self.getCurrentBranch(sProjectFolder) == ""
            assert self.getGitMessages(sProjectFolder) == [INITIAL_COMMIT_MSG]
            assert not os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))

    def test_repoSwitch(self):
        self.runRepo(["start", "topic_1"])
        self.runRepo(["start", "topic_2"])
        self.createCommit()

        self.runRepo(["switch", "topic_1"])

        for sProjectFolder in self.lProjectFolders:
            assert self.getCurrentBranch(sProjectFolder) == "topic_1"
            assert self.getGitMessages(sProjectFolder) == [INITIAL_COMMIT_MSG]
            assert not os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))

    def test_repoSync_rebase(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        for iChangeNumber in self.push():
            self.merge(iChangeNumber)
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")

        self.runRepo(["sync"])

        for iIdx, sProjectFolder in enumerate(self.lProjectFolders):
            assert self.getCurrentBranch(sProjectFolder) == "topic_2"
            assert os.path.isfile(os.path.join(sProjectFolder, "test_2.txt"))
            assert os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))
            assert self.getGitMessages(sProjectFolder) == ["Test commit (2)", "Test commit (1)",
                                                           INITIAL_COMMIT_MSG]

    def test_repoEnd_whenActive(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.runRepo(["end", "topic"])

        for sProjectFolder in self.lProjectFolders:
            lBranches = self.getAllBranches(sProjectFolder)
            assert len(lBranches) == 1
            assert re.match(r"\(HEAD detached at .*\)", lBranches[0], re.IGNORECASE) is not None
            assert self.getCurrentBranch(sProjectFolder) == ""
            assert self.getGitMessages(sProjectFolder) == [INITIAL_COMMIT_MSG]
            assert not os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))

    def test_repoEnd_whenNotActive(self):
        self.runRepo(["start", "topic_1"])
        self.runRepo(["start", "topic_2"])

        self.runRepo(["end", "topic_1"])

        for sProjectFolder in self.lProjectFolders:
            assert self.getAllBranches(sProjectFolder) == ["topic_2"]
            assert self.getCurrentBranch(sProjectFolder) == "topic_2"

    def test_repoTopic_whenNoTopic(self):
        sOutput = self.runRepo(["topic"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = ["%s: (no topic)" % os.path.basename(s) for s in self.lProjectFolders]
        assert Counter(lOutputLines) == Counter(lExpectedOutputLines)

    def test_repoTopic_whenTopic(self):
        self.runRepo(["start", "topic_test"])

        sOutput = self.runRepo(["topic"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = ["%s: %s" % (os.path.basename(s), "topic_test") for s in self.lProjectFolders]
        assert Counter(lOutputLines) == Counter(lExpectedOutputLines)

    def test_repoPush(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.push()

        for sProjectFolder in self.lProjectFolders:
            sProjectName = os.path.basename(sProjectFolder)
            dJson = self.oTestSetup.oGerritClient.get("changes/?q=%s" % requests.utils.quote("p:%s" % sProjectName),
                                                      bGetJson=True)
            assert len(dJson) == 1
            assert dJson[0]["project"] == sProjectName

    def test_repoPush_crossrepo(self):
        self.runRepo(["start", "crossrepo/topic"])
        self.createCommit()

        self.runRepo(["push"])

        for sProjectFolder in self.lProjectFolders:
            sProjectName = os.path.basename(sProjectFolder)
            dJson = self.oTestSetup.oGerritClient.get("changes/?q=%s" % requests.utils.quote("p:%s" % sProjectName),
                                                      bGetJson=True)
            assert len(dJson) == 1
            assert dJson[0]["project"] == sProjectName
            assert dJson[0]["topic"] == "crossrepo/topic"

    def test_repoDownload_rebase(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        iChangeNumber = self.push()[0]
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")

        self.runRepo(["download", os.path.basename(self.lProjectFolders[0]), "%d/1" % iChangeNumber])

        for iIdx, sProjectFolder in enumerate(self.lProjectFolders):
            assert self.getCurrentBranch(sProjectFolder) == "topic_2"
            assert os.path.isfile(os.path.join(sProjectFolder, "test_2.txt"))
            if iIdx == 0:
                assert os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))
                assert self.getGitMessages(sProjectFolder) == ["Test commit (2)", "Test commit (1)",
                                                               INITIAL_COMMIT_MSG]
            else:
                assert not os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))
                assert self.getGitMessages(sProjectFolder) == ["Test commit (2)", INITIAL_COMMIT_MSG]

    def test_repoDownload_detach(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        iChangeNumber = self.push()[0]
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")

        self.runRepo(["download", "-d", os.path.basename(self.lProjectFolders[0]), "%d/1" % iChangeNumber])

        for iIdx, sProjectFolder in enumerate(self.lProjectFolders):
            if iIdx == 0:
                assert self.getCurrentBranch(sProjectFolder) == ""
                assert os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))
                assert not os.path.isfile(os.path.join(sProjectFolder, "test_2.txt"))
                assert self.getGitMessages(sProjectFolder) == ["Test commit (1)", INITIAL_COMMIT_MSG]
            else:
                assert self.getCurrentBranch(sProjectFolder) == "topic_2"
                assert not os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))
                assert os.path.isfile(os.path.join(sProjectFolder, "test_2.txt"))
                assert self.getGitMessages(sProjectFolder) == ["Test commit (2)", INITIAL_COMMIT_MSG]

    def test_repoRebase_simple(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")

        self.runRepo(["rebase", "topic_1"])

        for iIdx, sProjectFolder in enumerate(self.lProjectFolders):
            assert self.getCurrentBranch(sProjectFolder) == "topic_2"
            assert os.path.isfile(os.path.join(sProjectFolder, "test_1.txt"))
            assert os.path.isfile(os.path.join(sProjectFolder, "test_2.txt"))
            assert self.getGitMessages(sProjectFolder) == ["Test commit (2)", "Test commit (1)",
                                                           INITIAL_COMMIT_MSG]

    def test_repoRebase_complex(self):
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        self.runRepo(["start", "topic_2"])
        self.createCommit(sId="2")
        self.runRepo(["switch", "topic_1"])
        self.createCommit(sId="1", bAmend=True)
        self.runRepo(["switch", "topic_2"])

        self.runRepo(["rebase", "topic_1"])

        for iIdx, sProjectFolder in enumerate(self.lProjectFolders):
            assert self.getCurrentBranch(sProjectFolder) == "topic_2"
            sFilePath = os.path.join(sProjectFolder, "test_1.txt")
            assert os.path.isfile(sFilePath)
            with open(sFilePath, "r") as oFile:
                assert oFile.read() == "This is an amended test (1)."
            assert os.path.isfile(os.path.join(sProjectFolder, "test_2.txt"))
            assert self.getGitMessages(sProjectFolder) == ["Test commit (2)", "Amended test commit (1)",
                                                           INITIAL_COMMIT_MSG]

    def test_repoRename(self):
        self.runRepo(["start", "topic"])

        self.runRepo(["rename", "renamed_topic"])

        for sProjectFolder in self.lProjectFolders:
            assert self.getCurrentBranch(sProjectFolder) == "renamed_topic"
            assert self.getAllBranches(sProjectFolder) == ["renamed_topic"]

    def test_repoStash(self):
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        for sProjectFolder in self.lProjectFolders:
            with open(os.path.join(sProjectFolder, "test_1.txt"), "w") as oFile:
                oFile.write("Modified!")

        self.runRepo(["stash"])

        for sProjectFolder in self.lProjectFolders:
            with open(os.path.join(sProjectFolder, "test_1.txt"), "r") as oFile:
                assert oFile.read() == "This is a test (1)."

    def test_repoPop(self):
        self.test_repoStash()

        self.runRepo(["pop"])

        for sProjectFolder in self.lProjectFolders:
            with open(os.path.join(sProjectFolder, "test_1.txt"), "r") as oFile:
                assert oFile.read() == "Modified!"
