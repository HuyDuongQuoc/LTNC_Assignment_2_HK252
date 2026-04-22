from __future__ import annotations

from ifp_ast import CHARS, CHARS_DECODED, TBinOp, TBool, TIf, TInt, TLam, TString, TUnOp, TVar, Term


_ENCODE_MAP = {dst: src for src, dst in zip(CHARS, CHARS_DECODED)}


def to_base94(x: int) -> str | None:
    if x < 0:
        return None
    if x == 0:
        return chr(33)

    out: list[str] = []
    n = x
    while n > 0:
        n, m = divmod(n, 94)
        out.append(chr(m + 33))
    out.reverse()
    return "".join(out)


def encode_string(s: str) -> str:
    out: list[str] = []
    for ch in s:
        if ch not in _ENCODE_MAP:
            raise ValueError(f"Unexpected character in string encoding: {ch!r}")
        out.append(_ENCODE_MAP[ch])
    return "".join(out)


def pp_term(term: Term) -> str:
    if isinstance(term, TInt):
        b94 = to_base94(term.value)
        if b94 is not None:
            return "I" + b94
        return pp_term(TUnOp("-", TInt(-term.value)))

    if isinstance(term, TString):
        return "S" + encode_string(term.value)

    if isinstance(term, TBool):
        return "T" if term.value else "F"

    if isinstance(term, TVar):
        b94 = to_base94(term.value)
        if b94 is None:
            raise ValueError("Negative variable found")
        return "v" + b94

    if isinstance(term, TLam):
        b94 = to_base94(term.var)
        if b94 is None:
            raise ValueError("Negative variable found")
        return "L" + b94 + " " + pp_term(term.body)

    if isinstance(term, TUnOp):
        return "U" + term.op + " " + pp_term(term.term)

    if isinstance(term, TBinOp):
        return "B" + term.op + " " + pp_term(term.left) + " " + pp_term(term.right)

    if isinstance(term, TIf):
        return "? " + pp_term(term.cond) + " " + pp_term(term.true_branch) + " " + pp_term(term.false_branch)

    raise TypeError(f"Unknown term type: {type(term).__name__}")
