"""Local calculate tool for basic arithmetic expressions.

This implementation safely evaluates arithmetic AST nodes without calling eval on arbitrary code.
"""

from __future__ import annotations

import ast
import operator

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "Evaluate a basic arithmetic expression.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression, e.g. '(3+5)*2'.",
                }
            },
            "required": ["expression"],
        },
    },
}


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_expr(node: ast.AST) -> float:
    """Recursively evaluate a safe arithmetic AST expression.

    >>> _eval_expr(ast.parse("2+3", mode="eval").body)
    5.0
    >>> _eval_expr(ast.parse("-7", mode="eval").body)
    -7.0
    """
    if type(node) is ast.Constant and type(node.value) in (int, float):
        return float(node.value)

    if type(node) is ast.BinOp and type(node.op) in _BIN_OPS:
        left = _eval_expr(node.left)
        right = _eval_expr(node.right)
        return _BIN_OPS[type(node.op)](left, right)

    if type(node) is ast.UnaryOp and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_expr(node.operand))

    raise ValueError("unsupported expression")


def run_calculate(expression: str) -> str:
    """Evaluate arithmetic input and return the result as a string.

    >>> run_calculate("(3+5)*2")
    '16'
    >>> run_calculate("7/2")
    '3.5'
    >>> run_calculate("x + 1")
    'ERROR: invalid expression'
    """
    try:
        parsed = ast.parse(expression, mode="eval")
        result = _eval_expr(parsed.body)
    except Exception:
        return "ERROR: invalid expression"

    if result.is_integer():
        return str(int(result))
    return str(result)
