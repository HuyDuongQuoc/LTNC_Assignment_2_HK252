from __future__ import annotations

from dataclasses import dataclass

from ifp_ast import CHARS, CHARS_DECODED, TBinOp, TBool, TIf, TInt, TLam, TString, TUnOp, TVar, Term
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
    
    decode_map = {src: dst for src,dst in zip(CHARS,CHARS_DECODED)}
    
    def decode_base94(body: str)->int:
        res = 0
        for i in body:
            res = res*94+(ord(i)-33)
        return res
    
    def decode_string_body(body: str)->str:
        res: list[str] = []
        for i in body:
            if i not in decode_map:
                raise TypeError_(f"Unexpected encoded character: {i!r}")
            res.append(decode_map[i])
        return "".join(res)
    
    def is_int(v: Value) -> int:
        if not isinstance(v, VInt):
            raise TypeError_(f"Expected integer, got {type(v).__name__}")
        return v.value

    def is_bool(v: Value) -> bool:
        if not isinstance(v, VBool):
            raise TypeError_(f"Expected boolean, got {type(v).__name__}")
        return v.value

    def is_string(v: Value) -> str:
        if not isinstance(v, VString):
            raise TypeError_(f"Expected string, got {type(v).__name__}")
        return v.value 
    
    def div_mod(a:int, b:int)->tuple[int,int]:
        if b==0:
            raise ArithmeticError_("Division by zero")
        q = abs(a) // abs(b)
        if (a<0)^(b<0):
            q = -q
        r = a-q*b
        return q,r
    
    def eval_term(t: Term, env: dict[int, Thunk]) -> Value:
        nonlocal steps
        
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
        if isinstance(t,TUnOp):
            v = eval_term(t.term, env)
            
            if t.op == "-":
                return VInt(-is_int(v))
            if t.op == "!":
                return VBool(not is_bool(v))
            if t.op == "#":
                s = is_string(v)
                encoded = encode_string(s)
                return VInt(decode_base94(encoded))
            if t.op == "$":
                n = is_int(v)
                if n<0:
                    raise TypeError_("U$ expects a non-negative integer")
                body = to_base94(n)
                if body is None:
                    raise TypeError_("U$ expects a non-negative integer")
                return VString(decode_string_body(body))
            
            raise UnknownUnOp(t.op)
        if isinstance(t, TBinOp):
            if t.op == "$":
                func = eval_term(t.left, env)
                if not isinstance(func, VClosure):
                    raise TypeError_("Function application expects a lambda on the left")
                steps += 1
                if check_max and steps>MAX_STEPS:
                    raise BetaReductionLimit(f"Exceeded beta-reduction limit ({MAX_STEPS})")

                thunk_arg = Thunk(kind = "thunk", term=t.right, env = env.copy())
                new_env = func.env.copy()
                new_env[func.var] = thunk_arg
                return eval_term(func.body, new_env)
                    
            l = eval_term(t.left, env)
            r = eval_term(t.right,env)
            
            if t.op == "+":
                return VInt(is_int(l)+is_int(r))
            if t.op == "-":
                return VInt(is_int(l)-is_int(r))
            if t.op == "*":
                return VInt(is_int(l)*is_int(r))
            if t.op == "/":
                q, r = div_mod(is_int(l),is_int(r))
                return VInt(q)
            if t.op == "%":
                q, r = div_mod(is_int(l),is_int(r))
                return VInt(r)
            if t.op == "<":
                return VBool(is_int(l)<is_int(r))
            if t.op == ">":
                return VBool(is_int(l)>is_int(r))
            if t.op == "=":
                if type(l) is not type(r):
                    return VBool(False)
                if isinstance(l, VInt):
                    return VBool(l.value == r.value)
                if isinstance(l, VBool):
                    return VBool(l.value == r.value)
                if isinstance(l, VString):
                    return VBool(l.value == r.value)
                raise TypeError_("Equality is not supported for closures")

            if t.op == "|":
                return VBool(is_bool(l) or is_bool(r))
            if t.op == "&":
                return VBool(is_bool(l) and is_bool(r))
            if t.op == ".":
                return VString(is_string(l) + is_string(r))
            if t.op == "T":
                n = is_int(l)
                s = is_string(r)
                return VString(s[:n])
            if t.op == "D":
                n = is_int(l)
                s = is_string(r)
                return VString(s[n:])
            
            raise UnknownBinOp(t.op)
        
        if isinstance(t,TIf):
            cond = eval_term(t.cond,env)
            if is_bool(cond):
                return eval_term(t.true_branch,env)
            return eval_term(t.false_branch,env)
         
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
        if th.kind == "lazy":
            if th.value is not None:
                return th.value
            if th.term is None or th.env is None:
                raise InterpreterError("Malformed lazy thunk")
            value = eval_term(th.term, th.env)
            th.value = value
            return value
        raise InterpreterError(f"Unknown thunk kind: {th.kind}")

    def thunk_to_term(th: Thunk) -> Term:
        if th.kind == "value":
            if th.value is None:
                raise InterpreterError("Malformed value thunk")
            return value_to_term(th.value)

        if th.kind == "thunk":
            if th.term is None or th.env is None:
                raise InterpreterError("Malformed delayed thunk")
            return close_term(th.term, th.env)

        if th.kind == "lazy":
            if th.value is not None:
                return value_to_term(th.value)
            if th.term is None or th.env is None:
                raise InterpreterError("Malformed lazy thunk")
            return close_term(th.term, th.env)

        raise InterpreterError(f"Unknown thunk kind: {th.kind}")

    def value_to_term(v: Value) -> Term:
        if isinstance(v, VInt):
            return TInt(v.value)

        if isinstance(v, VBool):
            return TBool(v.value)

        if isinstance(v, VString):
            return TString(v.value)

        if isinstance(v, VClosure):
            new_env = v.env.copy()
            new_env.pop(v.var, None)
            return TLam(v.var, close_term(v.body, new_env))
        raise TypeError_(f"Unknown value type: {type(v).__name__}")


    def close_term(t: Term, env: dict[int, Thunk]) -> Term:
        if isinstance(t, TInt) or isinstance(t, TString) or isinstance(t, TBool):
            return t
        if isinstance(t, TVar):
            if t.value in env:
                return thunk_to_term(env[t.value])
            return t
        if isinstance(t, TLam):
            new_env = env.copy()
            new_env.pop(t.var, None)
            return TLam(t.var, close_term(t.body, new_env))
        if isinstance(t, TUnOp):
            return TUnOp(t.op, close_term(t.term, env))
        if isinstance(t, TBinOp):
            return TBinOp(
                close_term(t.left, env),
                t.op,
                close_term(t.right, env),
            )
        if isinstance(t, TIf):
            return TIf(
                close_term(t.cond, env),
                close_term(t.true_branch, env),
                close_term(t.false_branch, env),
            )
        raise TypeError_(f"Unknown term type: {type(t).__name__}")

    result = eval_term(term, {})
    return value_to_term(result), steps