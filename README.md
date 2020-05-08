![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)
![](https://img.shields.io/github/license/CokieForever/RepoLite)
![](https://img.shields.io/github/workflow/status/CokieForever/RepoLite/Build)

# Repo Lite

A small command line tool to manage your [Gerrit](https://www.gerritcodereview.com/) repositories.

## Description

This is a small utility inspired by the
[Repo](https://gerrit.googlesource.com/git-repo/+/refs/heads/master/README.md) tool. Be aware that this does not aim
to be a replacement for the Repo tool. This is a simple client aiming to make the management of Gerrit repositories
easier, especially if you are on Windows and cannot run the Repo tool.

While some commands such as `repo sync` or `repo download` are available in a lightened form, many other ones are not,
and a few new ones are introduced such as `repo switch` or `repo push`.

## Installation

Go to the root folder and run: `pip install .`. This will install the tool and put it in your PATH.

## Usage

In order to use the tool, you will need to put a simple `manifest.txt` file in a folder (preferably empty), containing
a simple list of the Gerrit repositories you want to clone:

```
ssh://user@host.com:29418/Project_A
ssh://user@host.com:29418/tools/Project_B
```

Then within that folder run `repo sync` to clone all repositories. The typical workflow then looks as follow:

1. (Optional) Reset all your repositories to the state of the current master with `repo sync -d`.
2. Start a new topic with `repo start <topic>`. A _topic_ is merely a branch, which this command will create in all
your repositories.
3. Work on your files, and commit your changes. Don't forget the `Change-Id`.
4. Push all your changes with `repo push`.
5. After your changes are merged, delete your topic with `repo end <topic>`.

Other useful commands are:

* `repo switch <topic>` will switch all of your repositories to the specified topic.
* `repo sync` will rebase all of your repos on top of the current master.
* `repo rebase <topic>` will rebase all of your local repositories on top of the ones in the specified topic.
* `repo download <project> <change>` will download the specified change of the specified project and rebase your
matching local repository on top of it, if any. This is useful to rebase your work on top of the work of another
collaborator.
* `repo download -d <project> <change>` will download the specified change of the specified project. Unlike
 the previous point, in this case the HEAD is detached and your local work is not be rebased. This is useful to
 download and review the work of a collaborator.
 
Check `repo --help` for more information.

### A word about rebasing

When this tool performs rebasing, it will use the standard git rebasing but will also check for `Change-Id`s. For
example consider the two following topics:

```
T1: A --- B
T2: A --- B --- C
```

For now `T2`is on top of `T1`. Now if new changes are added on `T1`, it becomes:

```
T1: A --- B'
T2: A --- B --- C
```

`T2` is not on top of `T1` anymore, and simply rebasing it with git will bring you into trouble:

```
T1: A --- B'
T2: A --- B' --- B --- C
```

As git sees `B` and `B'` as two different commits, you will end up with a lot of conflicts for nothing. That's why the
tool will always additionally compare the `Change-Id`s of the commits and exclude commits with identical ones from the
rebasing process. You then end up with:

```
T1: A --- B'
T2: A --- B' --- C
```

Which is probably what you expected. Note however that if you had also added changes on `T2`, they will be lost in this
case.

## Uninstallation

Simply run `pip uninstall repolite` to uninstall the tool.

## Development status

The application is still being built. Therefore all functionalities may not be available / implemented yet.
