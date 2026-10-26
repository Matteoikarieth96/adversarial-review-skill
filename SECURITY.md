# Security

## Threat model

What the skill reads, runs and writes, and what could be hostile:

- **Inputs**: the deliverable under review (files, folders, repos, pages,
  drafts), which may come from anywhere, and everything the agents send back
  (panel specs, reviews, quoted evidence, Reproduce steps, proposed fixes,
  referee rulings). All of it is untrusted.
- **Instructions hidden in inputs** (a README telling reviewers what to do, a
  comment aimed at an agent, text in an image or a page) are data, not
  commands: they become a finding.
- **Commands** the skill runs: `scripts/snapshot.py` runs `rsync`, and only
  with `--session-work` it runs `git config --list`, `git diff` and
  `git status`. The deliverable's own code (tests, an app to screenshot) runs
  only when the work was produced in the session and the user approved that
  exact command.
- **Network**: reviewers may use web search and fetch public pages to check
  facts and links. The brief and the snapshot are read by agents on the same
  Claude account as the session.
- **Outputs**: a workspace folder in the session scratchpad or a `mktemp`
  folder (brief, read-only snapshot, one review per agent, report). Fixes are
  written to the deliverable only after the user picks them.

## Mitigations

| Risk | Mitigation | File |
| --- | --- | --- |
| Hidden instructions in the deliverable steer an agent | Everything in the target and in agent output is untrusted data; text aimed at an agent is reported as a finding; rules for the review come only from the user | `SKILL.md` (Ground rules), `agents/*.md` |
| The author steers the panel or buries a finding | A fresh agent designs the panel from the brief only; the author's known weak spots stay in a private folder no agent sees; the author can confirm a Critical or High but never reject or downgrade it; a referee agent rules | `SKILL.md` steps 1, 2 and 5, `agents/panel-designer.md`, `agents/referee.md` |
| Secrets reach the reviewers | Secret files (`.env`, keys, credential files, `.aws/`, `.ssh/`...) are left out by name, secret-looking values are redacted in what is copied, symlinks that leave the folder are skipped | `scripts/snapshot.py` |
| The originals are changed | The snapshot is read only; each agent works in its own scratch copy | `scripts/snapshot.py`, `agents/reviewer.md` |
| A repo's own git config runs programs | Git runs only on the session's own work, with hooks, fsmonitor, external diff, textconv, every filter driver and submodules turned off; a filter driver name git cannot override stops the git step | `scripts/snapshot.py`, `tests/test_snapshot.py` |
| Hostile code runs | Code runs only for work produced in the session and the exact run the user approved, in a scratch copy, with `env -i` and a scratch `HOME`, through the harness sandbox when there is one | `SKILL.md` (Running code), `agents/reviewer.md` |
| Side effects | No push, post, send, publish, deploy, delete, purchase, login or paid API call by any agent; fixes only on the user's choice; a fix that adds a URL, a download, a dependency, a command or a credential needs its own yes | `SKILL.md` (Ground rules, step 7) |
| Private data leaves through the web | Agents never put private data in a search, a URL or a query string; secrets are cited by their first 4 characters only | `agents/*.md` |
| Agents use powerful tools | A closed tool list: no MCP connectors, browsers, terminal tabs, Artifacts, scheduled tasks, settings or other sessions | `agents/*.md` |

Tests for these cases: `tests/test_snapshot.py`.

## Residual risks

- The rules for the agents are instructions to a language model, not
  enforced permissions. A well-crafted injection in the deliverable can
  still steer a reviewer. Claude Code's permission prompts and sandbox are
  the real boundary; keep them on.
- `env -i` hides environment tokens and keychain helpers from an approved
  run, but it does not stop writes by absolute path or network access.
  Without a harness sandbox, an approved run of hostile code can still do
  damage. That is why runs are limited to work produced in the session.
- Redaction is pattern based and secret files are left out by name. A secret
  in an unusual format, or inside a binary file, can reach the reviewers.
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
