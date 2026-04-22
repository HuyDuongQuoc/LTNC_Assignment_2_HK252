# IFP Mini Interpreter - Student Guide

This project reads an encoded expression, parses it into an AST, evaluates it, and prints the result.

## Quick Pipeline

1. Input encoded text in [main.py](main.py)
2. Parse text into AST nodes from [ifp_ast.py](ifp_ast.py) using [parser.py](parser.py)
3. Evaluate AST with [interpreter.py](interpreter.py)
4. Print result text with [printer.py](printer.py)

---

## File-by-File Class Guide

## [ifp_ast.py](ifp_ast.py)

This file defines the AST (Abstract Syntax Tree) node classes. Think of these as the grammar objects for your language.

### `Term`
- Base parent class for every AST node type.
- Purpose: lets the rest of the program treat all node types uniformly.

### `TInt`
- Stores an integer literal (`value: int`).
- Example meaning: number constants in code.

### `TString`
- Stores a string literal (`value: str`).
- Example meaning: text constants.

### `TBool`
- Stores a boolean literal (`value: bool`).
- Example meaning: true/false values.

### `TVar`
- Stores a variable ID (`value: int`).
- Purpose: represents variable references.

### `TLam`
- Lambda (function) node with parameter variable ID and body.
- Fields: `var`, `body`.
- Purpose: represents anonymous functions.

### `TUnOp`
- Unary operation node.
- Fields: operator `op` and operand `term`.
- Purpose: expressions like negation or logical not.

### `TBinOp`
- Binary operation node.
- Fields: `left`, `op`, `right`.
- Purpose: expressions like addition, application, string concat, and others.

### `TIf`
- If-then-else node.
- Fields: `cond`, `true_branch`, `false_branch`.
- Purpose: conditional execution.

---

## [parser.py](parser.py)

This file converts encoded text into AST nodes.

### `ParseError`
- Custom parser exception with metadata.
- Fields:
  - `kind`: error type (`UnexpectedChar`, `UnusedInput`, `UnexpectedEOF`)
  - `index`: where the issue happened
  - `ch`: offending character (if any)
- Purpose: provides clear parse diagnostics for users/students.

Note: most parser logic here is function-based (`p_term`, `_parse_term`, helpers), not class-based.

---

## [interpreter.py](interpreter.py)

This file evaluates AST nodes into runtime values.

### Error classes

#### `InterpreterError`
- Base class for interpreter-level failures.
- Purpose: catch all interpreter errors from one parent.

#### `BetaReductionLimit`
- Raised when evaluation step count passes `MAX_STEPS`.
- Purpose: avoid infinite/non-terminating reductions.

#### `ScopeError`
- Raised when a variable is missing from environment.
- Purpose: reports undefined variable usage.

#### `TypeError_`
- Raised when an operation gets wrong value types.
- Purpose: runtime type safety.

#### `ArithmeticError_`
- Raised for arithmetic issues (for example divide by zero).
- Purpose: isolate numeric runtime failures.

#### `UnknownUnOp`
- Raised for unsupported unary operator.
- Purpose: explicit error when op symbol is not implemented.

#### `UnknownBinOp`
- Raised for unsupported binary operator.
- Purpose: explicit error when op symbol is not implemented.

### Runtime value classes

#### `VInt`
- Runtime integer value container (`value: int`).

#### `VBool`
- Runtime boolean value container (`value: bool`).

#### `VString`
- Runtime string value container (`value: str`).

#### `VClosure`
- Runtime function closure.
- Fields:
  - `var`: function parameter variable ID
  - `body`: function body AST
  - `env`: captured environment at function creation time
- Purpose: implements lexical scoping (function remembers outside variables).

### Evaluation support class

#### `Thunk`
- Delayed computation holder used by application strategies.
- Fields include:
  - `kind`: `value`, `thunk`, or `lazy`
  - `value`: memoized evaluated value (when available)
  - `term` + `env`: suspended expression and its environment
  - `steps`: cached step cost used by the evaluator
- Purpose: supports deferred evaluation and memoization behavior.

Note: the evaluator itself is mostly function-based (`interpret`, `eval_term`, operator helpers).

---

## [printer.py](printer.py)

No classes are defined here.

Purpose of the file:
- encode numbers/strings back to project format
- pretty-print AST back to encoded term text (`pp_term`)

---

## [main.py](main.py)

No classes are defined here.

Purpose of the file:
- CLI entry point
- read input
- call parser + interpreter
- print user-friendly output and encoded result

## FAQ
1. What is AST? <br>
<b>Answer</b>: Please search for it online (e.g., Google) and review basic materials on Abstract Syntax Trees (AST), as this is a fundamental concept.
2. If I have not studied Principles of Programming Languages, can I still complete this assignment? <br>
<b>Answer</b>: Yes. While prior knowledge of Principles of Programming Languages is helpful, it is not required. You can complete this assignment by applying concepts from courses such as Fundamental Programming and Data Structures & Algorithms. However, you may need to spend additional time understanding concepts like parsing, Abstract Syntax Trees (AST), and basic interpreter design.

