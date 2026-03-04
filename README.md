## Clara Answers Onboarding Pipeline (Assignment Implementation)

This repo implements a zero-cost, file-based automation pipeline for the Clara Answers
intern assignment:

- **Pipeline A**: Demo call transcript → preliminary account memo (v1) + Retell agent draft spec (v1)
- **Pipeline B**: Onboarding transcript → updated account memo (v2) + Retell agent draft spec (v2) + changelog

It is designed to be:

- **Zero-cost**: Uses only local files and free Python packages (MongoDB Atlas free tier is optional).
- **Reproducible**: No paid APIs; everything is driven from transcripts on disk.
- **Idempotent**: Re-running with the same inputs regenerates the same JSON outputs.

### Storage: Files vs MongoDB Atlas

- **Default**: Outputs are written to `outputs/accounts/<account_id>/v1` and `v2` as JSON files.
- **Optional MongoDB**: If you set `MONGODB_URI`, the pipeline uses MongoDB Atlas instead.
  - Copy `.env.example` to `.env` and set `MONGODB_URI` to your Atlas connection string.
  - **Do not commit `.env` or put the connection string in code.** It is in `.gitignore`.
  - Database: `clara_pipeline`; collection: `accounts`; one document per `account_id` with `memo_v1`, `memo_v2`, `agent_spec_v1`, `agent_spec_v2`, and `changelog`.

### Project Structure

- `scripts/`
  - `schemas.py`: Data models for `AccountMemo`, `RetellAgentSpec`, and a simple `memo_diff`.
  - `storage.py`: Storage backend (file or MongoDB); selected via `MONGODB_URI`.
  - `pipeline_a.py`: CLI for Pipeline A (demo → v1).
  - `pipeline_b.py`: CLI for Pipeline B (onboarding → v2 + changelog).
- `workflows/`
  - `pipeline_description.md`: Text description of the orchestration steps (orchestrator export equivalent).
- `outputs/accounts/<account_id>/v1/`
  - `account_memo.v1.json`
  - `retell_agent_spec.v1.json`
- `outputs/accounts/<account_id>/v2/`
  - `account_memo.v2.json`
  - `retell_agent_spec.v2.json`
  - `changelog.json`
- `requirements.txt`: Python dependencies for the CLIs.

### Setup

1. **Create and activate a virtualenv** (recommended).
2. **Install dependencies**:

```bash
pip install -r requirements.txt
```

---

### How to add data and run Pipeline A or B

#### 1. Add your transcript files

| Pipeline | Folder | What to put there |
|----------|--------|-------------------|
| **A** (demo → v1) | `data/demo/` | One `.txt` file per account. Filename (without `.txt`) = **account_id**. |
| **B** (onboarding → v2) | `data/onboarding/` | One `.txt` file per account. Use the **same account_id** as in `data/demo/` for that company. |

**Examples:**

- `data/demo/bens_electrical.txt` → Pipeline A creates v1 for account `bens_electrical`.
- `data/onboarding/bens_electrical.txt` → Pipeline B updates that account to v2 (must run Pipeline A first).

You can have multiple accounts: e.g. `data/demo/account1.txt`, `account2.txt`, … and matching `data/onboarding/account1.txt`, `account2.txt`, …

#### 2. Run Pipeline A (demo → v1)

From the **project root** (the folder that contains `scripts/` and `data/`):

```bash
python -m scripts.pipeline_a data/demo --output-base .
```

- Reads every `.txt` in `data/demo/`.
- For each file, creates v1 memo + agent spec.
- Saves to `outputs/accounts/<account_id>/v1/` (or to MongoDB if `MONGODB_URI` is set).

#### 3. Run Pipeline B (onboarding → v2)

Run this **after** Pipeline A. From the project root:

```bash
python -m scripts.pipeline_b data/onboarding --output-base .
```

- Reads every `.txt` in `data/onboarding/`.
- For each file, loads v1 for that `account_id`, applies onboarding updates, writes v2 + changelog.
- Saves to `outputs/accounts/<account_id>/v2/` (or to MongoDB if `MONGODB_URI` is set).

#### Quick test with one account

1. Create `data/demo/mycompany.txt` and paste in a demo transcript.
2. Run: `python -m scripts.pipeline_a data/demo --output-base .`
3. Create `data/onboarding/mycompany.txt` and paste in the onboarding transcript.
4. Run: `python -m scripts.pipeline_b data/onboarding --output-base .`
5. Check `outputs/accounts/mycompany/v1/` and `v2/` for the generated JSON files.

### Where to Extend / Improve

- **Extraction quality**:
  - Replace the stub extraction in `pipeline_a.extract_from_demo_transcript` with:
    - A local, zero-cost LLM, or
    - A more sophisticated rule-based parser for the transcripts.
- **Onboarding updates**:
  - Implement real merging logic in `pipeline_b.apply_onboarding_updates` so onboarding
    data refines and overrides v1 fields without losing unrelated data.
- **Prompt generation**:
  - Enhance the `system_prompt` template in `pipeline_a.build_agent_spec_v1` (also used for v2)
    to inject account-specific flows based on memo fields while preserving the required
    business-hours and after-hours behaviors from the assignment.
- **Retell integration**:
  - Optionally document a manual step: copy each `RetellAgentSpec` JSON into the Retell UI.

### Known Limitations

- Current extraction and update steps are intentionally conservative stubs; they avoid
  hallucinating details and push unknowns into `questions_or_unknowns` for later confirmation.
- Audio handling (speech-to-text) is out of scope here; the pipeline assumes transcripts
  are already available as `.txt` files.

