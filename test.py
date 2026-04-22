from parser import p_term
from printer import pp_term

tests = [
    "T",
    "F",
    "I/6",
    "SB%,,/}Q/2,$",
    "U- I$",
    "U! T",
    "B+ I# I$",
    "B. S4% S34",
    "? B> I# I$ S9%3 S./",
    "L# v#",
    "B$ L# v# I$",
]

for s in tests:
    term = p_term(s)
    print("INPUT :", s)
    print("AST   :", term)
    print("PRINT :", pp_term(term))
    print("-" * 50)