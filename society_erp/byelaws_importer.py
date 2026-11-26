from __future__ import annotations

import csv
import html
import os
import re
import unicodedata
import xml.etree.ElementTree as ET

import docx
import frappe
from frappe import _
from frappe.utils import cint

CHAPTER_RE = re.compile(r"^(CHAPTER\s+[IVXLCDM]+)\b(.*)", re.I)
CLAUSE_RE = re.compile(r"^(\d+[A-Z]?)\.\s+(.+)")
TITLE_SPLIT_RE = re.compile(r"\s*(?:\.─|\.-|\.—|:-)\s*")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_PREFIX = f"{{{W_NS}}}"


def _split_clause_title_and_body(rest: str) -> tuple[str, str]:
    m = TITLE_SPLIT_RE.split(rest, maxsplit=1)
    if len(m) == 2:
        title = m[0].strip().rstrip(".")
        body = m[1].strip()
    else:
        sent_match = re.match(r"^([^.]{1,140})\.\s+(.+)$", rest)
        if sent_match:
            title = sent_match.group(1).strip()
            body = sent_match.group(2).strip()
        else:
            title = rest.strip()
            body = ""
    if len(title) > 140:
        title = title[:137].rstrip() + "..."
    return title, body


def _is_run_deviated(r_elem: ET.Element) -> bool:
    rPr = r_elem.find(f"{W_PREFIX}rPr")
    if rPr is None:
        return False
    col = rPr.find(f"{W_PREFIX}color")
    if col is not None:
        val = (col.attrib.get(f"{W_PREFIX}val") or "").strip().lower()
        if val not in ("", "000000", "auto"):
            return True
    hl = rPr.find(f"{W_PREFIX}highlight")
    if hl is not None:
        val = (hl.attrib.get(f"{W_PREFIX}val") or "").strip().lower()
        if val not in ("", "none", "white"):
            return True
    return False


def _extract_paragraph_info(p) -> tuple[str, str, bool]:
    """Return (plain_text, rendered_inner_html, has_deviation) for a python-docx Paragraph."""
    p_elem = p._p
    plain_parts: list[str] = []
    html_parts: list[str] = []
    has_dev = False

    for r_elem in p_elem.findall(f".//{W_PREFIX}r"):
        t_texts = [t.text or "" for t in r_elem.findall(f"{W_PREFIX}t")]
        raw = unicodedata.normalize("NFKC", "".join(t_texts))
        if not raw:
            continue
        plain_parts.append(raw)
        escaped = html.escape(raw)
        if _is_run_deviated(r_elem):
            has_dev = True
            html_parts.append(f'<span class="byelaw-deviation">{escaped}</span>')
        else:
            html_parts.append(escaped)

    plain = "".join(plain_parts).strip()
    if "[" in plain and "]" in plain:
        has_dev = True
    inner_html = "".join(html_parts).strip()
    return plain, inner_html, has_dev


def _format_para_html(inner_html: str, has_dev: bool) -> str:
    if has_dev:
        return (
            '<p class="byelaw-subclause-deviated">'
            '<span class="badge badge-warning mr-1">Modified from Model</span>'
            f"{inner_html}</p>"
        )
    return f'<p class="byelaw-subclause-model">{inner_html}</p>'


def _normalize_plain(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def parse_docx_clauses(
    file_path: str,
    baseline_file_path: str | None = None,
    lock_unmodified: bool = True,
) -> list[dict]:
    baseline_map: dict[str, str] = {}
    if baseline_file_path and os.path.isfile(baseline_file_path):
        for b_row in parse_docx_clauses(baseline_file_path, baseline_file_path=None, lock_unmodified=False):
            baseline_map[b_row["clause_number"]] = _normalize_plain(b_row.get("plain_text", ""))

    doc = docx.Document(file_path)
    para_items = [_extract_paragraph_info(p) for p in doc.paragraphs]
    non_empty = [(plain, h_inner, dev) for (plain, h_inner, dev) in para_items if plain]

    chapter_i_indices = [
        i for i, (t, _, _) in enumerate(non_empty) if re.match(r"^CHAPTER\s+I\b", t, re.I)
    ]
    start_idx = (
        chapter_i_indices[1]
        if len(chapter_i_indices) >= 2
        else (chapter_i_indices[0] if chapter_i_indices else 0)
    )

    clauses: list[dict] = []
    current_chapter = ""
    current_clause: dict | None = None
    body_paras: list[tuple[str, str, bool]] = []

    def flush_clause():
        nonlocal current_clause, body_paras
        if current_clause is not None:
            clause_has_dev = current_clause["has_deviation"] or any(dev for _, _, dev in body_paras)
            plain_all = " ".join(pl for pl, _, _ in body_paras)
            if baseline_map:
                b_text = baseline_map.get(current_clause["clause_number"])
                if b_text is None or b_text != _normalize_plain(plain_all):
                    clause_has_dev = True

            current_clause["has_deviation"] = clause_has_dev
            current_clause["plain_text"] = plain_all
            current_clause["draft_text"] = "\n".join(
                _format_para_html(h_inner, dev) for _, h_inner, dev in body_paras if h_inner
            )
            if lock_unmodified and not clause_has_dev:
                current_clause["is_readonly"] = 1
                current_clause["readonly_reason"] = (
                    "Unmodified TN Model Bye-Law (Statutory Baseline — Not Open for Consultation)"
                )
            clauses.append(current_clause)
            current_clause = None
            body_paras = []

    i = start_idx
    while i < len(non_empty):
        line, h_inner, dev = non_empty[i]
        ch_m = CHAPTER_RE.match(line)
        if ch_m:
            flush_clause()
            ch_head = ch_m.group(1).upper()
            ch_tail = ch_m.group(2).strip(" .:-─—")
            if not ch_tail and i + 1 < len(non_empty):
                next_line = non_empty[i + 1][0]
                if not CLAUSE_RE.match(next_line) and not CHAPTER_RE.match(next_line):
                    ch_tail = next_line
                    i += 1
            current_chapter = f"{ch_head}: {ch_tail}" if ch_tail else ch_head
            i += 1
            continue

        cl_m = CLAUSE_RE.match(line)
        if cl_m:
            flush_clause()
            clause_num = cl_m.group(1)
            title, inline_body = _split_clause_title_and_body(cl_m.group(2))
            current_clause = {
                "sequence_no": len(clauses) + 1,
                "chapter": current_chapter,
                "clause_number": clause_num,
                "clause_title": title,
                "draft_text": "",
                "is_readonly": 0,
                "readonly_reason": "",
                "has_deviation": dev,
            }
            if inline_body:
                body_paras.append((inline_body, html.escape(inline_body), dev))
            i += 1
            continue

        if current_clause is not None:
            body_paras.append((line, h_inner, dev))
        i += 1

    flush_clause()
    return clauses


def parse_csv_clauses(file_path: str) -> list[dict]:
    clauses: list[dict] = []
    with open(file_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            clause_num = (row.get("clause_number") or "").strip()
            clause_title = (row.get("clause_title") or "").strip()
            if not clause_num or not clause_title:
                continue
            seq = float(row["sequence_no"]) if (row.get("sequence_no") or "").strip() else float(idx)
            clauses.append(
                {
                    "sequence_no": seq,
                    "chapter": (row.get("chapter") or "").strip(),
                    "clause_number": clause_num,
                    "clause_title": clause_title[:140],
                    "draft_text": (row.get("draft_text") or "").strip(),
                    "is_readonly": cint(row.get("is_readonly") or 0),
                    "readonly_reason": (row.get("readonly_reason") or "").strip(),
                }
            )
    return clauses


def _parse_readonly_tokens(readonly_clauses: str | None) -> tuple[set[str], list[str]]:
    if not readonly_clauses:
        return set(), []
    tokens = [t.strip() for t in re.split(r"[,\n]+", readonly_clauses) if t.strip()]
    clause_nums: set[str] = set()
    chapter_prefixes: list[str] = []
    for tok in tokens:
        if tok.upper().startswith("CHAPTER "):
            chapter_prefixes.append(tok.upper())
        else:
            clause_nums.add(tok)
    return clause_nums, chapter_prefixes


def _resolve_file_path(file_url: str) -> str:
    if not file_url:
        frappe.throw(_("File URL is required."), frappe.ValidationError)
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if file_name:
        file_doc = frappe.get_doc("File", file_name)
        return file_doc.get_full_path()
    from frappe.utils.file_manager import get_file_path
    return get_file_path(file_url)


@frappe.whitelist()
def import_clauses_from_file(
    consultation: str,
    file_url: str,
    replace_existing: int = 0,
    readonly_clauses: str | None = None,
    readonly_reason: str | None = None,
    dry_run: int = 0,
    baseline_file_url: str | None = None,
    lock_unmodified: int = 1,
) -> dict:
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        from society_erp.www.resident.committee.index import check_committee_access
        has_access, _info = check_committee_access(frappe.session.user)
        if not has_access:
            frappe.has_permission("Bye-Law Consultation", "write", consultation, throw=True)

    file_path = _resolve_file_path(file_url)
    if not file_path or not os.path.isfile(file_path):
        frappe.throw(_("Source file not found on server."), frappe.ValidationError)

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        baseline_path = _resolve_file_path(baseline_file_url) if baseline_file_url else None
        rows = parse_docx_clauses(
            file_path,
            baseline_file_path=baseline_path,
            lock_unmodified=bool(cint(lock_unmodified)),
        )
    elif ext == ".csv":
        rows = parse_csv_clauses(file_path)
    else:
        frappe.throw(_("Unsupported file type. Please upload a .docx or .csv file."), frappe.ValidationError)

    clause_nums, chapter_prefixes = _parse_readonly_tokens(readonly_clauses)
    default_reason = (readonly_reason or "").strip() or "Mandatory under TNAOA 2022"

    for row in rows:
        ch_upper = (row.get("chapter") or "").upper()
        is_ro = (
            row.get("is_readonly")
            or row["clause_number"] in clause_nums
            or any(ch_upper == pref or ch_upper.startswith(pref + ":") for pref in chapter_prefixes)
        )
        if is_ro:
            row["is_readonly"] = 1
            if not row.get("readonly_reason"):
                row["readonly_reason"] = default_reason

    chapters = list(dict.fromkeys(r["chapter"] for r in rows if r.get("chapter")))

    if cint(dry_run):
        return {
            "count": len(rows),
            "chapters": chapters,
            "sample": rows[:5],
        }

    if cint(replace_existing):
        if frappe.db.exists("Bye-Law Clause Comment", {"consultation": consultation}):
            frappe.throw(
                _("Cannot replace existing clauses because owner comments already exist on this consultation."),
                frappe.ValidationError,
            )
        frappe.db.delete("Bye-Law Clause", {"consultation": consultation})

    readonly_count = 0
    for row in rows:
        doc = frappe.get_doc(
            {
                "doctype": "Bye-Law Clause",
                "consultation": consultation,
                "sequence_no": row["sequence_no"],
                "chapter": row["chapter"],
                "clause_number": row["clause_number"],
                "clause_title": row["clause_title"],
                "draft_text": row["draft_text"],
                "is_readonly": cint(row["is_readonly"]),
                "readonly_reason": row["readonly_reason"] if cint(row["is_readonly"]) else "",
            }
        ).insert(ignore_permissions=True)
        if doc.is_readonly:
            readonly_count += 1

    return {
        "imported": len(rows),
        "readonly_count": readonly_count,
        "chapters": chapters,
    }
