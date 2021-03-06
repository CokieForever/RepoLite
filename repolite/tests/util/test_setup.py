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

"""Utilities to prepare the test environment"""

__author__ = "Quoc-Nam Dessoulles"
__email__ = "cokie.forever@gmail.com"
__license__ = "MIT"

import os
import shutil
import signal
import stat
import subprocess
import time
from collections import OrderedDict
from configparser import ConfigParser
from urllib.parse import urlparse, quote

import requests
from requests import RequestException

from repolite.util.misc import FatalError, kill
from repolite.vcs import gerrit


class Setup:
    def __init__(self):
        self.sResDirPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "res"))
        self.sGerritInstallationFile = os.path.join(self.sResDirPath, "gerrit-3.1.4.war")
        self.sGerritInstallationFolder = os.path.join(self.sResDirPath, "gerrit")
        self.sGerritConfigFile = os.path.join(self.sGerritInstallationFolder, "etc", "gerrit.config")
        self.sAdminUsername = "admin"
        self.sAdminPassword = "admin"
        self.sRepoConfigFolder = os.path.join(self.sResDirPath, "repolite")
        self.oApiClient = None
        self.oGerritProcess = None
        self.lProjectUrls = []

    def setup(self):
        self.installGerrit()
        self.launchGerrit()
        self.configureGerrit()
        self.configureSsh()
        self.configureRepo()

    def teardown(self):
        try:
            self.restoreSsh()
        finally:
            self.stopGerrit()

    def installGerrit(self):
        print("Cleaning up previous gerrit installation")
        removeFolder(self.sGerritInstallationFolder)

        print("Installing gerrit")
        subprocess.run(["java", "-jar", self.sGerritInstallationFile, "init", "--install-all-plugins",
                        "--no-auto-start", "-b", "-d", self.sGerritInstallationFolder], check=True)

        print("Setting up config file")
        oConfig = self.readGerritConfig()
        oConfig["auth"]["type"] = "DEVELOPMENT_BECOME_ANY_ACCOUNT"
        self.writeGerritConfig(oConfig)

    def launchGerrit(self, bWait=True):
        print("Launching gerrit")
        self.oGerritProcess = subprocess.Popen(["java", "-jar", os.path.join("bin", "gerrit.war"),
                                                "daemon", "--console-log"], cwd=self.sGerritInstallationFolder)
        if bWait:
            self.waitForGerrit()

    def waitForGerrit(self, iTimeout=60):
        print("Waiting for gerrit")
        iStartTime = time.time()
        while True:
            try:
                requests.get("http://localhost:8080/", timeout=1)
                print("Gerrit is running")
                break
            except RequestException:
                if time.time() - iStartTime >= iTimeout:
                    raise FatalError("Gerrit does not seem to start")

    def configureGerrit(self):
        print("Generating SSH key")
        sPubKey = generateSshKey()

        print("Configuring admin user")
        oSession = requests.session()
        oSession.post("http://localhost:8080/login/%23%2Fregister",
                      data={"action": "create_account"}).raise_for_status()
        oSession.get("http://localhost:8080/")
        oSession.headers.update({"X-Gerrit-Auth": oSession.cookies.get_dict()["XSRF_TOKEN"]})
        oSession.put("http://localhost:8080/accounts/self/username",
                     json={"username": self.sAdminUsername}).raise_for_status()
        oSession.post("http://localhost:8080/accounts/self/sshkeys",
                      data=sPubKey).raise_for_status()
        oSession.put("http://localhost:8080/accounts/self/password.http",
                     json={"http_password": self.sAdminPassword}).raise_for_status()

        self.oApiClient = gerrit.ApiClient("http://localhost:8080", self.sAdminUsername, self.sAdminPassword)
        self.createProjects()

    def createProjects(self):
        print("Adding projects")
        self.lProjectUrls = []
        for sProject in ["Project1", "Project2", "sub/Project3"]:
            self.oApiClient.put("projects/%s" % quote(sProject, safe=""), json={"create_empty_commit": True})
            dJson = self.oApiClient.get("config/server/info")
            self.lProjectUrls.append(dJson["download"]["schemes"]["ssh"]["url"].replace("${project}", quote(sProject)))

    def resetProjects(self):
        print("Deleting all projects")
        for sProject in self.oApiClient.get("projects/"):
            if sProject.lower() not in ["all-projects", "all-users"]:
                self.oApiClient.post("projects/%s/delete-project~delete" % quote(sProject, safe=""),
                                     json={"force": True, "preserve": False})
        self.createProjects()

    def configureSsh(self):
        print("Configuring host SSH")
        sHostsFile = os.path.expanduser(os.path.join("~", ".ssh", "known_hosts"))
        sBackupHostsFile = sHostsFile + ".repo.backup"
        if os.path.isfile(sHostsFile) and not os.path.isfile(sBackupHostsFile):
            os.rename(sHostsFile, sBackupHostsFile)

        oUrl = urlparse(self.lProjectUrls[0])
        lKeys = subprocess.run(["ssh-keyscan", "-p", str(oUrl.port), oUrl.hostname],
                               capture_output=True, check=True, encoding="utf-8").stdout.splitlines()
        with open(sHostsFile, "w") as oFile:
            oFile.write("\n".join(lKeys) + "\n")

    def restoreSsh(self):
        print("Restoring original host SSH config")
        sHostsFile = os.path.expanduser(os.path.join("~", ".ssh", "known_hosts"))
        sBackupHostsFile = sHostsFile + ".repo.backup"
        if os.path.isfile(sBackupHostsFile):
            if os.path.isfile(sHostsFile):
                os.remove(sHostsFile)
            os.rename(sBackupHostsFile, sHostsFile)

    def configureRepo(self):
        os.makedirs(self.sRepoConfigFolder, exist_ok=True)
        with open(os.path.join(self.sRepoConfigFolder, ".repolite"), "w") as oFile:
            oFile.write("[DEFAULT]\n" +
                        "url = http://localhost:8080\n" +
                        "username = %s\n" % self.sAdminUsername +
                        "password = %s\n" % self.sAdminPassword)

    def stopGerrit(self):
        print("Stopping gerrit")
        if self.oGerritProcess is not None:
            kill(self.oGerritProcess.pid, signal.SIGINT)
            if self.waitForGerritProcess(10) is None:
                print("Gerrit did not response to SIGINT, sending SIGTERM")
                self.oGerritProcess.terminate()
                if self.waitForGerritProcess(5) is None:
                    raise FatalError("Unable to stop Gerrit")
            self.oGerritProcess = None

    def waitForGerritProcess(self, iTimeout):
        # Unfortunately using self.oGerritProcess.wait() seems to block the process itself, so we use our own loop
        iTimeStart = time.time()
        while self.oGerritProcess.poll() is None and time.time() - iTimeStart < iTimeout:
            time.sleep(1)
        return self.oGerritProcess.poll()

    def readGerritConfig(self):
        oConfig = ConfigParser(dict_type=ConcatOrderedDict, strict=False)
        oConfig.read(self.sGerritConfigFile)
        return oConfig

    def writeGerritConfig(self, oConfig):
        with open(self.sGerritConfigFile, 'w') as oFile:
            oConfig.write(oFile)


def removeQuotes(s):
    if len(s) > 1 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    else:
        return s


def generateSshKey():
    sRsaPubKeyFile = os.path.expanduser(os.path.join("~", ".ssh", "id_rsa.pub"))
    if not os.path.isfile(sRsaPubKeyFile):
        subprocess.run(["ssh-keygen", "-t", "rsa", "-N", "", "-f", os.path.splitext(sRsaPubKeyFile)[0]], check=True)
    with open(sRsaPubKeyFile, "r") as oFile:
        return oFile.read()


def removeFolder(sFolderPath):
    if os.path.isdir(sFolderPath):
        def onRmError(sPath):
            os.chmod(sPath, stat.S_IWRITE)
            os.remove(sPath)

        shutil.rmtree(sFolderPath, onerror=lambda *args: onRmError(args[1]))


def withRetry(xCallable):
    try:
        xCallable()
    except OSError:
        time.sleep(1)
        xCallable()


def getExecutablePath(sExeName):
    if os.name != 'nt':
        return sExeName
    sSystem32 = os.path.normcase(os.path.join(os.environ.get('SystemRoot'), "System32"))
    sSystemNative = os.path.normcase(os.path.join(os.environ.get('SystemRoot'), "SysNative"))
    for sFolder in os.environ.get("Path").split(";"):
        sPath = os.path.normcase(os.path.join(sFolder, sExeName))
        for s in [sPath, sPath.replace(sSystem32, sSystemNative)]:
            if os.path.isfile(s):
                return s


def configureGit(sGitFolder):
    dConfigs = {"user.name": __author__, "user.email": __email__}
    for sConfigKey, sConfigValue in dConfigs.items():
        subprocess.run(["git", "config", "--local", sConfigKey, sConfigValue], capture_output=True,
                       encoding="utf-8", check=True, cwd=sGitFolder).stdout.strip()


class ConcatOrderedDict(OrderedDict):
    def __setitem__(self, key, value):
        if isinstance(value, list) and key in self:
            self[key][0] = '"%s %s"' % (removeQuotes(self[key][0]), removeQuotes(value[0]))
        else:
            super().__setitem__(key, value)


if __name__ == "__main__":
    oSetup = Setup()
    try:
        oSetup.setup()
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, stopping")
    finally:
        oSetup.teardown()
