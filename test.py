from __future__ import annotations

from dataclasses import dataclass
from typing import Type

import interpreter
from ifp_ast import TBool, TInt, TString, Term
from interpreter import (
    ArithmeticError_,
    BetaReductionLimit,
    InterpreterError,
    ScopeError,
    TypeError_,
    interpret,
)
from parser import ParseError, p_term
from printer import encode_string, pp_term, to_base94


# ============================================================
# Helper functions to build encoded IFP programs safely
# ============================================================

def I(n: int) -> str:
    """
    Build an encoded integer term.
    For negative numbers, build unary negation because integer literal itself is non-negative.
    """
    if n < 0:
        return f"U- {I(-n)}"
    return "I" + to_base94(n)


def S(text: str) -> str:
    return "S" + encode_string(text)


def V(var_id: int) -> str:
    return "v" + to_base94(var_id)


def L(var_id: int, body: str) -> str:
    return "L" + to_base94(var_id) + " " + body


def U(op: str, term: str) -> str:
    return "U" + op + " " + term


def B(op: str, left: str, right: str) -> str:
    return "B" + op + " " + left + " " + right


def IF(cond: str, true_branch: str, false_branch: str) -> str:
    return "? " + cond + " " + true_branch + " " + false_branch


def APP(func: str, arg: str) -> str:
    return B("$", func, arg)


def render_value(term: Term) -> str:
    if isinstance(term, TInt):
        return str(term.value)
    if isinstance(term, TBool):
        return "true" if term.value else "false"
    if isinstance(term, TString):
        return term.value
    return pp_term(term)


# ============================================================
# Test case structures
# ============================================================

@dataclass(frozen=True)
class EvalCase:
    name: str
    program: str
    expected: Term | None = None
    expected_error: Type[Exception] | None = None
    check_max: bool = True
    patch_max_steps: int | None = None


@dataclass(frozen=True)
class ParseCase:
    name: str
    program: str
    expected_error_kind: str


# ============================================================
# Evaluation test cases
# ============================================================

EVAL_CASES: list[EvalCase] = [
    # --------------------------------------------------------
    # 1. Literal + base-94 parsing
    # --------------------------------------------------------
    EvalCase(
        name="bool true literal",
        program="T",
        expected=TBool(True),
    ),
    EvalCase(
        name="bool false literal",
        program="F",
        expected=TBool(False),
    ),
    EvalCase(
        name="integer base-94 example: I/6 -> 1337",
        program="I/6",
        expected=TInt(1337),
    ),
    EvalCase(
        name="integer zero",
        program=I(0),
        expected=TInt(0),
    ),
    EvalCase(
        name="empty string literal",
        program=S(""),
        expected=TString(""),
    ),
    EvalCase(
        name="string with space and punctuation",
        program=S("Hello World!"),
        expected=TString("Hello World!"),
    ),
    EvalCase(
        name="string with newline",
        program=S("line\nbreak"),
        expected=TString("line\nbreak"),
    ),

    # --------------------------------------------------------
    # 2. Unary operators
    # --------------------------------------------------------
    EvalCase(
        name="unary integer negation",
        program=U("-", I(3)),
        expected=TInt(-3),
    ),
    EvalCase(
        name="unary boolean negation true -> false",
        program=U("!", "T"),
        expected=TBool(False),
    ),
    EvalCase(
        name="unary boolean negation false -> true",
        program=U("!", "F"),
        expected=TBool(True),
    ),
    EvalCase(
        name="string to integer: test -> 15818151",
        program=U("#", S("test")),
        expected=TInt(15818151),
    ),
    EvalCase(
        name="integer to string: 15818151 -> test",
        program=U("$", I(15818151)),
        expected=TString("test"),
    ),
    EvalCase(
        name="string-int-string round trip",
        program=U("$", U("#", S("Hello World!"))),
        expected=TString("Hello World!"),
    ),
    EvalCase(
        name="int-string-int round trip",
        program=U("#", U("$", I(15818151))),
        expected=TInt(15818151),
    ),

    # --------------------------------------------------------
    # 3. Arithmetic operators
    # --------------------------------------------------------
    EvalCase(
        name="addition",
        program=B("+", I(2), I(3)),
        expected=TInt(5),
    ),
    EvalCase(
        name="subtraction",
        program=B("-", I(3), I(2)),
        expected=TInt(1),
    ),
    EvalCase(
        name="multiplication",
        program=B("*", I(6), I(7)),
        expected=TInt(42),
    ),
    EvalCase(
        name="division positive",
        program=B("/", I(7), I(2)),
        expected=TInt(3),
    ),
    EvalCase(
        name="division truncate toward zero with negative number",
        program=B("/", I(-7), I(2)),
        expected=TInt(-3),
    ),
    EvalCase(
        name="modulo with negative number follows assignment example",
        program=B("%", I(-7), I(2)),
        expected=TInt(-1),
    ),
    EvalCase(
        name="division by zero should raise ArithmeticError_",
        program=B("/", I(1), I(0)),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="modulo by zero should raise ArithmeticError_",
        program=B("%", I(1), I(0)),
        expected_error=ArithmeticError_,
    ),

    # --------------------------------------------------------
    # 4. Comparison and equality
    # --------------------------------------------------------
    EvalCase(
        name="less than true",
        program=B("<", I(2), I(3)),
        expected=TBool(True),
    ),
    EvalCase(
        name="less than false",
        program=B("<", I(3), I(2)),
        expected=TBool(False),
    ),
    EvalCase(
        name="greater than true",
        program=B(">", I(3), I(2)),
        expected=TBool(True),
    ),
    EvalCase(
        name="integer equality true",
        program=B("=", I(3), I(3)),
        expected=TBool(True),
    ),
    EvalCase(
        name="integer equality false",
        program=B("=", I(3), I(2)),
        expected=TBool(False),
    ),
    EvalCase(
        name="string equality true",
        program=B("=", S("abc"), S("abc")),
        expected=TBool(True),
    ),
    EvalCase(
        name="boolean equality true",
        program=B("=", "T", "T"),
        expected=TBool(True),
    ),

    # --------------------------------------------------------
    # 5. Boolean binary operators
    # Built-in binary operators should be strict except B$.
    # Therefore B| and B& should still evaluate both sides.
    # --------------------------------------------------------
    EvalCase(
        name="boolean OR",
        program=B("|", "T", "F"),
        expected=TBool(True),
    ),
    EvalCase(
        name="boolean AND",
        program=B("&", "T", "F"),
        expected=TBool(False),
    ),
    EvalCase(
        name="strict OR should evaluate right side and raise error",
        program=B("|", "T", B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="strict AND should evaluate right side and raise error",
        program=B("&", "F", B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),

    # --------------------------------------------------------
    # 6. String binary operators
    # --------------------------------------------------------
    EvalCase(
        name="string concatenation",
        program=B(".", S("te"), S("st")),
        expected=TString("test"),
    ),
    EvalCase(
        name="take first 3 characters",
        program=B("T", I(3), S("test")),
        expected=TString("tes"),
    ),
    EvalCase(
        name="drop first 3 characters",
        program=B("D", I(3), S("test")),
        expected=TString("t"),
    ),
    EvalCase(
        name="take zero characters",
        program=B("T", I(0), S("test")),
        expected=TString(""),
    ),
    EvalCase(
        name="drop zero characters",
        program=B("D", I(0), S("test")),
        expected=TString("test"),
    ),
    EvalCase(
        name="take more than string length",
        program=B("T", I(99), S("test")),
        expected=TString("test"),
    ),
    EvalCase(
        name="drop more than string length",
        program=B("D", I(99), S("test")),
        expected=TString(""),
    ),

    # --------------------------------------------------------
    # 7. Conditional expression
    # Important: only selected branch is evaluated.
    # --------------------------------------------------------
    EvalCase(
        name="if true selects true branch",
        program=IF("T", S("yes"), S("no")),
        expected=TString("yes"),
    ),
    EvalCase(
        name="if false selects false branch",
        program=IF("F", S("yes"), S("no")),
        expected=TString("no"),
    ),
    EvalCase(
        name="if true must not evaluate false branch",
        program=IF("T", I(3), B("/", I(1), I(0))),
        expected=TInt(3),
    ),
    EvalCase(
        name="if false must not evaluate true branch",
        program=IF("F", B("/", I(1), I(0)), I(4)),
        expected=TInt(4),
    ),
    EvalCase(
        name="if condition must be boolean",
        program=IF(I(1), I(2), I(3)),
        expected_error=TypeError_,
    ),

    # --------------------------------------------------------
    # 8. Lambda and function application
    # --------------------------------------------------------
    EvalCase(
        name="identity function",
        program=APP(L(0, V(0)), I(42)),
        expected=TInt(42),
    ),
    EvalCase(
        name="constant function ignores argument",
        program=APP(L(0, I(3)), I(999)),
        expected=TInt(3),
    ),
    EvalCase(
        name="function application with arithmetic body",
        program=APP(L(0, B("+", V(0), I(1))), I(41)),
        expected=TInt(42),
    ),
    EvalCase(
        name="nested lambda: ((lambda x. lambda y. x) 3) 4 -> 3",
        program=APP(APP(L(0, L(1, V(0))), I(3)), I(4)),
        expected=TInt(3),
    ),
    EvalCase(
        name="nested lambda: ((lambda x. lambda y. y) 3) 4 -> 4",
        program=APP(APP(L(0, L(1, V(1))), I(3)), I(4)),
        expected=TInt(4),
    ),
    EvalCase(
        name="shadowing: inner variable should hide outer variable",
        program=APP(L(0, APP(L(0, V(0)), I(3))), I(4)),
        expected=TInt(3),
    ),

    # --------------------------------------------------------
    # 9. Call-by-name behavior
    # --------------------------------------------------------
    EvalCase(
        name="call-by-name: ignored argument must not be evaluated",
        program=APP(L(0, I(3)), B("/", I(1), I(0))),
        expected=TInt(3),
    ),
    EvalCase(
        name="call-by-name: argument evaluated only when variable is needed",
        program=APP(L(0, B("+", V(0), I(1))), B("*", I(5), I(8))),
        expected=TInt(41),
    ),
    EvalCase(
        name="repeated variable use: substituted expression appears twice",
        program=APP(L(0, B("+", V(0), V(0))), B("*", I(3), I(4))),
        expected=TInt(24),
    ),

    # --------------------------------------------------------
    # 10. Capture-avoidance / lexical scoping stress test
    #
    # Program meaning:
    #   (lambda y.
    #       ((lambda x. lambda y. x) y) 5
    #   ) 3
    #
    # Correct capture-avoiding result: 3
    # A naive substitution that captures y may incorrectly return 5.
    # --------------------------------------------------------
    EvalCase(
        name="capture avoidance: free y in argument must not be captured by inner lambda",
        program=APP(
            L(
                0,
                APP(
                    APP(
                        L(1, L(0, V(1))),
                        V(0),
                    ),
                    I(5),
                ),
            ),
            I(3),
        ),
        expected=TInt(3),
    ),

    # --------------------------------------------------------
    # 11. Official-style examples from specification
    # --------------------------------------------------------
    EvalCase(
        name="spec-style example: ((lambda v2. lambda v3. v2) ('Hello' . ' World!')) 42",
        program=APP(
            APP(
                L(2, L(3, V(2))),
                B(".", S("Hello"), S(" World!")),
            ),
            I(42),
        ),
        expected=TString("Hello World!"),
    ),
    EvalCase(
        name="spec-style call-by-name reduction example",
        program=APP(
            L(2, APP(L(1, B("+", V(1), V(1))), B("*", I(3), I(2)))),
            V(23),
        ),
        expected=TInt(12),
    ),

    # --------------------------------------------------------
    # 12. Runtime error edge cases
    # --------------------------------------------------------
    EvalCase(
        name="undefined variable should raise ScopeError",
        program=V(0),
        expected_error=ScopeError,
    ),
    EvalCase(
        name="wrong type for addition should raise TypeError_",
        program=B("+", I(1), S("abc")),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="wrong type for unary ! should raise TypeError_",
        program=U("!", I(1)),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="applying non-function should raise TypeError_",
        program=APP(I(1), I(2)),
        expected_error=TypeError_,
    ),

    # --------------------------------------------------------
    # 13. Beta-reduction limit
    #
    # Omega expression:
    #   (lambda x. x x) (lambda x. x x)
    #
    # This does not terminate. We patch MAX_STEPS to a small number
    # so the test finishes quickly.
    # --------------------------------------------------------
    EvalCase(
        name="beta-reduction limit on omega expression",
        program=APP(
            L(0, APP(V(0), V(0))),
            L(0, APP(V(0), V(0))),
        ),
        expected_error=BetaReductionLimit,
        check_max=True,
        patch_max_steps=30,
    ),
]


# ============================================================
# Parser error tests
# These are useful while implementing parser.py.
# All official grading inputs are syntactically valid, but your
# parser should still fail clearly on invalid input.
# ============================================================

PARSE_ERROR_CASES: list[ParseCase] = [
    ParseCase(
        name="unexpected EOF after unary operator",
        program="U-",
        expected_error_kind="UnexpectedEOF",
    ),
    ParseCase(
        name="unused input after complete expression",
        program="T F",
        expected_error_kind="UnusedInput",
    ),
    ParseCase(
        name="unexpected indicator character",
        program="@",
        expected_error_kind="UnexpectedChar",
    ),
]


# ============================================================
# Test runners
# ============================================================

def run_eval_case(case: EvalCase) -> bool:
    old_max_steps = interpreter.MAX_STEPS

    try:
        if case.patch_max_steps is not None:
            interpreter.MAX_STEPS = case.patch_max_steps

        term = p_term(case.program)

        try:
            result, steps = interpret(check_max=case.check_max, term=term)
        except Exception as exc:
            if case.expected_error is not None and isinstance(exc, case.expected_error):
                print(f"[PASS] {case.name}")
                print(f"       expected error: {case.expected_error.__name__}")
                print(f"       got error     : {type(exc).__name__}")
                return True

            print(f"[FAIL] {case.name}")
            print(f"       program       : {case.program}")
            print(f"       unexpected err: {type(exc).__name__}: {exc}")
            if case.expected is not None:
                print(f"       expected      : {pp_term(case.expected)} ({render_value(case.expected)!r})")
            return False

        if case.expected_error is not None:
            print(f"[FAIL] {case.name}")
            print(f"       program       : {case.program}")
            print(f"       expected error: {case.expected_error.__name__}")
            print(f"       got result    : {pp_term(result)} ({render_value(result)!r})")
            return False

        if result != case.expected:
            print(f"[FAIL] {case.name}")
            print(f"       program       : {case.program}")
            print(f"       expected      : {pp_term(case.expected)} ({render_value(case.expected)!r})")
            print(f"       got           : {pp_term(result)} ({render_value(result)!r})")
            print(f"       steps         : {steps}")
            return False

        print(f"[PASS] {case.name}")
        print(f"       result        : {pp_term(result)} ({render_value(result)!r})")
        print(f"       steps         : {steps}")
        return True

    finally:
        interpreter.MAX_STEPS = old_max_steps


def run_parse_error_case(case: ParseCase) -> bool:
    try:
        result = p_term(case.program)
    except ParseError as exc:
        if exc.kind == case.expected_error_kind:
            print(f"[PASS] {case.name}")
            print(f"       expected parse error: {case.expected_error_kind}")
            print(f"       got parse error     : {exc}")
            return True

        print(f"[FAIL] {case.name}")
        print(f"       expected parse error: {case.expected_error_kind}")
        print(f"       got parse error     : {exc.kind}")
        return False

    except Exception as exc:
        print(f"[FAIL] {case.name}")
        print(f"       expected ParseError : {case.expected_error_kind}")
        print(f"       got other error     : {type(exc).__name__}: {exc}")
        return False

    print(f"[FAIL] {case.name}")
    print(f"       expected parse error: {case.expected_error_kind}")
    print(f"       got parsed result   : {result}")
    return False


def run_printer_roundtrip_tests() -> tuple[int, int]:
    """
    These tests check:
    - p_term can parse generated programs.
    - pp_term can print back an equivalent encoded term.
    - p_term(pp_term(p_term(program))) is structurally stable.
    """
    programs = [
        "T",
        "F",
        I(0),
        I(1337),
        S(""),
        S("Hello World!"),
        S("line\nbreak"),
        U("-", I(3)),
        U("!", "T"),
        B("+", I(2), I(3)),
        B(".", S("te"), S("st")),
        IF("T", I(1), I(2)),
        L(0, V(0)),
        APP(L(0, V(0)), I(42)),
        APP(APP(L(0, L(1, V(0))), I(3)), I(4)),
    ]

    passed = 0
    total = len(programs)

    for index, program in enumerate(programs, start=1):
        name = f"printer/parser roundtrip #{index}"

        try:
            term1 = p_term(program)
            encoded = pp_term(term1)
            term2 = p_term(encoded)
        except Exception as exc:
            print(f"[FAIL] {name}")
            print(f"       program: {program}")
            print(f"       error  : {type(exc).__name__}: {exc}")
            continue

        if term1 != term2:
            print(f"[FAIL] {name}")
            print(f"       original program: {program}")
            print(f"       printed program : {encoded}")
            print(f"       term1           : {term1}")
            print(f"       term2           : {term2}")
            continue

        print(f"[PASS] {name}")
        print(f"       encoded: {encoded}")
        passed += 1

    return passed, total


def main() -> int:
    print("=" * 72)
    print("IFP MINI INTERPRETER TEST SUITE")
    print("=" * 72)

    total = 0
    passed = 0

    print("\n[1] EVALUATION TESTS")
    print("-" * 72)
    for case in EVAL_CASES:
        total += 1
        if run_eval_case(case):
            passed += 1

    print("\n[2] PARSER ERROR TESTS")
    print("-" * 72)
    for case in PARSE_ERROR_CASES:
        total += 1
        if run_parse_error_case(case):
            passed += 1

    print("\n[3] PRINTER / PARSER ROUNDTRIP TESTS")
    print("-" * 72)
    roundtrip_passed, roundtrip_total = run_printer_roundtrip_tests()
    passed += roundtrip_passed
    total += roundtrip_total

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("ALL TESTS PASSED")
        return 0

    print("SOME TESTS FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())