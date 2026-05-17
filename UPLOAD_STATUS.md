# Quantum Trading Lab upload status

This branch was prepared from the local Quantum Trading Lab workspace on 2026-05-17.

Local validation completed:

- `pytest tests -q -p no:cacheprovider` -> 12 passed
- `python scripts/check_korean_buy_signals.py --max-kospi 3` -> completed successfully

The local workspace includes the full project source under `src/quantum_trading_lab`, configs, tests, examples, and the Korean buy-signal automation script at `scripts/check_korean_buy_signals.py`.

Note: the Codex GitHub connector in this session could create the branch but could not directly stream the full local source tree as a normal git push because the local machine does not have `git` installed and binary/source-tree upload through the connector is limited. The source remains available in the current Codex workspace and the online automations have been switched to worktree execution.
