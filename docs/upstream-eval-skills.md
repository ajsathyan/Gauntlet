# Eval Skill Provenance

Gauntlet vendors and namespaces the seven skills from [`hamelsmu/evals-skills`](https://github.com/hamelsmu/evals-skills) at commit `814ebeae0ecef6151a4d3846e19ab123e1832137`.

The upstream skills are MIT licensed. The required notice is preserved at `third_party/hamelsmu-evals-skills/LICENSE`.

Gauntlet changes only the skill names and their cross-skill references:

| Upstream | Gauntlet |
| --- | --- |
| `build-review-interface` | `eval-review-interface` |
| `error-analysis` | `eval-error-analysis` |
| `eval-audit` | `eval-audit` |
| `evaluate-rag` | `eval-rag` |
| `generate-synthetic-data` | `eval-synthetic-data` |
| `validate-evaluator` | `eval-validate-evaluator` |
| `write-judge-prompt` | `eval-judge-prompt` |

When updating, compare the upstream commit with this reviewed snapshot, copy substantive improvements selectively, reapply the `eval-` namespace, update this commit, and preserve the license notice.
