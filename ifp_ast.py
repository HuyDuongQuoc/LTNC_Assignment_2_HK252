from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    pass


@dataclass(frozen=True)
class TInt(Term):
    value: int


@dataclass(frozen=True)
class TString(Term):
    value: str


@dataclass(frozen=True)
class TBool(Term):
    value: bool


@dataclass(frozen=True)
class TVar(Term):
    value: int


@dataclass(frozen=True)
class TLam(Term):
    var: int
    body: Term


@dataclass(frozen=True)
class TUnOp(Term):
    op: str
    term: Term


@dataclass(frozen=True)
class TBinOp(Term):
    left: Term
    op: str
    right: Term


@dataclass(frozen=True)
class TIf(Term):
    cond: Term
    true_branch: Term
    false_branch: Term


def _ordered_unique(chars: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for ch in chars:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return "".join(out)


CHARS = "".join(chr(i) for i in range(33, 127))
CHARS_DECODED = _ordered_unique(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    + "".join(ch for ch in CHARS if ch not in "{}")
    + " \n"
)
