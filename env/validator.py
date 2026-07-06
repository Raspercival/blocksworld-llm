"""
Validator — Teacher-Provided Module

Validates action preconditions and provides effect descriptions for the
Blocksworld domain.
"""

from typing import Set, List, Tuple


# ── action preconditions ─────────────────────────────────────────────

def get_action_preconditions(action_name: str, args: List[str]) -> Set[str]:
    """
    Return the set of predicates that must hold for *action_name*(*args)
    to be executable.

    Parameters
    ----------
    action_name : str
        One of PICKUP, PUTDOWN, UNSTACK, STACK.
    args : List[str]
        List of block arguments.

    Returns
    -------
    Set[str]
        Required predicates.
    """
    if action_name == "PICKUP":
        x = args[0]
        return {f"ontable({x})", f"clear({x})", "handempty"}

    elif action_name == "PUTDOWN":
        x = args[0]
        return {f"holding({x})"}

    elif action_name == "UNSTACK":
        x, y = args[0], args[1]
        return {f"on({x},{y})", f"clear({x})", "handempty"}

    elif action_name == "STACK":
        x, y = args[0], args[1]
        return {f"holding({x})", f"clear({y})"}
    else:
        return set()


def get_action_effects(action_name: str, args: List[str]) -> Tuple[Set[str], Set[str]]:
    """
    Return (add_set, delete_set) for an action.

    Parameters
    ----------
    action_name : str
    args : List[str]

    Returns
    -------
    Tuple[Set[str], Set[str]]
        (predicates to add, predicates to delete)
    """
    if action_name == "PICKUP":
        x = args[0]
        return ({f"holding({x})"},
                {f"ontable({x})", f"clear({x})", "handempty"})

    elif action_name == "PUTDOWN":
        x = args[0]
        return ({f"ontable({x})", f"clear({x})", "handempty"},
                {f"holding({x})"})

    elif action_name == "UNSTACK":
        x, y = args[0], args[1]
        return ({f"holding({x})", f"clear({y})"},
                {f"on({x},{y})", f"clear({x})", "handempty"})

    elif action_name == "STACK":
        x, y = args[0], args[1]
        return ({f"on({x},{y})", f"clear({x})", "handempty"},
                {f"holding({x})", f"clear({y})"})

    else:
        return (set(), set())


def validate_step(
    state: Set[str],
    blocks: Set[str],
    action_name: str,
    args: List[str],
) -> Tuple[bool, str]:
    """
    Check whether *action_name*(*args) is executable in *state*.

    Parameters
    ----------
    state : Set[str]
        Current set of true predicates.
    blocks : Set[str]
        Valid block names.
    action_name : str
    args : List[str]

    Returns
    -------
    Tuple[bool, str]
        (is_valid, reason_string)
    """
    # 1. Check that all arguments are known blocks
    for arg in args:
        if arg not in blocks:
            return False, f"unknown block '{arg}'"

    # 2. Check preconditions
    preconditions = get_action_preconditions(action_name, args)
    missing = preconditions - state
    if missing:
        return False, f"missing preconditions: {sorted(missing)}"

    return True, "ok"
