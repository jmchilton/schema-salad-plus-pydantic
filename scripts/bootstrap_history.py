#!/usr/bin/env python
"""Generate HISTORY.rst entries from GitHub merge commits / PRs."""
import os
import re
import subprocess
import sys
import textwrap
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

PROJECT_DIRECTORY = os.path.join(os.path.dirname(__file__), "..")
new_path = [PROJECT_DIRECTORY, os.path.join(PROJECT_DIRECTORY, "src")]
new_path.extend(sys.path[1:])
sys.path = new_path

import schema_salad_plus_pydantic as project  # noqa: E402

PROJECT_AUTHOR = project.PROJECT_AUTHOR
PROJECT_NAME = project.PROJECT_NAME
PROJECT_URL = f"https://github.com/{PROJECT_AUTHOR}/{PROJECT_NAME}"
PROJECT_API = f"https://api.github.com/repos/{PROJECT_AUTHOR}/{PROJECT_NAME}/"


def get_last_release_tag():
    version = project.__version__
    if ".dev" in version:
        version = version.split(".dev")[0]
    parts = version.split(".")
    if len(parts) >= 3:
        major, minor, patch = parts[:3]
        last_patch = max(0, int(patch) - 1)
        return f"{major}.{minor}.{last_patch}"
    return version


def get_merge_commits_since_tag(tag):
    try:
        result = subprocess.run(
            ["git", "log", "--merges", "--oneline", f"{tag}..HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        return []


def extract_pr_info_from_merge(merge_line):
    match = re.match(r"[a-f0-9]+\s+Merge pull request #(\d+) from ([^/]+)/", merge_line)
    if match:
        return match.group(1), match.group(2)
    return None, None


def generate_acknowledgements():
    tag = get_last_release_tag()
    merge_commits = get_merge_commits_since_tag(tag)
    acknowledgements = []
    for merge in merge_commits:
        if not merge.strip():
            continue
        pr_number, author = extract_pr_info_from_merge(merge)
        if pr_number and author and requests:
            try:
                api_url = urljoin(PROJECT_API, f"pulls/{pr_number}")
                req = requests.get(api_url).json()
                title = req.get("title", "").rstrip(".")
                login = req["user"]["login"]
                ack_line = f"* {title} (thanks to `@{login}`_). `Pull Request {pr_number}`_"
                acknowledgements.append(ack_line)
                github_link = f".. _Pull Request {pr_number}: {PROJECT_URL}/pull/{pr_number}"
                acknowledgements.append(github_link)
            except Exception as e:
                print(f"Error processing PR {pr_number}: {e}", file=sys.stderr)
    return acknowledgements


def main(argv):
    history_path = os.path.join(PROJECT_DIRECTORY, "HISTORY.rst")
    with open(history_path, encoding="utf-8") as fh:
        history = fh.read()

    def extend(from_str, line):
        from_str += "\n"
        return history.replace(from_str, from_str + line + "\n")

    if len(argv) > 1 and argv[1] == "--acknowledgements":
        acknowledgements = generate_acknowledgements()
        if acknowledgements:
            current_version = project.__version__
            unreleased_marker = f"---------------------\n{current_version}\n---------------------"
            for ack in acknowledgements:
                if ack.startswith("*"):
                    print(ack)
                    history = extend(unreleased_marker, ack)
                elif ack.startswith(".."):
                    print(ack)
                    history = extend(".. github_links", ack)
            with open(history_path, "w", encoding="utf-8") as fh:
                fh.write(history)
        else:
            print("No merge commits found since last release.")
        return

    if len(argv) < 2:
        print("Usage: bootstrap_history.py <identifier> [message]")
        print("   or: bootstrap_history.py --acknowledgements")
        return

    ident = argv[1]
    message = ""
    if len(argv) > 2:
        message = argv[2]
    elif not (ident.startswith("pr") or ident.startswith("issue")):
        if requests:
            api_url = urljoin(PROJECT_API, "commits/%s" % ident)
            req = requests.get(api_url).json()
            message = req["commit"]["message"].split("\n")[0]
    elif requests and ident.startswith("pr"):
        pull_request = ident[len("pr"):]
        api_url = urljoin(PROJECT_API, "pulls/%s" % pull_request)
        req = requests.get(api_url).json()
        message = req["title"].rstrip(".") + f" (thanks to `@{req['user']['login']}`_)."
    elif requests and ident.startswith("issue"):
        issue = ident[len("issue"):]
        api_url = urljoin(PROJECT_API, "issues/%s" % issue)
        req = requests.get(api_url).json()
        message = req["title"]

    to_doc = message + " "
    if ident.startswith("pr"):
        pull_request = ident[len("pr"):]
        history = extend(".. github_links", ".. _Pull Request {0}: {1}/pull/{0}".format(pull_request, PROJECT_URL))
        to_doc += f"`Pull Request {pull_request}`_"
    elif ident.startswith("issue"):
        issue = ident[len("issue"):]
        history = extend(".. github_links", ".. _Issue {0}: {1}/issues/{0}".format(issue, PROJECT_URL))
        to_doc += f"`Issue {issue}`_"
    else:
        short_rev = ident[:7]
        history = extend(".. github_links", ".. _{0}: {1}/commit/{0}".format(short_rev, PROJECT_URL))
        to_doc += f"{short_rev}_"

    wrapper = textwrap.TextWrapper(initial_indent="* ", subsequent_indent="  ", width=78)
    to_doc = "\n".join(wrapper.wrap(to_doc))
    history = extend(".. to_doc", to_doc)
    with open(history_path, "w", encoding="utf-8") as fh:
        fh.write(history)


if __name__ == "__main__":
    main(sys.argv)
