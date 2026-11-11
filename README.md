# MCP tool gating: tiers, not trust

A companion repo to [epsilon-greedy](https://github.com/vnbharani/epsilon-greedy) — the gating mechanism that paper's blast-radius answer depends on. Framed for any agent; the support agent is the originating example.

## What this is

Two runnable sketches of one idea: the agent never enforces its own limits. A gateway sits between the agent and its tools and enforces the tier of every call. The model asks; the gateway allows or blocks.

## The tiers

**Tier 1 — read-only (runs free).** ClickHouse MCP tools (read-only), telemetry API (read-only logs, no direct database connection), git clone / fetch (download repos to check whether something is a code bug).

**Tier 2 — bounded write (gated by an idempotency key).** Jira ticket create — one ticket per support ticket, for the dev agent. The gateway checks the key before it ever calls Jira.

**Tier 3 — human-only (never the agent).** git commit, git push. Code changes go via PR, after a human checks the dev agent's code.

Gate at the operation level, not the tool name. Same "git", different verbs, different tiers.

## The idempotency key

`key = hash(support ticket ID + action)` — for example, `hash("ticket-4821" + "create-jira")`. The gateway stores key → created Jira ticket ID and checks before calling Jira. A retry with the same key returns the same ticket; no duplicate is ever created.

Why not the Jira ticket ID as the key? Jira creates it after the fact — a new ID every time. It cannot be the key.

Why not a hash of the summary? The model rewords the summary on retry, the hash changes, and the duplicate slips through. The support ticket ID never changes — that is why it is the key.

## The sketches

- `tool_gating.py` — ticket-4821 walks the gateway: the reads execute, the Jira create is held without a key and then executed with one, and the git push is refused out loud, escalating to a human instead of failing silently.
- `idempotency_key.py` — the first create stores DEV-1001, a retry after a lost response returns the same DEV-1001, and a labelled wrong-way demo shows a reworded summary producing a different hash and a duplicate ticket.

Run either one with no setup: `python3 tool_gating.py`, `python3 idempotency_key.py`. Python standard library only. Both are sketches, not production code — they show the mechanism running, they are not the answer to any problem.

## References

- Arun C. "BARC: Blast-Radius-Aware Agentic Control." March 2026. https://arun7.com/papers/BARC_Paper_v2.pdf — the blast-radius model behind the tiers: every tool classified into read-only, draft, bounded write, or irreversible, with safety enforced by tier rather than by model confidence.
- [epsilon-greedy](https://github.com/vnbharani/epsilon-greedy) — the exploration-vs-exploitation design paper this gating implements: the 3-try gate, the $5 exploration budget, and the blast-radius tiers.
