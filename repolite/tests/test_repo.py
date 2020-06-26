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
from urllib.parse import quote_plus

import pytest

from repolite.tests.util.test_base import TestBase
from repolite.util.misc import changeWorkingDir
from repolite.vcs import git, gerrit

INITIAL_COMMIT_MSG = "Initial empty repository"


class TestRepo(TestBase):
    def test_repoSync_checkout(self):
        for sProjectFolder in self.dProjectFolders:
            with changeWorkingDir(sProjectFolder):
                lBranches = git.getAllBranches()
                assert len(lBranches) == 1
                assert re.match(r"\(HEAD detached at .*\)", lBranches[0], re.IGNORECASE) is not None
                assert git.getCurrentBranch() == ""
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]

    def test_repoStart_onDetached(self):
        self.runRepo(["start", "topic"])

        for sProjectFolder in self.dProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic"
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]

    def test_repoStart_onOtherTopic(self):
        self.runRepo(["start", "topic_1"])
        self.createCommit()
        self.runRepo(["start", "topic_2"])

        for sProjectFolder in self.dProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert git.getGitMessages() == ["Test commit (1)", INITIAL_COMMIT_MSG]
                assert os.path.isfile("test_1.txt")

    def test_repoSync_detach(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.runRepo(["sync", "-d"])

        for sProjectFolder in self.dProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == ""
                assert git.getGitMessages() == [INITIAL_COMMIT_MSG]
                assert not os.path.isfile("test_1.txt")

    def test_repoSwitch(self):
        self.runRepo(["start", "topic_1"])
        self.runRepo(["start", "topic_2"])
        self.createCommit()

        self.runRepo(["switch", "topic_1"])

        for sProjectFolder in self.dProjectFolders:
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

        for iIdx, sProjectFolder in enumerate(self.dProjectFolders):
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert os.path.isfile("test_2.txt")
                assert os.path.isfile("test_1.txt")
                assert git.getGitMessages() == ["Test commit (2)", "Test commit (1)", INITIAL_COMMIT_MSG]

    def test_repoEnd_whenActive(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.runRepo(["end", "topic"])

        for sProjectFolder in self.dProjectFolders:
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

        for sProjectFolder in self.dProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getAllBranches() == ["topic_2"]
                assert git.getCurrentBranch() == "topic_2"

    def test_repoTopic(self):
        self.runRepo(["start", "topic_test"])

        sOutput = self.runRepo(["topic"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        assert lOutputLines[0] == "topic_test"

    def test_repoTopic_whenMultipleTopic(self):
        with changeWorkingDir(next(iter(self.dProjectFolders))):
            self.runGit(["checkout", "-b", "topic_test"])

        sOutput = self.runRepo(["topic"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = ["%s ........ (none)" % os.path.basename(s) for s in self.dProjectFolders]
        lExpectedOutputLines[0] = "%s .... topic_test" % os.path.basename(next(iter(self.dProjectFolders)))
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines

    def test_repoPush_newChange(self):
        self.runRepo(["start", "topic"])
        self.createCommit()

        self.push()

        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            dJson = self.oApiClient.get("changes/?q=%s" % quote_plus("p:%s" % sProjectName))
            assert len(dJson) == 1
            assert dJson[0]["project"] == sProjectName

    def test_repoPush_updateChange(self):
        self.test_repoPush_newChange()
        self.createCommit(bAmend=True)

        self.push()

        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            dJson = self.oApiClient.get("changes/?q=%s&o=ALL_REVISIONS" % quote_plus("p:%s" % sProjectName))
            assert len(dJson) == 1
            assert dJson[0]["project"] == sProjectName
            assert len(dJson[0]["revisions"]) == 2

    def test_repoPush_whenNoNewChange(self):
        self.test_repoPush_newChange()

        sOutput = self.runRepo(["push"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = []
        for sProjectFolder in self.dProjectFolders:
            lExpectedOutputLines += ["### %s ###" % os.path.basename(sProjectFolder), "WARN: No new changes", "Done"]
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines

        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            dJson = self.oApiClient.get("changes/?q=%s&o=ALL_REVISIONS" % quote_plus("p:%s" % sProjectName))
            assert len(dJson) == 1
            assert dJson[0]["project"] == sProjectName
            assert len(dJson[0]["revisions"]) == 1

    def test_repoPush_whenRemoteUpdated(self):
        self.runRepo(["start", "topic"])
        self.createCommit()
        iChangeNumber = self.push()[0]
        self.oApiClient.put("changes/%d/message" % iChangeNumber, json={"message": "Updated!"})
        self.createCommit(bAmend=True)

        oProcess = self.runRepo(["push"], input="n", check=False)
        assert oProcess.returncode != 0

        lOutputLines = list(filter(bool, oProcess.stdout.splitlines()))
        sName = os.path.basename(next(iter(self.dProjectFolders)))
        lExpectedOutputLines = ["### %s ###" % sName, "WARN: You are about to overwrite unknown changes.",
                                "Continue? (y/n): ERROR: [%s] Operation aborted" % sName]
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines

        for iIdx, (sProjectFolder, sProjectName) in enumerate(self.dProjectFolders.items()):
            dJson = self.oApiClient.get("changes/?q=%s&o=ALL_REVISIONS" % quote_plus("p:%s" % sProjectName))
            assert len(dJson) == 1
            assert dJson[0]["project"] == sProjectName
            assert len(dJson[0]["revisions"]) == 2
            with changeWorkingDir(sProjectFolder):
                sLastCommit = git.getLastCommit()
            if iIdx == 0:
                assert dJson[0]["current_revision"] != sLastCommit
            else:
                assert dJson[0]["current_revision"] == sLastCommit

    def test_repoPush_multipleTopics(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")

        self.push()
        self.runRepo(["switch", "topic_1"])
        self.push()

        for iIdx, (sProjectFolder, sProjectName) in enumerate(self.dProjectFolders.items()):
            dJson = self.oApiClient.get("changes/?q=%s&o=ALL_REVISIONS" % quote_plus("p:%s" % sProjectName))
            assert len(dJson) == 2
            for dData in dJson:
                assert dData["project"] == sProjectName
                assert len(dData["revisions"]) == 1

    def test_repoPull(self):
        self.runRepo(["start", "topic"])
        self.createCommit()
        self.push()
        dCommits = self.createChange(bAmend=True)

        self.runRepo(["pull"])

        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            with changeWorkingDir(sProjectFolder):
                assert dCommits[sProjectName] == git.getLastCommit()

    def test_repoPull_whenAlreadyUpToDate(self):
        self.runRepo(["start", "topic"])
        dCommits = self.createCommit()
        self.runRepo(["push"])

        sOutput = self.runRepo(["pull"], capture_output=True, encoding="utf-8").stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = []
        for sProjectFolder in self.dProjectFolders:
            lExpectedOutputLines += ["### %s ###" % os.path.basename(sProjectFolder), "Already up-to-date.", "Done"]
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines

        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            with changeWorkingDir(sProjectFolder):
                assert dCommits[sProjectName] == git.getLastCommit()

    def test_repoPull_whenAhead(self):
        self.runRepo(["start", "topic"])
        self.createCommit()
        self.runRepo(["push"])
        dCommits = self.createCommit(bAmend=True)

        sOutput = self.runRepo(["pull"], capture_output=True, encoding="utf-8").stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = []
        for sProjectFolder in self.dProjectFolders:
            lExpectedOutputLines += ["### %s ###" % os.path.basename(sProjectFolder),
                                     "You are ahead of Gerrit.", "Done"]
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines

        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            with changeWorkingDir(sProjectFolder):
                assert dCommits[sProjectName] == git.getLastCommit()

    def test_repoPull_whenConflict(self):
        self.runRepo(["start", "topic"])
        self.createCommit()
        self.runRepo(["push"])
        self.createChange(bAmend=True)
        dCommits = self.createCommit(bAmend=True)

        oProcess = self.runRepo(["pull"], capture_output=True, encoding="utf-8", check=False)
        assert oProcess.returncode != 0

        lOutputLines = list(filter(bool, oProcess.stdout.splitlines()))
        lExpectedOutputLines = []
        for sProjectFolder in self.dProjectFolders:
            sName = os.path.basename(sProjectFolder)
            lExpectedOutputLines += ["### %s ###" % sName,
                                     "ERROR: [%s] You have local commits unknown to Gerrit" % sName]
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines

        for sProjectFolder, sProjectName in self.dProjectFolders.items():
            with changeWorkingDir(sProjectFolder):
                assert dCommits[sProjectName] == git.getLastCommit()

    def repoDownloadTestSetup(self):
        self.runRepo(["start", "topic_2"])
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        self.push()
        self.createCommit(sId="1", bAmend=True)
        iChangeNumber = self.push()[0]
        with changeWorkingDir(next(iter(self.dProjectFolders))):
            sChangeId = gerrit.getChangeId()
        self.runRepo(["switch", "topic_2"])
        self.createCommit(sId="2")
        return iChangeNumber, sChangeId

    def repoDownloadTestAssertResult(self, iPatch):
        for iIdx, sProjectFolder in enumerate(self.dProjectFolders):
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert os.path.isfile("test_2.txt")
                if iIdx == 0:
                    assert os.path.isfile("test_1.txt")
                    if iPatch == 1:
                        assert git.getGitMessages() == ["Test commit (2)", "Test commit (1)", INITIAL_COMMIT_MSG]
                    elif iPatch == 2:
                        assert git.getGitMessages() == ["Test commit (2)", "Amended test commit (1)",
                                                        INITIAL_COMMIT_MSG]
                    else:
                        pytest.fail("iPatch parameter must be 1 or 2, received %d" % iPatch)
                else:
                    assert not os.path.isfile("test_1.txt")
                    assert git.getGitMessages() == ["Test commit (2)", INITIAL_COMMIT_MSG]

    def test_repoDownload_rebase_project_changeNumber_patchNumber(self):
        iChangeNumber, _ = self.repoDownloadTestSetup()

        self.runRepo(["download", next(iter(self.dProjectFolders.values())), "%d/1" % iChangeNumber])

        self.repoDownloadTestAssertResult(iPatch=1)

    def test_repoDownload_rebase_project_changeId_patchNumber(self):
        _, sChangeId = self.repoDownloadTestSetup()

        self.runRepo(["download", next(iter(self.dProjectFolders.values())), "%s/1" % sChangeId])

        self.repoDownloadTestAssertResult(iPatch=1)

    def test_repoDownload_rebase_wrongProject(self):
        iChangeNumber, _ = self.repoDownloadTestSetup()

        oProcess = self.runRepo(["download", "foobar", "%d/1" % iChangeNumber], check=False)
        assert oProcess.returncode != 0

        for iIdx, sProjectFolder in enumerate(self.dProjectFolders):
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "topic_2"
                assert os.path.isfile("test_2.txt")
                assert not os.path.isfile("test_1.txt")
                assert git.getGitMessages() == ["Test commit (2)", INITIAL_COMMIT_MSG]

    def test_repoDownload_rebase_noProject_changeNumber_patchNumber(self):
        iChangeNumber, _ = self.repoDownloadTestSetup()

        self.runRepo(["download", "%d/1" % iChangeNumber])

        self.repoDownloadTestAssertResult(iPatch=1)

    def test_repoDownload_rebase_noProject_changeNumber_noPatchNumber(self):
        iChangeNumber, _ = self.repoDownloadTestSetup()

        self.runRepo(["download", "%d" % iChangeNumber])

        self.repoDownloadTestAssertResult(iPatch=2)

    def test_repoDownload_detach(self):
        iChangeNumber, _ = self.repoDownloadTestSetup()

        self.runRepo(["download", "-d", next(iter(self.dProjectFolders.values())), "%d/1" % iChangeNumber])

        for iIdx, sProjectFolder in enumerate(self.dProjectFolders):
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

        for iIdx, sProjectFolder in enumerate(self.dProjectFolders):
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

        for iIdx, sProjectFolder in enumerate(self.dProjectFolders):
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

        for sProjectFolder in self.dProjectFolders:
            with changeWorkingDir(sProjectFolder):
                assert git.getCurrentBranch() == "renamed_topic"
                assert git.getAllBranches() == ["renamed_topic"]

    def test_repoStash(self):
        self.runRepo(["start", "topic_1"])
        self.createCommit(sId="1")
        for sProjectFolder in self.dProjectFolders:
            with open(os.path.join(sProjectFolder, "test_1.txt"), "w") as oFile:
                oFile.write("Modified!")

        self.runRepo(["stash"])

        for sProjectFolder in self.dProjectFolders:
            with open(os.path.join(sProjectFolder, "test_1.txt"), "r") as oFile:
                assert oFile.read() == "This is a test (1)."

    def test_repoPop(self):
        self.test_repoStash()

        self.runRepo(["pop"])

        for sProjectFolder in self.dProjectFolders:
            with open(os.path.join(sProjectFolder, "test_1.txt"), "r") as oFile:
                assert oFile.read() == "Modified!"

    def test_repoPop_whenNoContent(self):
        sOutput = self.runRepo(["pop"]).stdout

        lOutputLines = list(filter(bool, sOutput.splitlines()))
        lExpectedOutputLines = []
        for sProjectFolder in self.dProjectFolders:
            lExpectedOutputLines += ["### %s ###" % os.path.basename(sProjectFolder),
                                     "Retrieving stashed content", "WARN: No content to retrieve", "Done"]
        assert lOutputLines[:len(lExpectedOutputLines)] == lExpectedOutputLines
