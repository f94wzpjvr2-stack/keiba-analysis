# Codex instructions for keiba-hybrid-system-v1

## Purpose
This repository supports a horse-racing expected-value workflow. The goal is not to maximize hit rate; it is to build a reproducible, testable process aimed at long-run ROI improvement.

## Repository rules
- Source code lives in `src/keiba_ev/`.
- Colab is only the execution and review interface. Do not place core logic only inside notebook cells.
- Persistent user data must live outside the repository, normally in Google Drive.
- Every behavior change requires tests under `tests/`.
- Run `python -m pytest -q` before declaring work complete.
- Keep functions deterministic unless randomness is explicitly seeded.
- Never silently force the entire race budget to be spent. The budget is a ceiling, not a quota.
- Never label a model-derived probability as objectively true. Report model/version and assumptions.
- Do not update scoring weights from a single race. Require repeated evidence and out-of-sample validation.
- Do not use race results, final odds, or post-race information as pre-race features.
- Preserve backward compatibility for CSV schemas unless a migration is included.

## Modeling constraints
- Separate ability ranking from expected-value ranking.
- The score-to-probability conversion is provisional until calibrated on enough historical races.
- Pair and triple ticket probabilities use a Plackett-Luce approximation. Document this limitation in outputs.
- Wide odds ranges must use the lower bound for conservative EV by default.
- Correlated tickets require conservative staking. Keep per-ticket and total exposure caps.

## Definition of done
- The requested feature is implemented.
- Tests cover normal and failure cases.
- README or manual is updated when user-facing behavior changes.
- `python -m pytest -q` passes.
- No secrets, tokens, race data, or private Drive paths are committed.
