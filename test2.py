from __future__ import annotations

from dataclasses import dataclass
from typing import Type

import interpreter
from ifp_ast import TBinOp, TBool, TInt, TLam, TString, TVar, Term
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
    Negative integers are represented using unary negation.
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
# Difficult evaluation tests
# ============================================================

EVAL_CASES: list[EvalCase] = [
    # --------------------------------------------------------
    # 1. Large arithmetic / base-94 / negative-number edge cases
    # --------------------------------------------------------
    EvalCase(
        name="large integer base-94 value",
        program=I(987654321),
        expected=TInt(987654321),
    ),
    EvalCase(
        name="large integer arithmetic",
        program=B("+", I(987654321), I(123456789)),
        expected=TInt(1111111110),
    ),
    EvalCase(
        name="large multiplication",
        program=B("*", I(12345), I(6789)),
        expected=TInt(83810205),
    ),
    EvalCase(
        name="subtraction gives negative result",
        program=B("-", I(2), I(10)),
        expected=TInt(-8),
    ),
    EvalCase(
        name="negative plus positive",
        program=B("+", I(-20), I(7)),
        expected=TInt(-13),
    ),
    EvalCase(
        name="negative minus negative",
        program=B("-", I(-20), I(-7)),
        expected=TInt(-13),
    ),
    EvalCase(
        name="negative times negative",
        program=B("*", I(-6), I(-7)),
        expected=TInt(42),
    ),
    EvalCase(
        name="positive divided by negative truncates toward zero",
        program=B("/", I(7), I(-2)),
        expected=TInt(-3),
    ),
    EvalCase(
        name="negative divided by negative truncates toward zero",
        program=B("/", I(-7), I(-2)),
        expected=TInt(3),
    ),
    EvalCase(
        name="positive modulo negative",
        program=B("%", I(7), I(-2)),
        expected=TInt(1),
    ),
    EvalCase(
        name="negative modulo negative",
        program=B("%", I(-7), I(-2)),
        expected=TInt(-1),
    ),

    # --------------------------------------------------------
    # 2. Difficult string cases
    # --------------------------------------------------------
    EvalCase(
        name="string with many common symbols",
        program=S("abcXYZ012!@#$%^&*()_+-=[]:;,.?/"),
        expected=TString("abcXYZ012!@#$%^&*()_+-=[]:;,.?/"),
    ),
    EvalCase(
        name="concatenate empty string left",
        program=B(".", S(""), S("abc")),
        expected=TString("abc"),
    ),
    EvalCase(
        name="concatenate empty string right",
        program=B(".", S("abc"), S("")),
        expected=TString("abc"),
    ),
    EvalCase(
        name="concatenate two empty strings",
        program=B(".", S(""), S("")),
        expected=TString(""),
    ),
    EvalCase(
        name="take from empty string",
        program=B("T", I(3), S("")),
        expected=TString(""),
    ),
    EvalCase(
        name="drop from empty string",
        program=B("D", I(3), S("")),
        expected=TString(""),
    ),
    EvalCase(
        name="take exact string length",
        program=B("T", I(4), S("test")),
        expected=TString("test"),
    ),
    EvalCase(
        name="drop exact string length",
        program=B("D", I(4), S("test")),
        expected=TString(""),
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
    EvalCase(
        name="string conversion with empty string to int",
        program=U("#", S("")),
        expected=TInt(0),
    ),
    EvalCase(
        name="integer zero to string",
        program=U("$", I(0)),
        expected=TString("a"),
    ),
    EvalCase(
        name="string-int-string round trip with newline and symbols",
        program=U("$", U("#", S("a B!\nZ9"))),
        expected=TString(" B!\nZ9"),
    ),

    # --------------------------------------------------------
    # 3. Deep conditional laziness
    # --------------------------------------------------------
    EvalCase(
        name="nested if should only evaluate selected path 1",
        program=IF(
            B("=", I(1), I(1)),
            IF("T", S("safe"), B("/", I(1), I(0))),
            B("/", I(1), I(0)),
        ),
        expected=TString("safe"),
    ),
    EvalCase(
        name="nested if should only evaluate selected path 2",
        program=IF(
            B("=", I(1), I(2)),
            B("/", I(1), I(0)),
            IF("F", B("/", I(1), I(0)), S("safe")),
        ),
        expected=TString("safe"),
    ),
    EvalCase(
        name="if condition is evaluated before branch",
        program=IF(B("/", I(1), I(0)), I(1), I(2)),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="if selected branch can contain lambda application",
        program=IF(
            "T",
            APP(L(0, B("+", V(0), I(10))), I(5)),
            B("/", I(1), I(0)),
        ),
        expected=TInt(15),
    ),
    EvalCase(
        name="if unselected branch contains undefined variable",
        program=IF("T", I(42), V(999)),
        expected=TInt(42),
    ),
    EvalCase(
        name="if selected branch contains undefined variable",
        program=IF("F", I(42), V(999)),
        expected_error=ScopeError,
    ),

    # --------------------------------------------------------
    # 4. Strict built-in operator tests
    # All built-in operators except B$ should evaluate operands.
    # --------------------------------------------------------
    EvalCase(
        name="strict addition evaluates left error",
        program=B("+", B("/", I(1), I(0)), I(2)),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="strict addition evaluates right error",
        program=B("+", I(2), B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="strict equality evaluates both sides",
        program=B("=", I(2), B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="strict OR evaluates right side even when left is true",
        program=B("|", "T", B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="strict AND evaluates right side even when left is false",
        program=B("&", "F", B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="strict string concat evaluates right side",
        program=B(".", S("abc"), B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="strict take evaluates string expression",
        program=B("T", I(1), B("/", I(1), I(0))),
        expected_error=ArithmeticError_,
    ),

    # --------------------------------------------------------
    # 5. Difficult lambda / closure / shadowing tests
    # --------------------------------------------------------
    EvalCase(
        name="closure captures outer variable",
        program=APP(
            APP(L(0, L(1, B("+", V(0), V(1)))), I(10)),
            I(32),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="closure captures outer variable after nested application",
        program=APP(
            L(0, APP(L(1, B("+", V(0), V(1))), I(7))),
            I(35),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="three-level lambda application",
        program=APP(
            APP(
                APP(
                    L(0, L(1, L(2, B("+", B("+", V(0), V(1)), V(2))))),
                    I(10),
                ),
                I(20),
            ),
            I(12),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="shadowing many levels 1",
        program=APP(
            L(0, APP(L(0, APP(L(0, V(0)), I(3))), I(2))),
            I(1),
        ),
        expected=TInt(3),
    ),
    EvalCase(
        name="shadowing many levels 2",
        program=APP(
            L(0, B("+", APP(L(0, V(0)), I(10)), V(0))),
            I(32),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="lambda returns lambda without applying inner one",
        program=APP(L(0, L(1, V(0))), I(42)),
        expected=TLam(1, TVar(0)),
    ),
    EvalCase(
        name="returned lambda then applied should use captured value",
        program=APP(APP(L(0, L(1, V(0))), I(42)), I(999)),
        expected=TInt(42),
    ),

    # --------------------------------------------------------
    # 6. Call-by-name difficult tests
    # --------------------------------------------------------
    EvalCase(
        name="call-by-name deeply ignored dangerous expression",
        program=APP(
            L(0, APP(L(1, I(42)), V(0))),
            B("/", I(1), I(0)),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="call-by-name dangerous expression evaluated when used",
        program=APP(
            L(0, APP(L(1, V(0)), I(42))),
            B("/", I(1), I(0)),
        ),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="call-by-name repeated dangerous expression in unused branch is safe",
        program=APP(
            L(0, IF("T", I(42), B("+", V(0), V(0)))),
            B("/", I(1), I(0)),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="call-by-name repeated dangerous expression in selected branch fails",
        program=APP(
            L(0, IF("F", I(42), B("+", V(0), V(0)))),
            B("/", I(1), I(0)),
        ),
        expected_error=ArithmeticError_,
    ),
    EvalCase(
        name="call-by-name argument used inside nested lambda",
        program=APP(
            L(0, APP(L(1, B("+", V(0), V(1))), I(2))),
            B("*", I(20), I(2)),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="ignored omega argument should not loop",
        program=APP(
            L(0, I(42)),
            APP(L(1, APP(V(1), V(1))), L(1, APP(V(1), V(1)))),
        ),
        expected=TInt(42),
        check_max=True,
        patch_max_steps=30,
    ),

    # --------------------------------------------------------
    # 7. Higher-order function tests
    # --------------------------------------------------------
    EvalCase(
        name="apply function argument once",
        program=APP(
            APP(
                L(0, L(1, APP(V(0), V(1)))),
                L(2, B("+", V(2), I(1))),
            ),
            I(41),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="apply function argument twice",
        program=APP(
            APP(
                L(0, L(1, APP(V(0), APP(V(0), V(1))))),
                L(2, B("+", V(2), I(1))),
            ),
            I(40),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="compose two functions",
        program=APP(
            APP(
                APP(
                    L(0, L(1, L(2, APP(V(0), APP(V(1), V(2)))))),
                    L(3, B("*", V(3), I(2))),
                ),
                L(4, B("+", V(4), I(1))),
            ),
            I(20),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="higher-order constant function ignores dangerous second argument",
        program=APP(
            APP(L(0, L(1, V(0))), L(2, B("+", V(2), I(1)))),
            B("/", I(1), I(0)),
        ),
        expected=TLam(2, TBinOp(TVar(2), "+", TInt(1))),
    ),

    # --------------------------------------------------------
    # 8. Capture avoidance stress tests
    # --------------------------------------------------------
    EvalCase(
        name="capture avoidance stress 1",
        program=APP(
            L(
                0,
                APP(
                    APP(L(1, L(0, B("+", V(1), V(0)))), V(0)),
                    I(2),
                ),
            ),
            I(40),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="capture avoidance stress 2",
        program=APP(
            L(
                0,
                APP(
                    APP(L(1, L(2, B("+", V(1), V(2)))), V(0)),
                    I(7),
                ),
            ),
            I(35),
        ),
        expected=TInt(42),
    ),
    EvalCase(
        name="capture avoidance with same inner variable name",
        program=APP(
            L(
                0,
                APP(
                    APP(L(1, L(0, V(1))), V(0)),
                    I(999),
                ),
            ),
            I(42),
        ),
        expected=TInt(42),
    ),

    # --------------------------------------------------------
    # 9. Type mismatch edge cases
    # --------------------------------------------------------
    EvalCase(
        name="less than with string should fail",
        program=B("<", S("a"), S("b")),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="greater than with bool should fail",
        program=B(">", "T", "F"),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="boolean OR with integer should fail",
        program=B("|", I(1), "F"),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="boolean AND with string should fail",
        program=B("&", S("x"), "T"),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="string concat with int should fail",
        program=B(".", S("x"), I(1)),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="take with string count should fail",
        program=B("T", S("1"), S("abc")),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="drop with bool count should fail",
        program=B("D", "T", S("abc")),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="unary string-to-int with integer should fail",
        program=U("#", I(123)),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="unary int-to-string with string should fail",
        program=U("$", S("abc")),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="unary negation with bool should fail",
        program=U("-", "T"),
        expected_error=TypeError_,
    ),
    EvalCase(
        name="applying non-function should fail",
        program=APP(I(1), I(2)),
        expected_error=TypeError_,
    ),

    # --------------------------------------------------------
    # 10. Unknown operator tests
    # --------------------------------------------------------
    EvalCase(
        name="unknown unary operator should fail",
        program=U("~", I(1)),
        expected_error=InterpreterError,
    ),
    EvalCase(
        name="unknown binary operator should fail",
        program=B("~", I(1), I(2)),
        expected_error=InterpreterError,
    ),

    # --------------------------------------------------------
    # 11. Beta-reduction limit tests
    # --------------------------------------------------------
    EvalCase(
        name="beta limit with omega expression",
        program=APP(
            L(0, APP(V(0), V(0))),
            L(0, APP(V(0), V(0))),
        ),
        expected_error=BetaReductionLimit,
        check_max=True,
        patch_max_steps=30,
    ),
    EvalCase(
        name="beta limit with self application hidden in selected if branch",
        program=IF(
            "T",
            APP(L(0, APP(V(0), V(0))), L(0, APP(V(0), V(0)))),
            I(42),
        ),
        expected_error=BetaReductionLimit,
        check_max=True,
        patch_max_steps=30,
    ),
    EvalCase(
        name="beta limit should not trigger if infinite expression is unselected branch",
        program=IF(
            "F",
            APP(L(0, APP(V(0), V(0))), L(0, APP(V(0), V(0)))),
            I(42),
        ),
        expected=TInt(42),
        check_max=True,
        patch_max_steps=30,
    ),
]


# ============================================================
# Parser error tests
# ============================================================

PARSE_ERROR_CASES: list[ParseCase] = [
    ParseCase(
        name="empty input should raise UnexpectedEOF",
        program="",
        expected_error_kind="UnexpectedEOF",
    ),
    ParseCase(
        name="unexpected EOF after unary operator",
        program="U-",
        expected_error_kind="UnexpectedEOF",
    ),
    ParseCase(
        name="binary operator missing right operand",
        program="B+ " + I(1),
        expected_error_kind="UnexpectedEOF",
    ),
    ParseCase(
        name="lambda missing body",
        program="L" + to_base94(0),
        expected_error_kind="UnexpectedEOF",
    ),
    ParseCase(
        name="if missing false branch",
        program="? T " + I(1),
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
# Runners
# ============================================================

def run_eval_case(case: EvalCase) -> bool:
    old_max_steps = interpreter.MAX_STEPS

    try:
        if case.patch_max_steps is not None:
            interpreter.MAX_STEPS = case.patch_max_steps

        try:
            term = p_term(case.program)
        except Exception as exc:
            print(f"[FAIL] {case.name}")
            print(f"       parser error   : {type(exc).__name__}: {exc}")
            print(f"       program        : {case.program}")
            return False

        try:
            result, steps = interpret(check_max=case.check_max, term=term)
        except Exception as exc:
            if case.expected_error is not None and isinstance(exc, case.expected_error):
                print(f"[PASS] {case.name}")
                print(f"       expected error : {case.expected_error.__name__}")
                print(f"       got error      : {type(exc).__name__}")
                return True

            print(f"[FAIL] {case.name}")
            print(f"       program        : {case.program}")
            print(f"       unexpected err : {type(exc).__name__}: {exc}")
            if case.expected is not None:
                print(f"       expected       : {pp_term(case.expected)} ({render_value(case.expected)!r})")
            return False

        if case.expected_error is not None:
            print(f"[FAIL] {case.name}")
            print(f"       program        : {case.program}")
            print(f"       expected error : {case.expected_error.__name__}")
            print(f"       got result     : {pp_term(result)} ({render_value(result)!r})")
            print(f"       steps          : {steps}")
            return False

        if result != case.expected:
            print(f"[FAIL] {case.name}")
            print(f"       program        : {case.program}")
            print(f"       expected       : {pp_term(case.expected)} ({render_value(case.expected)!r})")
            print(f"       got            : {pp_term(result)} ({render_value(result)!r})")
            print(f"       steps          : {steps}")
            return False

        print(f"[PASS] {case.name}")
        print(f"       result         : {pp_term(result)} ({render_value(result)!r})")
        print(f"       steps          : {steps}")
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


def run_roundtrip_case(program: str, name: str) -> bool:
    try:
        term1 = p_term(program)
        encoded = pp_term(term1)
        term2 = p_term(encoded)
    except Exception as exc:
        print(f"[FAIL] {name}")
        print(f"       program: {program}")
        print(f"       error  : {type(exc).__name__}: {exc}")
        return False

    if term1 != term2:
        print(f"[FAIL] {name}")
        print(f"       original program: {program}")
        print(f"       printed program : {encoded}")
        print(f"       term1           : {term1}")
        print(f"       term2           : {term2}")
        return False

    print(f"[PASS] {name}")
    print(f"       encoded: {encoded}")
    return True


def run_roundtrip_tests() -> tuple[int, int]:
    programs = [
        I(987654321),
        S("abcXYZ012!@#$%^&*()_+-=[]:;,.?/"),
        S("a B!\nZ9"),
        B("+", I(-20), I(7)),
        IF("T", APP(L(0, B("+", V(0), I(1))), I(41)), B("/", I(1), I(0))),
        APP(APP(L(0, L(1, V(0))), I(42)), I(999)),
        APP(
            APP(
                L(0, L(1, APP(V(0), APP(V(0), V(1))))),
                L(2, B("+", V(2), I(1))),
            ),
            I(40),
        ),
    ]

    passed = 0
    total = len(programs)

    for index, program in enumerate(programs, start=1):
        if run_roundtrip_case(program, f"roundtrip difficult #{index}"):
            passed += 1

    return passed, total


def main() -> int:
    print("=" * 72)
    print("IFP MINI INTERPRETER DIFFICULT TEST SUITE - test2.py")
    print("=" * 72)

    total = 0
    passed = 0

    print("\n[1] DIFFICULT EVALUATION TESTS")
    print("-" * 72)
    for case in EVAL_CASES:
        total += 1
        if run_eval_case(case):
            passed += 1

    print("\n[2] PARSER EDGE TESTS")
    print("-" * 72)
    for case in PARSE_ERROR_CASES:
        total += 1
        if run_parse_error_case(case):
            passed += 1

    print("\n[3] DIFFICULT PRINTER / PARSER ROUNDTRIP TESTS")
    print("-" * 72)
    roundtrip_passed, roundtrip_total = run_roundtrip_tests()
    passed += roundtrip_passed
    total += roundtrip_total

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")

    if passed == total:
        print("ALL DIFFICULT TESTS PASSED")
        return 0

    print("SOME DIFFICULT TESTS FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
