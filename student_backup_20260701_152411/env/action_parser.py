"""
Action Parser — Teacher-Provided Module

Parses and validates the format of Blocksworld action strings.
"""

import re
from typing import Optional, Tuple, List

# Pattern: ACTION_NAME(ARG1,ARG2,...)
_ACTION_RE = re.compile(r"^(PICKUP|PUTDOWN|UNSTACK|STACK)\(([A-Za-z0-9_,\s]*)\)$")


def validate_action_format(action: str) -> bool:
    """
    Return True if *action* is a syntactically valid Blocksworld action string.
    """
    return parse_action(action) is not None


def parse_action(action: str) -> Optional[Tuple[str, List[str]]]:
    """
    Parse an action string into (name, [args]).

    Returns
    -------
    Optional[Tuple[str, List[str]]]
        (action_name, [arg1, arg2, ...]) if valid, else None.

    Examples
    --------
    >>> parse_action("UNSTACK(C,A)")
    ("UNSTACK", ["C", "A"])
    >>> parse_action("PICKUP(A)")
    ("PICKUP", ["A"])
    >>> parse_action("INVALID(X)")
    None
    """
    if not isinstance(action, str):
        return None

    action = action.strip()
    m = _ACTION_RE.match(action)
    if not m:
        return None

    name = m.group(1)
    args_str = m.group(2).strip()

    if args_str == "":
        args = []
    else:
        args = [a.strip() for a in args_str.split(",") if a.strip()]

    # Validate argument count
    expected = {"PICKUP": 1, "PUTDOWN": 1, "UNSTACK": 2, "STACK": 2}
    if len(args) != expected.get(name, -1):
        return None

    return name, args
