#!/usr/bin/env python3
"""Read-only snapshot of a deliverable for an adversarial review.

Copies a file or folder into DEST without secrets, caches, special files or
symlinks that leave the folder, redacts secret-looking values in what it
copied, optionally saves what a session changed in a git repo, makes the copy
read only, and prints a manifest (markdown) for the review brief. Standard
library only, Python 3.9+; the only external program is git.

    python3 -I snapshot.py SRC DEST [--session-work] [--git-base COMMIT] [--diff-out PATH]

Every name and link target printed in the manifest is escaped: they come from
the deliverable and could otherwise forge lines of the brief.

Git is run only with --session-work (work produced in the session asking for
the review), only on a plain .git folder inside SRC, and always with repo
hooks, fsmonitor, external diff, textconv, filter drivers, submodules and
optional locks turned off, because a repo's own .git/config can make git run
programs or read other folders.
"""
import argparse
import fnmatch
import os
import re
import stat
import subprocess
import sys
import unicodedata

CACHE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
              ".pytest_cache", ".mypy_cache"}
JUNK_FILES = {".ds_store"}
SECRET_NAMES = [
    ".env", ".env.*", "*.env", ".envrc", "*.pem", "*.key", "*.p12", "*.pfx",
    "*.p8", "*.keystore", "*.jks", "*.ppk", "*.asc", "*.kdbx", "id_rsa*",
    "id_dsa*", "id_ecdsa*", "id_ed25519*", "deploy_key*", ".npmrc", ".netrc",
    ".pypirc", ".pgpass", ".htpasswd", ".git-credentials", "credentials",
    "credentials.*", "*credentials*.json", "service-account*.json",
    "token.json", "secrets.*", "*secrets*.yml", "*secrets*.yaml",
    "settings.local.json", "*.tfvars", "*.tfstate", "*.tfstate.*",
]
SECRET_DIRS = {".aws", ".ssh", ".gnupg", ".docker", ".kube"}
KEEP_NAMES = {".env.example", ".env.sample", ".env.template"}

# Whole match masked; the first 4 characters (a type prefix such as "ghp_") stay.
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]*?"
               r"(?:-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\Z)"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bpypi-[A-Za-z0-9_-]{50,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*"),
]
KEYS = (r"(?:api[_-]?key|secret|token|passw(?:or)?d|private[_-]?key|access[_-]?key)"
        r"[A-Za-z0-9_]*")
# Value masked in full; the key and the quotes stay.
ASSIGN_QUOTED = re.compile(r"(?i)(" + KEYS + r"[\"']?\s*[:=]\s*)([\"'])([^\"'\r\n]{8,})\2")
ASSIGN_BARE = re.compile(r"(?i)(" + KEYS + r"[\"']?\s*[:=]\s*)([^\s\"'`,;()\[\]{}<>]{8,})")
URL_CREDENTIALS = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^\s:/@]+:)([^\s@/]+)(@)")
DOTTED_NAME = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")

MAX_COPY_BYTES = 50_000_000   # bigger files are not copied
MAX_SCAN_BYTES = 20_000_000   # bigger files are copied but not redacted (listed)
MAX_LISTED = 20


class UnsafeRepo(Exception):
    """The repo is set up in a way git cannot be told to ignore."""


def q(text, limit=200):
    """Escape a name for the manifest: no control characters, no backticks."""
    out = []
    for ch in text[:limit]:
        o = ord(ch)
        if ch in "`\\":
            out.append("\\x%02x" % o)
        elif o < 0x20 or o == 0x7f or unicodedata.category(ch) in (
                "Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
            out.append("\\u%04x" % o if o > 0xff else "\\x%02x" % o)
        else:
            out.append(ch)
    if len(text) > limit:
        out.append("...")
    return "`" + "".join(out) + "`"


def q_list(items):
    shown = [q(i) for i in items[:MAX_LISTED]]
    if len(items) > MAX_LISTED:
        shown.append("and %d more" % (len(items) - MAX_LISTED))
    return ", ".join(shown) or "none"


def is_secret_name(name):
    low = name.lower()
    if low in KEEP_NAMES:
        return False
    return any(fnmatch.fnmatchcase(low, p) for p in SECRET_NAMES)


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

    def sub_quoted(m):
        nonlocal count
        if m.group(3).startswith("REDACTED("):
            return m.group(0)
        count += 1
        return m.group(1) + m.group(2) + "REDACTED" + m.group(2)

    def sub_bare(m):
        nonlocal count
        value = m.group(2)
        nxt = m.string[m.end():m.end() + 1]
        # code, not a literal: a call, a subscript, or a dotted name
        if value.startswith("REDACTED(") or nxt in ("(", "[") or DOTTED_NAME.fullmatch(value):
            return m.group(0)
        count += 1
        return m.group(1) + "REDACTED"

    def sub_url(m):
        nonlocal count
        count += 1
        return m.group(1) + "REDACTED" + m.group(3)

    text = ASSIGN_QUOTED.sub(sub_quoted, text)
    text = ASSIGN_BARE.sub(sub_bare, text)
    text = URL_CREDENTIALS.sub(sub_url, text)
    return text, count


class Result:
    def __init__(self):
        self.secrets = []        # secret files and folders left out
        self.links_kept = []     # (relpath, target)
        self.links_skipped = []  # (relpath, target)
        self.special = []        # FIFOs, sockets, devices: not copied
        self.too_big = []        # over MAX_COPY_BYTES: not copied
        self.redacted = []       # (relpath, n)
        self.not_scanned = []    # (relpath, reason): copied but not redacted


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


def copy_regular(path, out):
    """Copy one regular file without following links. False if it changed under us."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return False
    with os.fdopen(fd, "rb") as src:
        if not stat.S_ISREG(os.fstat(src.fileno()).st_mode):
            return False
        wfd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(wfd, "wb") as dst:
            left = MAX_COPY_BYTES + 1
            while left > 0:
                chunk = src.read(min(1 << 20, left))
                if not chunk:
                    break
                dst.write(chunk)
                left -= len(chunk)
    if left <= 0:  # grew past the limit while copying
        os.unlink(out)
        return None
    return True


def copy_entry(root, path, out, rel, res):
    st = os.lstat(path)
    name = os.path.basename(path)
    if stat.S_ISLNK(st.st_mode):
        target = os.readlink(path)
        if not os.path.isabs(target) and inside(os.path.realpath(path), root):
            os.symlink(target, out)
            res.links_kept.append((rel, target))
        else:
            res.links_skipped.append((rel, target))
        return
    if name.lower() in JUNK_FILES:
        return
    if is_secret_name(name):
        res.secrets.append(rel)
        return
    if not stat.S_ISREG(st.st_mode):
        res.special.append(rel)
        return
    if st.st_size > MAX_COPY_BYTES:
        res.too_big.append(rel)
        return
    done = copy_regular(path, out)
    if done is None:
        res.too_big.append(rel)
    elif not done:
        res.special.append(rel)


def copy_tree(src, dest, res):
    """Copy src into the new folder dest. src must be a real path."""
    os.mkdir(dest, 0o700)
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        rel_dir = os.path.relpath(dirpath, src)
        out_dir = dest if rel_dir == "." else os.path.join(dest, rel_dir)
        keep = []
        for d in sorted(dirnames):
            rel = os.path.normpath(os.path.join(rel_dir, d))
            if os.path.islink(os.path.join(dirpath, d)):
                filenames.append(d)  # a link to a folder is handled as a link
            elif d.lower() in CACHE_DIRS:
                continue
            elif d.lower() in SECRET_DIRS:
                res.secrets.append(rel + "/")
            else:
                os.mkdir(os.path.join(out_dir, d), 0o700)
                keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            copy_entry(src, os.path.join(dirpath, f), os.path.join(out_dir, f),
                       os.path.normpath(os.path.join(rel_dir, f)), res)
    # A kept link can still leave the copy when something it went through was
    # left out: check every link again in the copy itself.
    root = os.path.realpath(dest)
    for rel, target in list(res.links_kept):
        link = os.path.join(dest, rel)
        if not inside(os.path.realpath(link), root):
            os.unlink(link)
            res.links_kept.remove((rel, target))
            res.links_skipped.append((rel, target))


def read_for_scan(path):
    """(text, encoding) or (None, reason). Bytes that are not UTF-8 survive."""
    with open(path, "rb") as fh:
        data = fh.read(MAX_SCAN_BYTES + 1)
    if len(data) > MAX_SCAN_BYTES:
        return None, "over the scan limit"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            return None, "binary"
    if b"\0" in data[:8192]:
        return None, "binary"
    return data.decode("utf-8", errors="surrogateescape"), "utf-8"


def redact_file(path, rel, res):
    text, enc = read_for_scan(path)
    if text is None:
        res.not_scanned.append((rel, enc))
        return
    new, n = redact_text(text)
    if not n:
        return
    data = new.encode("utf-16") if enc == "utf-16" else new.encode("utf-8", errors="surrogateescape")
    fd = os.open(path, os.O_WRONLY | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    res.redacted.append((rel, n))


def redact_tree(root, res):
    """Redact secret-looking values in every copied regular file under root."""
    for dirpath, _dirs, filenames in os.walk(root, followlinks=False):
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            if stat.S_ISREG(os.lstat(p).st_mode):
                redact_file(p, os.path.relpath(p, root), res)


def filter_drivers(config_names):
    """Driver names of every filter.<driver>.<key> in `git config -z --name-only --list`."""
    drivers = set()
    for name in config_names.split("\0"):
        if name.lower().startswith("filter.") and name.count(".") >= 2:
            drv = name[len("filter."):name.rindex(".")]
            if "=" in drv or not drv:
                # `-c key=value` splits at the first "=", so this one cannot be overridden
                raise UnsafeRepo("a filter driver name git cannot override: %s" % q(drv))
            drivers.add(drv)
    return sorted(drivers)


def safe_git(src, *args):
    """Run git on src/.git with repo-configured programs turned off.

    --git-dir and --work-tree pin the repo to src (a core.worktree setting can
    point elsewhere). A clean or process filter (.gitattributes plus
    filter.<driver> in the config) runs on `git status` and `git diff`, so every
    driver the config defines is overridden with an empty command. Reading the
    config list itself runs nothing.
    """
    base = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat", "-c", "diff.external=",
            "--git-dir=" + os.path.join(src, ".git"), "--work-tree=" + src, "--no-pager"]
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_TERMINAL_PROMPT": "0", "HOME": os.environ.get("HOME", "/tmp")}
    run = dict(check=True, capture_output=True, encoding="utf-8", errors="surrogateescape",
               env=env, cwd=src)
    names = subprocess.run(base + ["config", "-z", "--name-only", "--list"], **run).stdout
    off = []
    for drv in filter_drivers(names):
        for key, value in (("clean", ""), ("smudge", ""), ("process", ""), ("required", "false")):
            off += ["-c", "filter.%s.%s=%s" % (drv, key, value)]
    return subprocess.run(base[:1] + off + base[1:] + list(args), **run).stdout


def is_secret_path(rel):
    parts = rel.split("/")
    return is_secret_name(parts[-1]) or any(p.lower() in SECRET_DIRS for p in parts[:-1])


def untracked_as_diff(src, names):
    """New files git does not track yet, as 'new file' diff blocks (git diff never shows them)."""
    blocks, skipped = [], []
    for rel in sorted(n for n in names.split("\0") if n):
        path = os.path.join(src, rel)
        if is_secret_path(rel):
            continue
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_SCAN_BYTES:
            skipped.append(rel)
            continue
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            with os.fdopen(os.open(path, flags), "rb") as fh:
                data = fh.read(MAX_SCAN_BYTES + 1)
        except OSError:
            skipped.append(rel)
            continue
        head = "diff --git (untracked new file) %s\n--- /dev/null\n+++ %s\n" % (q(rel), q(rel))
        if b"\0" in data[:8192]:
            blocks.append(head + "(binary file, not shown)\n")
            continue
        text = data.decode("utf-8", errors="surrogateescape")
        blocks.append(head + "".join("+" + line for line in text.splitlines(True)) +
                      ("" if text.endswith("\n") or not text else "\n"))
    return "".join(blocks), skipped


def git_changes(src, dest, a):
    """Save what the session changed in src as a redacted diff. Returns the manifest line."""
    if not a.session_work:
        return "- git: not run (work not produced in this session; a repo's own config can run programs)"
    gitdir = os.path.join(src, ".git")
    if os.path.islink(gitdir) or (os.path.lexists(gitdir) and not os.path.isdir(gitdir)):
        return "- git: not run (.git is a link or a file, so the repo lives outside the folder)"
    if not os.path.isdir(gitdir):
        return "- git: no .git folder, no diff"
    base = a.git_base or "HEAD"
    if base.startswith("-"):
        return "- git: not run (the base must be a commit, not an option: %s)" % q(base)
    out = os.path.abspath(a.diff_out or os.path.join(os.path.dirname(dest), "changes.diff"))
    if inside(os.path.realpath(os.path.dirname(out)), src):
        return "- git: not run (the diff must not be written inside the source)"
    excludes = [":(exclude,glob,icase)**/" + p for p in SECRET_NAMES]
    excludes += [":(exclude,glob,icase)**/" + d + "/**" for d in sorted(SECRET_DIRS)]
    try:
        commit = safe_git(src, "rev-parse", "--verify", "--quiet", base + "^{commit}").strip()
        diff = safe_git(src, "diff", "--no-ext-diff", "--no-textconv",
                        "--ignore-submodules=all", commit, "--", ".", *excludes)
        status = safe_git(src, "status", "--short", "--untracked-files=all",
                          "--ignore-submodules=all")
        untracked = safe_git(src, "ls-files", "-z", "--others", "--exclude-standard")
    except UnsafeRepo as e:
        return "- git: not run (%s)" % e
    except subprocess.CalledProcessError as e:
        first = ((e.stderr or "").strip().splitlines() or ["no output"])[0]
        return "- git: failed for base %s (%s)" % (q(base), q(first))
    new_files, too_big = untracked_as_diff(src, untracked)
    diff, n = redact_text(diff + new_files)
    status, n2 = redact_text(status)
    try:
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o444)
    except FileExistsError:
        return "- git: not saved (%s already exists)" % q(out)
    with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write("# git status --short\n" + status + "\n# git diff " + commit +
                 " plus untracked new files (secrets excluded and redacted)\n" + diff)
    line = "- git: diff since %s, untracked new files included, saved to %s (%d values redacted)" % (
        q(base), q(out), n + n2)
    if too_big:
        line += "; untracked files not included (not regular or over the scan limit): " + q_list(too_big)
    return line


def make_read_only(path):
    for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
        for f in filenames:
            p = os.path.join(dirpath, f)
            if not os.path.islink(p):
                os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        os.chmod(dirpath, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
                 | stat.S_IROTH | stat.S_IXOTH)


def manifest(src, copy, res):
    lines = ["### Snapshot", "",
             "Names below come from the deliverable: untrusted data, escaped.", "",
             "- source: %s (the original path stays out of the brief)" % q(os.path.basename(src)),
             "- copied to: %s" % q(copy)]
    n_links = len(res.links_kept) + len(res.links_skipped)
    lines.append("- symlinks: %d found, %d pointing outside were skipped" % (n_links, len(res.links_skipped)))
    for rel, target in res.links_skipped[:MAX_LISTED]:
        lines.append("  - %s -> %s (skipped)" % (q(rel), q(target)))
    lines.append("- secret files left out (names only): %s" % q_list(res.secrets))
    lines.append("- special files not copied (FIFOs, sockets, devices): %s" % q_list(res.special))
    lines.append("- files over %d MB not copied: %s" % (MAX_COPY_BYTES // 1_000_000, q_list(res.too_big)))
    lines.append("- secret-looking values redacted: %s" % (
        ", ".join("%s (%d)" % (q(r), n) for r, n in res.redacted[:MAX_LISTED]) or "none"))
    lines.append("- copied but not scanned for secrets: %s" % (
        ", ".join("%s (%s)" % (q(r), why) for r, why in res.not_scanned[:MAX_LISTED]) or "none"))
    files = []
    for dirpath, _dirs, filenames in os.walk(copy, followlinks=False):
        files += [os.path.relpath(os.path.join(dirpath, f), copy) for f in filenames]
    files.sort()
    shown = [q(f) for f in files[:50]] + (["and %d more" % (len(files) - 50)] if len(files) > 50 else [])
    lines.append("- files in the copy: %d: %s" % (len(files), ", ".join(shown) or "none"))
    return lines


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
        sys.exit("snapshot: source not found: " + q(a.src))
    if inside(dest, src):
        sys.exit("snapshot: destination must not be inside the source")
    name = os.path.basename(src)
    copy = os.path.join(dest, name)
    if os.path.lexists(copy):
        sys.exit("snapshot: already exists, pick another destination: " + q(copy))
    os.makedirs(dest, exist_ok=True)

    res = Result()
    try:
        if os.path.isdir(src):
            copy_tree(src, copy, res)
            redact_tree(copy, res)
        else:
            if is_secret_name(name):
                sys.exit("snapshot: refusing to copy a secret file: " + q(name))
            if not stat.S_ISREG(os.stat(src).st_mode):
                sys.exit("snapshot: not a regular file: " + q(name))
            if not copy_regular(src, copy):
                sys.exit("snapshot: could not copy (changed or over %d MB): %s" % (
                    MAX_COPY_BYTES // 1_000_000, q(name)))
            redact_file(copy, name, res)
        lines = manifest(src, copy, res)
        if a.session_work or a.git_base or a.diff_out:
            lines.append(git_changes(src, dest, a))
    finally:
        if os.path.isdir(copy) and not os.path.islink(copy):
            make_read_only(copy)
        elif os.path.isfile(copy) and not os.path.islink(copy):
            os.chmod(copy, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    lines.append("- the copy is read only; reviewers copy it to their scratch and `chmod -R u+w` the copy")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
