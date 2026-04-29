from parser import p_term
from interpreter import interpret
from printer import pp_term

tests = [
    ("U# S", "I!"),
    ("U$ I!", "S!"),
    ("U$ U# S", "S!"),

    ("? T I# B/ I# I!", "I#"),
    ("? F B/ I# I! I$", "I$"),

    ("B$ L# I$ B/ I# I!", "I$"),

    ('B$ L# L# v# I"', "L# v#"),

    # Edge case cần sửa: không được lỗi chia 0 khi chỉ trả về lambda
    ("B$ L# L$ ? T I! v# B/ I# I!", "L$ ? T I! B/ I# I!"),
]

for program, expected in tests:
    try:
        result, steps = interpret(True, p_term(program))
        got = pp_term(result)
        print(program)
        print("got     :", got)
        print("expected:", expected)
        print("PASS" if got == expected else "CHECK")
        print("-" * 50)
    except Exception as e:
        print(program)
        print("ERROR:", type(e).__name__, e)
        print("-" * 50)