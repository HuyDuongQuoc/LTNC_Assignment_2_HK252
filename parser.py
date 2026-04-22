from __future__ import annotations

from dataclasses import dataclass

from ifp_ast import (
    CHARS,
    CHARS_DECODED,
    TBinOp,
    TBool,
    TIf,
    TInt,
    TLam,
    TString,
    TUnOp,
    TVar,
    Term,
)

_DECODE_MAP = {key:val for key,val in zip(CHARS,CHARS_DECODED)}

@dataclass(frozen=True)
class ParseError(Exception):
    kind: str
    index: int | None = None
    ch: str | None = None

    def __str__(self) -> str:
        if self.kind == "UnexpectedChar":
            return f"UnexpectedChar({self.ch!r}, {self.index})"
        if self.kind == "UnusedInput":
            return f"UnusedInput({self.index})"
        return "UnexpectedEOF"

def decode_base94(body : str) -> int:
    value = 0
    for ch in body:
        if ch not in CHARS:
            raise ParseError("UnexpectedChar", ch=ch)
        digit = ord(ch) - 33
        value = value * 94 + digit
    return value

def decode_string(body : str) -> str:
    result: list[str] = []
    for ch in body:
        if ch not in CHARS:
            raise ParseError("UnexpectedChar", ch=ch)
        result.append(_DECODE_MAP[ch])
    return "".join(result)

def _parse_term(tokens: list[str], i: int) -> tuple[Term, int]:
    if i >= len(tokens):
        raise ParseError("UnexpectedEOF")

    token = tokens[i]
    indicator = token[0]
    body = token[1:]
    
    # Boolean
    if token == "T":
        return TBool(True), i + 1
    if token == "F":
        return TBool(False), i + 1

    # Int
    if indicator == "I":
        if body == "":
            raise ParseError("UnexpectedEOF")
        return TInt(decode_base94(body)), i + 1

    # String
    if indicator == "S":
        return TString(decode_string(body)), i + 1

    # Variable
    if indicator == "v":
        if body == "":
            raise ParseError("UnexpectedEOF")
        return TVar(decode_base94(body)), i + 1

    # Lambda
    if indicator == "L":
        var_id = decode_base94(body)
        body_term, j = _parse_term(tokens, i+1)
        return TLam(var_id, body_term), j

    # Branch condition
    if indicator == "?":
        cond, j = _parse_term(tokens, i+1)
        true, k = _parse_term(tokens,j)
        false, m = _parse_term(tokens,k)
        return TIf(cond, true, false), m

    # Unary operator
    if indicator == "U":
        if len(body)!=1:
            bad = body[1] if len(body) > 1 else None
            raise ParseError("UnexpectedChar", index=i, ch=bad)
        oper = body
        subterm, j = _parse_term(tokens, i+1)
        return TUnOp(oper,subterm),j
    
    # Binary operator
    if indicator == "B":
        if len(body)!=1:
            bad = body[1] if len(body) > 1 else None
            raise ParseError("UnexpectedChar", index=i, ch=bad)
        oper = body
        left, j = _parse_term(tokens, i+1)
        right, m = _parse_term(tokens, j)
        return TBinOp(left, oper, right),m
        
    raise ParseError("UnexpectedChar", index=i, ch=indicator)


def p_term(inp: str) -> Term:
    tokens = inp.split()
    if not tokens:
        raise ParseError("UnexpectedEOF")
    term, next_i = _parse_term(tokens,0)
    if next_i != len(tokens):
        raise ParseError("UnusedInput", index=next_i)
    return term