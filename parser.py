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

def decode_base94(body: str, start_index: int) -> int:
    value = 0
    for offset, ch in enumerate(body):
        if ch not in CHARS:
            raise ParseError("UnexpectedChar", index=start_index + offset, ch=ch)

        digit = ord(ch) - 33
        value = value * 94 + digit
    return value

def decode_string(body: str, start_index: int) -> str:
    result: list[str] = []
    for offset, ch in enumerate(body):
        if ch not in CHARS:
            raise ParseError("UnexpectedChar", index=start_index + offset, ch=ch)

        result.append(_DECODE_MAP[ch])
    return "".join(result)

def _read_token(inp: str, i: int) -> tuple[str, int, int]:
    if i >= len(inp):
        raise ParseError("UnexpectedEOF")

    if inp[i] == " ":
        raise ParseError("UnexpectedChar", index=i, ch=inp[i])

    if inp[i] not in CHARS:
        raise ParseError("UnexpectedChar", index=i, ch=inp[i])

    start = i

    while i < len(inp) and inp[i] != " ":
        if inp[i] not in CHARS:
            raise ParseError("UnexpectedChar", index=i, ch=inp[i])
        i += 1

    token = inp[start:i]
    return token, start, i

def _expect_space_then_term(inp: str, i: int) -> int:
    if i >= len(inp):
        raise ParseError("UnexpectedEOF")

    if inp[i] != " ":
        raise ParseError("UnexpectedChar", index=i, ch=inp[i])

    next_i = i + 1

    if next_i >= len(inp):
        raise ParseError("UnexpectedEOF")

    if inp[next_i] == " ":
        raise ParseError("UnexpectedChar", index=next_i, ch=inp[next_i])

    return next_i

def _missing_body_error(inp: str, token_end: int) -> None:
    if token_end >= len(inp):
        raise ParseError("UnexpectedEOF")

    raise ParseError("UnexpectedChar", index=token_end, ch=inp[token_end])

def _parse_term(inp: str, i: int) -> tuple[Term, int]:   
    token, start, end = _read_token(inp, i)

    indicator = token[0]
    body = token[1:]
    body_start = start + 1
        
    # Boolean
    if indicator == "T":
        if body != "":
            raise ParseError("UnexpectedChar", index=body_start, ch=body[0])
        return TBool(True), end

    if indicator == "F":
        if body != "":
            raise ParseError("UnexpectedChar", index=body_start, ch=body[0])
        return TBool(False), end

    # Int
    if indicator == "I":
        if body == "":
            _missing_body_error(inp, end)
        return TInt(decode_base94(body, body_start)), end

    # String
    if indicator == "S":
        return TString(decode_string(body, body_start)), end

    # Variable
    if indicator == "v":
        if body == "":
            _missing_body_error(inp, end)
        return TVar(decode_base94(body, body_start)), end

    # Lambda
    if indicator == "L":
        if body == "":
            _missing_body_error(inp, end)

        var_id = decode_base94(body, body_start)

        j = _expect_space_then_term(inp, end)
        body_term, k = _parse_term(inp, j)

        return TLam(var_id, body_term), k

    # Branch condition
    if indicator == "?":
        if body != "":
            raise ParseError("UnexpectedChar", index=body_start, ch=body[0])
        j = _expect_space_then_term(inp, end)
        cond, k = _parse_term(inp, j)
        k = _expect_space_then_term(inp, k)
        true_branch, m = _parse_term(inp, k)
        m = _expect_space_then_term(inp, m)
        false_branch, n = _parse_term(inp, m)
        return TIf(cond, true_branch, false_branch), n

    # Unary operator
    if indicator == "U":
        if len(body) == 0:
            _missing_body_error(inp, end)
        if len(body) > 1:
            raise ParseError("UnexpectedChar", index=body_start + 1, ch=body[1])
        oper = body
        j = _expect_space_then_term(inp, end)
        subterm, k = _parse_term(inp, j)
        return TUnOp(oper, subterm), k
    
    # Binary operator
    if indicator == "B":
        if len(body) == 0:
            _missing_body_error(inp, end)
        if len(body) > 1:
            raise ParseError("UnexpectedChar", index=body_start + 1, ch=body[1])
        oper = body
        j = _expect_space_then_term(inp, end)
        left, k = _parse_term(inp, j)
        k = _expect_space_then_term(inp, k)
        right, m = _parse_term(inp, k)
        return TBinOp(left, oper, right), m
        
    raise ParseError("UnexpectedChar", index=start, ch=indicator)

def p_term(inp: str) -> Term:
    if inp == "":
        raise ParseError("UnexpectedEOF")
    term, end = _parse_term(inp, 0)
    if end == len(inp):
        return term
    if inp[end] == " ":
        if end == len(inp) - 1:
            return term
        if inp[end + 1] == " ":
            raise ParseError("UnexpectedChar", index=end + 1, ch=inp[end + 1])
        raise ParseError("UnusedInput", index=end + 1)

    raise ParseError("UnexpectedChar", index=end, ch=inp[end])