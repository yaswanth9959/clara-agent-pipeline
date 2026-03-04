from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional, Literal
from copy import deepcopy


@dataclass
class BusinessHours:
    day: str  # e.g. "Monday"
    start: str  # "HH:MM" 24h
    end: str  # "HH:MM" 24h
    timezone: Optional[str] = None


@dataclass
class RoutingRules:
    description: str
    contacts: List[str] = field(default_factory=list)
    fallback: Optional[str] = None


@dataclass
class CallTransferRules:
    timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    on_failure_message: Optional[str] = None


@dataclass
class AccountMemo:
    account_id: str
    company_name: Optional[str] = None
    business_hours: List[BusinessHours] = field(default_factory=list)
    office_address: Optional[str] = None
    services_supported: List[str] = field(default_factory=list)
    emergency_definition: List[str] = field(default_factory=list)
    emergency_routing_rules: Optional[RoutingRules] = None
    non_emergency_routing_rules: Optional[RoutingRules] = None
    call_transfer_rules: Optional[CallTransferRules] = None
    integration_constraints: List[str] = field(default_factory=list)
    after_hours_flow_summary: Optional[str] = None
    office_hours_flow_summary: Optional[str] = None
    questions_or_unknowns: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountMemo":
        bh = [
            BusinessHours(**item)
            for item in data.get("business_hours", [])
        ]
        er = data.get("emergency_routing_rules")
        ner = data.get("non_emergency_routing_rules")
        ctr = data.get("call_transfer_rules")
        return cls(
            account_id=data["account_id"],
            company_name=data.get("company_name"),
            business_hours=bh,
            office_address=data.get("office_address"),
            services_supported=data.get("services_supported", []),
            emergency_definition=data.get("emergency_definition", []),
            emergency_routing_rules=RoutingRules(**er) if er else None,
            non_emergency_routing_rules=RoutingRules(**ner) if ner else None,
            call_transfer_rules=CallTransferRules(**ctr) if ctr else None,
            integration_constraints=data.get("integration_constraints", []),
            after_hours_flow_summary=data.get("after_hours_flow_summary"),
            office_hours_flow_summary=data.get("office_hours_flow_summary"),
            questions_or_unknowns=data.get("questions_or_unknowns", []),
            notes=data.get("notes"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        return result


VersionTag = Literal["v1", "v2"]


@dataclass
class RetellAgentSpec:
    agent_name: str
    version: VersionTag
    voice_style: str
    system_prompt: str
    timezone: Optional[str] = None
    business_hours: List[BusinessHours] = field(default_factory=list)
    office_address: Optional[str] = None
    emergency_routing: Optional[RoutingRules] = None
    non_emergency_routing: Optional[RoutingRules] = None
    call_transfer: Optional[CallTransferRules] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def memo_diff(old: AccountMemo, new: AccountMemo) -> Dict[str, Any]:
    """Compute a simple field-level diff between two memos."""
    old_dict = old.to_dict()
    new_dict = new.to_dict()
    changes: Dict[str, Any] = {}
    for key in sorted(set(old_dict.keys()) | set(new_dict.keys())):
        if old_dict.get(key) != new_dict.get(key):
            changes[key] = {
                "from": deepcopy(old_dict.get(key)),
                "to": deepcopy(new_dict.get(key)),
            }
    return changes

