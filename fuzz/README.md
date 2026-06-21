# Cutctx Fuzz Testing

## Setup

```bash
# Install cargo-fuzz
cargo install cargo-fuzz

# Run a specific fuzzer
cd fuzz
cargo fuzz run fuzz_smart_crusher
cargo fuzz run fuzz_live_zone_anthropic
cargo fuzz run fuzz_diff_compressor

# Run with timeout (stop after 60s)
cargo fuzz run fuzz_smart_crusher -- -max_total_time=60

# Run with specific sanitizer
cargo fuzz run fuzz_smart_crusher -- -sanitizer=address
```

## Targets

| Target | Fuzzes | Input |
|--------|--------|-------|
| `fuzz_smart_crusher` | SmartCrusher.process_value() | Valid JSON |
| `fuzz_live_zone_anthropic` | compress_anthropic_live_zone() | Raw bytes (JSON body) |
| `fuzz_diff_compressor` | DiffCompressor.compress() | UTF-8 strings |

## Corpus

Fuzz corpora are stored in `fuzz/corpus/`. To add seed inputs:

```bash
# Add a seed JSON file
cp my_test.json fuzz/corpus/fuzz_smart_crusher/

# Minimize corpus
cargo fuzz tmin fuzz_smart_crusher
```

## Interpreting Results

- **Panic**: Bug found! The fuzzer will save the input to `fuzz/artifacts/`.
- **OOM**: Memory limit exceeded. Check for unbounded allocation.
- **Timeout**: Processing took too long. Check for algorithmic complexity issues.

## What We're Looking For

1. **Panics on malformed input** — any unwrap() or expect() on user data
2. **Memory exhaustion** — adversarial JSON causing huge allocations
3. **Incorrect compression** — valid input producing invalid output
4. **Edge cases** — empty arrays, deeply nested objects, very long strings
5. **Byte-range surgery errors** — off-by-one in live_zone replacement logic
