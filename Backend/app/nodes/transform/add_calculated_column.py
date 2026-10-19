import re
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np
import pandas as pd

from app.dataframe.frame import FluxDataFrame
from app.dataframe.schema import Column, DataSchema, DataType
from app.nodes.base import FieldSchema, FieldType, NodeCategory, NodePlugin, SchemaValidationError


class ExpressionSyntaxError(ValueError):
    """Raised on malformed add_calculated_column expressions."""


@dataclass
class _Num:
    value: float


@dataclass
class _Str:
    value: str


@dataclass
class _ColumnRef:
    name: str


@dataclass
class _BinaryOp:
    op: str
    left: "AstNode"
    right: "AstNode"


@dataclass
class _IfExpr:
    condition: "AstNode"
    then: "AstNode"
    otherwise: "AstNode"


AstNode = Union[_Num, _Str, _ColumnRef, _BinaryOp, _IfExpr]

_COMPARISON_OPS = {"=", "≠", ">", "<", "≥", "≤", "<>", ">=", "<="}
_COMPARISON_ALIASES = {"<>": "≠", ">=": "≥", "<=": "≤"}
_EXCEL_OP_ALIASES = {"≠": "<>", "≥": ">=", "≤": "<="}

_TOKEN_SPEC = [
    ("NUMBER", r"\d+(?:\.\d+)?"),
    ("STRING", r'"[^"]*"|\'[^\']*\''),
    ("BRACKET_IDENT", r"\[[^\]]+\]"),
    ("COMP", r"<>|>=|<=|≠|≥|≤|=|>|<"),
    ("OP", r"[+\-*/&]"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("COMMA", r","),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("SKIP", r"[ \t]+"),
]
_MASTER_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPEC))


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens = []
    pos = 0
    while pos < len(text):
        match = _MASTER_RE.match(text, pos)
        if not match:
            raise ExpressionSyntaxError(f"Unexpected character in expression at position {pos}: '{text[pos]}'")
        kind = match.lastgroup
        value = match.group()
        pos = match.end()
        if kind != "SKIP":
            tokens.append((kind, value))
    tokens.append(("EOF", ""))
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> tuple[str, str]:
        return self._tokens[self._pos]

    def _advance(self) -> tuple[str, str]:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _expect(self, kind: str) -> tuple[str, str]:
        token = self._advance()
        if token[0] != kind:
            raise ExpressionSyntaxError(f"Expected {kind} but got '{token[1] or 'end of expression'}'")
        return token

    def parse(self) -> AstNode:
        node = self._comparison()
        self._expect("EOF")
        return node

    def _comparison(self) -> AstNode:
        # Comparisons are one level, not chainable (a<b<c isn't supported, matching Excel),
        # and available anywhere an expression is both standalone 
        # column, "price > 10") and inside IF's condition clause.
        node = self._additive()
        if self._peek()[0] == "COMP":
            op = self._advance()[1]
            node = _BinaryOp(op, node, self._additive())
        return node

    def _additive(self) -> AstNode:
        node = self._term()
        while self._peek()[0] == "OP" and self._peek()[1] in ("+", "-", "&"):
            op = self._advance()[1]
            node = _BinaryOp(op, node, self._term())
        return node

    def _term(self) -> AstNode:
        node = self._atom()
        while self._peek()[0] == "OP" and self._peek()[1] in ("*", "/"):
            op = self._advance()[1]
            node = _BinaryOp(op, node, self._atom())
        return node

    def _atom(self) -> AstNode:
        kind, value = self._peek()
        if kind == "NUMBER":
            self._advance()
            return _Num(float(value))
        if kind == "STRING":
            self._advance()
            return _Str(value[1:-1])
        if kind == "BRACKET_IDENT":
            self._advance()
            return _ColumnRef(value[1:-1])
        if kind == "LPAREN":
            self._advance()
            node = self._comparison()
            self._expect("RPAREN")
            return node
        if kind == "IDENT":
            if value.upper() == "IF" and self._tokens[self._pos + 1][0] == "LPAREN":
                return self._if_expr()
            self._advance()
            return _ColumnRef(value)
        raise ExpressionSyntaxError(f"Unexpected token '{value or 'end of expression'}' in expression")

    def _if_expr(self) -> _IfExpr:
        self._advance()  # IF
        self._expect("LPAREN")
        condition = self._comparison()
        self._expect("COMMA")
        then_expr = self._comparison()
        self._expect("COMMA")
        else_expr = self._comparison()
        self._expect("RPAREN")
        return _IfExpr(condition, then_expr, else_expr)


def parse_expression(text: str) -> AstNode:
    if not text or not text.strip():
        raise ExpressionSyntaxError("Expression is empty.")
    return _Parser(_tokenize(text)).parse()


def evaluate_expression(node: AstNode, df: pd.DataFrame):
    if isinstance(node, _Num):
        return node.value
    if isinstance(node, _Str):
        return node.value
    if isinstance(node, _ColumnRef):
        if node.name not in df.columns:
            raise ValueError(f"Column '{node.name}' not found in the input data.")
        return df[node.name]
    if isinstance(node, _IfExpr):
        condition = evaluate_expression(node.condition, df)
        then_val = evaluate_expression(node.then, df)
        else_val = evaluate_expression(node.otherwise, df)
        return np.where(condition, then_val, else_val)
    if isinstance(node, _BinaryOp):
        left = evaluate_expression(node.left, df)
        right = evaluate_expression(node.right, df)
        op = _COMPARISON_ALIASES.get(node.op, node.op)
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right
        if op == "&":
            return _stringify(left) + _stringify(right)
        if op == "=":
            return left == right
        if op == "≠":
            return left != right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == "≥":
            return left >= right
        if op == "≤":
            return left <= right
        raise ExpressionSyntaxError(f"Unsupported operator '{node.op}'")
    raise ExpressionSyntaxError(f"Unknown expression node: {node!r}")


def _stringify(value):
    if isinstance(value, pd.Series):
        return value.astype(str)
    return str(value)


def _static_infer_type(node: AstNode, schema: DataSchema) -> DataType:
    """Walks the whole tree (not just the branches that determine the final type) so that
    a bad column reference anywhere in the expression — e.g. in a comparison's operands, or
    in an IF branch that isn't the reported type — is still caught here rather than only
    surfacing later at execute() time."""
    if isinstance(node, _Num):
        return DataType.NUMBER
    if isinstance(node, _Str):
        return DataType.STRING
    if isinstance(node, _ColumnRef):
        if not schema.has_column(node.name):
            raise SchemaValidationError(f"Column '{node.name}' not found in the input data.")
        return schema.get_column(node.name).type
    if isinstance(node, _IfExpr):
        _static_infer_type(node.condition, schema)
        then_type = _static_infer_type(node.then, schema)
        _static_infer_type(node.otherwise, schema)
        return then_type
    if isinstance(node, _BinaryOp):
        _static_infer_type(node.left, schema)
        _static_infer_type(node.right, schema)
        if node.op in _COMPARISON_OPS:
            return DataType.BOOLEAN
        if node.op == "&":
            return DataType.STRING
        return DataType.NUMBER  # + - * /
    raise SchemaValidationError("Could not determine the result type of this expression.")


def _to_excel(node: AstNode) -> str:
    if isinstance(node, _Num):
        return repr(node.value) if node.value % 1 else str(int(node.value))
    if isinstance(node, _Str):
        return f'"{node.value}"'
    if isinstance(node, _ColumnRef):
        return f"[{node.name}]"
    if isinstance(node, _IfExpr):
        return f"IF({_to_excel(node.condition)}, {_to_excel(node.then)}, {_to_excel(node.otherwise)})"
    if isinstance(node, _BinaryOp):
        op = _EXCEL_OP_ALIASES.get(node.op, node.op)
        return f"({_to_excel(node.left)}{op}{_to_excel(node.right)})"
    raise ExpressionSyntaxError("Cannot render this expression as an Excel formula.")


class AddCalculatedColumnNode(NodePlugin):
    id = "add_calculated_column"
    display_name = "Add Calculated Column"
    category = NodeCategory.TRANSFORM

    def get_config_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(key="new_column_name", label="New Column Name", type=FieldType.TEXT),
            FieldSchema(key="expression", label="Expression", type=FieldType.EXPRESSION),
        ]

    def infer_output_schema(self, input_schema: DataSchema, config: dict) -> DataSchema:
        new_column_name = config.get("new_column_name")
        if not new_column_name:
            raise SchemaValidationError("Add Calculated Column requires a new column name.")
        if input_schema.has_column(new_column_name):
            raise SchemaValidationError(f"Column '{new_column_name}' already exists in the input data.")
        try:
            ast = parse_expression(config.get("expression", ""))
        except ExpressionSyntaxError as e:
            raise SchemaValidationError(f"Invalid expression: {e}") from e
        inferred_type = _static_infer_type(ast, input_schema)
        return DataSchema(columns=[*input_schema.columns, Column(name=new_column_name, type=inferred_type)])

    def execute(self, input_df: FluxDataFrame, config: dict) -> FluxDataFrame:
        new_column_name = config.get("new_column_name")
        if not new_column_name:
            raise ValueError("Add Calculated Column requires a new column name.")
        ast = parse_expression(config.get("expression", ""))

        df = input_df.df.copy()
        result = evaluate_expression(ast, df)
        if isinstance(result, np.ndarray):
            result = pd.Series(result, index=df.index)
        df[new_column_name] = result

        new_schema = self.infer_output_schema(input_df.schema, config)
        return FluxDataFrame(schema=new_schema, df=df, total_row_count=len(df))

    def to_excel_formula(self, input_ref: Optional[str], config: dict) -> Optional[str]:
        expression_text = config.get("expression")
        if not expression_text:
            return None
        try:
            return _to_excel(parse_expression(expression_text))
        except ExpressionSyntaxError:
            return None

    def to_excel_formula_explanation(self, config: dict) -> str:
        new_column_name = config.get("new_column_name", "?")
        expression_text = config.get("expression", "")
        return f"Add a new column '{new_column_name}' computed as: {expression_text}"
