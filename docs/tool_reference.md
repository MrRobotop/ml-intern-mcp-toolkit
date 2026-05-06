# Tool reference

Generated from the live MCP server registrations by
``scripts/gen_tool_reference.py``. Do not edit by hand; run ``make docs`` to
regenerate after modifying any tool definition.

Two servers ship in this toolkit:

| Server | Tools | Source |
|---|---|---|
| ``arxiv-deep`` | paper fetch, figure extraction, code-link discovery, structured implementation brief | [arxiv_deep/](../arxiv_deep) |
| ``experiment-tracker`` | run lifecycle, metric and artifact logging, comparison and winner selection | [experiment_tracker/](../experiment_tracker) |

Tool naming inside ml-intern follows ``fastmcp``'s convention: each tool
appears as ``<server-name>_<tool-name>`` in the agent's registered-tools list,
e.g. ``arxiv-deep_fetch_paper``. The bare names below match the function
exported from each server.

## `arxiv-deep`

### `extract_figures`

Extracts every figure from an arxiv paper PDF and returns one entry per figure. Accepts the bare arxiv ID (e.g. '2305.14314'), the 'arXiv:<id>' form, or a full arxiv abs/pdf URL. Call this when the user wants to inspect, summarise, or reason about figures from a paper, after fetch_paper has confirmed the paper is available. Raster figures (embedded JPEG/PNG XObjects) are extracted directly; pages whose captions reference a figure but contain only vector graphics are rendered to PNG so vector figures are still surfaced. Returns a list of dicts, each with keys: page_number (int, 1-indexed), caption (str, the 'Figure N:' line plus the following line; may be empty when no caption is detected), image_path (str, absolute path to a PNG on disk). Extracted PNGs are cached on disk so repeat calls for the same paper are cheap.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `arxiv_id` | `string` | yes | Arxiv Id |

**Output schema**

```json
{
  "properties": {
    "result": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Result",
      "type": "array"
    }
  },
  "required": [
    "result"
  ],
  "title": "extract_figuresOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``arxiv-deep_extract_figures``

### `fetch_paper`

Fetches the title, authors, abstract, full body text, publication date, and arxiv categories for a paper given its arxiv ID. Accepts the bare ID (e.g. '2305.14314'), the 'arXiv:<id>' form, or a full arxiv abs/pdf URL. Always call this before any other arxiv-deep tool when working with a new paper. Returns a dict with keys: title, authors, abstract, full_text, published_date, categories. The PDF is cached on disk so repeat calls within or across sessions are cheap.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `arxiv_id` | `string` | yes | Arxiv Id |

**Output schema**

```json
{
  "additionalProperties": true,
  "title": "fetch_paperDictOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``arxiv-deep_fetch_paper``

### `find_reference_code`

Scans the full text of an arxiv paper for github.com URLs and reports each unique URL together with surrounding context and a reachability flag. Call this after fetch_paper to discover the official code implementations the authors link to (the agent should prefer these over third-party reimplementations). Returns a list of dicts, each with keys: url (str, the canonical GitHub URL), context (str, roughly 200 characters of paper text surrounding the URL), and validated (bool, True iff an HTTP HEAD against the URL returned a 2xx response within 5 seconds). URLs are de-duplicated case-sensitively and preserved in the order they first appear in the paper. The tool never raises for individual URL failures; it sets validated=False and logs a warning instead, so the agent can still surface unreachable links to the user.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `arxiv_id` | `string` | yes | Arxiv Id |

**Output schema**

```json
{
  "properties": {
    "result": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Result",
      "type": "array"
    }
  },
  "required": [
    "result"
  ],
  "title": "find_reference_codeOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``arxiv-deep_find_reference_code``

### `implementation_brief`

Synthesises a structured implementation brief for an arxiv paper. Internally calls fetch_paper and find_reference_code, then runs heuristic regex/keyword extractors over the abstract and body text to surface fields a developer needs to start reproducing the work. Returns a dict with keys: title (str), core_method (str, the opening sentences of the abstract), architecture (list[str], detected components and base models), hyperparameters (dict[str, str], detected values keyed by canonical parameter name), dataset (list[str], detected dataset names), eval_protocol (str, first paragraph after an Evaluation/Experiments/Results heading; empty if not found), and reference_implementations (list[dict], the output of find_reference_code). Extraction is fuzzy by design and prefers recall over precision; treat empty fields as 'unknown' rather than 'absent from the paper'.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `arxiv_id` | `string` | yes | Arxiv Id |

**Output schema**

```json
{
  "additionalProperties": true,
  "title": "implementation_briefDictOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``arxiv-deep_implementation_brief``

## `experiment-tracker`

### `best_run`

Returns the run with the best final value of a metric, optionally filtered. Use this when the agent needs to pick a winner (e.g. for model upload). Inputs: metric_name (e.g. 'accuracy'), direction ('max' for higher-is-better, 'min' for lower-is-better; default 'max'), and an optional filters dict with the same keys list_runs accepts (recipe, model_base, dataset, status), AND-combined. The 'best' run is the one whose final metric value (the Metric row with the highest step for that (run, metric_name) pair) is the maximum or minimum across the candidate set. Returns the same dict shape as list_runs entries (run_uid, recipe, model_base, dataset, hyperparameters, status, created_at, notes), or None if the database is empty, no run matches the filters, or no candidate run has a value for metric_name. Does not raise on missing data; the agent should check for None.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `metric_name` | `string` | yes | Metric Name |
| `direction` | `string` | no | Direction |
| `filters` | `{'additionalProperties': True, 'type': 'object'} \| {'type': 'null'}` | no | Filters |

**Output schema**

```json
{
  "properties": {
    "result": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Result"
    }
  },
  "required": [
    "result"
  ],
  "title": "best_runOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``experiment-tracker_best_run``

### `compare_runs`

Renders a Markdown table comparing the final value of a single metric across an explicit list of runs. Call this when the agent needs to reason about how several runs stack up on one metric (e.g. final accuracy or final loss). Inputs: run_uids (list of run_uid strings as returned by start_run / list_runs) and metric_name (e.g. 'accuracy', 'loss'). Returns a Markdown table with columns run_uid (truncated to the first 8 characters), recipe, hyperparameters (compact JSON), and the final value of metric_name. The 'final value' is the Metric row with the highest step for that (run, metric_name) pair. Rows are sorted by metric value, highest first; runs with no recorded value for the metric render as 'n/a' and sort to the bottom. Raises RunNotFoundError if any run_uid does not exist.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `run_uids` | `array` | yes | Run Uids |
| `metric_name` | `string` | yes | Metric Name |

**Output schema**

```json
{
  "properties": {
    "result": {
      "title": "Result",
      "type": "string"
    }
  },
  "required": [
    "result"
  ],
  "title": "compare_runsOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``experiment-tracker_compare_runs``

### `complete_run`

Marks a run as terminal by updating its status. Call this once a training attempt has finished, regardless of outcome. The status argument must be 'completed' (default, for successful runs) or 'failed' (for runs that crashed or produced unusable artifacts); any other value raises a ValueError so the agent can correct the call. Raises RunNotFoundError if the run_uid does not match a row, which is how the agent should detect a typo or a stale handle. Returns the updated row as a dict with the same shape that list_runs returns.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `run_uid` | `string` | yes | Run Uid |
| `status` | `string` | no | Status |

**Output schema**

```json
{
  "additionalProperties": true,
  "title": "complete_runDictOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``experiment-tracker_complete_run``

### `list_runs`

Lists run rows, optionally narrowed by exact-match filters. Call this to discover prior runs before deciding whether to start a new one or to feed compare_runs / best_run. The filters argument is a dict whose keys may include any subset of: recipe, model_base, dataset, status. All supplied filters are AND-ed together; unknown keys are ignored. Pass None or an empty dict to return every row. An empty database returns an empty list, never an error. Returns a list of dicts, each with keys: run_uid (str), id (int), recipe (str), model_base (str), dataset (str), hyperparameters (dict, the original JSON-round-tripped value), status (str, one of 'running', 'completed', 'failed'), notes (str, empty when no notes were supplied to start_run), and created_at (str, ISO 8601 UTC timestamp).

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `filters` | `{'additionalProperties': True, 'type': 'object'} \| {'type': 'null'}` | no | Filters |

**Output schema**

```json
{
  "properties": {
    "result": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Result",
      "type": "array"
    }
  },
  "required": [
    "result"
  ],
  "title": "list_runsOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``experiment-tracker_list_runs``

### `log_artifact`

Records one artifact (model weights, checkpoint, or log file) produced by an existing run, identified by its run_uid (the opaque string handle returned by start_run). Call this whenever a training run materialises an output the agent might want to reference later, for example after pushing a fine-tuned model to the Hub or saving an intermediate checkpoint. Inputs: run_uid (str), kind (str, free-form label such as 'model', 'checkpoint', or 'log'), uri (str, where the artifact lives, e.g. an hf:// or file:// URL). Returns a dict with keys logged (bool, always True on success) and artifact_id (int, the database row id of the newly inserted artifact). Raises RunNotFoundError if run_uid does not match any existing run; the agent should call start_run first or verify the uid via list_runs. Multiple artifacts per run are allowed; the same (kind, uri) tuple may be logged repeatedly and each call appends a new row.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `run_uid` | `string` | yes | Run Uid |
| `kind` | `string` | yes | Kind |
| `uri` | `string` | yes | Uri |

**Output schema**

```json
{
  "additionalProperties": true,
  "title": "log_artifactDictOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``experiment-tracker_log_artifact``

### `log_metric`

Records one metric value for an existing run, identified by its run_uid (the opaque string handle returned by start_run). Call this after each training step to build the time series the agent will later compare across runs. Inputs: run_uid (str), step (int, monotonically increasing within a run by convention but not enforced), name (str, the metric label such as 'loss' or 'accuracy'), value (float). Returns a dict with keys logged (bool, always True on success) and metric_id (int, the database row id of the newly inserted metric). Raises RunNotFoundError if run_uid does not match any existing run; the agent should call start_run first or verify the uid via list_runs. The same (step, name) tuple may be logged multiple times: each call appends a new row, no implicit deduplication.

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `run_uid` | `string` | yes | Run Uid |
| `step` | `integer` | yes | Step |
| `name` | `string` | yes | Name |
| `value` | `number` | yes | Value |

**Output schema**

```json
{
  "additionalProperties": true,
  "title": "log_metricDictOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``experiment-tracker_log_metric``

### `start_run`

Creates a new run row for a fine-tuning attempt and returns its handle. Call this exactly once at the start of every training attempt, before logging metrics or artifacts. The tool is NOT idempotent: each call inserts a new row with a fresh run_uid, so retrying after a transient client error will produce a duplicate run. Required arguments: recipe (str, the recipe name such as 'lora-rank-8'), model_base (str, the base model identifier such as 'Qwen/Qwen3-VL-2B-Instruct'), dataset (str, the training dataset identifier such as 'oxford-pets'), and hyperparameters (dict, an arbitrary nested JSON-serialisable dict round-tripped through a SQLite JSON column). Optional notes (str) is free-form prose, default empty string. The new row's status is set to 'running'; flip it later via complete_run. Returns a dict with keys: run_uid (str, a 32-character uuid4 hex used as the agent-facing handle for every other tracker tool) and id (int, the integer primary key, surfaced for joins and rarely needed by the agent directly).

**Input parameters**

| Name | Type | Required | Description |
|---|---|---|---|
| `recipe` | `string` | yes | Recipe |
| `model_base` | `string` | yes | Model Base |
| `dataset` | `string` | yes | Dataset |
| `hyperparameters` | `object` | yes | Hyperparameters |
| `notes` | `string` | no | Notes |

**Output schema**

```json
{
  "additionalProperties": true,
  "title": "start_runDictOutput",
  "type": "object"
}
```

**Agent-facing name (under ml-intern)**: ``experiment-tracker_start_run``
