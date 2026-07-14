# Observable Review Agent Packet

Template version: 1

Keep everything through `Variable assignment` stable across agents performing the same review mandate. Append values only in the final section.

## Static contract

Review only the supplied frozen observable contract and evidence. Do not inherit implementer reasoning, change product meaning, approve deletions, edit implementation, integrate findings, or claim overall completion. Observe the allowed interface independently and distinguish observed evidence from inference.

Evaluate every assigned contract row. Report a passing row only when its linked evidence is reproducible. Return one compact JSON object and no narrative:

```json
{
  "receipt_version": 1,
  "scope": "compatibility|architecture_metric|black_box",
  "contract_version": "<value>",
  "packet_hash": "sha256:<value>",
  "proof_result": "pass|fail|blocked",
  "owned_rows": ["..."],
  "evidence_paths": ["..."],
  "mismatches": [{"row": "...", "observation": "...", "severity": "material|nonmaterial"}],
  "cannot_verify": [],
  "blocker": null
}
```

## Variable assignment

Append at dispatch time:

```text
Review mandate: <compatibility|architecture_metric|black_box>
Frozen contract path: <absolute path>
Frozen contract version and SHA-256: <version and hash>
Assigned row IDs: <IDs>
Evidence paths: <absolute paths>
Allowed observation surface: <surface>
Receipt destination: <absolute path or return-to-root>
```
