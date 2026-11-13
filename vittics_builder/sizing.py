"""How much process a project needs, judged from what it asks for.

The full process (assessment, department tickets, two reviewers per ticket, audits) is right for a product with
users and data. For a one-page local tool it was most of the cost: a personal checklist spent 86% of its tokens on
legal, support and documentation tickets. So Small is chosen only when the brief says the project is simple AND
asks for nothing heavy; anything else stays Standard, and the person can always pick the size themselves.
"""
from __future__ import annotations

import re

# Said plainly, these mean a small, local, self-contained tool. "simple" and "small" alone do not: a "small business
# invoicing system" is a product.
SIMPLE = re.compile(
    r"\b(single[- ]page|one[- ]page|static|calculator|checklist|personal|local(ly|storage)?|browser[- ]only|"
    r"plain html|offline|tiny|to-?do (list|app))\b", re.I)

# These mean accounts, data, other people or infrastructure: a real product.
HEAVY = re.compile(
    r"\b(log[- ]?in|sign[- ]?(in|up)|authenticat\w*|authoriz\w*|accounts?|passwords?|oauth|sso|"
    r"database|postgres\w*|mysql|sqlite|mongo\w*|redis|"
    r"payments?|stripe|billing|checkout|subscriptions?|"
    r"back-?end|server|apis?|rest|graphql|websockets?|real-?time|multi-?user|multi-?tenant|tenants?|"
    r"teams?|collaborat\w*|shared?|sharing|customers?|clients?|employees|staff|enterprise|organi[sz]ations?|portal|"
    r"marketplace|deploy\w*|hosting|docker|kubernetes|microservices?|"
    r"mobile app|ios|android|notifications?|e-?mail|admin|dashboard|integrat\w*)\b", re.I)

# "No backend, login or deployment." says what the project does NOT need: ignore that clause.
NEGATED = re.compile(r"\b(no|not|without|never|avoid|exclude|excluding|except|don't|do not)\b[^.\n;]*", re.I)

MAX_SIMPLE_BRIEF = 1500


def suggest_size(brief: str) -> tuple[str, str]:
    """('small' | 'standard', why). Conservative: when in doubt, Standard."""
    text = brief or ""
    wanted = NEGATED.sub(" ", text)
    heavy = sorted({m.group(0).lower() for m in HEAVY.finditer(wanted)})
    simple = sorted({m.group(0).lower() for m in SIMPLE.finditer(text)})
    if heavy:
        return "standard", "It asks for " + ", ".join(heavy[:4]) + ", which is a product, not a small tool."
    if len(text) > MAX_SIMPLE_BRIEF:
        return "standard", "The brief is long, so there is a lot to build."
    if not simple:
        return "standard", "Nothing in the brief says it is a small tool."
    return "small", "It is described as " + ", ".join(simple[:3]) + ", with no accounts, database, payments or backend."
