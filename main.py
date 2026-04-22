from __future__ import annotations

import sys

from ifp_ast import TBool, TInt, TString, Term
from interpreter import InterpreterError, interpret
from parser import ParseError, p_term
from printer import pp_term


def _render_value(term: Term) -> str:
    if isinstance(term, TInt):
        return str(term.value)
    if isinstance(term, TBool):
        return "true" if term.value else "false"
    if isinstance(term, TString):
        return term.value
    return pp_term(term)


def cmd_eval(program: str, check_max: bool) -> int:
    try:
        term = p_term(program)
        result, steps = interpret(check_max=check_max, term=term)
    except ParseError as exc:
        print(f"Parse error: {exc}", file=sys.stderr)
        return 2
    except InterpreterError as exc:
        print(f"Interpreter error: {exc}", file=sys.stderr)
        return 3

    print(f"Result (human): {_render_value(result)}")
    print(f"Result (encoded term): {pp_term(result)}")
    print(f"Steps: {steps}")
    return 0


def main() -> int:
    print("Enter encoded phrase to evaluate:")
    try:
        program = input().strip()
    except EOFError:
        print("No input program provided.", file=sys.stderr)
        return 1

    if not program:
        print("No input program provided.", file=sys.stderr)
        return 1

    return cmd_eval(program, check_max=False)


if __name__ == "__main__":
    raise SystemExit(main())
