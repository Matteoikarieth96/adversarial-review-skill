#!/usr/bin/env python3
"""Read-only snapshot of a deliverable for an adversarial review.

Copies a file or folder into DEST without secrets, caches or symlinks that
leave the folder, redacts secret-looking values in what it copied, optionally
saves what a session changed in a git repo, makes the copy read only, and
prints a manifest (markdown) for the review brief. Stdlib only, Python 3.9+.

    python3 -I snapshot.py SRC DEST [--session-work] [--git-base COMMIT] [--diff-out PATH]

Git is run only with --session-work (work produced in the session asking for
the review) and always with repo hooks, fsmonitor, external diff, textconv,
filter drivers and submodules turned off, because a repo's own .git/config
can make git run programs.
"""
import argparse
import fnmatch
import os
import re
import shutil
import stat
import subprocess
import sys

CACHE_DIRS = [".git", "node_modules", ".venv", "venv", "__pycache__",
              ".pytest_cache", ".mypy_cache", ".DS_Store"]
SECRET_NAMES = [
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore",
    "*.jks", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*", "deploy_key*",
    ".npmrc", ".netrc", ".pypirc", ".git-credentials", "credentials",
    "credentials.*", "*credentials*.json", "service-account*.json",
    "token.json", "secrets.*", "*secrets*.yml", "*secrets*.yaml",
    "settings.local.json",
]
SECRET_DIRS = [".aws", ".ssh", ".gnupg", ".docker"]
KEEP_NAMES = [".env.example", ".env.sample", ".env.template"]

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
]
ASSIGNMENT = re.compile(
    r"(?i)((?:api[_-]?key|secret|token|passw(?:or)?d|private[_-]?key|access[_-]?key)"
    r"[A-Za-z0-9_]*[\"']?\s*[:=]\s*[\"']?)([^\s\"',;]{8,})")
MAX_SCAN_BYTES = 2_000_000


def is_secret_name(name):
    if name in KEEP_NAMES:
        return False
    return any(fnmatch.fnmatch(name, p) for p in SECRET_NAMES)


def mask(value):
    return "REDACTED(" + value[:4] + "...)"


def redact_text(text):
    """Return (new_text, number_of_redactions)."""
    count = 0

    def sub_whole(m):
        nonlocal count
        count += 1
        return mask(m.group(0))

    for pat in SECRET_PATTERNS:
        text = pat.sub(sub_whole, text)

    def sub_value(m):
        nonlocal count
        if m.group(2).startswith("REDACTED("):
            return m.group(0)
        count += 1
        return m.group(1) + mask(m.group(2))

    text = ASSIGNMENT.sub(sub_value, text)
    return text, count


def list_symlinks(src):
    """Every symlink under src, with its target and whether it stays inside."""
    out = []
    root = os.path.realpath(src)
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                target = os.readlink(path)
                resolved = os.path.realpath(path)
                inside = (not os.path.isabs(target)) and (
                    resolved == root or resolved.startswith(root + os.sep))
                out.append((os.path.relpath(path, src), target, inside))
    return out


def copy_tree(src, dest):
    """Copy src into dest with rsync, keeping only symlinks that stay inside."""
    cmd = ["rsync", "-a", "--safe-links"]
    for k in KEEP_NAMES:  # first match wins, so the keeps go before the excludes
        cmd += ["--include", k]
    for p in CACHE_DIRS + SECRET_NAMES:
        cmd += ["--exclude", p]
    for d in SECRET_DIRS:
        cmd += ["--exclude", d + "/"]
    cmd += [src.rstrip(os.sep) + os.sep, dest.rstrip(os.sep) + os.sep]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def excluded_files(src):
    """Secret files and folders present in src (names only)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in CACHE_DIRS]
        for d in list(dirnames):
            if d in SECRET_DIRS:
                out.append(os.path.relpath(os.path.join(dirpath, d), src) + "/")
                dirnames.remove(d)
        for f in filenames:
            if is_secret_name(f):
                out.append(os.path.relpath(os.path.join(dirpath, f), src))
    return sorted(out)


def redact_file(path, root):
    """Redact one copied text file in place. Returns [(relpath, n)] or []."""
    if os.path.islink(path) or os.path.getsize(path) > MAX_SCAN_BYTES:
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (UnicodeDecodeError, OSError):
        return []
    new, n = redact_text(text)
    if not n:
        return []
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    return [(os.path.relpath(path, root), n)]


def redact_tree(root):
    """Redact secret-looking values in every copied text file under root."""
    hits = []
    for dirpath, _dirs, filenames in os.walk(root, followlinks=False):
        for f in filenames:
            hits += redact_file(os.path.join(dirpath, f), root)
    return hits


class UnsafeRepo(Exception):
    """The repo config is set up in a way git cannot be told to ignore."""


def filter_drivers(config_names):
    """Driver names of every filter.<driver>.<key> in `git config -z --name-only --list`."""
    drivers = set()
    for name in config_names.split("\0"):
        if name.lower().startswith("filter.") and name.count(".") >= 2:
            drv = name[len("filter."):name.rindex(".")]
            if "=" in drv or not drv:
                # `-c key=value` splits at the first "=", so this one cannot be overridden
                raise UnsafeRepo("a filter driver name git cannot override: %r" % drv)
            drivers.add(drv)
    return sorted(drivers)


def safe_git(src, *args):
    """Run git in src with repo-configured programs turned off.

    A clean or process filter (.gitattributes plus filter.<driver> in the
    config) runs on `git status` and `git diff`, so every driver the config
    defines is overridden with an empty command. Reading the config list
    itself runs nothing.
    """
    base = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
            "-c", "core.pager=cat", "-c", "diff.external=", "-C", src, "--no-pager"]
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_TERMINAL_PROMPT": "0", "HOME": os.environ.get("HOME", "/tmp")}
    names = subprocess.run(base + ["config", "-z", "--name-only", "--list"], check=True,
                           capture_output=True, text=True, env=env).stdout
    off = []
    for drv in filter_drivers(names):
        for key, value in (("clean", ""), ("smudge", ""), ("process", ""), ("required", "false")):
            off += ["-c", "filter.%s.%s=%s" % (drv, key, value)]
    cmd = base[:1] + off + base[1:] + list(args)
    return subprocess.run(cmd, check=True, capture_output=True, text=True, env=env).stdout


def git_changes(src, dest, a):
    """Save what the session changed in src as a redacted diff. Returns the manifest line."""
    if not a.session_work:
        return "- git: not run (work not produced in this session; a repo's own config can run programs)"
    if not os.path.isdir(os.path.join(src, ".git")):
        return "- git: no .git folder, no diff"
    base = a.git_base or "HEAD"
    excludes = [":(exclude,glob)**/" + p for p in SECRET_NAMES]
    excludes += [":(exclude,glob)**/" + d + "/**" for d in SECRET_DIRS]
    try:
        diff = safe_git(src, "diff", "--no-ext-diff", "--no-textconv",
                        "--ignore-submodules=all", base, "--", ".", *excludes)
        status = safe_git(src, "status", "--short", "--untracked-files=all",
                          "--ignore-submodules=all")
    except UnsafeRepo as e:
        return "- git: not run (%s)" % e
    diff, n = redact_text(diff)
    out = a.diff_out or os.path.join(os.path.dirname(dest), "changes.diff")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("# git status --short\n" + status + "\n# git diff " + base +
                 " (secrets excluded and redacted)\n" + diff)
    os.chmod(out, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return "- git: diff since `%s` saved to `%s` (%d values redacted)" % (base, out, n)


def make_read_only(path):
    for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
        for f in filenames:
            p = os.path.join(dirpath, f)
            if not os.path.islink(p):
                os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        os.chmod(dirpath, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
                 | stat.S_IROTH | stat.S_IXOTH)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("dest", help="target folder to create, e.g. $WS/input/target")
    ap.add_argument("--session-work", action="store_true",
                    help="the work was produced in the session asking for the review")
    ap.add_argument("--git-base", help="commit the task started from (needs --session-work)")
    ap.add_argument("--diff-out", help="where to save the redacted diff, e.g. $WS/input/changes.diff")
    a = ap.parse_args(argv)

    src = os.path.realpath(a.src)
    dest = os.path.realpath(a.dest)  # realpath on both sides: /var is a link on macOS
    if not os.path.exists(src):
        sys.exit("snapshot: source not found: " + a.src)
    if dest == src or dest.startswith(src + os.sep):
        sys.exit("snapshot: destination must not be inside the source")
    name = os.path.basename(src)
    copy = os.path.join(dest, name)
    if os.path.lexists(copy):
        sys.exit("snapshot: already exists, pick another destination: " + copy)
    os.makedirs(dest, exist_ok=True)

    lines = ["### Snapshot", "", "- source: `%s`" % src]
    if os.path.isfile(src):
        if is_secret_name(name):
            sys.exit("snapshot: refusing to copy a secret file: " + name)
        shutil.copy2(src, copy)
        links, skipped = [], []
    else:
        copy_tree(src, copy)
        links = list_symlinks(src)
        skipped = excluded_files(src)
    lines.append("- copied to: `%s`" % copy)

    hits = redact_tree(copy) if os.path.isdir(copy) else redact_file(copy, dest)
    outside = [l for l in links if not l[2]]
    lines.append("- symlinks: %d found, %d pointing outside were skipped" % (len(links), len(outside)))
    for rel, target, _ in outside:
        lines.append("  - `%s` -> `%s` (skipped)" % (rel, target))
    lines.append("- secret files left out (names only): %s" % (", ".join("`%s`" % s for s in skipped) or "none"))
    lines.append("- secret-looking values redacted: %s" % (
        ", ".join("`%s` (%d)" % h for h in hits) or "none"))

    if a.git_base or a.diff_out:
        lines.append(git_changes(src, dest, a))

    if os.path.isdir(copy):
        make_read_only(copy)
    else:
        os.chmod(copy, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    lines.append("- the copy is read only; reviewers copy it to their scratch and `chmod -R u+w` the copy")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
