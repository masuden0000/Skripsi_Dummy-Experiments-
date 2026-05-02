from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from schema import CatalogEntry


def load_dictionary(dictionary_path: Path) -> dict[str, Any]:
    if not dictionary_path.exists():
        raise FileNotFoundError(f"Dictionary tidak ditemukan: {dictionary_path}")

    raw = dictionary_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        # Beberapa baris dictionary punya jejak sitasi yang membuat YAML gagal dibaca.
        sanitized = re.sub(r"【[^】]*】", "", raw)
        sanitized = re.sub(r"ã€[^ã€‘]*ã€‘", "", sanitized)
        sanitized = re.sub(r"Ã£â‚¬Â.*?Ã£â‚¬â€˜", "", sanitized)
        sanitized_lines: list[str] = []
        for line in sanitized.splitlines():
            line = re.sub(r'^(\s*[^:#\n]+:\s*"(?:[^"\\]|\\.)*").*$', r"\1", line)
            line = re.sub(r"^(\s*[^:#\n]+:\s*'(?:[^'\\]|\\.)*').*$", r"\1", line)
            line = re.sub(r'(:\s*".*")\.\s*$', r"\1", line)
            line = re.sub(r"(:\s*'.*')\.\s*$", r"\1", line)
            sanitized_lines.append(line)
        data = yaml.safe_load("\n".join(sanitized_lines))

    if not isinstance(data, dict):
        raise ValueError("Format dictionary harus object/dict.")
    return data


def _extract_enum_members(data: dict[str, Any]) -> dict[str, list[str]]:
    enum_root = data.get("enumerations", {})
    if not isinstance(enum_root, dict):
        return {}

    members: dict[str, list[str]] = {}
    for enum_name, enum_payload in enum_root.items():
        if not isinstance(enum_payload, dict):
            continue
        raw_members = enum_payload.get("members", [])
        if isinstance(raw_members, list):
            members[str(enum_name)] = [str(item).strip() for item in raw_members if str(item).strip()]
    return members


def _guess_enum_name(value_type: str | None, description: str) -> str | None:
    joined = f"{value_type or ''} {description}".upper()
    match = re.search(r"\bWD_[A-Z_]+\b", joined)
    return match.group(0) if match else None


def _entry_text(
    section: str,
    kind: str,
    path: str,
    value_type: str | None,
    description: str,
    signature: str | None,
    enum_name: str | None,
    enum_members: list[str],
) -> str:
    # Teks ini yang nanti diberikan ke retriever dan LLM sebagai sumber utama.
    lines = [f"section={section}", f"kind={kind}", f"path={path}"]
    if value_type:
        lines.append(f"type={value_type}")
    if signature:
        lines.append(f"signature={signature}")
    if enum_name:
        lines.append(f"enum={enum_name}")
    if enum_members:
        lines.append("enum_members=" + ", ".join(enum_members))
    if description:
        lines.append("description=" + description.strip())
    return "\n".join(lines)


def build_catalog(dictionary_path: Path) -> list[CatalogEntry]:
    data = load_dictionary(dictionary_path)
    enum_members_map = _extract_enum_members(data)
    entries: list[CatalogEntry] = []

    for section, payload in data.items():
        if section == "enumerations" or not isinstance(payload, dict):
            continue

        properties = payload.get("properties", {})
        if isinstance(properties, dict):
            for prop_name, prop_payload in properties.items():
                if not isinstance(prop_payload, dict):
                    continue
                value_type = str(prop_payload.get("type")) if prop_payload.get("type") is not None else None
                description = str(prop_payload.get("description", "")).strip()
                enum_name = _guess_enum_name(value_type, description)
                enum_members = enum_members_map.get(enum_name, []) if enum_name else []
                path = f"{section}.{prop_name}"
                entries.append(
                    CatalogEntry(
                        id=f"property::{path}",
                        section=str(section),
                        kind="property",
                        path=path,
                        value_type=value_type,
                        description=description,
                        enum_name=enum_name,
                        enum_members=enum_members,
                        chunk_text=_entry_text(
                            str(section),
                            "property",
                            path,
                            value_type,
                            description,
                            None,
                            enum_name,
                            enum_members,
                        ),
                    )
                )

        methods = payload.get("methods", {})
        if isinstance(methods, dict):
            for method_name, method_payload in methods.items():
                if not isinstance(method_payload, dict):
                    continue
                signature = str(method_payload.get("signature", "")).strip() or None
                description = str(method_payload.get("description", "")).strip()
                path = f"{section}.{method_name}"
                entries.append(
                    CatalogEntry(
                        id=f"method::{path}",
                        section=str(section),
                        kind="method",
                        path=path,
                        description=description,
                        signature=signature,
                        chunk_text=_entry_text(
                            str(section),
                            "method",
                            path,
                            None,
                            description,
                            signature,
                            None,
                            [],
                        ),
                    )
                )

    for enum_name, members in enum_members_map.items():
        path = f"enumerations.{enum_name}"
        entries.append(
            CatalogEntry(
                id=f"enumeration::{enum_name}",
                section="enumerations",
                kind="enumeration",
                path=path,
                value_type="enum",
                description=f"Allowed members for {enum_name}.",
                enum_name=enum_name,
                enum_members=members,
                chunk_text=_entry_text(
                    "enumerations",
                    "enumeration",
                    path,
                    "enum",
                    f"Allowed members for {enum_name}.",
                    None,
                    enum_name,
                    members,
                ),
            )
        )

    return entries
