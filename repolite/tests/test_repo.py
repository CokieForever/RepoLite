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

import requests

from repolite.tests.util.test_base import TestBase
from repolite.util.misc import changeWorkingDir
from repolite.vcs import git

INITIAL_COMMIT_MSG = "Initial empty repository"


class TestRepo(TestBase):
    def test_repoSync_checkout(self):
        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                lBranches = git.getAllBranches()
                assert len(lBranches) == 1
                assert re.match(r"\(HEAD detached at .*\)", lBranches[0], re.IGNORECASE) is not None
                assert git.getCurrentBranch() == ""
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]

    def test_repoStart_onDetached(self):
        self.runRepo(["start", "topic"])

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic"
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]

    def test_repoStart_onOtherTopic(self):
        self.runRepo(["start", "topic_1"])
        self.createCommit()
        self.runRepo(["start", "topic_2"])

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert git.getGitMessages() == ["Test commit (1)", INITIAL_COMMIT_MSG]
                assert os.path.isfile("test_1.txt")

    def test_repoSync_detach(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.runRepo(["sync", "-d"])

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == ""
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]
                assert not os.path.isfile("test_1.txt")

    def test_repoSwitch(self):
        self.runRepo(["start", "topic_1"])
        self.runRepo(["start", "topic_2"])
        self.createCommit()

        self.runRepo(["switch", "topic_1"])

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_1"
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]
                assert not os.path.isfile("test_1.txt")

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
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert os.path.isfile("test_2.txt")
                assert os.path.isfile("test_1.txt")
                assert git.getGitMessages() == ["Test commit (2)", "Test commit (1)", INITIAL_COMMIT_MSG]

    def test_repoEnd_whenActive(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.runRepo(["end", "topic"])

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                lBranches = git.getAllBranches()
                assert len(lBranches) == 1
                assert re.match(r"\(HEAD detached at .*\)", lBranches[0], re.IGNORECASE) is not None
                assert git.getCurrentBranch() == ""
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]
                assert not os.path.isfile("test_1.txt")

    def test_repoEnd_whenNotActive(self):
        self.runRepo(["start", "topic_1"])
        self.runRepo(["start", "topic_2"])

        self.runRepo(["end", "topic_1"])

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getAllBranches() == ["topic_2"]
                assert git.getCurrentBranch() == "topic_2"

    def test_repoTopic(self):
        self.runRepo(["start", "topic_test"])

        sOutput = self.runRepo(["topic"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        assert lOutputLines[0] == "topic_test"

    def test_repoTopic_whenMultipleTopic(self):
        self.runGit(["checkout", "-b", "topic_test"], self.lProjectFolders[0])
        sOutput = self.runRepo(["topic"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = ["%s ........ (none)" % os.path.basename(s) for s in self.lProjectFolders]
        lExpectedOutputLines[0] = "%s .... topic_test" % os.path.basename(self.lProjectFolders[0])
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines

    def test_repoPush(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.push()

        for sProjectFolder in self.lProjectFolders:
            sProjectName = os.path.basename(sProjectFolder)
            dJson = self.oApiClient.get("changes/?q=%s" % requests.utils.quote("p:%s" % sProjectName), bGetJson=True)
            assert len(dJson) == 1
            assert dJson[0]["project"] == sProjectName

    def test_repoPush_crossrepo(self):
        self.runRepo(["start", "crossrepo/topic"])
        self.createCommit()

        self.runRepo(["push"])

        for sProjectFolder in self.lProjectFolders:
            sProjectName = os.path.basename(sProjectFolder)
            dJson = self.oApiClient.get("changes/?q=%s" % requests.utils.quote("p:%s" % sProjectName), bGetJson=True)
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
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert os.path.isfile("test_2.txt")
                if iIdx == 0:
                    assert os.path.isfile("test_1.txt")
                    assert git.getGitMessages() == ["Test commit (2)", "Test commit (1)", INITIAL_COMMIT_MSG]
                else:
                    assert not os.path.isfile("test_1.txt")
                    assert git.getGitMessages() == ["Test commit (2)", INITIAL_COMMIT_MSG]

    def test_repoDownload_detach(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        iChangeNumber = self.push()[0]
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")

        self.runRepo(["download", "-d", os.path.basename(self.lProjectFolders[0]), "%d/1" % iChangeNumber])

        for iIdx, sProjectFolder in enumerate(self.lProjectFolders):
            with changeWorkingDir(sProjectFolder):
                if iIdx == 0:
                    assert git.getCurrentBranch() == ""
                    assert os.path.isfile("test_1.txt")
                    assert not os.path.isfile("test_2.txt")
                    assert git.getGitMessages() == ["Test commit (1)", INITIAL_COMMIT_MSG]
                else:
                    assert git.getCurrentBranch() == "topic_2"
                    assert not os.path.isfile("test_1.txt")
                    assert os.path.isfile("test_2.txt")
                    assert git.getGitMessages() == ["Test commit (2)", INITIAL_COMMIT_MSG]

    def test_repoRebase_simple(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")

        self.runRepo(["rebase", "topic_1"])

        for iIdx, sProjectFolder in enumerate(self.lProjectFolders):
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert os.path.isfile("test_1.txt")
                assert os.path.isfile("test_2.txt")
                assert git.getGitMessages() == ["Test commit (2)", "Test commit (1)", INITIAL_COMMIT_MSG]

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
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                sFileName = "test_1.txt"
                assert os.path.isfile(sFileName)
                with open(sFileName, "r") as oFile:
                    assert oFile.read() == "This is an amended test (1)."
                assert os.path.isfile("test_2.txt")
                assert git.getGitMessages() == ["Test commit (2)", "Amended test commit (1)", INITIAL_COMMIT_MSG]

    def test_repoRename(self):
        self.runRepo(["start", "topic"])

        self.runRepo(["rename", "renamed_topic"])

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "renamed_topic"
                assert git.getAllBranches() == ["renamed_topic"]

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

    def test_repoPop_whenNoContent(self):
        sOutput = self.runRepo(["pop"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = []
        for sProjectFolder in self.lProjectFolders:
            lExpectedOutputLines += ["### %s ###" % os.path.basename(sProjectFolder),
                                     "Retrieving stashed content", "WARN: No content to retrieve", "Done"]
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines
