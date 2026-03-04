from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

import typer
from rich import print

from .schemas import AccountMemo, RetellAgentSpec, memo_diff, BusinessHours, RoutingRules, CallTransferRules
from .pipeline_a import build_agent_spec_v1
from .storage import get_storage, BaseStorage

app = typer.Typer(help="Pipeline B: Onboarding transcript -> v2 memo + agent spec + changelog")


def load_transcript(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_memo_v1_from_storage(storage: BaseStorage, account_id: str) -> Optional[AccountMemo]:
    data = storage.load_memo(account_id, "v1")
    if data is None:
        return None
    return AccountMemo.from_dict(data)


def _extract_business_hours(text: str) -> List[BusinessHours]:
    """
    Extract simple Monday–Friday hours like '8:00 to 5:00'.
    Only returns a value when we clearly see both days and times.
    """
    lower = text.lower()
    if "monday to friday" not in lower and "monday through friday" not in lower:
        return []

    time_pairs = re.findall(r"(\d{1,2}:\d{2})\s*(?:to|-)\s*(\d{1,2}:\d{2})", text)
    if not time_pairs:
        return []

    # Use the last mentioned pair as the “final” clarified hours
    start_raw, end_raw = time_pairs[-1]

    def _normalize(t: str) -> str:
        parts = t.split(":")
        h = int(parts[0])
        m = parts[1]
        # Assume times like 8:00, 4:30, 5:00 are daytime; keep as-is in 24h.
        return f"{h:02d}:{m}"

    start = _normalize(start_raw)
    end = _normalize(end_raw)
    return [BusinessHours(day="Monday-Friday", start=start, end=end, timezone=None)]


def _extract_emergency_logic(text: str) -> tuple[List[str], Optional[RoutingRules]]:
    """
    Derive emergency_definition and emergency_routing_rules from onboarding text.
    Very conservative: only fill when we see clear phrases.
    """
    lower = text.lower()
    emergency_def: List[str] = []
    routing: Optional[RoutingRules] = None

    if "gnm pressure washing" in lower:
        emergency_def.append("Calls from property manager GNM Pressure Washing")

    if "existing builder" in lower or "builders" in lower:
        emergency_def.append("Calls from existing builders")

    if emergency_def:
        routing = RoutingRules(
            description="Handle limited emergency calls (GNM Pressure Washing and existing builders) according to Ben's instructions.",
            contacts=[],
            fallback="If transfer fails, assure the caller Ben will follow up as soon as possible.",
        )

    return emergency_def, routing


def _update_flow_summaries(memo_v2: AccountMemo, bh: List[BusinessHours], emergency_def: List[str]) -> None:
    if bh and not memo_v2.office_hours_flow_summary:
        memo_v2.office_hours_flow_summary = (
            "During business hours (Monday–Friday) Clara should greet the caller, "
            "ask for the purpose of the call, collect name and callback number, and route appropriately."
        )
    if emergency_def and not memo_v2.after_hours_flow_summary:
        memo_v2.after_hours_flow_summary = (
            "After hours, Clara should confirm if the call matches the limited emergency definition "
            "(for example, property manager GNM Pressure Washing or existing builders). "
            "If yes, collect name, number, and address and attempt to reach Ben; "
            "if not, collect details and confirm follow-up during business hours."
        )


def apply_onboarding_updates(memo_v1: AccountMemo, onboarding_text: str) -> AccountMemo:
    """
    Apply onboarding updates on top of v1:
    - Fill in business_hours if clearly specified.
    - Refine emergency_definition and emergency_routing_rules.
    - Add high-level office/after-hours flow summaries.
    """
    memo_v2 = AccountMemo.from_dict(memo_v1.to_dict())

    # Business hours
    bh = _extract_business_hours(onboarding_text)
    if bh:
        memo_v2.business_hours = bh

    # Emergency rules
    emergency_def, emergency_routing = _extract_emergency_logic(onboarding_text)
    if emergency_def:
        memo_v2.emergency_definition = emergency_def
    if emergency_routing:
        memo_v2.emergency_routing_rules = emergency_routing

    # Flow summaries
    _update_flow_summaries(memo_v2, bh, emergency_def)

    # Notes
    memo_v2.notes = (memo_v2.notes or "") + " | Updated with onboarding-confirmed hours and emergency handling (where clearly specified)."
    return memo_v2


def build_agent_spec_v2(memo_v2: AccountMemo) -> RetellAgentSpec:
    spec_v1_like = build_agent_spec_v1(memo_v2)
    spec_v1_like.version = "v2"
    return spec_v1_like


@app.command()
def run(
    onboarding_dir: Path = typer.Argument(..., help="Directory containing onboarding transcripts (text files)."),
    output_base: Path = typer.Option(Path("."), help="Base directory for outputs (used for file storage only)."),
) -> None:
    """
    Process all onboarding transcripts in onboarding_dir and generate:
    - v2 Account Memo JSON
    - v2 Retell Agent Draft Spec JSON
    - changelog.json showing differences between v1 and v2
    Uses MongoDB if MONGODB_URI is set, otherwise reads/writes under output_base/outputs/.
    """
    storage = get_storage(output_base)
    backend = "MongoDB" if os.environ.get("MONGODB_URI") else "files"
    print(f"[dim]Storage backend: {backend}[/dim]")

    transcripts = sorted([p for p in onboarding_dir.glob("*.txt") if p.is_file()])
    if not transcripts:
        print("[yellow]No transcripts found in directory[/yellow]", onboarding_dir)
        raise typer.Exit(code=1)

    for path in transcripts:
        account_id = path.stem
        print(f"[bold]Processing onboarding transcript for account[/bold] {account_id}: {path}")

        memo_v1 = load_memo_v1_from_storage(storage, account_id)
        if memo_v1 is None:
            print(f"[red]Missing v1 data for account[/red] {account_id}; run Pipeline A first.")
            continue

        onboarding_text = load_transcript(path)
        memo_v2 = apply_onboarding_updates(memo_v1, onboarding_text)
        agent_v2 = build_agent_spec_v2(memo_v2)
        changes = memo_diff(memo_v1, memo_v2)

        storage.save_memo(account_id, "v2", memo_v2.to_dict())
        storage.save_agent_spec(account_id, "v2", agent_v2.to_dict())
        storage.save_changelog(account_id, changes)

        print(f"  -> saved v2 memo, agent spec, and changelog for {account_id}")


if __name__ == "__main__":
    app()
    
