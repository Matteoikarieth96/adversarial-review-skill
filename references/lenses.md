# Lenses

A lens is one reviewer's point of view: who they are, the one question they
answer, and how they check it. Good panels come from asking three things
about the output:

1. **What kind of thing is it?** Code, a document, numbers, a visual, a
   message to send, a plan, a skill or prompt, media, a physical object.
   Most outputs are two kinds at once (a report with a chart, a post with an
   infographic, a script with a README): take lenses from both.
2. **Who receives it?** The user only, a team, strangers, a client, an
   investor, a regulator, a machine (a cron job, a hook). Each real recipient
   is a candidate Audience or Counterparty persona.
3. **What breaks if it is wrong?** Money, reputation, safety, legal exposure,
   data, someone's time. The highest stake gets a lens of its own.

## Contents

- Spec of a lens
- Core lenses (always or nearly always)
- Catalog by output type
- Cross-cutting lenses
- Selection rules and sizes
- Worked examples
- A filled spec

## Spec of a lens

Fill these for every lens; they become the reviewer prompt placeholders.

| Field | What to write |
| --- | --- |
| name | A short name, in the user's language for the intake table |
| slug | kebab-case, in English, 1 to 40 characters matching `^[a-z0-9][a-z0-9-]{0,39}$`, unique; used for file and folder names |
| persona | Who they are, in one line, as concrete as possible ("a shop owner reading it on a phone between two customers", not "a reader") |
| question | The single question this lens answers |
| method | The kind of check (run it, recompute, trace sources, read it as the persona, attack the claims in the brief) with the concrete inputs or readings that fit this output. Never a guess at a specific defect |
| out of scope | What the other lenses on this panel cover, so this one goes deep instead of wide |
| critical | What a Critical finding looks like for this lens on this output |
| runs code | no, or yes with the exact run (see "Running code" in SKILL.md) |
| opens web | no, or yes and what for |
| stake | The stake from the brief this lens serves |

## Core lenses

**Goal fit** (the requester)
- Persona: the user who asked, rereading their own request.
- Question: did this deliver what was asked, all of it, in the form asked,
  following the rules stated along the way?
- Method: go through the request sentence by sentence and match each ask to
  the deliverable. Look for asks silently dropped or narrowed, things
  replaced by something easier, implicit expectations (format, language,
  location, tone), and work nobody asked for that adds risk.
- Critical: the main thing asked for is missing, or a stated rule is broken.

**Refuter** (red team)
- Persona: someone paid to prove this wrong.
- Question: what is the strongest case that this does not work, or that its
  central claim is false?
- Method: name the one to three claims the work rests on (including the
  "Claims to test" in the brief) and attack each: hostile and edge inputs,
  recomputation, counter-evidence, the condition under which it falls over.
- Critical: a central claim is false, or the work fails in a normal case.

**Audience** (first contact)
- Persona: the specific person who will receive it, with none of the
  context of the conversation that produced it.
- Question: what do they understand, feel and do in the first minute, and
  where do they get lost, misread it or give up?
- Method: read, open or use it cold, on their device and in their setting
  (phone at 375 px, a feed, a printed page, a terminal on a clean machine).
  Using something that executes is an approved run; otherwise simulate it
  by reading.
- Critical: the intended reader misreads the main point or cannot use it.

## Catalog by output type

### Code, scripts, apps, automations, hooks
- **Correctness and edge cases**: run it; empty, huge, malformed, Unicode,
  concurrent, offline, wrong permissions; error paths and exit codes.
- **Security**: untrusted input reaching a shell, a path, HTML or SQL;
  secrets in code, logs or command lines; permissions; network exposure;
  dependencies and supply chain.
- **Operability**: install from a clean state (an approved offline run in a
  scratch copy, or traced by reading), what happens when it fails at 3 a.m.,
  logs, idempotence, rollback, behaviour when run by a cron job or a hook
  with no terminal.
- **Test skeptic**: do the tests test the claim? Break the code on purpose in
  the scratch copy and see whether the tests notice.
- **Maintainer**: could half of it go? Duplication, naming, hidden coupling;
  could a newcomer change it safely?
- **Performance and cost**: only when scale or money matter (API spend,
  loops over large data, rate limits).

### Documents, reports, research, explainers, guides
- **Fact-checker**: every number, name, date and quote traced to a source and
  re-derived where possible; source dates; claims with no source; stale
  facts.
- **Logic and argument**: does the conclusion follow? Missing alternatives,
  cherry-picking, correlation read as cause, a conclusion stronger than the
  evidence.
- **Editor**: structure, length, the one-sentence takeaway, clarity, tone,
  consistency of terms.
- **Domain expert**: what a specialist in the field would call wrong or
  naive. Name the field, seniority and country ("a senior tax advisor in
  the country the report is for").
- **Legal and compliance**: whenever it touches law, regulated advice,
  privacy, IP, health, finance, or statements about real people and
  companies.

### Data, numbers, models, analyses, dashboards
- **Methodologist**: sample, baselines, leakage, wrong denominator,
  overfitting, survivorship; re-run the analysis from the files.
- **Reproducibility**: can it be rebuilt from what is saved? Pinned inputs,
  seeds, versions, manual steps.
- **Honest reporting**: overclaiming, cherry-picked windows, misleading
  charts (truncated axes, dual axes, area for length), uncertainty missing.

### Visuals, UI, design, print
- **Usability**: can the intended user do the main task? Mobile width,
  states (empty, loading, error), touch targets.
- **Accessibility**: contrast, text size, alt text, keyboard, colour-only
  signals, dark mode.
- **Craft and brand**: hierarchy, alignment, typography, consistency with the
  brand or the style the user set.
- **Production**: print specs (size, bleed, resolution, colour), file
  formats, mandatory text (labels, legal lines), what the printer or platform
  will reject.

### Posts, messages, emails, announcements
- **Hostile reader**: the reply-guy, the competitor, the journalist: what
  gets screenshotted and quoted against the author?
- **Fact and source**: every claim backed, numbers current, links working.
- **Reputation and relationships**: who could be offended or misrepresented;
  what it commits the author to; whether it leaks something private.
- **Platform fit**: length limits, the hook in the first line, format, media,
  link handling.

### Plans, strategies, decisions, proposals, pitches
- **Devil's advocate**: the strongest alternative plan and why it might win.
- **Premortem**: it is six months later and this failed: the most likely
  reasons, in order.
- **Feasibility and cost**: time, money, people, dependencies; do the
  numbers add up?
- **Counterparty**: the person who must say yes (investor, client, manager,
  partner, regulator): their objections and what would change their mind.

### Skills, prompts, agents, workflows
- **Cold-start user**: follows only the files on a realistic, fictional
  request, by reading (and approved offline runs only); where do they
  stall, guess or need the author's machine?
- **Prompt safety**: injection paths (files, pages, tool output the prompt
  reads), side effects without a yes, data leaving the machine, over-broad
  permissions, secrets asked in chat.
- **Trigger accuracy**: would the description fire on the right requests and
  stay quiet on near misses? Overlap with other skills.
- **Generality**: overfit to the examples it was built from; hard-coded
  paths, names, languages.

### Video, audio, media
Reviewers read frames, a transcript and measured numbers (ffprobe, loudness)
prepared in the snapshot; they never watch or listen in real time, so their
methods work from those.
- **Viewer**: first three seconds, pacing, the moment they scroll away.
- **Accuracy**: facts, numbers, names, captions matching the voice.
- **Technical**: resolution, loudness, sync, caption legibility, platform
  specs and safe areas.

### Hardware, electronics, 3D printing, physical objects
- **Safety**: voltages, currents, shorts, heat, batteries, mains, sharp
  edges, materials near food or skin.
- **Buildability**: can a person build it from the instructions with the
  listed parts and tools? Tolerances, print orientation, assembly order.
- **Parts and sourcing**: parts exist, are compatible, prices, alternatives.

## Cross-cutting lenses

Add when the stakes call for them:
- **Simplifier**: what could be removed, or done ten times simpler, with the
  same result?
- **Privacy**: personal data, secrets, metadata, things that must not leave
  the machine or the company.
- **Money**: spend, pricing, financial exposure, tax.
- **Time-to-stale**: what here will be wrong in a month (prices, versions,
  dates, "latest")?
- **Ethics and harm**: who could be hurt by this being used as intended, or
  misused.

## Selection rules and sizes

Mandatory lenses:
1. **Goal fit**, always.
2. **Refuter**, always, unless an adversarial specialist plays that role for
   this output (Premortem for a plan, Hostile reader for a post, Devil's
   advocate for a decision); that lens's spec then says it is the refuter.
3. **Audience** whenever anyone but the user receives the result. In Quick
   it may be merged into Goal fit.
4. **Security or Prompt safety** whenever the target contains code that will
   run, install steps, or text aimed at an agent (prompts, skills, agent
   configs), or was not produced in the session asking for the review.

Sizes (reviewer agents, referee not counted):

| Depth | Reviewers | Specialists |
| --- | --- | --- |
| Quick | 3 | Goal fit + 2 lenses from the output, one of them playing the Refuter |
| Standard | 4 to 6 | Goal fit, Refuter, Audience if needed, + 2 or 3 |
| Deep | 6 to 8 | as Standard, + 3 to 5, and a referee always |

How to pick:
5. Specialists come from the highest stakes in the brief first, then from
   the kind of output. A post with one number in it needs a fact-checker
   more than an editor. Each specialist names the stake it serves.
6. The worked examples below are illustrations, not templates. At least one
   lens must come from a stake in this brief that the nearest example does
   not cover (cost, publication, a legal angle, a specific recipient).
7. One question per lens. If you cannot state a lens's question in one
   sentence, it is two lenses or none.
8. Merge lenses whose findings would mostly overlap (Editor and Audience on
   a short message; Refuter and Correctness when the only claim is "it
   works": the Refuter then attacks the claims in the brief, Correctness runs
   the input matrix).
9. Invent a lens when the output needs one the catalog lacks, with a
   concrete persona ("a sommelier", "a city permit officer").
10. Make the persona specific to this output. "Security reviewer" becomes
    "an attacker who controls the repo names this script reads".
11. Methods describe how to check, never what you suspect is broken.
12. Fill "out of scope" for every lens with what the others cover.

## Worked examples

| Output | Depth | Panel |
| --- | --- | --- |
| Social media post with a chart on a market trend, every claim must be sourced | Standard | Goal fit; Refuter; Audience (a reader who follows the topic, scrolling a feed on a phone); Fact-checker (each number to its source, dates); Hostile reader (what a competitor quotes back) |
| Same post | Quick | Goal fit (merged with Audience); Fact-checker; Hostile reader (plays the Refuter) |
| Command-line script that changes account settings through a web API, run by a hook after other commands | Standard | Goal fit; Refuter; Correctness and edge cases (run it on fake API responses); Security (hostile names in API responses, token handling); Operability (hook with no terminal, rate limits, partial failure) |
| Printed label for a small batch of a homemade product, given as a gift | Standard | Goal fit; Audience (the person holding the product); Production (print size, bleed, mandatory text); Craft and brand; Refuter on originality (does any element copy a protected logo or mascot?) |
| Quarterly sales forecast built on a statistical model | Standard | Goal fit; Refuter; Methodologist (model inputs, baseline, error bands); Fact-checker (date and source of every input figure); Counterparty (the finance lead who must sign it off) |
| Rollout plan for a new internal tool | Standard | Goal fit; Counterparty (the manager who funds it); Premortem (plays the Refuter); Feasibility and cost |
| A new Claude Code skill, to be open-sourced, run often | Standard | Goal fit; Refuter; Cold-start user; Prompt safety; Trigger accuracy; Money (time and tokens per run) |
| Data dashboard for a team | Standard | Goal fit; Refuter (are the headline numbers right?); Audience (the team lead on a laptop on Monday); Methodologist; Honest reporting |

## A filled spec

```markdown
## Fact-checker
- slug: fact-checker
- persona: a financial journalist who has been burned by one wrong number before
- question: is every number, name and date in the post true, current and traceable to a source?
- method: list every factual claim in the post and the infographic; for each, open the source given under "Inputs and sources" or find the primary one; check the figure, its date and its unit; recompute any derived number (growth, share, totals); flag claims with no source
- out of scope: tone and reactions (Hostile reader), whether the post answers the request (Goal fit)
- critical: a wrong or unsourced number in the headline or the chart
- runs code: no
- opens web: yes, to open sources and primary data
- stake: the user's rule that every claim needs a source, and the author's reputation with the post's readers
```
