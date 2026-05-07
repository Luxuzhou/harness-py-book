# exp2 Defense Layers Quantitative — Summary Report

Source: `results/raw.jsonl` (one row per attack × level × seed)
Generated: run `python regenerate_summary.py` to refresh.

## Overall Block Rate and framework_blocks Mean

| Level | N | Block Rate | framework_blocks mean |
|-------|---|-----------|----------------------|
| L0 | 30 | 26.7% | 0.00 |
| L1 | 30 | 83.3% | 0.70 |
| L2 | 30 | 90.0% | 1.07 |
| L3 | 30 | 83.3% | 0.93 |

## Per-Category Block Rate

| Level | content_leak | dangerous_command | path_traversal |
|-------|---|---|---|
| L0 | 0/6 (0%) | 7/9 (78%) | 1/15 (7%) |
| L1 | 6/6 (100%) | 8/9 (89%) | 11/15 (73%) |
| L2 | 6/6 (100%) | 8/9 (89%) | 13/15 (87%) |
| L3 | 6/6 (100%) | 8/9 (89%) | 11/15 (73%) |

## How framework_blocks is derived

`block_reason` strings like `framework_blocks=2` are parsed with the regex
`framework_blocks=(\d+)`. Rows without a match contribute 0.
