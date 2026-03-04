## Clara Agent Pipeline Workflows (Python-Orchestrated)

This repository uses simple Python CLIs as the "orchestrator" instead of n8n/Make.
The workflows are:

### Pipeline A: Demo -> v1

1. **Input**: Demo call transcripts as `.txt` files in a directory.
2. **Step**: `scripts/pipeline_a.py run`:
   - Reads each transcript.
   - Derives `account_id` from the filename (without extension).
   - Generates a preliminary `AccountMemo` JSON (`account_memo.v1.json`).
   - Generates a v1 Retell Agent Draft Spec JSON (`retell_agent_spec.v1.json`).
   - Stores both under `outputs/accounts/<account_id>/v1/`.

### Pipeline B: Onboarding -> v2

1. **Input**: Onboarding call transcripts as `.txt` files in a directory.
2. **Step**: `scripts/pipeline_b.py run`:
   - Reads each onboarding transcript.
   - Uses the same `account_id` convention (filename stem).
   - Loads the existing v1 memo from `outputs/accounts/<account_id>/v1/account_memo.v1.json`.
   - Applies onboarding updates on top of v1 to produce v2 memo.
   - Generates a v2 Retell Agent Draft Spec JSON (`retell_agent_spec.v2.json`).
   - Computes a `changelog.json` diff of memo fields.
   - Stores all under `outputs/accounts/<account_id>/v2/`.

These steps are deterministic and idempotent: re-running the same transcripts for the same
account IDs overwrites existing JSON outputs with the same content.

