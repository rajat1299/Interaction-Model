# WP15 Active-Floor Diagnostic

**Verdict: FAIL.**

## Frozen identity

- Diagnostic spec: `sha256:c1a960f570b63a62d6bb4fcaf1e40581ae2fcc9f2deeb97f60e580a3349b288d`.
- Repository commit: `c91b55397274d57cbc05c8c874eb7f0d5f1be3dd`.
- Manifest: `sha256:87c824a2dad3c24fa05f7bd474dd8ef66a87532d3131dd9feb6932a4afee63b5`.
- Review: `sha256:761cb4a5f8c2f6755863741ad1d3c69fd1522073c5b29f3c0efc9bfed184a9e9`.
- Model: `gpt-5.6-terra` with reasoning effort `high`.
- Provider path: OpenAI Batch API targeting `/v1/responses`.

## Pre-registered gates

| Gate | Comparison | Threshold | Observed | Verdict |
|---|---:|---:|---:|---:|
| generation_schema_reference_license | >= | 1.0000 | 0.8889 | FAIL |
| active_floor_generation | >= | 1.0000 | 0.6667 | FAIL |
| active_floor_pairwise | >= | 1.0000 | 0.9444 | FAIL |
| active_floor_listwise | >= | 1.0000 | 1.0000 | PASS |
| yielded_floor_generation | >= | 1.0000 | 1.0000 | PASS |
| yielded_floor_pairwise | >= | 1.0000 | 1.0000 | PASS |
| yielded_floor_listwise | >= | 1.0000 | 1.0000 | PASS |
| yielded_semantic_text | >= | 1.0000 | 1.0000 | PASS |
| control_generation | >= | 1.0000 | 1.0000 | PASS |
| control_pairwise | >= | 1.0000 | 1.0000 | PASS |
| control_listwise | >= | 1.0000 | 1.0000 | PASS |
| pairwise_expected_a | >= | 1.0000 | 0.9815 | FAIL |
| pairwise_expected_b | >= | 1.0000 | 0.9815 | FAIL |
| family10_pairwise_v1 | >= | 1.0000 | 1.0000 | PASS |
| family10_pairwise_v2 | >= | 1.0000 | 0.9167 | FAIL |
| family10_pairwise_v3 | >= | 1.0000 | 1.0000 | PASS |
| position_bias | <= | 0.0000 | 0.0000 | PASS |
| family10_paraphrase_spread | <= | 0.1000 | 0.0833 | PASS |

## Cost

- Provider-usage charge under pinned Batch pricing: `$0.574256`.
- Total decoded provider usage:

```json
{
  "cache_write_tokens": 85437,
  "cached_input_tokens": 1769097,
  "input_tokens": 1936801,
  "output_tokens": 15572,
  "reasoning_tokens": 12783
}
```
- Usage submitted during the final/resume invocation:

```json
{
  "cache_write_tokens": 85437,
  "cached_input_tokens": 1769097,
  "input_tokens": 1936801,
  "output_tokens": 15572,
  "reasoning_tokens": 12783
}
```
- Offline estimate:

```json
{
  "request_counts": {
    "generation": 18,
    "listwise": 18,
    "pairwise": 108,
    "semantic_text_grading": 6,
    "total": 150
  },
  "token_assumptions": {
    "expected_input_tokens": 2040049,
    "expected_output_tokens": 35700
  },
  "usd": {
    "all_calls_one_retry_warm_cache": "2.843820",
    "batch_no_cache": "2.817811",
    "synchronous_no_cache": "5.635622",
    "synchronous_warm_cache": "1.309410"
  }
}
```

## Batch jobs

- `p0` shard 0: `batch_6a55d3d34dec8190837abb16dcba75cf`; 60 requests; input `sha256:93084a2be2ac11dc0b48e7e07fe301f268141394196f9a235448667096cd20cf`; output `sha256:fa8da3044ecb2557cb23d71f457efb4ff5e52e1050bb78f7a872feeb6be2ccf6`; error `None`; status `completed`.
- `p0` shard 1: `batch_6a55d47ea7208190986cf659a3491cc3`; 61 requests; input `sha256:ff8ccd1b6d2ce5fe67bd5227fe79ab47be2000e8bf15def9fa893ba8409d1102`; output `sha256:d6aec7859d6d8f7e85eb71ad23977a22e3ef3e4784e8ad4225c40aa0525c7d3f`; error `None`; status `completed`.
- `p0` shard 2: `batch_6a55d52961188190a3c274eec1f55e4c`; 23 requests; input `sha256:8f60544be954acbd49040842ea88ade896cec4954ead0ea76822da7b4577df18`; output `sha256:11d40ae2f4ec1596c2970ce8d726c50c9f1040bed7def71fd27cc7234755a022`; error `None`; status `completed`.
- `s0` shard 0: `batch_6a55d5955e548190a4c6311e2e90e4fd`; 6 requests; input `sha256:d28b5ccf92b03cb4363a6ecc8799a335292990892070372ca1bf1a78f050da06`; output `sha256:39c90e6db8e0f4f23f8a4da493a04a28ff2ce2c243c84e6a11193fb05443a853`; error `None`; status `completed`.

## Full diagnostic metrics

```json
{
  "active_floor": {
    "generation": {
      "passed": 4,
      "rate": 0.6666666666666666,
      "total": 6
    },
    "listwise": {
      "passed": 6,
      "rate": 1.0,
      "total": 6
    },
    "pairwise": {
      "passed": 34,
      "rate": 0.9444444444444444,
      "total": 36
    }
  },
  "all_gates_passed": false,
  "controls": {
    "generation": {
      "passed": 6,
      "rate": 1.0,
      "total": 6
    },
    "listwise": {
      "passed": 6,
      "rate": 1.0,
      "total": 6
    },
    "pairwise": {
      "passed": 36,
      "rate": 1.0,
      "total": 36
    }
  },
  "family10_pairwise_variant_accuracy": {
    "v1": {
      "passed": 24,
      "rate": 1.0,
      "total": 24
    },
    "v2": {
      "passed": 22,
      "rate": 0.9166666666666666,
      "total": 24
    },
    "v3": {
      "passed": 24,
      "rate": 1.0,
      "total": 24
    }
  },
  "family10_paraphrase_spread": 0.08333333333333337,
  "gates": {
    "active_floor_generation": {
      "comparison": ">=",
      "observed": 0.6666666666666666,
      "passed": false,
      "threshold": 1.0
    },
    "active_floor_listwise": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "active_floor_pairwise": {
      "comparison": ">=",
      "observed": 0.9444444444444444,
      "passed": false,
      "threshold": 1.0
    },
    "control_generation": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "control_listwise": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "control_pairwise": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "family10_pairwise_v1": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "family10_pairwise_v2": {
      "comparison": ">=",
      "observed": 0.9166666666666666,
      "passed": false,
      "threshold": 1.0
    },
    "family10_pairwise_v3": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "family10_paraphrase_spread": {
      "comparison": "<=",
      "observed": 0.08333333333333337,
      "passed": true,
      "threshold": 0.1
    },
    "generation_schema_reference_license": {
      "comparison": ">=",
      "observed": 0.8888888888888888,
      "passed": false,
      "threshold": 1.0
    },
    "pairwise_expected_a": {
      "comparison": ">=",
      "observed": 0.9814814814814815,
      "passed": false,
      "threshold": 1.0
    },
    "pairwise_expected_b": {
      "comparison": ">=",
      "observed": 0.9814814814814815,
      "passed": false,
      "threshold": 1.0
    },
    "position_bias": {
      "comparison": "<=",
      "observed": 0.0,
      "passed": true,
      "threshold": 0.0
    },
    "yielded_floor_generation": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "yielded_floor_listwise": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "yielded_floor_pairwise": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    },
    "yielded_semantic_text": {
      "comparison": ">=",
      "observed": 1.0,
      "passed": true,
      "threshold": 1.0
    }
  },
  "generation_safety": {
    "passed": 16,
    "rate": 0.8888888888888888,
    "total": 18
  },
  "pairwise_position": {
    "bias": 0.0,
    "expected_a": {
      "passed": 53,
      "rate": 0.9814814814814815,
      "total": 54
    },
    "expected_b": {
      "passed": 53,
      "rate": 0.9814814814814815,
      "total": 54
    }
  },
  "population": {
    "absolute_one_correction_ceiling": 300,
    "active_floor_probe_ids": [
      "f10-t01-a",
      "f10-t02-a",
      "f10-t03-a",
      "f10-t04-a",
      "f10-t05-a",
      "f10-t06-a"
    ],
    "control_probe_ids": [
      "f07-t01-a",
      "f07-t02-a",
      "f07-t03-a",
      "f07-t04-a",
      "f07-t05-a",
      "f07-t06-a"
    ],
    "diagnostic_spec_sha256": "sha256:c1a960f570b63a62d6bb4fcaf1e40581ae2fcc9f2deeb97f60e580a3349b288d",
    "expected_semantic_requests": 6,
    "logical_probes": 18,
    "passing_path_requests": 150,
    "primary_requests": 144,
    "yielded_floor_probe_ids": [
      "f10-t01-b",
      "f10-t02-b",
      "f10-t03-b",
      "f10-t04-b",
      "f10-t05-b",
      "f10-t06-b"
    ]
  },
  "yielded_floor": {
    "generation": {
      "passed": 6,
      "rate": 1.0,
      "total": 6
    },
    "listwise": {
      "passed": 6,
      "rate": 1.0,
      "total": 6
    },
    "pairwise": {
      "passed": 36,
      "rate": 1.0,
      "total": 36
    }
  },
  "yielded_semantic_text": {
    "passed": 6,
    "rate": 1.0,
    "total": 6
  }
}
```
