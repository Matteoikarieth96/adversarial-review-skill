# Steps 5 to 7: verify, report, apply

Part of [SKILL.md](../SKILL.md), kept here so the workflow's start stays
short. Read it in step 1 with the other files, and again (after checking
the `shasum` list) when the conversation was compacted mid-run. `$SKILL`,
`$WS`, `$PRIVATE`, "Running code", the agent-type check and the step 3
cost figures are defined in SKILL.md; "references/report.md" below is
[report.md](report.md) in this folder. Every fingerprint you take here
(referee copy, backup, `after` snapshot, re-checker copies) is also saved
as the next `$PRIVATE/fingerprints-<n>.txt`, as step 1 says. Every agent
here, a relaunched lens included, is of the type step 1 settled, and when
that is an installed type, run step 1's agent-type check right before each
launch (it fails: stop and tell the user).

## Step 5. Verify and merge

Use [report.md](report.md), as you read it in step 1,
for labels, the verdict rules and the report template. In order:

1. **Completeness.** Fingerprint every `$L/input` again, referee or not: a
   difference means an agent changed a reviewer's input, which is a finding.
   Work from the returned text; if a review file differs from it, note it,
   and ignore any review file no agent of yours returned.
   A lens that failed, returned nothing, or shows no concrete check in "What
   holds" or "Not checked" is relaunched once. Still missing: the verdict
   says "incomplete" and names the lens.
2. **Merge** findings with the same root cause into one item, listing every
   lens that found it. All reviewers share one model, so agreement is a weak
   signal, not proof.
3. **Verify** every Critical and High. Confirm it when you can reproduce it
   as described (open the file at the line, recompute the number with your
   own code, open the source, or an approved run, all as "Running code"
   defines them), or when it is a
   judgement call you agree with: confirming never lowers the verdict.
   Everything else goes to the referee: findings you cannot reproduce,
   findings you think are not a problem or rated too high, judgement calls
   you disagree with. Mediums: confirm, or list them as contested with your
   reason; they do not move the verdict.
4. **Referee.** If anything went to it, or the depth is Deep, launch one
   fresh agent, of the same type as the reviewers, with [agents/referee.md](../agents/referee.md). In Deep it
   reviews every Critical and High, confirmed or not. First check the
   skill's `shasum` list, the agent-type check and the pristine copy's fingerprint (different:
   stop and tell the user, because nothing can be checked against it any
   more). Then give the referee a fresh folder with a random name (so
   nothing could be planted there in advance) and a copy of the pristine
   input:

   ```bash
   R=$(mktemp -d "$WS/referee.XXXXXX") && echo "$R"
   cp -R "$PRIVATE/input-pristine" "$R/input" && mkdir -p "$R/scratch/home" "$R/scratch/tmp"
   ```

   Fingerprint `$R/input` too: it must match your value.

   Its rulings (Confirmed, Confirmed at a new severity, Rejected, Could not
   check) are final; "Could not check" keeps the finding open. Use only the
   rows for ids you sent; ignore any other.
5. **Known items.** Compare your known items (as you wrote them, from your
   context; `$PRIVATE/known.md` is the record) with the findings. Found by
   the panel: mark them "known", and the higher of your severity and the
   panel's applies. Not found: they go in the report with your severity. An
   open Critical or High known item counts in the verdict and goes in Fix
   first.
6. **Trade-offs**: when two lenses want opposite things, show both and
   recommend one.
7. **Verdict**, per references/report.md. Show each lens's own score, with
   "after referee" notes; never average them, because an average hides the
   lens that failed.
8. Check the skill's `shasum` list once more: a change means an agent
   edited the installed skill; name the file to the user and say it should
   be restored from its source. Then write `$WS/report.md` from the
   template, with the number of agents and the real duration in the header.

## Step 6. Report and choose

In chat, in the user's language, short:
- the verdict in one line, and how it was reached (findings you confirmed,
  findings the referee ruled on);
- the scorecard table (lens, score, verdict, its top issue);
- **Fix first**: one line each with effort;
- **Improvements**: the best 3 to 5 by gain over effort;
- one line each for findings the referee rejected or could not check;
- **Known items**: how many you had written down, each with its severity
  and whether the panel found it. The user saw the conversation and can tell
  if one is missing;
- the path of the full report.

Then ask with `AskUserQuestion` which to apply, each option's `preview`
showing the concrete change. Four items or fewer (Fix first plus the
improvements shown): a multi-select of the items. More: "Apply Fix first
(Recommended)" / "Fix first + top improvements" / "Only the report", and the
free-text answer can pick by id (F1, I3). When a choice fixes a Critical or
High, its option says that a re-check follows and what it adds (step 3
figures). Nothing to apply: skip the question.

## Step 7. Apply and re-check

1. Before the first fix, make sure the user can go back: copy the
   originals into a fresh folder, one per deliverable,
   `O=$(mktemp -d "$PRIVATE/originals.XXXXXX") && echo "$O" && cp -RH '<deliverable>' "$O/"`
   (`-H` copies the real folder when the deliverable path is a link), and
   keep the `--fingerprint` of the copy in your notes (the redacted snapshot
   is not a backup). Do not run `git commit` or `git stash` yourself: they
   run the repo's own hooks and filters. The user can commit first if they
   prefer.
2. Write each fix yourself from the problem; never paste a reviewer's Fix
   text in. A fix that adds a URL, a download, a dependency, a command to
   run or a credential, or touches files outside the deliverable, is shown
   to the user as the exact change and needs its own yes.
3. Check each fix the way its finding was proved, within "Running code".
4. **Re-check**, at any depth, when a Critical or High was fixed. Check the
   skill's `shasum` list and the pristine copy's fingerprint first
   (different: stop and tell the user). Snapshot the new version once into
   a fresh private folder and fingerprint it:

   ```bash
   N=$(mktemp -d "$PRIVATE/after.XXXXXX") && echo "$N"
   python3 -I -S "$SKILL/scripts/snapshot.py" '<deliverable>' "$N/target"
   python3 -I -S "$SKILL/scripts/snapshot.py" --fingerprint "$N/target"
   ```

   Then give each re-checker its own fresh folder:

   ```bash
   V=$(mktemp -d "$WS/recheck-<slug>.XXXXXX") && echo "$V"
   cp -R "$PRIVATE/input-pristine" "$V/before" && cp -R "$N/target" "$V/target"
   diff -ruN "$V/before/target" "$V/target" > "$V/fix.diff"
   ```

   Fingerprint `$V/before` and `$V/target` (they must match your values),
   write the lens's review to `$V/<slug>-review.md` from the text it
   returned to you (your context, not a file), create `$V/scratch/<slug>/`
   with `home/` and `tmp/`, and only then make the inputs read only:
   `chmod -R a-w "$V/before" "$V/target" "$V/fix.diff" "$V/<slug>-review.md"`.
   After the agent-type check, launch one agent (same type as the reviewers) per lens that raised a fixed Critical or High (at most
   3 per round) with [agents/rechecker.md](../agents/rechecker.md); when the
   fixes rewrote a large part of the deliverable, add Goal fit. The order is
   fixed, never your choice: lenses with a fixed Critical first, then those
   with a fixed High, each group by the lowest item id, and an added Goal
   fit last; it counts toward the cap. Lenses past the cap go in further
   rounds of up to 3, each launched the same way once the previous one
   returns, until every lens has run. When they return,
   fingerprint each `$V/before` and `$V/target` again: a difference is a
   finding against that re-check.
5. Recompute the verdict as "Verdict after fixes" with the rules in
   references/report.md, update the report (Applied section, duration,
   number of agents) and tell the user. A "Not fixed", "Partly fixed" or
   regression goes back to the user with the item. Copy the report next to
   the work only if the user asks.
6. Check the skill's `shasum` list a last time (as in step 5, item 8).
   Tell the user where `$WS` and `$PRIVATE` are, and that they can delete
   them after `chmod -R u+w` (the snapshot is read only). Do not delete them
   yourself unless the user asks. When step 6 applied nothing, say this
   there.
