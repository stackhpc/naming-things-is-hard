#!/usr/bin/env python3

"""
Proposes a list of downstream patches to cherry pick for a new release
branch. The list is generated based on the downstream patches in a previous
release, and accounts for patches that have been merged into the new
release. It also looks for newer versions of a patch on later branches.

TODO:
* Fall back to find patches by title, in case the change ID was changed
* Fail if branch is considerably out of sync with upstream?
"""

import argparse
import os
import subprocess
import sys


DEFAULT_RELEASE = os.environ.get("DEFAULT_RELEASE", "xena")
STABLE_PREFIX = "stable/"

# Commit message parsing.
COMMIT_ID = "commit "
AUTHOR = "Author:"
CHANGE_ID = "    Change-Id: I"
TITLE = "    "


def rev_parse(ref):
    cmd = ["git", "rev-parse", ref]
    output = subprocess.check_output(cmd)
    return output.decode(encoding=sys.stdout.encoding).strip()


def fetch(remote):
    print("Fetching from", remote)
    cmd = ["git", "fetch", remote]
    output = subprocess.check_output(cmd)
    return output.decode(encoding=sys.stdout.encoding).strip()


def list_branches_on_remote(remote):
    print("Listing branches on remote %s" % remote)
    cmd = ["git", "branch", "-r"]
    output = subprocess.check_output(cmd)
    all_branches = output.decode(encoding=sys.stdout.encoding).strip()
    remote_branches = []
    for branch in all_branches.splitlines():
        branch = branch.strip()
        prefix = "%s/" % remote
        if branch.startswith(prefix):
            remote_branches.append(branch[len(prefix):])
    return remote_branches


def log_difference(ref1, ref2):
    print("Comparing %s and %s" % (ref1, ref2))
    cmd = ["git", "log", "%s..%s" % (ref2, ref1), "--no-merges"]
    output = subprocess.check_output(cmd)
    return output.decode(encoding=sys.stdout.encoding).strip()


def list_commits(ref1, ref2):
    """List commits in history of ref1 but not ref2.

    Parse git log output. Example:

    commit 6c72fa811739573c502240d9ee93bf1823d20447
    Author: Will Szumski <will@stackhpc.com>
    Date:   Thu Jul 29 10:53:24 2021 +0000

        Support multiple inventories

        Multiple inventories can now be passed to `kolla-ansible`.  This can be
        useful to construct a common inventory that is shared between multiple
        environments.

        Change-Id: I2ac5d7851b310bea2ba362b353f18c592a0a6a2e

    Returns a list of dicts describing commits, each with the following fields:

    * sha1: Commit sha1 hash
    * title: Commit title
    * change_id: Gerrit Change-ID
    * bot: whether the commit was created by the StackHPC CI bot
    """
    difference = log_difference(ref1, ref2)
    commits = []
    sha1, title, change_id, bot = None, None, None, False
    for line in difference.splitlines():
        if line.startswith(COMMIT_ID):
            if sha1:
                previous = {
                    "sha1": sha1,
                    "title": title,
                    "change_id": change_id,
                    "bot": bot
                }
                commits.append(previous)
            sha1 = line.split()[1]
            title = None
            change_id = None
            bot = False
        elif line.startswith(AUTHOR):
            if line.split()[1] == "stackhpc-ci":
                bot = True
        elif line.startswith(CHANGE_ID):
            change_id = "I%s" % line[len(CHANGE_ID):]
        elif line.startswith(TITLE) and not title:
            title = line[len(TITLE):]
    if sha1:
        previous = {
            "sha1": sha1,
            "title": title,
            "change_id": change_id,
            "bot": bot
        }
        commits.append(previous)
    return commits


def find_commit(commits, commit):
    """Find a commit by change ID."""
    for _commit in commits:
        if _commit["change_id"] == commit["change_id"]:
            return _commit


def cherry_pop(candidates, release, previous_release, new_branch_commits, later_branch_commits):
    """Run the analysis, display results and a list of proposed cherry picks."""
    cherries = []
    for candidate in candidates:
        print("[%s] %s %s %s" % (previous_release, candidate["sha1"][:10], candidate["change_id"], candidate["title"]))
        print()

        if candidate["bot"]:
            # Commit was created by a bot.
            print("  SKIP: created by stackhpc-ci bot")
        elif not candidate["change_id"]:
            # Commit does not have a Gerrit Change-Id. Cannot track it across
            # branches.
            print("  KEEP: No change ID")
            cherries.append(candidate)
        else:
            new_branch_commit = find_commit(new_branch_commits, candidate)
            if new_branch_commit:
                # Commit is present on the new branch.
                print("  SKIP: present on %s" % release)
            else:
                options = []
                last_sha1 = None
                for later_branch_commit in later_branch_commits:
                    later_commit = find_commit(later_branch_commit["commits"], candidate)
                    if later_commit:
                        if later_commit["sha1"] == last_sha1:
                            break
                        options.append({"branch": later_branch_commit["branch"], "commit": later_commit})
                        last_sha1 = later_commit["sha1"]

                if options:
                    # Commit is present on multiple later branches. Cherry pick from one.
                    print("  CHOICE: present on multiple branches")
                    print()
                    for option in options:
                        print("    [%s] %s" % (option["branch"], option["commit"]["sha1"][:10]))
                    cherries.append(options[0]["commit"])
                else:
                    # Use original commit.
                    cherries.append(candidate)
                    print("  KEEP: Use original commit")
        print()

    print("Proposed cherries:")
    for cherry in reversed(cherries):
        print("git cherry-pick -x %s  # %s" % (cherry["sha1"][:10], cherry["title"]))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--branch-prefix", default="stackhpc",
                        help="Name of the prefix to apply to downstream "
                             "branches. Default is 'stackhpc'")
    parser.add_argument("-d", "--downstream-remote", default="stackhpc",
                        help="Name of the downstream git remote. Default is "
                             "'stackhpc'")
    parser.add_argument("-p", "--previous-release",
                        help="Name of the previous OpenStack release. "
                             "Default is determined automatically from --release")
    parser.add_argument("-r", "--release", default=DEFAULT_RELEASE,
                        help="Name of the OpenStack release. "
                             "Default is '{}'".format(DEFAULT_RELEASE))
    parser.add_argument("-u", "--upstream-remote", default="origin",
                        help="Name of the upstream git remote. Default is "
                             "'origin'")
    return parser.parse_args()


def main():
    parsed_args = parse_args()
    branch_prefix = parsed_args.branch_prefix
    previous_release = parsed_args.previous_release
    release = parsed_args.release
    upstream_remote = parsed_args.upstream_remote
    downstream_remote = parsed_args.downstream_remote

    fetch(upstream_remote)
    fetch(downstream_remote)

    upstream_branches = list_branches_on_remote(upstream_remote)
    upstream_branches.sort()

    release_index = upstream_branches.index("%s%s" % (STABLE_PREFIX, release))

    if not previous_release:
        previous_upstream_branch = upstream_branches[release_index - 1]
        previous_release = previous_upstream_branch[len(STABLE_PREFIX):]

    upstream_branch = "stable/{}".format(previous_release)
    upstream_ref = rev_parse("{}/{}".format(upstream_remote, upstream_branch))

    later_branches = []
    for branch in upstream_branches[release_index + 1:]:
        if branch.startswith(STABLE_PREFIX):
            later_branches.append(branch)
    later_branches.append("master")

    previous_branch = "{}/{}".format(branch_prefix, previous_release)
    previous_ref = rev_parse("{}/{}".format(downstream_remote, previous_branch))

    new_branch = "{}/{}".format(branch_prefix, release)
    new_ref = rev_parse("{}/{}".format(downstream_remote, new_branch))

    # Downstream patches on previous branch.
    candidates = list_commits(previous_ref, upstream_ref)

    # Upstream commits on new branch that are not on previous branch.
    new_branch_commits = list_commits(new_ref, previous_ref)

    # Upstream commits on later branches that are not on previous branch.
    later_branch_commits = [
        {
            "branch": branch,
            "commits": list_commits(rev_parse("{}/{}".format(upstream_remote, branch)),
                                    previous_ref)
        }
        for branch in later_branches
    ]

    cherry_pop(candidates, release, previous_release, new_branch_commits, later_branch_commits)


if __name__ == "__main__":
    main()
