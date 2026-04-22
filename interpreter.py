from __future__ import annotations

from dataclasses import dataclass

from ifp_ast import TBinOp, TBool, TIf, TInt, TLam, TString, TUnOp, TVar, Term
from printer import encode_string, to_base94


MAX_STEPS = 10_000_000


class InterpreterError(Exception):
    pass


class BetaReductionLimit(InterpreterError):
    pass


class ScopeError(InterpreterError):
    pass


class TypeError_(InterpreterError):
    pass


class ArithmeticError_(InterpreterError):
    pass


class UnknownUnOp(InterpreterError):
    def __init__(self, op: str):
        super().__init__(f"Unknown unary operator: {op}")
        self.op = op


class UnknownBinOp(InterpreterError):
    def __init__(self, op: str):
        super().__init__(f"Unknown binary operator: {op}")
        self.op = op


@dataclass
class VInt:
    value: int


@dataclass
class VBool:
    value: bool


@dataclass
class VString:
    value: str


@dataclass
class VClosure:
    var: int
    body: Term
    env: dict[int, "Thunk"]


Value = VInt | VBool | VString | VClosure


@dataclass
class Thunk:
    kind: str
    value: Value | None = None
    steps: int = 0
    term: Term | None = None
    env: dict[int, "Thunk"] | None = None


def _to_term(v: Value) -> Term:
    if isinstance(v, VInt):
        return TInt(v.value)
    if isinstance(v, VBool):
        return TBool(v.value)
    if isinstance(v, VString):
        return TString(v.value)
    if isinstance(v, VClosure):
        return TLam(v.var, v.body)
    raise TypeError_(f"Unknown value type: {type(v).__name__}")

def interpret(check_max: bool, term: Term) -> tuple[Term, int]:
    steps = 0
    
    def eval_term(t: Term, env: dict[int, Thunk]) -> Value:
        if isinstance(t, TInt):
            return VInt(t.value)
        if isinstance(t, TString):
            return VString(t.value)
        if isinstance(t, TBool):
            return VBool(t.value)
        if isinstance(t, TLam):
            return VClosure(t.var, t.body, env.copy())
        if isinstance(t, TVar):
            if t.value not in env:
                raise ScopeError(f"Unbound variable: v{t.value}")
            return force(env[t.value])
        
        raise TypeError_(f"Unknown term type: {type(t).__name__}")

    def force(th: Thunk) -> Value:
        if th.kind == "value":
            if th.value is None:
                raise InterpreterError("Malformed value thunk")
            return th.value
        if th.kind == "thunk":
            if th.term is None or th.env is None:
                raise InterpreterError("Malformed delayed thunk")
            return eval_term(th.term, th.env)
        raise InterpreterError(f"Unknown thunk kind: {th.kind}")

    result = eval_term(term, {})
    return _to_term(result), steps
