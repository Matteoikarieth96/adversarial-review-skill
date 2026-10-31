# Labels, verdict and report template

## Labels

Every Critical and High ends with exactly one status:

| Status | Who sets it | Meaning | In the verdict |
| --- | --- | --- | --- |
| Confirmed | the author or the referee | reproduced as raised, or a judgement call the author agrees with | counts |
| Confirmed at <severity> | the referee only | real, at a different severity | counts at that severity |
| Rejected | the referee only | evidence against it | does not count |
| Could not check | the referee only | the referee could not redo the check | counts |
| Pending referee | the author | sent to the referee, no ruling yet | counts |
| Pending re-check | the author | fixed, but no re-checker has said Fixed yet | counts |

The author never rejects or downgrades a Critical or High. Mediums the
author thinks are wrong are listed as **Contested** with the reason; they do
not move the verdict. Lows go at the end of the Improvements table, or are
left out when there are many.

## Merging

- **Same root cause, one item.** Two lenses that found the same defect from
  different sides become one item listing both. Keep the highest severity
  and the best evidence from each.
- **Ids.** Fix first items are F1, F2... by severity, then gain over effort.
  Improvements are I1, I2... by gain over effort. A Medium goes under Fix
  first only when the user's stakes make it urgent.
- **Agreement**: an item found by two or more lenses is marked so. All
  reviewers share one model, so this raises confidence only a little.
- **Trade-offs**: opposite recommendations from two lenses are not both
  fixes. Show the trade-off, recommend one side, say why.
- **Known items** (from `$PRIVATE/known.md`): found by the panel, mark the
  item "known"; the higher of the author's and the panel's severity applies.
  Not found, list under "Known, not found by the panel" with the author's
  severity. An open known Critical or High also goes in Fix first, as an item
  to apply.

## Verdict

- **Rework**: at least one Critical that counts (table above), or a known
  Critical still open.
- **Fix first**: no Rework, and at least one High that counts or a known High
  still open, or any item in the Fix first section.
- **Good to go**: neither.
- Add **(incomplete: <lens> missing)** when a lens never returned a usable
  review.

Show each lens's own score and verdict, with a note when the referee changed
its findings ("after referee: 1 rejected, 1 lowered to Medium"). Never
average the scores.

## Verdict after fixes (step 7)

- **Fixed** (re-checker): the item no longer counts.
- **Not fixed** or **Partly fixed**: the item keeps its status and severity.
- **Regression** found by a re-checker: a new finding. A Critical or High
  regression is Confirmed if you reproduce it, otherwise Pending referee,
  exactly as in step 5.
- Mediums and improvements fixed without a re-check: mark them "fixed,
  checked by the author" in the Applied section.
- A Critical or High never leaves the verdict on the author's word: fixed
  but not yet re-checked (a round still to run, a re-checker that failed),
  it is **Pending re-check**, counts, and the verdict line names it.

Then apply the verdict rules above to what is left.

## Report template

Write `$WS/report.md` in the user's language. Headings may be translated.

```markdown
# Adversarial review: <what was reviewed>
<date> · <depth> · <N> reviewers<, + referee><, + N re-checkers> · <duration> · target: <path, version, commit or URL>

**Verdict: <Rework | Fix first | Good to go>.** <One sentence on why.>
<How it was reached: N findings confirmed by the author, N ruled by the referee.>

## Scorecard
| Lens | Score | Verdict | Top issue |
| --- | --- | --- | --- |

## Fix first
### F1 <title> (<severity>, <status>)
Found by: <lenses>. Where: <location>.
<Problem in two or three sentences.>
Evidence: <short>.
Fix: <the change>. Effort: <S|M|L>.

## Improvements
| Id | Change | Gain | Effort | Lens |
| --- | --- | --- | --- | --- |

## Trade-offs
<Lens A wants X, lens B wants Y. Recommendation and why.>

## Rejected by the referee, could not check, and contested
<Id, finding, who raised it, the referee's ruling or the author's reason.>

## What holds
<What the reviewers tried to break and could not. This is what to keep.>

## Known items
<Every item the author wrote down before the panel ran, with its severity,
and whether the panel found it.>

## Limits of this review
<What no lens could check (logins, paid services, real devices, watching or
listening in real time), the shared model, anything that ran without
independence (author-designed panel, no Agent tool), any change an agent
made to the shared input. Always end with: a verdict here is a model
review, not a legal, financial, medical or security sign-off.>

## Applied
<Filled after step 7: what was applied, what was skipped, re-check results,
verdict after fixes.>

## Panel
<Each lens: persona and question, one line, and the path of its review.
Then the path of the brief every agent was given.>
```

## Chat summary

The verdict line with how it was reached, the scorecard, Fix first (one line
per item with effort), the top 3 to 5 improvements, one line per finding
the referee rejected or could not check, the known items (count, each with
severity and whether the panel found it), and the report path. No more: the
full detail is in the file.
