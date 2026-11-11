"""Idempotency key sketch for Jira ticket creation.
Core mechanism only -- NOT a solution.

  * The key comes from the INPUT, never the output: hash of the
    incoming support ticket id + the action. The Jira ticket id cannot
    be the key -- Jira creates it after the fact, a new one each time.
  * The key is stable across retries because the ticket id and the
    action never change. A hash of the summary is not: the model
    rewords the summary on retry, the hash changes, and the duplicate
    slips through.
  * The gateway checks its store BEFORE calling Jira: key seen ->
    return the ticket already created. Key unseen -> create, store,
    return. The model just attaches the key; it enforces nothing.
"""

import hashlib

# --- Numbers and names from the problem, as named constants ---
TICKET_ID = "ticket-4821"          # the incoming support ticket
ACTION_CREATE_JIRA = "create-jira"  # the action, fixed per operation
KEY_TTL_HOURS = 24  # keys expire so the store never grows forever


def idempotency_key(ticket_id, action):
    # Deterministic: same ticket + same action always makes the same
    # key, so a retry reuses it. Truncated for readability; the full
    # hash is what a real store keeps.
    raw = f"{ticket_id}:{action}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class JiraGateway:
    """The store lives in the gateway, not the agent."""

    def __init__(self):
        self.seen = {}  # key -> jira ticket id
        self.created = 0

    def create_ticket(self, key, summary):
        # The check happens BEFORE the Jira call, never after.
        if key in self.seen:
            return self.seen[key], "RETURNED existing ticket -- no duplicate"
        self.created += 1
        jira_id = f"DEV-{1000 + self.created}"
        self.seen[key] = jira_id
        return jira_id, "CREATED and stored"


def demo():
    gateway = JiraGateway()
    key = idempotency_key(TICKET_ID, ACTION_CREATE_JIRA)
    print(f"{TICKET_ID}: checkout fails with intermittent 500s")
    print(f"  key = hash(\"{TICKET_ID}\" + \"{ACTION_CREATE_JIRA}\") = {key}\n")

    # First attempt: creates the ticket and stores the key.
    jira_id, outcome = gateway.create_ticket(key, "checkout 500s")
    print(f"  attempt 1: {outcome} -> {jira_id}")

    # Failure path 1 -- the happy retry: the first response is lost
    # (timeout), so the agent retries with the SAME key. The gateway
    # finds the key and returns the same ticket. One ticket, not two.
    jira_id, outcome = gateway.create_ticket(key, "checkout 500s")
    print(f"  attempt 2 (retry, same key): {outcome} -> {jira_id}")
    print(f"  tickets created: {gateway.created} (not 2)\n")

    # Failure path 2 -- the WRONG way: the retry hashes a reworded
    # summary instead of the ticket id. Same ticket, different words,
    # different hash -- the gateway sees a new key and creates a
    # duplicate. This is why the key must come from the ticket id.
    summary_v1 = "checkout fails with 500s"
    summary_v2 = "checkout returns 500 errors"
    key_v1 = hashlib.sha256(summary_v1.encode()).hexdigest()[:16]
    key_v2 = hashlib.sha256(summary_v2.encode()).hexdigest()[:16]
    print("  WRONG WAY -- key from the summary, not the ticket id:")
    print(f"    summary v1 -> {key_v1}")
    print(f"    summary v2 -> {key_v2}   (reworded, so the key changed)")
    _, outcome = gateway.create_ticket(key_v1, summary_v1)
    print(f"    attempt with v1 key: {outcome}")
    _, outcome = gateway.create_ticket(key_v2, summary_v2)
    print(f"    attempt with v2 key: {outcome}  <-- duplicate created")
    print(f"  tickets created: {gateway.created} -- the wrong-way retries")
    print("  added 2 duplicates. With the ticket-id key it stays 1.")


if __name__ == "__main__":
    demo()
