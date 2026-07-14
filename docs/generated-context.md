# Generated Context Contract

Status: versioned shared contract for bounded Gauntlet machine projections.

`scripts/generated_context.py` renders human-readable child context from named source files. It does not rewrite those sources or make a model request. The renderer uses literal, versioned prompt-family templates and appends ticket- and attempt-specific material after a byte-stable prefix.

## Version 1 manifest

The input is a strict JSON object:

```json
{
  "schema_version": 1,
  "family": "implementation",
  "template_version": 1,
  "stable_sources": [
    {"role": "global", "id": "global-v1", "path": "shared/global-v1.md"},
    {"role": "cohort", "id": "context-v1", "path": "shared/context-v1.md"},
    {"role": "dependency", "id": "api-v2", "path": "contracts/api-v2.md"}
  ],
  "volatile_sources": [
    {"role": "ticket", "id": "ticket", "path": "tickets/T01.md"},
    {"role": "handoff", "id": "handoff", "path": "handoffs/T01-A1.md"}
  ]
}
```

Version 1 supports the `implementation`, `research`, and `review` families. Every family and template version maps to one literal file below `templates/generated-context/`. Templates contain no interpolation markers. Adding or changing stable instruction text requires a new template version.

Stable context requires exactly one `global` and one `cohort` source, plus zero or more `dependency` sources. Volatile context requires exactly one `ticket` and one `handoff` source. The renderer sorts sources by role and source ID, preserves each source's UTF-8 bytes, and rejects unknown fields, a volatile role in the stable phase, duplicate IDs/files/content, empty critical context, caller-supplied padding, and caller-supplied provenance claims.

The rendered byte order is:

```text
literal family template
global source
cohort source
dependency sources
assigned-ticket heading          <- stable prefix ends here
ticket source
receipt-handoff heading
handoff source                   <- volatile material is last
```

This layout makes the stable-prefix digest identical when only a ticket or handoff changes. It is an exact-byte property, not a claim that a host or model will cache the prefix.

## Provenance and privacy

The renderer reads each source locally and records its source ID, role, phase, byte length, and SHA-256 digest. A plain digest detects byte changes; it does not authenticate who produced the source. Metadata therefore declares `"authenticated": false` and rejects manifests that try to supply or upgrade provenance claims.

Metadata omits source text, filesystem paths, run IDs, timestamps, agent names, and receipt destinations. Its canonical JSON uses sorted keys and a final newline. Prompt and metadata files are written atomically and cannot replace an input file.

## Command line

```sh
python3 scripts/generated_context.py \
  --manifest path/to/context.json \
  --source-root /absolute/repository/root \
  --output path/to/rendered.md \
  --metadata-output path/to/rendered.metadata.json
```

All input and output paths must resolve within `--source-root`. Other generators may import `render_manifest` to receive the same `prompt`, `stable_prefix`, metadata object, and canonical metadata bytes without writing files.

## Behavioral proof

Run:

```sh
python3 scripts/test-generated-context.py
```

The tests compare exact prompt, prefix, and metadata bytes across equivalent assignments. Adversarial cases cover early volatile data, duplicated context, padding, missing critical sources, and a false claim that an unauthenticated digest is authenticated.
