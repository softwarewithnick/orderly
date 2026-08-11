# Demo walkthrough

This repo is staged so that every claim in the script has something on screen
behind it. Two pull requests do the work:

| PR | Branch | Shows |
| --- | --- | --- |
| [#3](https://github.com/softwarewithnick/orderly/pull/3) | `feat/promo-codes` | The review itself: findings, suggested edits, the sequence diagram, inline chat |
| [#2](https://github.com/softwarewithnick/orderly/pull/2) | `chore/stock-audit-trail` | A merge conflict, resolved from the PR |

Auto-review is switched **off** in [`.coderabbit.yaml`](../.coderabbit.yaml) on
purpose, so PR #3 is sitting there unreviewed until someone asks. That is the
shot: you type the comment, the review arrives.

---

## PR #3 — the review

**Branch:** `feat/promo-codes` → `main`

A ten-file feature that adds percentage-off promo codes to checkout. It looks
like an ordinary Tuesday PR. The tests pass. CI is green. It is also carrying
nine or so real defects, planted on purpose and spread across the layers so the
review has to actually understand the codebase to find them:

| Where | What is wrong |
| --- | --- |
| `app/services/promotions.py` | `lookup()` builds SQL with an f-string — injectable, and reachable without auth |
| `app/routers/promotions.py` | `/promotions/validate` has no API key dependency and no rate limit |
| `app/services/pricing.py` | Discount computed in binary float, then truncated instead of rounded |
| `app/services/pricing.py` | Tax is charged on the pre-discount subtotal, so promo customers are overtaxed |
| `app/services/pricing.py` | Nothing bounds `percent_off`, so a 150% code produces a negative total |
| `app/services/promotions.py` | `redeem()` reads the counter, then writes `read + 1` — a lost update under concurrency |
| `app/services/orders.py` | A network call to the partner service runs while the write transaction is open |
| `app/services/orders.py` | `except Exception: pass` swallows every promo failure silently |
| `app/services/orders.py` | `send_order_confirmation(order)` is missing its `await` — no receipt is ever sent |
| `app/config.py` | A live-looking API key is hardcoded as a default |
| `tests/` | Two shallow tests, none covering the discount arithmetic |

The last one is the point worth landing on camera: **the test suite is green.**
CI passes. Nothing here is caught by a linter or a type checker. This is what
gets missed by a human reviewer at 5pm on a Friday.

On a trial run against this PR, CodeRabbit returned eight findings, including
the hardcoded credential, the float discount, the network call inside the write
transaction, the missing `await`, and the absent test coverage — plus one nobody
planted: existing databases need a migration for the new columns. Expect the
exact set to move around between runs.

### Beats to hit

1. Open the PR. It looks routine — ten files, a feature nobody would block.
   CI is green. There is no review on it yet.
2. Comment `@coderabbitai review` in the PR.
3. The review lands as a comment on the PR itself. Open the **Change Stack**
   from the banner at the top of that comment.
4. Walk the layers of the viewer:
   - the summary of what the PR does
   - a finding, then the **suggested edit** attached to it
   - the **sequence diagram** — worth pausing on, because a checkout crosses a
     router, four services, the database, and two external systems, and the
     diagram is the fastest way to see that path
   - drop an **inline comment** from inside the viewer
5. Ask it something in the thread, e.g.
   `@coderabbitai why is the discount calculation a problem if the tests pass?`

### Good ones to zoom in on

- **The SQL injection.** `lookup()` interpolates the code straight into the
  query, and the endpoint that calls it has no auth. Two files, one exploit —
  the reviewer has to connect them.
- **The missing `await`.** One keyword. Tests pass. Every customer silently
  stops getting receipts.
- **Tax before discount.** Not a crash, not a lint error. Just every promo
  order overcharged by a few cents, forever.

---

## PR #2 — the merge conflict

**Branch:** `chore/stock-audit-trail` → `main`

Both this branch and `main` rewrote `release()` in
`app/services/inventory.py`. `main` batched the restock into a single
`executemany`; the branch kept the loop and added an audit-trail insert next to
each update. Same function, same lines, two reasonable answers — git cannot
pick one.

GitHub will show **"This branch has conflicts that must be resolved."** That is
the cue for the conflict-resolution beat — resolved from the PR page, without
dropping to a terminal.

Leave this PR conflicted until you are filming it.

---

## Resetting between takes

`@coderabbitai review` is incremental — run it twice with nothing changed in
between and the second one correctly reports that it found nothing new. That is
right, and it is not the shot you want. Between takes:

```text
@coderabbitai full review   # re-review everything from scratch
@coderabbitai resolve       # clear the existing CodeRabbit comments
@coderabbitai configuration # print the config in effect
```

For a completely fresh take, close the PR and open a new one from the same
branch. With auto-review off, the new PR arrives with no review on it, ready for
the comment.

## Configuration

[`.coderabbit.yaml`](../.coderabbit.yaml) turns on sequence diagrams and adds
per-path review instructions — the money rules for `pricing.py`, the atomicity
rules for `inventory.py`, the parameterized-query rule for `db.py`. Worth a few
seconds on screen: the review is following rules this repo declared, not
generic advice.
