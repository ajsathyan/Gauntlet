# Breakthrough Agent Packet

Template version: 1

Keep everything through `Variable assignment` byte-for-byte identical for every agent in the independent round. Append values only in the final section.

## Static contract

Work independently from the supplied frozen evidence. Do not seek or use another proposal, infer a favored architecture, edit the repository, make product decisions, adjudicate parity, or claim completion.

Identify the dominant accidental complexity. Propose up to three structurally different compression hypotheses, select the strongest credible end state, and state the mechanism that could produce step-change gains. For each retained hypothesis, assess effects on production/test LOC, concept and dependency count, extension cost, test feedback, and runtime or resources; name compatibility and migration risks; define the smallest common, complex, and structural-outlier prototype; and give falsification evidence. Preserve the supplied behavioral, data, export, saved-workflow, correctness, accessibility, security, and privacy floor.

Read only the listed artifacts. Treat their recorded hashes and contract versions as binding. Return one compact JSON object and no narrative:

```json
{
  "receipt_version": 1,
  "scope": "breakthrough_proposal",
  "evidence_packet_hash": "sha256:<value>",
  "proof_result": "pass|blocked",
  "dominant_accidental_complexity": ["..."],
  "hypotheses": [
    {
      "mechanism": "...",
      "expected_effects": {"production_test_loc": "...", "concepts_dependencies": "...", "extension_cost": "...", "test_feedback": "...", "runtime_resources": "..."},
      "risks": ["..."],
      "diverse_slice_prototype": ["common:...", "complex:...", "outlier:..."],
      "falsification_evidence": ["..."]
    }
  ],
  "selected_hypothesis_index": 0,
  "evidence_paths": ["..."],
  "mismatches": [],
  "blocker": null
}
```

## Variable assignment

Append at dispatch time:

```text
Evidence packet path: <absolute path>
Evidence packet SHA-256: <hash>
Allowed repository root: <absolute path>
Receipt destination: <absolute path or return-to-root>
```
