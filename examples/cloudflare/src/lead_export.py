from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape


SHEETS = ("Contacts", "Leads", "Answers", "Sources", "CRM references", "Export metadata")


def _rows(leads: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> dict[str, list[list[Any]]]:
    contacts = [["lead_id", "name", "phone", "email", "country", "channel_user_id"]]
    lead_rows = [["lead_id", "created_at", "channel", "account_id", "user_id", "status", "admin_message_id"]]
    answers = [["lead_id", "field", "value"]]
    sources = [["lead_id", "field", "value"]]
    crm = [["lead_id", "provider", "external_id"]]
    for lead in leads:
        lead_id = lead.get("lead_id", "")
        contacts.append([lead_id, lead.get("name", ""), lead.get("phone", ""), lead.get("email", ""), lead.get("country", ""), lead.get("channel_user_id", "")])
        lead_rows.append([lead_id, lead.get("created_at", ""), lead.get("channel", ""), lead.get("account_id", ""), lead.get("user_id", ""), lead.get("status", ""), lead.get("admin_message_id", "")])
        answers.extend([lead_id, key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value] for key, value in (lead.get("answers") or {}).items())
        sources.extend([lead_id, key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value] for key, value in (lead.get("source") or {}).items())
        crm.extend([lead_id, key, value] for key, value in (lead.get("crm_refs") or {}).items())
    report = {"created_at": datetime.now(UTC).isoformat(), "lead_count": len(leads), **(metadata or {})}
    meta = [["key", "value"], *[[key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value] for key, value in report.items()]]
    return dict(zip(SHEETS, (contacts, lead_rows, answers, sources, crm, meta), strict=True))


def export_leads_csv(leads: Iterable[dict[str, Any]], path: str | Path, metadata: dict[str, Any] | None = None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = _rows(list(leads), metadata)["Leads"]
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        csv.writer(stream).writerows(rows)
    return target


def _column(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def _sheet_xml(rows: list[list[Any]]) -> str:
    body: list[str] = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for column_index, value in enumerate(row, 1):
            ref = f"{_column(column_index)}{row_index}"
            text = escape("" if value is None else str(value))
            style = ' s="1"' if row_index == 1 else ""
            cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t>{text}</t></is></c>')
        body.append(f'<row r="{row_index}">' + "".join(cells) + "</row>")
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(body) + "</sheetData></worksheet>"


def export_leads_xlsx(leads: Iterable[dict[str, Any]], path: str | Path, metadata: dict[str, Any] | None = None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheets = _rows(list(leads), metadata)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets) + 1)) + "</Types>")
        book.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        book.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheets, 1)) + "</sheets></workbook>")
        book.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        book.writestr("xl/styles.xml", '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font/><font><b/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0"/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>')
        for index, rows in enumerate(sheets.values(), 1):
            book.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
    return target
