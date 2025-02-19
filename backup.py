from __future__ import print_function

import os
import re
import sys
import json
import errno
import argparse
import requests
import subprocess

if sys.version_info[0] < 3:
    import urlparse
else:
    from urllib import parse as urlparse

def get_json(url, token):
    while True:
        response = requests.get(url, headers={
            "Authorization": "token {0}".format(token)
        })
        response.raise_for_status()
        yield response.json()

        if "next" not in response.links:
            break
        url = response.links["next"]["url"]


def check_name(name):
    if not re.match(r"^\w[-\.\w]*$", name):
        raise RuntimeError("invalid name '{0}'".format(name))
    return name


def mkdir(path):
    try:
        os.makedirs(path, 0o770)
    except OSError as ose:
        if ose.errno != errno.EEXIST:
            raise
        return False
    return True


def mirror(repo_name, repo_url, to_path, username, token):
    parsed = urlparse.urlparse(repo_url)
    modified = list(parsed)
    modified[1] = "{username}:{token}@{netloc}".format(
        username=username,
        token=token,
        netloc=parsed.netloc
    )
    repo_url_with_token = urlparse.urlunparse(modified)

    repo_path = os.path.join(to_path, repo_name + ".git")

    try:
        # clone or fetch repo
        if mkdir(repo_path):
            print("cloning new repository: {path}".format(path=repo_path))
            subprocess.call(["git", "clone", "--mirror", repo_url_with_token], cwd=to_path)
        else:
            print("updating existing repository: {path}".format(path=repo_path))
            subprocess.call(["git", "remote", "set-url", "origin", repo_url_with_token], cwd=repo_path)
            subprocess.call(["git", "remote", "update", "--prune"], cwd=repo_path)

        # git lfs fetch
        subprocess.call(["git", "lfs", "fetch", "--all", "--prune"], cwd=repo_path)
    finally:
        # remove token from remote url
        subprocess.call(["git", "remote", "set-url", "origin", repo_url], cwd=repo_path)

        print("done")

def main():
    parser = argparse.ArgumentParser(description="Backup GitHub repositories")
    parser.add_argument("config", metavar="CONFIG", help="a configuration file")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = json.loads(f.read())

    token = config["token"]
    path = os.path.expanduser(config["directory"])
    if mkdir(path):
        print("Created directory {0}".format(path), file=sys.stderr)

    user = next(get_json("https://api.github.com/user", token))
    for page in get_json("https://api.github.com/user/repos", token):
        for repo in page:
            name = check_name(repo["name"])
            owner = check_name(repo["owner"]["login"])
            clone_url = repo["clone_url"]

            owner_path = os.path.join(path, owner)
            mkdir(owner_path)
            mirror(name, clone_url, owner_path, user["login"], token)


if __name__ == "__main__":
    main()
