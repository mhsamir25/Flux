"""Excel formula engine: forward (pipeline -> formula) and reverse (formula -> pipeline)
translation.

## Forward direction — gaps resolved beyond the plan's literal compose() pseudocode
"""
import itertools
import re
from typing import Optional, Union

from pydantic import BaseModel

from app.engine.registry import NodeRegistry
from app.nodes.base import NodeCategory
from app.schemas.pipeline import EdgeDefinition, NodeDefinition


class FormulaResult(BaseModel):
    formula: Optional[str]
    explanation: str
    compatibility: str


class ParsedPipeline(BaseModel):
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]


class ParseError(BaseModel):
    message: str
    supported_patterns: list[str]


class ParseFailure(Exception):
    """Internal control-flow exception for reverse parsing — always caught at parse()'s top
    level and converted into a returned ParseError, matching the plan's "return an error
    object rather than raise" style for parse()'s public signature."""


class FormulaEngine:
    def __init__(self, registry: NodeRegistry):
        self.registry = registry

    # --- forward: pipeline -> formula ------------------------------------------------

    def generate(self, nodes: list[NodeDefinition], edges: list[EdgeDefinition]) -> FormulaResult:
        terminal_id = self._find_terminal_node(nodes, edges)
        if terminal_id is None:
            return FormulaResult(
                formula=None,
                explanation="No output node found — connect your nodes into a single chain ending in an output.",
                compatibility="N/A",
            )

        explanation_lines: list[str] = []
        formula = self._compose(terminal_id, terminal_id, nodes, edges, explanation_lines)
        return FormulaResult(
            formula=(f"={formula}" if formula else None),
            explanation="\n".join(explanation_lines),
            compatibility=_determine_compatibility(formula),
        )

    def _compose(
        self,
        node_id: str,
        terminal_id: str,
        nodes: list[NodeDefinition],
        edges: list[EdgeDefinition],
        explanation_lines: list[str],
    ) -> Optional[str]:
        node = _find_node(node_id, nodes)
        plugin = self.registry.get(node.type)

        if plugin.id == "join":
            formula = plugin.to_excel_formula(None, node.config)
            explanation_lines.append(plugin.to_excel_formula_explanation(node.config))
            return formula

        parent_id = _find_parent(node_id, edges)
        if parent_id is None:
            formula = plugin.to_excel_formula(None, node.config)
            explanation_lines.append(plugin.to_excel_formula_explanation(node.config))
            return formula

        parent_formula = self._compose(parent_id, terminal_id, nodes, edges, explanation_lines)
        if parent_formula is None:
            return None  # an upstream node broke the chain; stop here, nothing more to add

        if plugin.id == "add_calculated_column" and node_id != terminal_id:
            explanation_lines.append(plugin.to_excel_formula_explanation(node.config))
            return parent_formula

        this_formula = plugin.to_excel_formula(parent_formula, node.config)
        explanation_lines.append(plugin.to_excel_formula_explanation(node.config))
        return this_formula

    def _find_terminal_node(self, nodes: list[NodeDefinition], edges: list[EdgeDefinition]) -> Optional[str]:
        nodes_with_outgoing = {e.source_node_id for e in edges}
        for node in nodes:
            if node.id in nodes_with_outgoing:
                continue
            try:
                plugin = self.registry.get(node.type)
            except KeyError:
                continue
            if plugin.category == NodeCategory.SOURCE:
                continue
            return node.id
        return None

    # --- reverse: formula -> pipeline ------------------------------------------------

    def parse(self, formula: str) -> Union[ParsedPipeline, ParseError]:
        # Unlike _parse_node_chain's nested-argument case, the top-level input must itself be
        # a recognized function call — falling back to a bare "source range" placeholder here
        # would silently accept arbitrary non-formula text as a trivial one-node "pipeline".
        try:
            name, args = extract_call_parts(formula)
        except ParseFailure as e:
            return ParseError(message=str(e), supported_patterns=sorted(KNOWN_PATTERNS))

        parser = KNOWN_PATTERNS.get(name)
        if parser is None:
            return ParseError(
                message=f"'{name}' isn't a supported pattern yet. Supported: {', '.join(sorted(KNOWN_PATTERNS))}",
                supported_patterns=sorted(KNOWN_PATTERNS),
            )

        try:
            nodes, edges, _terminal_id = parser(args, itertools.count(1))
        except ParseFailure as e:
            return ParseError(message=str(e), supported_patterns=sorted(KNOWN_PATTERNS))
        return ParsedPipeline(nodes=nodes, edges=edges)


def _find_node(node_id: str, nodes: list[NodeDefinition]) -> NodeDefinition:
    for node in nodes:
        if node.id == node_id:
            return node
    raise ValueError(f"Node '{node_id}' not found in the pipeline definition.")


def _find_parent(node_id: str, edges: list[EdgeDefinition]) -> Optional[str]:
    for edge in edges:
        if edge.target_node_id == node_id:
            return edge.source_node_id
    return None


_DYNAMIC_ARRAY_FUNCS = ("FILTER(", "SORT(", "UNIQUE(", "XLOOKUP(", "CHOOSECOLS(")


def _determine_compatibility(formula: Optional[str]) -> str:
    if formula is None:
        return "N/A — no formula available for this pipeline"
    upper = formula.upper()
    if any(fn in upper for fn in _DYNAMIC_ARRAY_FUNCS):
        return "Requires Excel 365 (dynamic arrays)"
    return "Compatible with Excel 2016 and later"


# =====================================================================================
# Reverse parsing: tokenizing helpers
# =====================================================================================

def extract_call_parts(formula: str) -> tuple[str, list[str]]:
    """Returns (FUNCTION_NAME, [arg1, arg2, ...]) for a formula like "=FUNC(a, b, c)"."""
    text = formula.strip()
    if text.startswith("="):
        text = text[1:].strip()
    match = re.match(r"^([A-Za-z][A-Za-z0-9_.]*)\s*\((.*)\)\s*$", text, re.DOTALL)
    if not match:
        raise ParseFailure(f"Could not parse '{formula}' as a function call.")
    name = match.group(1).upper()
    args = _split_top_level_args(match.group(2))
    return name, args


def _split_top_level_args(inner: str) -> list[str]:
    """Splits a function's argument list on top-level commas, respecting nested
    parens/brackets and quoted strings (so a comma inside a nested call or a string literal
    doesn't incorrectly split an argument in two)."""
    inner = inner.strip()
    if inner == "":
        return []
    args: list[str] = []
    depth = 0
    current: list[str] = []
    in_string: Optional[str] = None
    for ch in inner:
        if in_string:
            current.append(ch)
            if ch == in_string:
                in_string = None
            continue
        if ch in ('"', "'"):
            in_string = ch
            current.append(ch)
            continue
        if ch in "([":
            depth += 1
            current.append(ch)
            continue
        if ch in ")]":
            depth -= 1
            current.append(ch)
            continue
        if ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    args.append("".join(current).strip())
    return args


def _strip_brackets(text: str) -> str:
    return text.strip().strip("[]").strip()


def _extract_unique_inner(text: str) -> Optional[str]:
    try:
        name, args = extract_call_parts(text)
    except ParseFailure:
        return None
    if name == "UNIQUE" and len(args) == 1:
        return _strip_brackets(args[0])
    return None


_CONDITION_RE = re.compile(r'^\s*\[?([^\]=<>!]+?)\]?\s*(<>|>=|<=|=|>|<)\s*(.+?)\s*$')
_EXCEL_TO_OPERATOR = {"=": "=", "<>": "≠", ">": ">", "<": "<", ">=": "≥", "<=": "≤"}


def _parse_condition(text: str) -> tuple[str, str, str]:
    match = _CONDITION_RE.match(text.strip())
    if not match:
        raise ParseFailure(
            f"Could not parse condition '{text}'. Only basic comparisons "
            "(=, <>, >, <, >=, <=) are supported for reverse parsing."
        )
    column, excel_op, value = match.groups()
    operator = _EXCEL_TO_OPERATOR.get(excel_op, excel_op)
    value = value.strip().strip('"').strip("'")
    return _strip_brackets(column), operator, value


# =====================================================================================
# Reverse parsing: recursive chain builder + per-pattern node constructors
# =====================================================================================

def _parse_node_chain(
    formula: str, id_counter: "itertools.count"
) -> tuple[list[NodeDefinition], list[EdgeDefinition], str]:
    """Recursively parses `formula` into (nodes, edges, terminal_node_id)."""
    text = formula.strip()
    try:
        name, args = extract_call_parts(text)
    except ParseFailure:
        node_id = f"n{next(id_counter)}"
        node = NodeDefinition(id=node_id, type="read_csv", config={"_source_range": text})
        return [node], [], node_id

    parser = KNOWN_PATTERNS.get(name)
    if parser is None:
        raise ParseFailure(
            f"'{name}' isn't a supported pattern yet. Supported: {', '.join(sorted(KNOWN_PATTERNS))}"
        )
    return parser(args, id_counter)


def _append_child(
    nodes: list[NodeDefinition], edges: list[EdgeDefinition], parent_id: str,
    node_type: str, config: dict, id_counter: "itertools.count",
) -> str:
    node_id = f"n{next(id_counter)}"
    nodes.append(NodeDefinition(id=node_id, type=node_type, config=config))
    edges.append(EdgeDefinition(source_node_id=parent_id, target_node_id=node_id))
    return node_id


def parse_filter_pattern(args, id_counter):
    if len(args) != 2:
        raise ParseFailure("FILTER expects exactly 2 arguments: FILTER(range, condition).")
    range_arg, condition_arg = args
    nodes, edges, parent_id = _parse_node_chain(range_arg, id_counter)
    column, operator, value = _parse_condition(condition_arg)
    node_id = _append_child(
        nodes, edges, parent_id, "filter", {"column": column, "operator": operator, "value": value}, id_counter
    )
    return nodes, edges, node_id


def parse_sort_pattern(args, id_counter):
    if len(args) < 2:
        raise ParseFailure("SORT expects at least 2 arguments: SORT(range, column, [order]).")
    range_arg = args[0]
    column = _strip_brackets(args[1])
    order = args[2].strip() if len(args) > 2 else "1"
    direction = "DESC" if order == "-1" else "ASC"
    nodes, edges, parent_id = _parse_node_chain(range_arg, id_counter)
    node_id = _append_child(nodes, edges, parent_id, "sort", {"column": column, "direction": direction}, id_counter)
    return nodes, edges, node_id


def parse_unique_pattern(args, id_counter):
    if len(args) != 1:
        raise ParseFailure("UNIQUE expects exactly 1 argument: UNIQUE(range).")
    nodes, edges, parent_id = _parse_node_chain(args[0], id_counter)
    node_id = _append_child(nodes, edges, parent_id, "remove_duplicates", {"columns": []}, id_counter)
    return nodes, edges, node_id


def _build_join_node(left_key: str, right_key: str, id_counter):
    left_id, right_id, join_id = (f"n{next(id_counter)}" for _ in range(3))
    nodes = [
        NodeDefinition(id=left_id, type="read_csv", config={}),
        NodeDefinition(id=right_id, type="read_csv", config={}),
        NodeDefinition(
            id=join_id, type="join",
            config={"left_key": left_key, "right_key": right_key, "join_type": "LEFT"},
        ),
    ]
    edges = [
        EdgeDefinition(source_node_id=left_id, target_node_id=join_id, target_port="left"),
        EdgeDefinition(source_node_id=right_id, target_node_id=join_id, target_port="right"),
    ]
    return nodes, edges, join_id


def _strip_right_prefix(text: str) -> str:
    text = _strip_brackets(text)
    if "!" in text:
        text = text.split("!", 1)[1]
    return text


def parse_xlookup_pattern(args, id_counter):
    if len(args) < 3:
        raise ParseFailure("XLOOKUP expects at least 3 arguments: XLOOKUP(lookup_value, lookup_array, return_array).")
    left_key = _strip_brackets(args[0])
    right_key = _strip_right_prefix(args[1])
    return _build_join_node(left_key, right_key, id_counter)


def parse_vlookup_pattern(args, id_counter):
    if len(args) < 3:
        raise ParseFailure(
            "VLOOKUP expects at least 3 arguments: VLOOKUP(lookup_value, table_array, col_index, [range_lookup])."
        )
    left_key = _strip_brackets(args[0])
    # VLOOKUP's table_array doesn't name its lookup column explicitly (unlike XLOOKUP) — best
    # effort: assume the same column name is used on both sides, a common real-world convention.
    right_key = left_key
    return _build_join_node(left_key, right_key, id_counter)


def _build_group_by_node(group_ref: str, criteria: str, value_ref: Optional[str], function: str, id_counter):
    group_column = _extract_unique_inner(criteria) or _strip_brackets(group_ref)
    nodes, edges, parent_id = _parse_node_chain(group_ref, id_counter)
    if function == "COUNT":
        aggregations = [{"column": group_column, "function": "COUNT"}]
    else:
        aggregations = [{"column": _strip_brackets(value_ref), "function": function}]
    node_id = _append_child(
        nodes, edges, parent_id, "group_by_aggregate",
        {"group_column": group_column, "aggregations": aggregations}, id_counter,
    )
    return nodes, edges, node_id


def parse_sumif_pattern(args, id_counter):
    if len(args) != 3:
        raise ParseFailure("SUMIF expects 3 arguments: SUMIF(group_range, criteria, sum_range).")
    group_ref, criteria, value_ref = args
    return _build_group_by_node(group_ref, criteria, value_ref, "SUM", id_counter)


def parse_averageif_pattern(args, id_counter):
    if len(args) != 3:
        raise ParseFailure("AVERAGEIF expects 3 arguments: AVERAGEIF(group_range, criteria, average_range).")
    group_ref, criteria, value_ref = args
    return _build_group_by_node(group_ref, criteria, value_ref, "AVERAGE", id_counter)


def parse_countif_pattern(args, id_counter):
    if len(args) != 2:
        raise ParseFailure("COUNTIF expects 2 arguments: COUNTIF(group_range, criteria).")
    group_ref, criteria = args
    return _build_group_by_node(group_ref, criteria, None, "COUNT", id_counter)


def parse_sumifs_pattern(args, id_counter):
    if len(args) != 3:
        raise ParseFailure(
            "Only single-criteria SUMIFS(sum_range, criteria_range, criteria) is supported for reverse parsing."
        )
    value_ref, group_ref, criteria = args
    return _build_group_by_node(group_ref, criteria, value_ref, "SUM", id_counter)


def parse_averageifs_pattern(args, id_counter):
    if len(args) != 3:
        raise ParseFailure(
            "Only single-criteria AVERAGEIFS(average_range, criteria_range, criteria) is supported for reverse parsing."
        )
    value_ref, group_ref, criteria = args
    return _build_group_by_node(group_ref, criteria, value_ref, "AVERAGE", id_counter)


def parse_countifs_pattern(args, id_counter):
    if len(args) != 2:
        raise ParseFailure(
            "Only single-criteria COUNTIFS(criteria_range, criteria) is supported for reverse parsing."
        )
    group_ref, criteria = args
    return _build_group_by_node(group_ref, criteria, None, "COUNT", id_counter)


KNOWN_PATTERNS = {
    "FILTER": parse_filter_pattern,
    "SORT": parse_sort_pattern,
    "UNIQUE": parse_unique_pattern,
    "XLOOKUP": parse_xlookup_pattern,
    "VLOOKUP": parse_vlookup_pattern,
    "SUMIF": parse_sumif_pattern,
    "SUMIFS": parse_sumifs_pattern,
    "AVERAGEIF": parse_averageif_pattern,
    "AVERAGEIFS": parse_averageifs_pattern,
    "COUNTIF": parse_countif_pattern,
    "COUNTIFS": parse_countifs_pattern,
}
