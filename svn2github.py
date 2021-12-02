#!/usr/bin/env python3

import subprocess
import re
import collections
import os
import tempfile
import shutil
import sys
import argparse
import xdg
import inspect


class Svn2GithubException(Exception):
    pass


GitSvnInfo = collections.namedtuple('GitSvnInfo', 'svn_url svn_revision svn_uuid')


def debug(*args, **kwargs):
    print(*args, **kwargs)


run_kwargs_default = {
    'check': True,
    'stdin': subprocess.DEVNULL,
    'stdout': subprocess.PIPE
}


popen_kwargs_default = {
    'stdin': subprocess.DEVNULL,
    'stdout': subprocess.PIPE
}


def popen(*args, **kwargs):
    if 'cwd' in kwargs:
        debug("run: ( cd " + kwargs['cwd'] + " && " + " ".join(args[0]) + " )")
    else:
        debug("run: " + " ".join(args[0]))
    kwargs = {**popen_kwargs_default, **kwargs}
    return subprocess.Popen(*args, **kwargs)


def run(*args, **kwargs):
    if 'cwd' in kwargs:
        debug("run: ( cd " + kwargs['cwd'] + " && " + " ".join(args[0]) + " )")
    else:
        debug("run: " + " ".join(args[0]))
    kwargs = {**run_kwargs_default, **kwargs}
    return subprocess.run(*args, **kwargs)


def get_last_revision_from_svn(svn_url):
    args = ["svn", "info", svn_url, "--no-newline", "--show-item", "revision"]
    result = run(args)
    rev = int (result.stdout.decode().strip())
    if rev:
        return rev

    return Svn2GithubException("svn info {} output did not specify the current revision".format(svn_url))


def run_git_cmd(args, git_dir):
    args = ["git"] + args
    return run(args, cwd=git_dir)


def is_repo_empty(git_dir):
    args = ["ls", ".git/refs/heads"]
    result = run(args, cwd=git_dir)
    return len(result.stdout) == 0


def get_svn_info_from_git(git_dir):
    result = run_git_cmd(["log", "-1", "HEAD", "--pretty=%B"], git_dir=git_dir)

    pattern = re.compile("^git-svn-id: (.*)@([0-9]+) ([0-9a-f-]{36})$".encode())

    for line in result.stdout.split("\n".encode()):
        m = pattern.match(line)
        if m:
             return GitSvnInfo(svn_url=m.group(1), svn_revision=int(m.group(2)), svn_uuid=m.group(3))

    return Svn2GithubException("git log -1 HEAD --pretty=%B output did not specify the current revision")


def git_svn_init(git_svn_info, git_dir):
    if git_svn_info.svn_uuid:
        rewrite_uuid = ["--rewrite-uuid", git_svn_info.svn_uuid]
    else:
        rewrite_uuid = []
    run_git_cmd(["svn", "init"] + rewrite_uuid + [git_svn_info.svn_url], git_dir)


def git_svn_rebase(git_dir):
    run_git_cmd(["svn", "rebase"], git_dir)


def git_svn_fetch(git_dir):
    args = ["git", "svn", "fetch"]
    print("run: ( cd "+git_dir+" && "+" ".join(args)+" )")
    cmd = popen(args, cwd=git_dir, universal_newlines=True)

    pattern = re.compile("^r([0-9]+) = [0-9a-f]{40}")

    while True:
        line = cmd.stdout.readline()
        if not line:
            break
        m = pattern.match(line)
        if m:
            yield int(m.group(1))


def git_clone(git_src, git_dir):
    os.makedirs(git_dir, exist_ok=False)
    run_git_cmd(["clone", git_src, "."], git_dir)


def git_push(git_dir):
    run_git_cmd(["push", "origin", "master"], git_dir)


def unpack_cache(cache_path, git_dir):
    dot_git_dir = os.path.join(git_dir, ".git")
    os.makedirs(dot_git_dir, exist_ok=False)
    args = ["tar", "-xf", cache_path]
    
    run(args, cwd=dot_git_dir) # , stdout=subprocess.DEVNULL
    run_git_cmd(["config", "core.bare", "false"], git_dir)
    run_git_cmd(["checkout", "."], git_dir)


def save_cache(cache_path, tmp_path, git_dir):
    dot_git_dir = os.path.join(git_dir, ".git")
    args = ["tar", "-cf", tmp_path, "."]
    
    run(args, cwd=dot_git_dir) # , stdout=subprocess.DEVNULL
    shutil.copyfile(tmp_path, cache_path)


def sync_github_mirror(github_repo, cache_dir, new_svn_url=None):
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "cache." + github_repo.replace("/", ".") + ".tar")
        cached = os.path.exists(cache_path)
    else:
        cached = False

    github_url = "git@github.com:" + github_repo + ".git"

    with tempfile.TemporaryDirectory(prefix="svn2github-") as tmp_dir:
        git_dir = os.path.join(tmp_dir, "repo")
        if cached and not new_svn_url:
            print("Using cached Git repository from " + cache_path)
            unpack_cache(cache_path, git_dir)
        else:
            print("Cloning " + github_url)
            git_clone(github_url, git_dir)

        if new_svn_url:
            if not is_repo_empty(git_dir):
                raise Svn2GithubException("Specifed new_svn_url, but the destination repo is not empty")
            git_svn_info = GitSvnInfo(svn_url=new_svn_url, svn_revision=0, svn_uuid=None)
        else:
            git_svn_info = get_svn_info_from_git(git_dir)

        print("Checking for SVN updates")
        upstream_revision = get_last_revision_from_svn(git_svn_info.svn_url)

        print("Last upstream revision: " + str(upstream_revision))
        print("Last mirrored revision: " + str(git_svn_info.svn_revision))
        if upstream_revision == git_svn_info.svn_revision:
            print("Everything up to date. Bye!")
            return

        print("Fetching from SVN")
        if not cached or new_svn_url:
            git_svn_init(git_svn_info, git_dir)

        for rev in git_svn_fetch(git_dir):
            print("Fetching from SVN, revision {}/{}".format(rev, upstream_revision))
        print()

        print("Rebasing SVN changes")
        git_svn_rebase(git_dir)

        print("Pushing to GitHub")
        git_push(git_dir)

        if cache_dir:
            print("Saving Git directory to cache")
            save_cache(cache_path, os.path.join(tmp_dir, "cache.tar"), git_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Mirror SVN repositories to GitHub",
        formatter_class=argparse.RawTextHelpFormatter
    )
    default_cache_dir = xdg.xdg_cache_home() / "svn2github"
    parser.add_argument(
        "--cache-dir",
        help=inspect.cleandoc(f"""
            Directory to keep the cached data,
            to avoid re-downloading all SVN and Git history each time.
            Default: {default_cache_dir}
        """),
        default=default_cache_dir
    )
    subparsers = parser.add_subparsers()

    subparser_import = subparsers.add_parser("import", help="Import SVN repository to the GitHub repo")
    subparser_import.add_argument("github_repo", metavar="GITHUB_REPO", help="GitHub repo in format: user/name")
    subparser_import.add_argument("svn_url", metavar="SVN_URL", help="SVN repository to import")

    subparser_update = subparsers.add_parser("update", help="Update the GitHub repository from SVN")
    subparser_update.add_argument("github_repo", metavar="GITHUB_REPO", help="GitHub repo in format: user/name")
    args = parser.parse_args(sys.argv[1:] or ["--help"])

    new_svn_url = args.svn_url if "svn_url" in args else None
    sync_github_mirror(args.github_repo, args.cache_dir, new_svn_url=new_svn_url)



if __name__ == "__main__":
    main()
