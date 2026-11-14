"""Build the profile charts from public GitHub repositories and manifests."""

import argparse
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from detect import detect_technologies, is_manifest
from render import render_languages, render_primary_languages, render_technologies


API = "https://api.github.com"
LANGUAGES_SHOWN = 5
PRIMARY_LANGUAGES_SHOWN = 4
TECHNOLOGIES_SHOWN = 6


def github_json(path, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-repository-analytics",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(API + path, headers=headers), timeout=25) as response:
        return json.load(response)


def repositories(owner, token):
    page = 1
    while True:
        query = urlencode({"type": "owner", "per_page": 100, "page": page})
        batch = github_json(f"/users/{quote(owner, safe='')}/repos?{query}", token)
        for repo in batch:
            if (
                repo["owner"]["login"].casefold() == owner.casefold()
                and not (repo["private"] or repo["fork"] or repo["archived"] or repo["disabled"])
                and repo["name"].casefold() != owner.casefold()
            ):
                yield repo
        if len(batch) < 100:
            break
        page += 1


def inspect_repository(repo, token):
    name = repo["full_name"]
    prefix = f"/repos/{quote(name, safe='/')}"
    languages = github_json(f"{prefix}/languages", token)
    branch = quote(repo["default_branch"], safe="")
    try:
        tree = github_json(f"{prefix}/git/trees/{branch}?recursive=1", token)
    except HTTPError as error:
        if error.code == 409 and repo["size"] == 0 and not languages:
            return name, languages, set()
        raise
    if tree["truncated"]:
        raise ValueError(f"GitHub returned an incomplete file tree for {name}")

    manifests = {}
    for entry in tree["tree"]:
        if entry["type"] != "blob" or not is_manifest(entry["path"]):
            continue
        blob = github_json(f"{prefix}/git/blobs/{entry['sha']}", token)
        if blob["encoding"] != "base64":
            raise ValueError(f"Unsupported encoding in {name}/{entry['path']}")
        manifests[entry["path"]] = base64.b64decode(blob["content"]).decode("utf-8-sig", errors="replace")
    return name, languages, detect_technologies(manifests)


def ranked(counts):
    return sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))


def primary_language_rows(repos):
    counts = Counter(repo["language"] for repo in repos)
    undetected = counts.pop(None, 0)
    ordered = ranked(counts)
    rows = ordered[:PRIMARY_LANGUAGES_SHOWN]
    other = sum(count for _, count in ordered[PRIMARY_LANGUAGES_SHOWN:])
    if other:
        rows.append(("Other", other))
    if undetected:
        rows.append(("Undetected", undetected))
    return [(language, count / len(repos) * 100) for language, count in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN")
    repos = list(repositories(args.owner, token))
    if not repos:
        raise SystemExit("No public source repositories found")

    with ThreadPoolExecutor(max_workers=5) as pool:
        summary = list(pool.map(lambda repo: inspect_repository(repo, token), repos))

    languages = Counter()
    technologies = Counter()
    for _, language_bytes, detected in summary:
        languages.update(language_bytes)
        technologies.update(detected)
    total_bytes = languages.total()
    most_common = ranked(languages)
    language_rows = [(name, count / total_bytes * 100) for name, count in most_common[:LANGUAGES_SHOWN]]
    other = sum(count for _, count in most_common[LANGUAGES_SHOWN:])
    if other:
        language_rows.append(("Other", other / total_bytes * 100))
    primary_rows = primary_language_rows(repos)
    technology_rows = [
        (name, count / len(repos) * 100) for name, count in ranked(technologies)[:TECHNOLOGIES_SHOWN]
    ]

    measured_repos = sum(bool(language_bytes) for _, language_bytes, _ in summary)
    cards = {
        f"languages-icons.{locale}.svg": render_languages(language_rows, measured_repos, locale)
        for locale in ("en", "ru")
    }
    cards.update({
        f"primary-languages-icons.{locale}.svg": render_primary_languages(primary_rows, len(repos), locale)
        for locale in ("en", "ru")
    })
    cards.update({
        f"technologies-icons.{locale}.svg": render_technologies(technology_rows, len(repos), locale)
        for locale in ("en", "ru")
    })
    args.output.mkdir(parents=True, exist_ok=True)
    for name, svg in cards.items():
        (args.output / name).write_text(svg, encoding="utf-8")

    largest_repo, largest_bytes, _ = max(summary, key=lambda item: sum(item[1].values()))
    print(f"Scanned {len(repos)} repositories. {measured_repos} had detected code.")
    if total_bytes:
        print(f"Largest repository by detected code: {largest_repo} ({sum(largest_bytes.values()) / total_bytes:.1%})")
    print("Languages:", language_rows)
    print("Primary languages:", primary_rows)
    print("Technologies:", technology_rows)


if __name__ == "__main__":
    main()
