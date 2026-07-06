"""
Blocksworld Environment — Teacher-Provided Module

Implements a classic Blocksworld domain with four actions:
    PICKUP(x), PUTDOWN(x), UNSTACK(x, y), STACK(x, y)

State is represented as a set of predicate strings.
"""

from typing import List, Dict, Optional, Set
from .action_parser import parse_action
from .validator import validate_step


class BlocksworldEnv:
    """Simplified Blocksworld environment for course use."""

    # ── valid actions & their signatures ──────────────────────────────
    ACTION_SIGNATURES = {
        "PICKUP":  1,   # PICKUP(x)
        "PUTDOWN": 1,   # PUTDOWN(x)
        "UNSTACK": 2,   # UNSTACK(x, y)
        "STACK":   2,   # STACK(x, y)
    }

    def __init__(self, blocks: List[str]):
        """
        Parameters
        ----------
        blocks : List[str]
            List of block names, e.g. ["A", "B", "C"].
        """
        self.blocks = set(blocks)
        self.state: Set[str] = set()
        self.initial_state: List[str] = []

    # ── public API ────────────────────────────────────────────────────

    def reset(self, initial_state: List[str]) -> None:
        """
        Reset the environment to the given initial state.

        Parameters
        ----------
        initial_state : List[str]
            Predicates describing the initial configuration, e.g.
            ["on(C,A)", "ontable(A)", "ontable(B)", "clear(C)", "clear(B)", "handempty"]
        """
        self.initial_state = list(initial_state)
        self.state = set(initial_state)

    def step(self, action: str) -> Dict:
        """
        Execute a single action and return the result.

        Parameters
        ----------
        action : str
            A Blocksworld action, e.g. "UNSTACK(C,A)".

        Returns
        -------
        dict
            {
                "success": bool,
                "message": str,
                "state": List[str]   # current state predicates
            }
        """
        parsed = parse_action(action)
        if parsed is None:
            return {
                "success": False,
                "message": f"Invalid action format: '{action}'",
                "state": sorted(self.state),
            }

        action_name, args = parsed
        valid, reason = validate_step(self.state, self.blocks, action_name, args)

        if not valid:
            return {
                "success": False,
                "message": f"Precondition not satisfied: {reason}",
                "state": sorted(self.state),
            }

        # apply effects
        self._apply_effects(action_name, args)
        return {
            "success": True,
            "message": "Action executed",
            "state": sorted(self.state),
        }

    def execute_plan(self, plan: List[str]) -> Dict:
        """
        Execute an entire plan (sequence of actions) from the *current* state.

        Parameters
        ----------
        plan : List[str]
            Ordered list of action strings.

        Returns
        -------
        dict
            {
                "plan_valid": bool,
                "failed_step": Optional[int],    # 0-indexed step where failure occurred
                "failed_action": Optional[str],  # the action that failed
                "final_state": List[str]
            }
        """
        for i, action in enumerate(plan):
            result = self.step(action)
            if not result["success"]:
                return {
                    "plan_valid": False,
                    "failed_step": i,
                    "failed_action": action,
                    "final_state": sorted(self.state),
                }
        return {
            "plan_valid": True,
            "failed_step": None,
            "failed_action": None,
            "final_state": sorted(self.state),
        }

    def is_goal_satisfied(self, goal_state: List[str]) -> bool:
        """
        Check whether every predicate in *goal_state* is present in the
        current state.

        Parameters
        ----------
        goal_state : List[str]
            Goal predicates.

        Returns
        -------
        bool
        """
        return set(goal_state).issubset(self.state)

    def render(self) -> str:
        """
        Return an ASCII visualisation of the current block stacks.

        Returns
        -------
        str
        """
        if not self.state:
            return "(empty state)"

        # Determine which blocks are being held
        holding = None
        on_table = set()
        on_map: Dict[str, str] = {}  # x -> y  (x is ON y)
        clear_set = set()
        handempty = False

        for p in self.state:
            if p == "handempty":
                handempty = True
            elif p.startswith("holding("):
                holding = p[8:-1]   # holding(x)
            elif p.startswith("ontable("):
                on_table.add(p[8:-1])
            elif p.startswith("on("):
                # on(x,y)
                inner = p[3:-1]
                x, y = inner.split(",", 1)
                on_map[x] = y
            elif p.startswith("clear("):
                clear_set.add(p[6:-1])

        if holding:
            on_table.add(holding)

        # Build stacks bottom-up
        # Find all blocks that are supported by something
        supported = set(on_map.keys())
        # Find bottom blocks (on table, not on another block)
        bottom_blocks = sorted(on_table - supported, key=lambda b: b)
        # Also blocks that are on table AND have something on them
        bottom_others = sorted(on_table & supported, key=lambda b: b)
        bottom_blocks = bottom_blocks + bottom_others

        lines: List[str] = []
        stacks: List[List[str]] = []

        # Build each stack
        for b in bottom_blocks:
            stack = [b]
            # Walk upwards
            while True:
                top = stack[-1]
                # Find block that is ON top
                above = [x for x, y in on_map.items() if y == top]
                if above:
                    stack.append(above[0])
                else:
                    break
            stacks.append(stack)

        # Render stacks side-by-side
        max_height = max(len(s) for s in stacks) if stacks else 0
        for level in range(max_height - 1, -1, -1):
            row_parts = []
            for s in stacks:
                if level < len(s):
                    row_parts.append(f" [{s[level]}] ")
                else:
                    row_parts.append("     ")
            lines.append("".join(row_parts))

        lines.append("-" * (len(stacks) * 5))
        lines.append("table")

        # Arm info
        if holding and not handempty:
            lines.insert(0, f"arm holding: [{holding}]")
        else:
            lines.insert(0, "arm: empty")

        return "\n".join(lines)

    # ── internal helpers ──────────────────────────────────────────────

    def _apply_effects(self, action_name: str, args: List[str]) -> None:
        """Apply the effects of *action_name* with *args* to self.state."""
        if action_name == "PICKUP":
            x = args[0]
            self.state.discard("ontable(" + x + ")")
            self.state.discard("clear(" + x + ")")
            self.state.discard("handempty")
            self.state.add("holding(" + x + ")")

        elif action_name == "PUTDOWN":
            x = args[0]
            self.state.discard("holding(" + x + ")")
            self.state.add("ontable(" + x + ")")
            self.state.add("clear(" + x + ")")
            self.state.add("handempty")

        elif action_name == "UNSTACK":
            x, y = args[0], args[1]
            self.state.discard("on(" + x + "," + y + ")")
            self.state.discard("clear(" + x + ")")
            self.state.discard("handempty")
            self.state.add("holding(" + x + ")")
            self.state.add("clear(" + y + ")")

        elif action_name == "STACK":
            x, y = args[0], args[1]
            self.state.discard("holding(" + x + ")")
            self.state.discard("clear(" + y + ")")
            self.state.add("on(" + x + "," + y + ")")
            self.state.add("clear(" + x + ")")
            self.state.add("handempty")
