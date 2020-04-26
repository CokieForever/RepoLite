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

import json
import os
import shutil
import signal
import stat
import subprocess
import time
from collections import OrderedDict
from configparser import ConfigParser
from urllib.parse import urlparse

import requests
from requests import RequestException


class GerritClient:
    def __init__(self, sBaseUrl, sUsername, sPassword):
        self.sBaseUrl = sBaseUrl
        self.oSession = requests.session()
        self.oSession.auth = (sUsername, sPassword)

    def url(self, sUrl):
        return "/".join([self.sBaseUrl, "a", sUrl])

    def get(self, sUrl, bGetJson=False, **kwargs):
        oResponse = self.oSession.get(self.url(sUrl), **kwargs)
        oResponse.raise_for_status()
        return json.loads(oResponse.content[5:]) if bGetJson else oResponse

    def put(self, sUrl, bGetJson=False, **kwargs):
        oResponse = self.oSession.put(self.url(sUrl), **kwargs)
        oResponse.raise_for_status()
        return json.loads(oResponse.content[5:]) if bGetJson else oResponse

    def post(self, sUrl, bGetJson=False, **kwargs):
        oResponse = self.oSession.post(self.url(sUrl), **kwargs)
        oResponse.raise_for_status()
        return json.loads(oResponse.content[5:]) if bGetJson else oResponse

    def delete(self, sUrl, bGetJson=False, **kwargs):
        oResponse = self.oSession.delete(self.url(sUrl), **kwargs)
        oResponse.raise_for_status()
        return json.loads(oResponse.content[5:]) if bGetJson else oResponse


class Setup:
    def __init__(self):
        self.sResDirPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "res"))
        self.sGerritInstallationFile = os.path.join(self.sResDirPath, "gerrit-3.1.4.war")
        self.sGerritInstallationFolder = os.path.join(self.sResDirPath, "gerrit")
        self.sGerritConfigFile = os.path.join(self.sGerritInstallationFolder, "etc", "gerrit.config")
        self.sAdminUsername = "admin"
        self.sAdminPassword = "admin"
        self.oGerritClient = None
        self.oGerritProcess = None
        self.lProjectUrls = []

    def setup(self):
        self.installGerrit()
        self.launchGerrit()
        self.waitForGerrit()
        self.configureGerrit()
        self.configureSsh()

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

    def launchGerrit(self):
        print("Launching gerrit")
        self.oGerritProcess = subprocess.Popen(["java", "-jar", os.path.join("bin", "gerrit.war"),
                                                "daemon", "--console-log"], cwd=self.sGerritInstallationFolder)

    def waitForGerrit(self, iTimeout=30):
        print("Waiting for gerrit")
        iStartTime = time.time()
        while True:
            try:
                requests.get("http://localhost:8080/", timeout=1)
                print("Gerrit is running")
                break
            except RequestException:
                if time.time() - iStartTime >= iTimeout:
                    raise

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

        self.oGerritClient = GerritClient("http://localhost:8080", self.sAdminUsername, self.sAdminPassword)
        self.createProjects()

    def createProjects(self):
        print("Adding projects")
        self.lProjectUrls = []
        for sProject in ["Project1", "Project2"]:
            self.oGerritClient.put("projects/%s" % sProject, json={"create_empty_commit": True})
            dJson = self.oGerritClient.get("config/server/info", bGetJson=True)
            self.lProjectUrls.append(dJson["download"]["schemes"]["ssh"]["url"].replace("${project}", sProject))

    def resetProjects(self):
        print("Deleting all projects")
        for sProject in self.oGerritClient.get("projects/", bGetJson=True):
            if sProject.lower() not in ["all-projects", "all-users"]:
                self.oGerritClient.post("projects/%s/delete-project~delete" % sProject,
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
                               capture_output=True, check=True, encoding="latin-1").stdout.splitlines()
        with open(sHostsFile, "w") as oFile:
            oFile.write("\n".join(lKeys) + "\n")

    def restoreSsh(self):
        print("Restoring original host SSH config")
        sHostsFile = os.path.expanduser(os.path.join("~", ".ssh", "known_hosts"))
        os.remove(sHostsFile)
        sBackupHostsFile = sHostsFile + ".repo.backup"
        if os.path.isfile(sBackupHostsFile):
            os.rename(sBackupHostsFile, sHostsFile)

    def stopGerrit(self):
        print("Stopping gerrit")
        if self.oGerritProcess is not None:
            os.kill(self.oGerritProcess.pid, signal.CTRL_C_EVENT)
            # oGerritProcess.send_signal(signal.SIGINT)
            try:
                self.oGerritProcess.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("Gerrit did not response to SIGINT, sending SIGTERM")
                os.kill(self.oGerritProcess.pid, signal.SIGTERM)
            except KeyboardInterrupt:
                pass  # Expected
            self.oGerritProcess = None

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
