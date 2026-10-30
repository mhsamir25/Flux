# Node test suite — findings

`tests/nodes/test_node_execution_matrix.py` plus the per-stage integration modules in this
directory were written to answer one question: **why do so many nodes fail in the app when
their own unit tests pass?**

Short answer: they mostly don't fail inside the node. They fail in the seams between the
node and the engine — the source data never arrives, the config is never validated, or the
node succeeds while quietly producing the wrong rows. The per-node modules in
`tests/nodes/test_*.py` cover each node's arithmetic in isolation and cannot see any of that.

## How to read the suite

* `tests/conftest.py` — shared fixtures. The important one is `executor`, built with the
  `data_reference_cache` resolver exactly as `routers/pipeline.py` builds it. Without a
  resolver **every source node fails**, so a test suite that forgets it would "prove" the
  whole app is broken.
* `test_node_execution_matrix.py` — every one of the 17 node types, run through
  `DAGExecutor`, checked against the four invariants the rest of the app depends on:
  `success`, schema columns matching the real data, `total_row_count` matching the rows, and
  `preview_data` being strictly JSON-safe. One parametrized case per node, so a failure names
  the node.
* `test_source_nodes_integration.py`, `test_transform_integration.py`,
  `test_aggregate_integration.py`, `test_join_integration.py`, `test_output_integration.py` —
  the pipeline stages, source → processor → sink, each driven through the engine on data that
  came out of the real parser.
* `tests/test_pipeline_stages_integration.py` — whole pipelines, including the onboarding
  pipeline the app loads on first visit, plus partial execution, cycle rejection, skip
  cascading, the 100-row preview cap and export.
* `tests/test_api_node_lifecycle.py` — the same thing over HTTP, using the exact payload
  shape `Frontend/src/components/canvas/ReactFlowCanvas.jsx` sends.

Run everything with `pytest` from `Backend/`. Current state: **642 passed, 0 xfailed.**
Every bug below was found by a test in this suite, fixed, and the test kept as a permanent
regression test (each docstring says what used to go wrong).

## Bugs found and fixed

Each was a genuine defect, confirmed first as a failing test and then fixed in `app/`.

### 1. `read_xlsx` ignored its own `sheet_name` — multi-sheet workbooks always loaded sheet 1 ✅
`DAGExecutor._execute_source()` short-circuited to the already-parsed `FluxDataFrame` from the
`data_reference_id` cache and never re-parsed with the node's `sheet_name`. Since the cached
reference is the *only* way the app can feed an XLSX file (XLSX is binary, so there is no
inline-text path), the `sheet_name` field the config panel renders did nothing.

**Fix:** `DataReferenceCache` now keeps the upload bytes (`put(data, raw=...)`, `get_raw()`),
source nodes declare when their config changes *what* gets parsed via a new
`NodePlugin.requires_reparse()` hook (only `read_xlsx`, only when `sheet_name` is set), and the
executor re-parses from those bytes when asked. A cache entry with no raw bytes still falls
back to the cached frame rather than failing.

* `test_source_nodes_integration.py::test_read_xlsx_honours_its_sheet_name_config`
* `test_api_node_lifecycle.py::test_sheet_selection_on_the_node_itself_is_honoured`

### 2. Chart nodes never validated their config ✅
`ChartNode.execute()` is a pure pass-through, so a bar/line/pie chart pointed at a column that
doesn't exist — very easily the case after a `group_by_aggregate`, which renames `score` to
`score_average` — reported **success** and rendered an empty chart.

**Fix:** part of the shared root-cause fix below, plus `ChartNode.execute()` now validates its
own axes so direct callers get the same guarantee.

* `test_output_integration.py::test_chart_columns_must_exist_in_the_upstream_data`
* `test_output_integration.py::test_chart_config_pointing_at_a_pre_aggregation_column_fails_clearly`

### 3. `group_by_aggregate` COUNT counted non-null values, not rows ✅
It mapped straight onto pandas' `count` aggregation, which skips nulls, so a 3-row group with
one null reported 1 — while the node's own Excel export is `COUNTIF`, which counts rows. The
chart on the canvas and the generated spreadsheet formula disagreed about the same pipeline.

**Fix:** `COUNT` now maps to pandas' `size` (rows in the group). `COUNT_DISTINCT` already
covered "how many different values".

* `test_aggregate_integration.py::test_group_by_count_counts_rows_in_each_group`

### 4. `pivot` silently dropped rows with a missing key ✅
`DataFrame.pivot_table` defaults to `dropna=True` on both axes, so a row with a blank category
disappeared with no error and no warning. `group_by_aggregate` already passed `dropna=False`,
so the two aggregate nodes contradicted each other.

**Fix:** `dropna=False` on both axes, and a surviving null category is labelled `(blank)`
rather than producing a column literally named `nan`.

* `test_aggregate_integration.py::test_pivot_keeps_rows_whose_key_values_are_missing`

### 5. `convert_type` to DATE turned numbers into `1970-01-01 00:00:00.000000085` ✅
`pd.to_datetime(85, errors="coerce")` doesn't fail — it reads a bare int as nanoseconds since
the epoch, so converting an ID or count column produced nonsense dates and reported success.

**Fix:** numeric cells are masked out before parsing, so they become nulls and are reported as
row-level errors; a column that's already datetime-typed passes straight through.

* `test_transform_integration.py::test_convert_number_to_date_coerces_unconvertible_values_to_null`

### 6. `fill_missing` average/median on a string column failed with a pandas internal ✅
The canvas showed `Cannot perform reduction 'mean' with string dtype` instead of saying the
strategy doesn't apply to that column.

**Fix:** `infer_output_schema` (and therefore `execute`) rejects average/median on
non-reducible column types up front, naming the column, the strategy, and what to use instead.

* `test_transform_integration.py::test_fill_missing_average_on_a_string_column_fails_with_a_clear_message`

### 7. Unconfigured `select_columns` / `limit_rows` returned empty tables and reported success ✅
`df[[]]` quietly yielded zero columns and `config.get("count", 0)` turned a missing count into
zero rows, though both fields are declared required and both nodes' `infer_output_schema`
raise for the empty config.

**Fix:** part of the shared root-cause fix below.

* `test_transform_integration.py::test_unconfigured_select_columns_fails_instead_of_returning_an_empty_table`
* `test_transform_integration.py::test_unconfigured_limit_rows_fails_instead_of_returning_no_rows`

### The shared root cause behind 2, 6 and 7

`DAGExecutor._run()` never called `plugin.infer_output_schema()` before `execute()`. The plan's
NodePlugin contract (§5) has `infer_output_schema` raise `SchemaValidationError` with a
plain-English message precisely so bad config is caught without executing — but nothing in the
execution path called it, so every node that didn't independently re-validate degraded into
whatever pandas did next.

**Fix:** the executor now validates the config against the input schema inside the same `try`
block as `execute()`, turning a `SchemaValidationError` into that node's `NodeResult`. The
matrix test (`tests/nodes/test_node_execution_matrix.py`) is what proves this didn't change the
behaviour of any correctly-configured node.


## Notes, not bugs

* `preview_data` is already strictly JSON-safe (nulls serialize as `null`), so the
  NaN-poisons-the-whole-response failure mode is closed — worth keeping a test on, since one
  `float('nan')` leaking out of any node would take down live preview for the whole canvas.
* A back edge into a single-input node always trips the "already has a connected input"
  check before the cycle check, so the cycle branch of `/api/pipeline/validate-edge` is only
  reachable through a join's free port. Tested that way in
  `test_api_node_lifecycle.py::test_edge_validation_rejects_a_connection_that_would_create_a_cycle`.
* Source nodes' `infer_output_schema` returns an empty schema by design (a file's real
  columns are only known after parsing), so the matrix test doesn't hold them to the
  schema-matches-data invariant.
