"""MCP tool gating sketch (BARC tiers) for a support-ticket agent.
Core mechanism only -- NOT a solution.

  * The gate lives in the gateway, never in the model: the agent asks,
    the gateway allows or blocks. A prompt cannot be trusted to refuse.
  * Tiers are registered per OPERATION, not per tool name: git clone
    is read-only, git push is human-only. Same tool, different verbs,
    different tiers.
  * Read-only runs free. Bounded writes are gated by an idempotency
    key (see idempotency_key.py). Human-only is never executed by the
    agent -- it escalates, out loud, not silently.
"""

# --- Numbers and names from the problem, as named constants ---
TICKET_ID = "ticket-4821"   # the checkout 500s ticket in the demo

TIER_READ_ONLY = "read-only"          # runs free
TIER_BOUNDED_WRITE = "bounded-write"  # gated by an idempotency key
TIER_HUMAN_ONLY = "human-only"        # never the agent; via PR after review

# Operation-level registry: (tool, operation) -> tier. Nothing runs
# without a registry entry -- an unregistered operation fails closed.
TOOL_TIERS = {
    ("logs", "query"): TIER_READ_ONLY,
    ("observability", "read_logs"): TIER_READ_ONLY,
    ("git", "clone"): TIER_READ_ONLY,   # download the repo to check the code
    ("git", "fetch"): TIER_READ_ONLY,
    ("ticketing", "create_ticket"): TIER_BOUNDED_WRITE,
    ("git", "commit"): TIER_HUMAN_ONLY,
    ("git", "push"): TIER_HUMAN_ONLY,   # push goes via PR, never direct
}


def gateway_call(tool, operation, idempotency_key=None):
    """One gated call. Returns (outcome, detail).

    The three outcomes are decided up front, not caught later:
    EXECUTED, HELD (bounded write without its key), REFUSED.
    """
    tier = TOOL_TIERS.get((tool, operation))
    if tier is None:
        # Fail closed: no registry entry means no permission at all.
        return "REFUSED", "no registry entry -- unknown operation"
    if tier == TIER_READ_ONLY:
        return "EXECUTED", "read-only, runs free"
    if tier == TIER_BOUNDED_WRITE:
        if not idempotency_key:
            return "HELD", "bounded write needs an idempotency key"
        return "EXECUTED", f"bounded write, key {idempotency_key} recorded"
    return "REFUSED", "human-only -- the agent never runs this"


def show(tool, operation, outcome, detail):
    print(f"  {tool:11} {operation:14} -> {outcome:9} {detail}")


def demo():
    print(f"{TICKET_ID}: checkout fails with intermittent 500s")
    print("  the agent works the ticket; the gateway decides each call:\n")

    show("logs", "query",
         *gateway_call("logs", "query"))
    show("git", "clone",
         *gateway_call("git", "clone"))
    # Bounded write without its key is held, not refused: the agent can
    # still do it once it attaches the key.
    show("ticketing", "create_ticket",
         *gateway_call("ticketing", "create_ticket"))
    show("ticketing", "create_ticket",
         *gateway_call("ticketing", "create_ticket",
                       idempotency_key="defbc70b6943f12e"))  # hash(ticket-4821 + create-ticket)
    # The failure path: a code bug is confirmed, so the agent wants to
    # push a fix. Push is human-only. The gateway refuses, and the
    # agent escalates WITH the analysis instead of going silent.
    show("git", "push",
         *gateway_call("git", "push"))
    print("\n  ESCALATE to human: code bug confirmed in checkout, fix goes")
    print("  to the dev agent as a ticket; push happens via PR after")
    print("  a human reviews the dev agent's code. Nothing was pushed.")


if __name__ == "__main__":
    demo()
