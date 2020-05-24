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

"""test_api.py"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import os

from repolite.tests.util.test_base import TestBase
from repolite.util.misc import changeWorkingDir
from repolite.vcs import gerrit


class TestApi(TestBase):
    def test_getChange(self):
        self.createCommit()
        self.push()

        for sProjectFolder in self.lProjectFolders:
            with changeWorkingDir(sProjectFolder):
                sProjectName = os.path.basename(sProjectFolder)
                sChangeId = gerrit.getChangeId()
                dChange = self.oApiClient.getChange("%s~master~%s" % (sProjectName, sChangeId))

                assert dChange is not None
                assert dChange["id"] == "%s~master~%s" % (sProjectName, sChangeId)
                assert dChange["project"] == sProjectName
                assert dChange["branch"] == "master"
                assert dChange["change_id"] == sChangeId
                assert dChange["status"] == "NEW"
