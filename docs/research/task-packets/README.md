# Contributor task packets, Week 3

One packet per owner, matched to the roles in the operating plan:

| Packet | Owner | Area |
| --- | --- | --- |
| [nikhil-architecture.md](nikhil-architecture.md) | Nikhil | Architecture, review policy, baseline design |
| [sanjana-requirements.md](sanjana-requirements.md) | Sanjana | Requirements and task adequacy |
| [sai-security.md](sai-security.md) | Sai | Security reproduction and isolation |
| [ramu-benchmark.md](ramu-benchmark.md) | Ramu | Benchmark protocol, metrics and budget |

## Rules for every packet

1. Do the work yourself, from **your own GitHub account**, so the commit history and reviews show who did it.
2. Record what you actually did, the date, and the commands with their real output. If something fails or
   is blocked, record that. A failed or blocked result is a valid result.
3. If you use an AI tool, say which one and for what, in your PR description or review.
4. Write your conclusions in your own words. Agreeing with a document is fine, but say what you checked
   before agreeing.
5. Nothing is marked approved or verified until you have done the check and recorded it.

## Common setup (about 10 minutes)

```
git clone https://github.com/Ramch16/vittics-builder
cd vittics-builder
git fetch origin fix/review-and-isolation-policies
git checkout fix/review-and-isolation-policies
python3 -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest -q -p no:cacheprovider               # expect: all pass (2 SEC-01 xfails without bubblewrap)
```

Linux only, to enable the SEC-01 sandbox: `sudo apt-get install bubblewrap`, then run
`bwrap --dev-bind / / true`, which must exit 0.

## Where results go

- Code or test changes: a branch from your account and a pull request against
  `fix/review-and-isolation-policies` (or the branch the packet names).
- Reviews: a GitHub review on the named PR ("Approve", "Request changes" or "Comment"), with your reasons.
- Written records: `docs/research/reviews/<your-name>-week3.md`, added in your own PR.
