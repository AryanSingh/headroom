# crates/cutctx-core/src/transforms/smart_crusher/compaction/

## Responsibility
Builds and serializes a recursive compact intermediate representation for arrays of JSON objects.

## Design
The IR models schemas, rows, missing/scalar/nested/opaque cells, tables, and discriminator buckets. Classifiers recognize scalar, nested/stringified JSON, and opaque blobs; the compactor infers stable field order/types, flattens uniform objects, recursively compacts arrays, and buckets heterogeneous records. Formatter/walker modules traverse and render the IR.

## Flow
Classify array shape -> infer schema/discriminator -> convert values to cells and opaque references -> recurse into nested arrays or bucket record variants -> walker/formatter emit deterministic compact text; unsuitable inputs remain untouched.

## Integration
- Invoked by smart-crusher planning/execution.
- Uses serde JSON and stable hashing for opaque CCR references.
