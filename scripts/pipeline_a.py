from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List

import typer
from rich import print

from .schemas import (
    AccountMemo,
    RetellAgentSpec,
    BusinessHours,
)
from .storage import get_storage

app = typer.Typer(help="Pipeline A: Demo transcript -> v1 memo + agent spec")


def load_transcript(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_account_id(transcript_path: Path) -> str:
    """Derive a stable account_id from filename (without extension)."""
    return transcript_path.stem


def _extract_company_name(text: str, account_id: str) -> str | None:
    # Look for an explicit "Company: ..." style line
    m = re.search(r"Company\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fall back: if the account_id appears in text in a readable form
    if account_id.replace("_", " ").lower() in text.lower():
        return account_id.replace("_", " ").title()
    # Known pattern from Ben's Electrical demo
    if "ben's electrical solutions" in text.lower():
        return "Ben's Electrical Solutions"
    return None


def _extract_services(text: str) -> List[str]:
    services: List[str] = []
    # Very simple keyword-based extraction; only add entries that are clearly mentioned.
    candidates = {
        "service calls": ["service call", "service calls"],
        "electrical troubleshooting": ["troubleshooting"],
        "renovations": ["renovations", "renovation work"],
        "EV charger installation": ["ev charger", "car charger"],
        "hot tub electrical hookup": ["hot tub", "spa hookup"],
        "panel changes": ["panel change", "panel upgrade"],
        "residential electrical work": ["residential", "house wiring"],
        "commercial electrical work": ["commercial", "tenant improvement"],
    }
    lower = text.lower()
    for label, keywords in candidates.items():
        if any(k in lower for k in keywords):
            services.append(label)
    return services


def extract_from_demo_transcript(text: str, account_id: str) -> AccountMemo:
    """
    Lightweight, rule-based extraction from demo transcript.

    We only populate fields when we see clear evidence in the text,
    and leave the rest for onboarding (v2) to refine.
    """
    company_name = _extract_company_name(text, account_id)
    services_supported = _extract_services(text)

    questions: List[str] = []
    if not company_name:
        questions.append("Company name not clearly stated in demo.")
    if not services_supported:
        questions.append("Services supported not clearly listed in demo.")
    questions.extend(
        [
            "Exact business hours (days, start/end, timezone) not confirmed in demo.",
            "Precise emergency definition and routing contacts missing from demo.",
            "Detailed non-emergency routing rules missing from demo.",
            "Transfer timeout and retry configuration missing from demo.",
        ]
    )

    memo = AccountMemo(
        account_id=account_id,
        company_name=company_name,
        business_hours=[],
        office_address=None,
        services_supported=services_supported,
        emergency_definition=[],
        emergency_routing_rules=None,
        non_emergency_routing_rules=None,
        call_transfer_rules=None,
        integration_constraints=[],
        after_hours_flow_summary=None,
        office_hours_flow_summary=None,
        questions_or_unknowns=questions,
        notes="Preliminary memo generated from demo call; many details to be confirmed during onboarding.",
    )
    return memo


def build_agent_spec_v1(memo: AccountMemo) -> RetellAgentSpec:
    """Create a Retell agent draft spec for v1 based on the memo."""
    business_hours = memo.business_hours
    office_address = memo.office_address

    system_prompt = f"""
You are Clara, an AI voice agent for {memo.company_name or "this service company"}.
You handle inbound calls related to service requests, emergencies, and scheduling.

Follow these rules:

1) General behavior
- Be concise, friendly, and professional.
- Never mention tools, function calls, or internal systems to the caller.
- Only ask for information needed for routing and dispatch.

2) Office hours flow
- Greet the caller and mention the company name if known.
- Ask for the purpose of the call.
- Collect the caller's name and callback phone number.
- Route or transfer the call according to the office-hours routing rules you have.
- If a transfer fails (no answer or technical failure), apologize and explain that someone will follow up.
- Confirm what will happen next.
- Ask if they need anything else.
- Close the call politely if they do not need anything else.

3) After-hours flow
- Greet the caller and clarify that they have reached the after-hours line.
- Ask for the purpose of the call.
- Confirm whether this is an emergency according to the emergency definition you have.
- If it is an emergency:
  - Immediately collect the caller's name, callback number, and service address.
  - Attempt to transfer to the designated emergency contact or phone tree.
  - If the transfer fails, apologize and assure the caller that someone will be notified and will follow up as soon as possible.
- If it is not an emergency:
  - Collect the necessary details about their request.
  - Confirm that someone will follow up during business hours.
- Ask if they need anything else.
- Close the call politely.

If any configuration detail is missing or unclear, follow the safest and most conservative behavior and do not invent new rules.
""".strip()

    spec = RetellAgentSpec(
        agent_name=f"{memo.company_name or memo.account_id} - Clara Agent",
        version="v1",
        voice_style="neutral-professional",
        system_prompt=system_prompt,
        timezone=business_hours[0].timezone if business_hours else None,
        business_hours=business_hours,
        office_address=office_address,
        emergency_routing=memo.emergency_routing_rules,
        non_emergency_routing=memo.non_emergency_routing_rules,
        call_transfer=memo.call_transfer_rules,
    )
    return spec


@app.command()
def run(
    transcripts_dir: Path = typer.Argument(..., help="Directory containing demo transcripts (text files)."),
    output_base: Path = typer.Option(Path("."), help="Base directory for outputs (used for file storage only)."),
) -> None:
    """
    Process all demo transcripts in transcripts_dir and generate:
    - v1 Account Memo JSON
    - v1 Retell Agent Draft Spec JSON
    for each account. Uses MongoDB if MONGODB_URI is set, otherwise writes to output_base/outputs/.
    """
    storage = get_storage(output_base)
    backend = "MongoDB" if os.environ.get("MONGODB_URI") else "files"
    print(f"[dim]Storage backend: {backend}[/dim]")

    transcripts = sorted([p for p in transcripts_dir.glob("*.txt") if p.is_file()])
    if not transcripts:
        print("[yellow]No transcripts found in directory[/yellow]", transcripts_dir)
        raise typer.Exit(code=1)

    for path in transcripts:
        account_id = extract_account_id(path)
        print(f"[bold]Processing demo transcript for account[/bold] {account_id}: {path}")

        text = load_transcript(path)
        memo_v1 = extract_from_demo_transcript(text, account_id=account_id)
        agent_v1 = build_agent_spec_v1(memo_v1)

        storage.save_memo(account_id, "v1", memo_v1.to_dict())
        storage.save_agent_spec(account_id, "v1", agent_v1.to_dict())

        print(f"  -> saved v1 memo and agent spec for {account_id}")


if __name__ == "__main__":
    app()

