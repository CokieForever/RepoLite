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

Go to the root folder and run:
```commandline
pip install .
```
This will install the tool and put it in your PATH.

## Usage

### Initial repository setup

In order to use the tool, you will need to put a simple `manifest.txt` file in a folder (preferably empty), containing
a simple list of the Gerrit repositories you want to clone:

```text
ssh://user@host.com:29418/Project_A
ssh://user@host.com:29418/tools/Project_B
```

Then within that folder run `repo sync` to clone all repositories.

### Typical workflow

Typically, you work as follows:

1. Reset all your repositories to the state of the current master with `repo sync -d`.
2. Start a new topic with `repo start <topic>`. A _topic_ is merely a branch, which this command will create in all
your repositories.
3. Work on your files, and commit your changes. Don't forget the `Change-Id`.
4. Push all your changes with `repo push`.
5. Keep working on your files, and amend the previous commit. The `Change-Id` must stay the same.
6. Push your changes with `repo push`, re-work your files, amend the commit, etc.
7. Once you are done, and your changes are merged on the server, you can delete your topic locally with
`repo end <topic>`.

Of course, depending on the situation, you may need to perform more advanced operations. The next section lists the
available commands.

### Available commands

<table>
    <tr>
        <td nowrap><code>repo start</code></td>
        <td>
            Starts a new topic, i.e. creates a new branch with the specified name in all of your local repositories.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo end</code></td>
        <td>
            Deletes a topic, i.e. deletes the branch with the specified name of all of your local repositories.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo topic</code></td>
        <td>
            Displays the current topic, with highlighting in case of inconsistencies across your repositories.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo switch &lt;topic&gt;</code></td>
        <td>
            Switches to the specified topic, i.e. switch all of your local repositories to the specified branch.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo rename &lt;new name&gt;</code></td>
        <td>
            Renames the current topic, i.e. renames the current branch to the specified name in all of your
            repositories. If there is no topic (e.g. you are in detached HEAD state after <code>repo sync -d</code>
            or <code>repo download -d</code>), the operation will fail.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo push</code></td>
        <td>
            Uploads your local content to the remote repositories, but only if the local repositories are ahead of
            the remote ones. There is no force behavior.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo download &lt;change&gt;</code></td>
        <td>
            Downloads the specified change and rebase the matching local repository on top of it. This is 
            useful to rebase your work on top of the work of another collaborator which is not yet merged.
            See <code>repo download --help</code> for alternative syntaxes.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo download -d &lt;change&gt;</code></td>
        <td>
            Downloads the specified change. Unlike the command above, in this case the HEAD is detached and your local
            work is not be rebased. This is useful to download and review the work of a collaborator.
            See <code>repo download --help</code> for alternative syntaxes.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo pull</code></td>
        <td>
            Opposite of <code>repo push</code>, downloads the remote versions of your repositories to be used locally.
            Unlike <code>repo download</code>, no rebase or detach is done, this really replaces your local content
            with the remote one, but only if the remote repository is ahead of the local one. There is no merge or
            force behavior. This is useful when you made a change to your work through the Gerrit UI or another
            computer and you wish to have that change locally.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo rebase &lt;topic&gt;</code></td>
        <td>
            Rebases your local repositories on top of the (local) ones in the specified topic.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo sync</code></td>
        <td>
            Rebases your local repositories on top of the remote master.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo sync -d</code></td>
        <td>
            Downloads the remote master. Unlike <code>repo sync</code>, in this case the HEAD is detached and your
            local work is not be rebased.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo stash</code></td>
        <td>
            Stashes all uncommitted work in all of your local repositories. 
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo pop</code></td>
        <td>
            Opposite of `repo stash`, retrieves the stashed content in all of your local repositories. In case of
            conflict, you will have to solve it manually using the usual Git process. In this case, the stashed content
            is preserved, otherwise it is automatically deleted.
        </td>
    </tr>
    <tr>
        <td nowrap><code>repo forall &lt;command&gt;</code></td>
        <td>
            Executes the provided command in all repositories. Typically intended for batch execution of Git commands,
            but is not restricted to the sole usage of Git commands.
        </td>
    </tr>
</table>
 
Check `repo --help` for more information.

### A word about rebasing

When this tool performs rebasing, it will use the standard git rebasing but will also check for `Change-Id`s. For
example consider the two following topics:

```text
T1: A --- B
T2: A --- B --- C
```

For now `T2`is on top of `T1`. Now if new changes are added on `T1`, it becomes:

```text
T1: A --- B'
T2: A --- B --- C
```

`T2` is not on top of `T1` anymore, and simply rebasing it with git will bring you into trouble:

```text
T1: A --- B'
T2: A --- B' --- B --- C
```

As git sees `B` and `B'` as two different commits, you will end up with a lot of conflicts for nothing. That's why the
tool will always additionally compare the `Change-Id`s of the commits and exclude commits with identical ones from the
rebasing process. You then end up with:

```text
T1: A --- B'
T2: A --- B' --- C
```

Which is probably what you expected. Note however that if you had also added changes on `T2`, they will be lost in this
case.

## Uninstallation

To uninstall the tool, simply run:
```commandline
pip uninstall repolite
```

## Development status

The application is still being built. Therefore all functionalities may not be available / implemented yet.
