# internship-tracker

A tiny CLI + JSON store for tracking internship postings (built for ML/AI
internship hunting, but role-agnostic). Designed to be driven by an AI agent
on a daily schedule *or* by a human at a terminal. No dependencies — Python
stdlib only.

## Why

Job links rot, deadlines sneak up, and "did I already apply there?" is a
real question at 2am. This keeps one canonical list where every posting has:

- a **status** (`new → interested → applied → interview → offer/rejected/closed/dropped`)
- a **deadline** with days-remaining math
- **pay provenance** — every pay figure is labeled *employer-posted* vs
  *aggregator estimate*, never a guess
- the **source + date** it was found, and a deduped application URL

## Quick start

```bash
./tracker.py add \
  --company NVIDIA --role "2027 Internships: Deep Learning" \
  --url https://jobs.nvidia.com/careers/job/893397026418 \
  --location "Santa Clara, CA" \
  --pay "\$62/hr" --pay-source "employer-posted" \
  --deadline 2026-12-01 --term "Summer 2027" --tags ml,internship

./tracker.py list --status new
./tracker.py due --within 14          # deadlines in the next 2 weeks
./tracker.py update <id> --status applied
./tracker.py stats
./tracker.py import data/seed.json    # bulk add, URL-deduped
./tracker.py sync -m "daily scan"     # commit + push data/ to git
```

## Commands

| command | what it does |
|---|---|
| `add` | add one posting (skips if the URL is already tracked) |
| `update` | change status/deadline/notes/pay/tags by job id |
| `list` | list jobs, filter by `--status --company --term --due-within` |
| `show` | full JSON for one job |
| `due` | open jobs with deadlines, soonest first |
| `stats` | counts per status |
| `import` | bulk add from a JSON file (same fields as `add`) |
| `sync` | git commit + push `data/` if it changed |

Job ids are auto-generated slugs (`company-role`), so they're readable and
stable.

## Agent-driven daily workflow

The intended setup is a cron job where an agent:

1. searches for new postings matching your profile,
2. verifies each one is live at the primary ATS source,
3. `add`s the new ones (dedupe is built in),
4. runs `due --within 14` and pastes the output into your daily digest,
5. `sync`s so the tracker history is published here on GitHub.

The full history of postings, statuses, and deadlines lives in
`data/jobs.json` — git log doubles as an audit trail of the search.

## Data

Everything lives in `data/jobs.json`. Fields per job: `id, company, role,
url, location, remote, pay, pay_source, deadline, term, status, source,
tags, notes, added, updated`.

Pay-provenance rule (non-negotiable): `pay_source` must say whether the
figure is employer-posted or an aggregator estimate. An estimate is never
presented as a posted rate.

## License

MIT
