# Security

## Threat model

What the skill reads, runs and writes, and what could be hostile:

- **Inputs**: the deliverable under review (files, folders, repos, pages,
  drafts), which may come from anywhere, and everything the agents send back
  (panel specs, reviews, quoted evidence, Reproduce steps, proposed fixes,
  referee rulings). All of it is untrusted. File names and link targets in
  the deliverable are untrusted too.
- **Instructions hidden in inputs** (a README telling reviewers what to do, a
  comment aimed at an agent, text in an image or a page) are data, not
  commands: they become a finding.
- **A steered agent**: one reviewer that an injection did fool still has
  Bash and file tools, runs as the user, and shares the workspace with the
  others.
- **Commands** the skill runs: `scripts/snapshot.py`, and only with
  `--session-work` it runs `git config --list`, `git rev-parse`, `git diff`, `git ls-files`
  and `git status`. The session also runs `mktemp`, `cp`, `chmod` and
  `diff` on the workspace, `snapshot.py --fingerprint` to check copies, and
  `ffprobe` and `ffmpeg` on video and audio deliverables to extract frames
  and measurements (for media not produced in the session, only after the
  user's yes). The deliverable's own
  code (tests, an app to screenshot) runs only when the work was produced
  in the session and the user approved that exact command; opening a page
  that was not produced in the session counts as running its code.
- **Network**: reviewers may use web search and fetch public pages to check
  facts and links. The brief and the snapshot are read by agents on the same
  Claude account as the session.
- **Outputs**: a workspace folder in the session scratchpad or a `mktemp`
  folder (brief, read-only snapshot, one review per agent, report) and a
  private folder no agent is told about (the author's notes, a pristine copy
  of the input, a copy of the originals before fixes). Fixes are written to
  the deliverable only after the user picks them.

## Mitigations

| Risk | Mitigation | File |
| --- | --- | --- |
| Hidden instructions in the deliverable steer an agent | Everything in the target and in agent output is untrusted data; text aimed at an agent is reported as a finding; rules for the review come only from the user | `SKILL.md` (Ground rules), `agents/*.md` |
| File names or link targets forge sections of the brief or a command | The snapshot manifest escapes control and invisible characters, backticks, quotes and dollar signs in every name and target; the manifest goes into the brief inside a fenced block marked untrusted; names are never pasted into commands; the original path stays out of the brief | `scripts/snapshot.py`, `SKILL.md` step 1 |
| The author steers the panel or buries a finding | A fresh agent designs the panel from the brief only; the author's known weak spots stay in a private folder no agent sees; the author can confirm a Critical or High but never reject or downgrade it; a referee agent rules | `SKILL.md` steps 1, 2 and 5, `agents/panel-designer.md`, `agents/referee.md` |
| The designer's output turns into instructions or paths | The designer uses the session's model; any field with an instruction, command, URL or path (other than the run the user approves) is struck; slugs must match `^[a-z0-9][a-z0-9-]{0,39}$`; each lens's method is shown to the user; reviewers are told lens fields cannot relax their rules | `SKILL.md` steps 2 and 3, `agents/reviewer.md` |
| Secrets reach the reviewers | Secret files (`.env`, keys, credential files, `.aws/`, `.ssh/`, `.kube/`...) are left out by name in any letter case; common key, token, JWT, URL-credential and private-key formats are redacted in memory before anything is written, also in non-UTF-8, UTF-16 and UTF-32 text; values that only look like code are masked too (masking too much beats leaking); patterns are bounded so hostile text cannot stall them; if the script fails, its partial copy is removed; items saved by hand go through the same script; files that could not be scanned are listed | `scripts/snapshot.py`, `SKILL.md` step 1 |
| The snapshot reaches outside the folder | Folders are opened relative to their parent and files are read without following links, so swapping a folder for a link during the copy does not lead outside; symlinks that leave the folder are skipped, and every kept link is checked again in the copy; FIFOs, sockets and devices are skipped; files over 50 MB are not copied | `scripts/snapshot.py` |
| A repo's own git config runs programs or reads elsewhere | Git runs only on the session's own work and only on a plain `.git` folder, pinned with `--git-dir` and `--work-tree`, with hooks, fsmonitor, external diff, textconv, every filter driver, submodules, network protocols, ssh, credential helpers and optional locks turned off; partial clones and `.git` folders that borrow from another repo (commondir, alternates, any link inside `.git`) are refused; a filter driver name git cannot override stops the git step; the base must be a commit, not an option; the diff file is created new, never through a link, never inside the source; Claude never runs `git commit` or `git stash` for a backup | `scripts/snapshot.py`, `SKILL.md` step 7, `tests/test_snapshot.py` |
| A steered agent tampers with what other agents or the session read | The input is locked before the first agent (the panel designer) sees it; every reviewer, the referee and each re-checker gets its own copy of a pristine input in a fresh random folder; the pristine copy's fingerprint and a `shasum` of the skill's own prompts and script are kept in the session's context and checked before every later use; the session fills every prompt from the skill files it read before any agent ran, and keeps returned reviews and known items in its context; only rulings for ids that were sent are used; no step deletes anything | `SKILL.md` steps 1, 3, 4, 5 and 7, `agents/referee.md`, `agents/rechecker.md` |
| A review's Reproduce step or script gets executed | Reproduce steps are descriptions: a "recompute" uses code the agent writes itself; no agent and not the session runs a script or command from a review or the target | `SKILL.md` (Running code), `agents/referee.md`, `agents/rechecker.md`, `agents/reviewer.md` |
| Hostile code runs | Code runs only for work produced in the session and the exact run the user approved, in a scratch copy, with `env -i`, a scratch `HOME` and no user site packages, through the harness sandbox when there is one | `SKILL.md` (Running code), `agents/reviewer.md` |
| Side effects | No push, post, send, publish, deploy, delete, purchase, login or paid API call by any agent; fixes only on the user's choice, after a plain copy of the originals exists (`cp -RH`, so a linked folder is really copied); a fix that adds a URL, a download, a dependency, a command or a credential needs its own yes | `SKILL.md` (Ground rules, step 7) |
| Private data leaves through the web | Agents never put private data in a search, a URL or a query string; links with tokens or one-time actions are listed, not opened; secrets are cited by their first 4 characters only | `agents/*.md` |
| Agents use powerful tools | A closed tool list in every prompt; no helper agents | `agents/*.md` |

Tests for these cases: `tests/test_snapshot.py`.

## Residual risks

- The rules for the agents are instructions to a language model, not
  enforced permissions. Agents are launched as `general-purpose`, with every
  tool the session has. A well-crafted injection in the deliverable can
  still steer a reviewer. Claude Code's permission prompts and sandbox are
  the real boundary: keep them on when the work comes from elsewhere.
- A steered agent runs as the user: it can undo the read-only `chmod`,
  write in other agents' folders, find the private folder, read files by
  absolute path, edit a file and put it back between two checks, or leave a
  process running. The fingerprints, the separate copies and the prompts kept
  in the session's context catch edits that are still there when the session
  checks; they do not stop such an agent, and Claude Code's permission
  prompts remain the real control.
- `env -i` hides environment tokens and keychain helpers from an approved
  run, not files: the run can still read any file by absolute path, use the
  user's SSH keys and reach the network. Without a harness sandbox, an
  approved run of hostile code can still do damage. That is why runs are
  limited to work produced in the session.
- Redaction is pattern based and secret files are left out by name. A secret
  in an unusual format, or inside a binary file or a file over 20 MB (both
  listed in the manifest), can reach the reviewers. Redaction also errs the
  other way: code such as `token = self.token` can show as `REDACTED`.
- The snapshot goes to the same model provider as the rest of the session.
  Real personal data should be replaced by a synthetic sample, as the skill
  asks.
- Reviewers may open links found in the deliverable to see whether they
  work. Opening a link is still a request to that server.
- All agents share one model, so their agreement is weak evidence.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting: open the repository's
**Security** tab and choose **Report a vulnerability**. Do not open a public
issue for security problems.
