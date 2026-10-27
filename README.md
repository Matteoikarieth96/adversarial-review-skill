# adversarial-review

A Claude Code skill that hands a finished piece of work to a panel of
independent reviewer agents, each looking from one angle picked for that
output, and returns one verdict with ranked fixes.

The session that did the work is the worst judge of it: it knows what it
meant and wants to be done. Here the reviewers start cold. The panel is
never a fixed list: a shell script gets a security reviewer and an
operability reviewer, a social media post gets a fact-checker and a hostile
reader, a printed label gets a print production check. **Goal fit** (did it
deliver what was asked?) is always on, and so is a **Refuter** (what is the
strongest case that it is wrong?) or a lens that plays that role.

> **Independent project.** Not affiliated with or endorsed by Anthropic.

## What it does

1. **Collects** the original request, the deliverable, its inputs and
   sources, the claims made about it and the stakes, and writes a brief.
   A script takes a read-only snapshot: symlinks that leave the folder,
   special files, caches and secret files are left out, secret-looking
   values are redacted, and git runs only on the session's own work, with
   the repo's hooks, filters and other configured programs turned off. The
   author writes down the weak spots it already knows, privately.
2. **Designs the panel** with a fresh agent, from the brief and a lens
   catalog (`references/lenses.md`). The author can steer the panel only
   through the brief, which must not hint at the known weak spots.
3. **Asks once** whether the target and the panel are right.
4. **Launches one fresh agent per lens**, in parallel. Reviewers are told to
   read only the brief and the snapshot, work in their own scratch folder,
   use a closed set of tools, and run code only when the work was made in
   this session and you approved that exact run.
5. **Merges the findings.** The author can confirm a Critical or High but
   never reject or downgrade one: that goes to a referee agent, which works
   from its own copy of the input. Known weak spots still count, and all
   of them are shown to you. One report: verdict, per-lens scores, Fix
   first, ranked improvements, what holds.
6. **Applies only the fixes you pick**, after making sure you can go back,
   and re-checks Critical and High fixes with the lenses that raised them.

What the skill instructs Claude and the agents never to do during a review:
change the originals; push, post, send, publish, deploy, delete, buy, log in
or call a paid API; run code from work that was not produced in the session;
run code without your yes to that exact command; apply a fix you did not
choose. These are instructions to language models, not enforced limits:
Claude Code's own permissions are the real boundary (see Security).

## The intake questions

1. Only when the work was not done in the current conversation: what is the
   goal, and who receives the result?
2. Before the panel starts, one question with the target, the yardstick, the
   panel and the cost: **Go with this panel**, **Lighter: Quick** or
   **Deeper: Deep**. Free text can add, drop or rename lenses, or say what
   you want checked.
3. When a lens would run code: yes or no to that exact command.

After the report, it asks which fixes to apply.

## Install

```bash
git clone https://github.com/Matteoikarieth96/adversarial-review-skill ~/.claude/skills/adversarial-review
```

Requirements:

- Claude Code with the Agent tool. Without it, the skill plays the lenses one
  at a time and says the review was not independent.
- Python 3.9 or newer (standard library only) for `scripts/snapshot.py`.
- `git`, only to save a diff of what the session changed in a repo.
- Optional: `ffmpeg` and `ffprobe` for video and audio deliverables.
- Tested on macOS and Linux. Not tested on Windows (WSL should behave like
  Linux, untested).

## Usage

Right after a task, in Claude Code:

> Run an adversarial review of the report you just wrote. It goes to the
> board on Monday.

Other phrasings: "red team this", "poke holes in it", "give me a verdict",
or `/adversarial-review` with `quick` or `deep` to set the size. It also
responds to Italian phrasings such as "review avversariale" and "fai partire
la review".

| Depth | Reviewers | Rough time end to end | Rough tokens in total |
| --- | --- | --- | --- |
| Quick | 3 | 20 to 30 minutes | 0.4 to 0.6 million |
| Standard (default) | 4 to 6 | 30 to 55 minutes | 0.6 to 1.1 million |
| Deep | 6 to 8, plus a referee | 45 to 70 minutes | 1 to 1.6 million |

All figures are rough estimates built from one Standard run on the author's
machine, not an average: in that run each reviewer took 5 to 11 minutes and
roughly 120k to 170k tokens, all in parallel. A review uses your Claude Code
usage: on a plan it takes a large share of your limits, and with API-key
billing you pay for those tokens. The skill calls no other paid service.

Expect permission prompts while the reviewers work, unless your settings
already allow their tools. For work that comes from elsewhere (a cloned
repo, a download), keep those prompts on.

## Data and privacy

- **Reads**: the deliverable you point at, the conversation's request, your
  own standing rules that apply (from CLAUDE.md and memory), and the sources
  the work cites.
- **Sends**: the brief and the snapshot go to the reviewer agents, which run
  on the same Claude account as your session, so the model provider reads
  them like the rest of the session. Reviewers may search the web and open
  public pages to check facts and links; they are told never to put private
  data in a search, a URL or a query string.
- **Stores**: two folders in the session scratchpad (or made with
  `mktemp -d`): the workspace with the brief, the snapshot, one file per
  review and the report, and a private folder with the author's notes, a
  pristine copy of the input and, before fixes, a copy of the originals.
  Nothing is copied next to your work unless you ask. They stay until the
  scratchpad is cleared; to delete them yourself, run `chmod -R u+w` on each
  folder first, because the snapshot is read only.
- Real personal data (customers, patients, employees) is replaced by a
  synthetic sample with the same shape whenever the review can work without
  it. When it cannot, the skill tells you before including it.

## Security

Everything in the deliverable and everything the agents send back is treated
as untrusted data: text aimed at an agent becomes a finding, never an
instruction. The snapshot script escapes every name it prints, leaves out
secret files and redacts secret-looking values; every reviewer, the referee
and each re-checker gets its own copy of the input in a fresh folder. The rest are
rules for language-model agents, not a sandbox: Claude Code's own
permissions remain the real boundary. Details and residual risks:
[SECURITY.md](SECURITY.md).

## Limitations

- All reviewers share one model, so their agreement is weak evidence.
- Nobody on the panel watches video or listens to audio in real time: they
  work from frames, a transcript and measured numbers.
- Reviewers do not use a browser; pages and apps are judged from
  screenshots taken before the review.
- Redaction is pattern based, and secret files are left out by name: a
  secret in an unusual format can still reach the reviewers. Binary files
  and files over 20 MB are copied without redaction and listed as such. It
  also masks some code: a value masked on the line after its key shows as
  `REDACTED(line-break)` and is listed, because in code it can hide a line.
- A "Good to go" is a model review, not a legal, financial, medical or
  security sign-off.
- A review costs time and usage (see the table above). For a quick
  proofread, just ask Claude directly.

## Files

- `SKILL.md`: the workflow.
- `references/lenses.md`: lens catalog, mandatory lenses, sizes, worked
  examples.
- `references/report.md`: labels, verdict rules, report template.
- `agents/panel-designer.md`, `agents/reviewer.md`, `agents/referee.md`,
  `agents/rechecker.md`: the agent prompts.
- `scripts/snapshot.py`: the read-only snapshot.
- `tests/`: unit tests for the snapshot script.

## Tests

```bash
python3 -m unittest discover -s tests
```

CI runs them on every push and pull request, on Ubuntu and macOS with
Python 3.9 and 3.12.

## More skills

- [skill-release](https://github.com/Matteoikarieth96/skill-release-skill): take a Claude Code skill from a private folder to a public GitHub repo without leaking anything
- [evm-dd](https://github.com/Matteoikarieth96/evm-dd-skill): investor-angle due diligence on crypto and EVM projects, with a scored report and an A4 one-pager
- [hiring-prep](https://github.com/Matteoikarieth96/hiring-prep-skill): an interview prep page from a company, a role and your resume, with an interactive test
- [whiteboard-video](https://github.com/Matteoikarieth96/whiteboard-video-skill): hand-drawn whiteboard explainer videos with voice-over
- [3d-print-design](https://github.com/Matteoikarieth96/3d-print-design-skill): parametric parts for FDM 3D printing, checked before export
- [beer-can-label](https://github.com/Matteoikarieth96/beer-can-label-skill): print-ready beer can labels with a 3D preview
- [ai-privacy-check](https://github.com/Matteoikarieth96/ai-privacy-check-skill): privacy and AI rules check for a concrete use case (Italian)
- [claude-time-is-relative](https://github.com/Matteoikarieth96/claude-time-is-relative): time estimates for Claude Code tasks from your own past sessions
- [token-checkup-skill](https://github.com/Matteoikarieth96/token-checkup-skill): a weekly token checkup for Claude Code: session size, what loads at session start, memory kept true

## Licence

MIT, see [LICENSE](LICENSE).
