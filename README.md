# retryq

A retry policy usually lives as a handful of numbers scattered across a
config file: max attempts, a base delay, a multiplier, maybe a cap, maybe
jitter. It's hard to look at those numbers and know, without doing the
arithmetic yourself, whether attempt 6 waits 2 seconds or 200, or how long
a caller could be stuck retrying before giving up.

`retryq` takes a policy as JSON and prints the schedule it actually
produces: the delay before each attempt, and the cumulative elapsed time
up to that attempt. For jittered policies it reports the delay as a
min/max range rather than a fake single number, since the real value is
random by design.

## Policy format

```json
{
  "max_attempts": 5,
  "base_delay": 0.5,
  "multiplier": 2.0,
  "max_delay": 10.0,
  "jitter": "full"
}
```

- `max_attempts` (required) — how many retry attempts the policy allows.
- `base_delay` (required) — delay in seconds before the first retry.
- `strategy` (default `"exponential"`) — how the delay grows with each
  attempt:
  - `exponential` — `base_delay * multiplier ^ (attempt - 1)`.
  - `linear` — `base_delay * attempt`.
  - `constant` — always `base_delay`.
- `multiplier` (default `2.0`) — growth factor for `exponential`. Only
  valid with that strategy; set it for `linear` or `constant` and retryq
  will reject the policy.
- `max_delay` (optional) — cap on the delay, applied before jitter.
- `jitter` (default `"none"`) — one of:
  - `none` — no randomness, delay is exactly the computed value.
  - `full` — delay is a random value between 0 and the computed value.
  - `equal` — delay is half fixed, half random on top of that.

## Usage

From a file:

```
$ retryq policy.json
attempt   delay (min)   delay (max)   elapsed (min)   elapsed (max)
-------------------------------------------------------------------
      1         0.00s         0.50s           0.00s           0.50s
      2         0.00s         1.00s           0.00s           1.50s
      3         0.00s         2.00s           0.00s           3.50s
      4         0.00s         4.00s           0.00s           7.50s
      5         0.00s         8.00s           0.00s          15.50s
```

From stdin, so it composes with whatever produced the config:

```
$ curl -s https://example.com/service-config.json | jq .retry | retryq
```

Or explicitly with `-`:

```
$ cat policy.json | retryq -
```

Ask about one attempt instead of the whole schedule:

```
$ retryq policy.json --attempt 3
attempt 3: delay between 0.00s and 2.00s
```

If the attempt number is beyond `max_attempts`, retryq says so instead of
printing a number:

```
$ retryq policy.json --attempt 9
attempt 9: no retry (max_attempts is 5)
```

## Install

No dependencies beyond the standard library. Run directly:

```
python -m retryq.cli policy.json
```

or install locally with `pip install -e .` to get the `retryq` command.

## Status

Early. Currently supports exponential, linear, and constant backoff,
with an optional cap and jitter, read from a file or stdin. See the
roadmap for what's planned.

## Tests

```
python -m unittest discover
```
