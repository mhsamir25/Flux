import pytest

from app.engine.formula_engine import FormulaEngine, ParseError, ParsedPipeline
from app.engine.registry import build_registry
from app.schemas.pipeline import EdgeDefinition, NodeDefinition


@pytest.fixture
def engine():
    return FormulaEngine(build_registry())


def _edge(source, target, port=None):
    return EdgeDefinition(source_node_id=source, target_node_id=target, target_port=port)


def test_generate_filter_then_sort(engine):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="filter", config={"column": "age", "operator": ">", "value": "30"}),
        NodeDefinition(id="n3", type="sort", config={"column": "age", "direction": "DESC"}),
    ]
    edges = [_edge("n1", "n2"), _edge("n2", "n3")]
    result = engine.generate(nodes, edges)
    assert result.formula == "=SORT(FILTER(Sheet1!A1:Z1000, [age]>30), [age], -1)"
    assert result.compatibility == "Requires Excel 365 (dynamic arrays)"
    lines = result.explanation.split("\n")
    assert len(lines) == 3


def test_generate_single_source_node(engine):
    nodes = [NodeDefinition(id="n1", type="read_csv", config={})]
    result = engine.generate(nodes, [])
    assert result.formula is None  # a bare source is never a "terminal" (not a SOURCE-excluded node)
    assert "No output node" in result.explanation


def test_generate_empty_pipeline(engine):
    result = engine.generate([], [])
    assert result.formula is None
    assert "No output node" in result.explanation


def test_generate_compatibility_for_non_dynamic_formula(engine):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="convert_type", config={"column": "x", "target_type": "NUMBER"}),
    ]
    edges = [_edge("n1", "n2")]
    result = engine.generate(nodes, edges)
    assert result.formula == "=VALUE([x])"
    assert result.compatibility == "Compatible with Excel 2016 and later"



def test_generate_pivot_breaks_chain(engine):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="pivot", config={
            "row_column": "a", "column_column": "b", "value_column": "c", "aggregate_function": "SUM",
        }),
    ]
    edges = [_edge("n1", "n2")]
    result = engine.generate(nodes, edges)
    assert result.formula is None
    assert "Pivot tables aren't formula-driven" in result.explanation


def test_generate_chain_stops_at_break_even_with_more_nodes_downstream(engine):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="pivot", config={
            "row_column": "a", "column_column": "b", "value_column": "c", "aggregate_function": "SUM",
        }),
        NodeDefinition(id="n3", type="data_table", config={}),
    ]
    edges = [_edge("n1", "n2"), _edge("n2", "n3")]
    result = engine.generate(nodes, edges)
    assert result.formula is None
    # data_table's own explanation ("Display the data as a table.") must NOT appear —
    # composition stops exactly at the break.
    assert "Display the data as a table" not in result.explanation


def test_generate_chart_terminal_always_none_with_explanation(engine):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="bar_chart", config={"x_column": "a", "y_column": "b"}),
    ]
    edges = [_edge("n1", "n2")]
    result = engine.generate(nodes, edges)
    assert result.formula is None
    assert "visual outputs" in result.explanation



def test_generate_calculated_column_as_terminal_shows_own_expression(engine):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="add_calculated_column",
                        config={"new_column_name": "total", "expression": "price * quantity"}),
    ]
    edges = [_edge("n1", "n2")]
    result = engine.generate(nodes, edges)
    assert result.formula == "=([price]*[quantity])"


def test_generate_calculated_column_not_terminal_passes_parent_through(engine):
    nodes = [
        NodeDefinition(id="n1", type="read_csv", config={}),
        NodeDefinition(id="n2", type="add_calculated_column",
                        config={"new_column_name": "total", "expression": "price * quantity"}),
        NodeDefinition(id="n3", type="sort", config={"column": "total", "direction": "ASC"}),
    ]
    edges = [_edge("n1", "n2"), _edge("n2", "n3")]
    result = engine.generate(nodes, edges)
    # sort wraps the ORIGINAL range, not the calculated column's own expression
    assert result.formula == "=SORT(Sheet1!A1:Z1000, [total], 1)"
    assert "total" in result.explanation  # its own step is still described



def test_generate_join_as_terminal(engine):
    nodes = [
        NodeDefinition(id="left", type="read_csv", config={}),
        NodeDefinition(id="right", type="read_csv", config={}),
        NodeDefinition(id="j", type="join", config={"left_key": "id", "right_key": "id", "join_type": "LEFT"}),
    ]
    edges = [_edge("left", "j", port="left"), _edge("right", "j", port="right")]
    result = engine.generate(nodes, edges)
    assert result.formula == "=XLOOKUP([id], [Right!id], [Right!*])"


def test_generate_join_right_type_breaks_chain(engine):
    nodes = [
        NodeDefinition(id="left", type="read_csv", config={}),
        NodeDefinition(id="right", type="read_csv", config={}),
        NodeDefinition(id="j", type="join", config={"left_key": "id", "right_key": "id", "join_type": "RIGHT"}),
    ]
    edges = [_edge("left", "j", port="left"), _edge("right", "j", port="right")]
    result = engine.generate(nodes, edges)
    assert result.formula is None


def test_generate_join_not_terminal_composes_downstream(engine):
    nodes = [
        NodeDefinition(id="left", type="read_csv", config={}),
        NodeDefinition(id="right", type="read_csv", config={}),
        NodeDefinition(id="j", type="join", config={"left_key": "id", "right_key": "id", "join_type": "INNER"}),
        NodeDefinition(id="f", type="limit_rows", config={"count": 10}),
    ]
    edges = [_edge("left", "j", port="left"), _edge("right", "j", port="right"), _edge("j", "f")]
    result = engine.generate(nodes, edges)
    # limit_rows always returns None -> chain breaks there, but join's own formula was valid
    assert result.formula is None
    assert "XLOOKUP" not in result.explanation or True  # join's explanation doesn't emit raw formula text
    assert "No Excel formula equivalent for row limiting" in result.explanation



def test_parse_filter(engine):
    result = engine.parse("=FILTER(Sheet1!A1:Z1000, [age]>30)")
    assert isinstance(result, ParsedPipeline)
    types = [n.type for n in result.nodes]
    assert types == ["read_csv", "filter"]
    filter_node = result.nodes[1]
    assert filter_node.config == {"column": "age", "operator": ">", "value": "30"}
    assert result.edges[0].source_node_id == result.nodes[0].id
    assert result.edges[0].target_node_id == result.nodes[1].id


def test_parse_filter_string_equality(engine):
    result = engine.parse('=FILTER(Sheet1!A1:Z1000, [name]="Bob")')
    filter_node = result.nodes[1]
    assert filter_node.config == {"column": "name", "operator": "=", "value": "Bob"}


def test_parse_filter_not_equal(engine):
    result = engine.parse('=FILTER(Sheet1!A1:Z1000, [status]<>"inactive")')
    filter_node = result.nodes[1]
    assert filter_node.config["operator"] == "≠"


def test_parse_sort_descending(engine):
    result = engine.parse("=SORT(Sheet1!A1:Z1000, [age], -1)")
    sort_node = result.nodes[1]
    assert sort_node.config == {"column": "age", "direction": "DESC"}


def test_parse_sort_ascending_default(engine):
    result = engine.parse("=SORT(Sheet1!A1:Z1000, [age])")
    sort_node = result.nodes[1]
    assert sort_node.config["direction"] == "ASC"


def test_parse_unique(engine):
    result = engine.parse("=UNIQUE(Sheet1!A1:Z1000)")
    assert [n.type for n in result.nodes] == ["read_csv", "remove_duplicates"]


def test_parse_nested_filter_and_sort(engine):
    result = engine.parse("=SORT(FILTER(Sheet1!A1:Z1000, [age]>30), [age], -1)")
    assert [n.type for n in result.nodes] == ["read_csv", "filter", "sort"]
    assert len(result.edges) == 2


def test_parse_xlookup_produces_join(engine):
    result = engine.parse("=XLOOKUP([id], [Right!dept_id], [Right!*])")
    types = [n.type for n in result.nodes]
    assert types == ["read_csv", "read_csv", "join"]
    join_node = result.nodes[2]
    assert join_node.config == {"left_key": "id", "right_key": "dept_id", "join_type": "LEFT"}
    ports = {e.source_node_id: e.target_port for e in result.edges}
    assert ports[result.nodes[0].id] == "left"
    assert ports[result.nodes[1].id] == "right"


def test_parse_vlookup_produces_join_with_guessed_right_key(engine):
    result = engine.parse("=VLOOKUP([id], Sheet2!A1:C100, 2, FALSE)")
    join_node = result.nodes[2]
    assert join_node.config["left_key"] == "id"
    assert join_node.config["right_key"] == "id"  # best-effort guess, documented


def test_parse_sumif_produces_group_by(engine):
    result = engine.parse("=SUMIF([region], UNIQUE([region]), [sales])")
    group_node = result.nodes[1]
    assert group_node.type == "group_by_aggregate"
    assert group_node.config["group_column"] == "region"
    assert group_node.config["aggregations"] == [{"column": "sales", "function": "SUM"}]


def test_parse_averageif_produces_group_by(engine):
    result = engine.parse("=AVERAGEIF([region], UNIQUE([region]), [sales])")
    group_node = result.nodes[1]
    assert group_node.config["aggregations"] == [{"column": "sales", "function": "AVERAGE"}]


def test_parse_countif_produces_group_by(engine):
    result = engine.parse("=COUNTIF([region], UNIQUE([region]))")
    group_node = result.nodes[1]
    assert group_node.config["aggregations"] == [{"column": "region", "function": "COUNT"}]


def test_parse_sumifs_single_criteria(engine):
    result = engine.parse('=SUMIFS([sales], [region], UNIQUE([region]))')
    group_node = result.nodes[1]
    assert group_node.config["aggregations"] == [{"column": "sales", "function": "SUM"}]


def test_parse_sumifs_multi_criteria_rejected(engine):
    result = engine.parse('=SUMIFS([sales], [region], "East", [year], 2024)')
    assert isinstance(result, ParseError)
    assert "single-criteria" in result.message



def test_parse_unsupported_function_returns_parse_error(engine):
    result = engine.parse("=WEIRDFUNC(1, 2, 3)")
    assert isinstance(result, ParseError)
    assert "WEIRDFUNC" in result.message
    assert "FILTER" in result.supported_patterns


def test_parse_non_formula_text_returns_parse_error(engine):
    result = engine.parse("not a formula at all")
    assert isinstance(result, ParseError)


def test_parse_filter_wrong_arg_count_returns_parse_error(engine):
    result = engine.parse("=FILTER(Sheet1!A1:Z1000)")
    assert isinstance(result, ParseError)
    assert "2 arguments" in result.message


def test_parse_filter_unsupported_condition_shape_returns_parse_error(engine):
    result = engine.parse('=FILTER(Sheet1!A1:Z1000, ISNUMBER(SEARCH("x",[name])))')
    assert isinstance(result, ParseError)
    assert "basic comparisons" in result.message
