"""Storage backend for account memos and agent specs. Uses files by default, MongoDB when MONGODB_URI is set."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


def get_storage(output_base: Optional[Path] = None):
    """Return FileStorage or MongoStorage based on MONGODB_URI env var. Never pass credentials in code."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    uri = os.environ.get("MONGODB_URI", "").strip()
    if uri:
        return MongoStorage(uri)
    return FileStorage(output_base or Path("."))


class BaseStorage(ABC):
    @abstractmethod
    def save_memo(self, account_id: str, version: str, memo: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def load_memo(self, account_id: str, version: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_agent_spec(self, account_id: str, version: str, spec: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def save_changelog(self, account_id: str, changelog: Dict[str, Any]) -> None:
        pass


class FileStorage(BaseStorage):
    def __init__(self, output_base: Path):
        self.output_base = Path(output_base)

    def _dir(self, account_id: str, version: str) -> Path:
        d = self.output_base / "outputs" / "accounts" / account_id / version
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_memo(self, account_id: str, version: str, memo: Dict[str, Any]) -> None:
        path = self._dir(account_id, version) / f"account_memo.{version}.json"
        path.write_text(json.dumps(memo, indent=2), encoding="utf-8")

    def load_memo(self, account_id: str, version: str) -> Optional[Dict[str, Any]]:
        path = self.output_base / "outputs" / "accounts" / account_id / version / f"account_memo.{version}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_agent_spec(self, account_id: str, version: str, spec: Dict[str, Any]) -> None:
        path = self._dir(account_id, version) / f"retell_agent_spec.{version}.json"
        path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    def save_changelog(self, account_id: str, changelog: Dict[str, Any]) -> None:
        path = self._dir(account_id, "v2") / "changelog.json"
        path.write_text(json.dumps(changelog, indent=2), encoding="utf-8")


class MongoStorage(BaseStorage):
    DB_NAME = "clara_pipeline"
    COLL_ACCOUNTS = "accounts"

    def __init__(self, uri: str):
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("MongoDB support requires: pip install pymongo")
        self._client = MongoClient(uri)
        self._db = self._client[self.DB_NAME]
        self._coll = self._db[self.COLL_ACCOUNTS]

    def _doc_id(self, account_id: str) -> Dict[str, str]:
        return {"_id": account_id}

    def _get_doc(self, account_id: str) -> Dict[str, Any]:
        doc = self._coll.find_one(self._doc_id(account_id))
        return doc or {}

    def _set_doc(self, account_id: str, doc: Dict[str, Any]) -> None:
        doc["_id"] = account_id
        self._coll.replace_one(self._doc_id(account_id), doc, upsert=True)

    def save_memo(self, account_id: str, version: str, memo: Dict[str, Any]) -> None:
        doc = self._get_doc(account_id)
        doc[f"memo_{version}"] = memo
        self._set_doc(account_id, doc)

    def load_memo(self, account_id: str, version: str) -> Optional[Dict[str, Any]]:
        doc = self._get_doc(account_id)
        return doc.get(f"memo_{version}")

    def save_agent_spec(self, account_id: str, version: str, spec: Dict[str, Any]) -> None:
        doc = self._get_doc(account_id)
        doc[f"agent_spec_{version}"] = spec
        self._set_doc(account_id, doc)

    def save_changelog(self, account_id: str, changelog: Dict[str, Any]) -> None:
        doc = self._get_doc(account_id)
        doc["changelog"] = changelog
        self._set_doc(account_id, doc)
