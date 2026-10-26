"""Tests for scripts/snapshot.py. Run: python3 -m unittest discover -s tests"""
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import snapshot  # noqa: E402

# Fake secrets are assembled at run time so the source holds no key-shaped text.
FAKE_KEY = "sk-" + "A" * 30
PEM_LABEL = "RSA " + "PRIVATE" + " KEY"
FAKE_PEM = "-----BEGIN %s-----\nMIIEfake\n-----END %s-----\n" % (PEM_LABEL, PEM_LABEL)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def run(*args):
    out = io.StringIO()
    with redirect_stdout(out):
        snapshot.main(list(args))
    return out.getvalue()


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "work")
        self.outside = os.path.join(self.tmp, "outside.txt")
        write(self.outside, "original")
        write(os.path.join(self.src, "app.py"), 'API_KEY = "%s"\nprint(1)\n' % FAKE_KEY)
        write(os.path.join(self.src, "README.md"), "hello\n")
        write(os.path.join(self.src, ".env"), "TOKEN=abcdefghijkl\n")
        write(os.path.join(self.src, ".env.example"), "TOKEN=\n")
        write(os.path.join(self.src, "deploy_key"), FAKE_PEM)
        write(os.path.join(self.src, ".aws", "credentials"), "x")
        write(os.path.join(self.src, "config", "service-account-prod.json"), "{}")
        write(os.path.join(self.src, "notes.txt"), "key below\n" + FAKE_PEM)
        os.symlink(self.outside, os.path.join(self.src, "abs-out"))
        os.symlink("../outside.txt", os.path.join(self.src, "rel-out"))
        os.symlink("README.md", os.path.join(self.src, "rel-in"))
        self.dest = os.path.join(self.tmp, "ws", "input", "target")

    def tearDown(self):
        for dirpath, dirnames, filenames in os.walk(self.tmp):
            for n in dirnames + filenames:
                p = os.path.join(dirpath, n)
                if not os.path.islink(p):
                    os.chmod(p, 0o700)
        subprocess.run(["rm", "-rf", self.tmp], check=True)

    def copied(self, *parts):
        return os.path.join(self.dest, "work", *parts)

    def test_links_leaving_the_folder_are_skipped(self):
        out = run(self.src, self.dest)
        self.assertFalse(os.path.lexists(self.copied("abs-out")))
        self.assertFalse(os.path.lexists(self.copied("rel-out")))
        self.assertTrue(os.path.islink(self.copied("rel-in")))
        self.assertIn("2 pointing outside were skipped", out)

    def test_source_given_as_symlink_copies_the_real_folder(self):
        link = os.path.join(self.tmp, "skills-link")
        os.symlink(self.src, link)
        run(link, self.dest)
        self.assertTrue(os.path.isfile(self.copied("README.md")))
        self.assertFalse(os.path.islink(self.copied()))

    def test_secret_files_are_left_out_but_examples_kept(self):
        out = run(self.src, self.dest)
        for name in (".env", "deploy_key", os.path.join(".aws", "credentials"),
                     os.path.join("config", "service-account-prod.json")):
            self.assertFalse(os.path.exists(self.copied(name)), name)
        self.assertTrue(os.path.exists(self.copied(".env.example")))
        self.assertIn("`.env`", out)
        self.assertNotIn("abcdefghijkl", out)

    def test_secret_values_are_redacted(self):
        out = run(self.src, self.dest)
        with open(self.copied("app.py")) as fh:
            app = fh.read()
        with open(self.copied("notes.txt")) as fh:
            notes = fh.read()
        self.assertNotIn(FAKE_KEY, app)
        self.assertIn("REDACTED(sk-A...)", app)
        self.assertNotIn("MIIEfake", notes)
        self.assertNotIn(FAKE_KEY, out)

    def test_copy_is_read_only_and_original_untouched(self):
        run(self.src, self.dest)
        mode = os.stat(self.copied("README.md")).st_mode
        self.assertFalse(mode & stat.S_IWUSR)
        with open(os.path.join(self.src, "app.py")) as fh:
            self.assertIn(FAKE_KEY, fh.read())
        with open(self.outside) as fh:
            self.assertEqual(fh.read(), "original")

    def test_refuses_destination_inside_source(self):
        with self.assertRaises(SystemExit):
            run(self.src, os.path.join(self.src, "snap"))

    def test_several_deliverables_share_one_target_folder(self):
        post = os.path.join(self.tmp, "post.md")
        write(post, "token = %s\n" % FAKE_KEY)
        run(self.src, self.dest)
        out = run(post, self.dest)
        self.assertTrue(os.path.isdir(self.copied()))
        with open(os.path.join(self.dest, "post.md")) as fh:
            self.assertNotIn(FAKE_KEY, fh.read())
        self.assertIn("post.md", out)
        with self.assertRaises(SystemExit):
            run(post, self.dest)

    def git(self, *args):
        subprocess.run(["git", "-C", self.src, *args], check=True, capture_output=True,
                       env={"PATH": os.environ["PATH"], "HOME": self.tmp,
                            "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                            "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@example.com"})

    def make_repo(self):
        self.git("init", "-q")
        self.git("add", "-f", "README.md", ".env")
        self.git("commit", "-q", "-m", "x")
        write(os.path.join(self.src, ".env"), "TOKEN=NEWSECRETVALUE1\n")
        write(os.path.join(self.src, "README.md"), "changed\n")
        sentinel = os.path.join(self.tmp, "hook-ran")
        hook = os.path.join(self.tmp, "hook.sh")
        write(hook, "#!/bin/sh\necho ran >> '%s'\n" % sentinel)
        os.chmod(hook, 0o755)
        self.git("config", "core.fsmonitor", hook)
        return sentinel

    def test_git_not_run_for_work_from_elsewhere(self):
        sentinel = self.make_repo()
        out = run(self.src, self.dest, "--git-base", "HEAD")
        self.assertIn("git: not run", out)
        self.assertFalse(os.path.exists(sentinel))

    def test_git_diff_runs_no_repo_hooks_and_keeps_secrets_out(self):
        sentinel = self.make_repo()
        diff_out = os.path.join(self.tmp, "ws", "input", "changes.diff")
        run(self.src, self.dest, "--session-work", "--git-base", "HEAD", "--diff-out", diff_out)
        self.assertFalse(os.path.exists(sentinel), "repo fsmonitor hook ran")
        with open(diff_out) as fh:
            diff = fh.read()
        self.assertIn("+changed", diff)
        self.assertNotIn("NEWSECRETVALUE1", diff)

    def plant_filters(self, sentinel, *drivers):
        """Clean, smudge and process filters in the repo config that write to sentinel."""
        hook = os.path.join(self.tmp, "filter.sh")
        write(hook, "#!/bin/sh\necho ran >> '%s'\ncat\n" % sentinel)
        os.chmod(hook, 0o755)
        write(os.path.join(self.src, ".gitattributes"),
              "".join("*.md filter=%s\n" % d for d in drivers))
        for d in drivers:
            for key in ("clean", "smudge", "process"):
                self.git("config", "filter.%s.%s" % (d, key), hook)
            self.git("config", "filter.%s.required" % d, "true")

    def test_git_diff_runs_no_filter_drivers(self):
        sentinel = self.make_repo()
        self.plant_filters(sentinel, "evil", "dotted.name")
        diff_out = os.path.join(self.tmp, "ws", "input", "changes.diff")
        out = run(self.src, self.dest, "--session-work", "--git-base", "HEAD", "--diff-out", diff_out)
        self.assertFalse(os.path.exists(sentinel), "repo filter driver ran")
        self.assertIn("git: diff since", out)
        with open(diff_out) as fh:
            self.assertIn("+changed", fh.read())

    def test_filter_driver_that_cannot_be_overridden_stops_git(self):
        sentinel = self.make_repo()
        self.plant_filters(sentinel, "a=b")
        diff_out = os.path.join(self.tmp, "ws", "input", "changes.diff")
        out = run(self.src, self.dest, "--session-work", "--git-base", "HEAD", "--diff-out", diff_out)
        self.assertFalse(os.path.exists(sentinel), "repo filter driver ran")
        self.assertIn("git: not run", out)
        self.assertFalse(os.path.exists(diff_out))

    def test_filter_driver_names_are_parsed(self):
        names = "core.bare\0filter.lfs.clean\0filter.my.dotted.driver.process\0filter.x\0"
        self.assertEqual(snapshot.filter_drivers(names), ["lfs", "my.dotted.driver"])


if __name__ == "__main__":
    unittest.main()
