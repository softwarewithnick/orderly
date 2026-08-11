# Demo walkthrough

This repo is staged so that every claim in the script has something on screen
behind it. Two pull requests do the work:

| PR | Branch | Shows |
| --- | --- | --- |
| #1 | `feat/promo-codes` | The review itself: findings, suggested edits, the sequence diagram, inline chat |
| #2 | `chore/inventory-backorders` | A merge conflict, resolved from the PR |

---

## PR #1 — the review

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

### Beats to hit

1. Open the PR. It looks routine — ten files, a feature nobody would block.
2. Comment `@coderabbitai review` in the PR.
3. The review lands as a comment on the PR itself. Expand the **Change Stack**.
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

**Branch:** `chore/inventory-backorders` → `main`

Both this branch and `main` rewrote `release()` in
`app/services/inventory.py`. `main` batched the restock into one statement;
the branch taught it about backorders. Git cannot reconcile them.

GitHub will show **"This branch has conflicts that must be resolved."** That is
the cue for the conflict-resolution beat — resolved from the PR page, without
dropping to a terminal.

Leave this PR conflicted until you are filming it.

---

## Resetting between takes

```bash
# Re-run the review from scratch
@coderabbitai full review

# Other chat commands worth knowing
@coderabbitai resolve      # resolve all CodeRabbit comments
@coderabbitai configuration
```

If you want a clean run, close the PR and reopen it — CodeRabbit reviews it
again from the top.

## Configuration

[`.coderabbit.yaml`](../.coderabbit.yaml) turns on sequence diagrams and adds
per-path review instructions — the money rules for `pricing.py`, the atomicity
rules for `inventory.py`, the parameterized-query rule for `db.py`. Worth a few
seconds on screen: the review is following rules this repo declared, not
generic advice.
