from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
import os
from typing import Any, Dict, List
import re


class TaxWorkbookParser(BaseParser):
    """
    Modular parser for professional tax organizer workbooks (e.g., UltraTax, Lacerte, Drake).
    Outputs a structured JSON schema as described in the PRD, not the standard ParserOutput.
    Now also outputs a page inventory and a topic/form index for upstream ingest.
    """

    @staticmethod
    def can_parse(input_path: str) -> bool:
        try:
            import pdfplumber

            with pdfplumber.open(input_path) as pdf:
                for i in range(min(3, len(pdf.pages))):
                    text = pdf.pages[i].extract_text() or ""
                    if any(
                        keyword in text
                        for keyword in [
                            "Tax Organizer",
                            "Interest Income",
                            "Schedule D",
                            "1099",
                            "Topic Index",
                        ]
                    ):
                        return True
        except Exception:
            pass
        return False

    @staticmethod
    def parse_file(input_path: str, config: Any = None) -> Dict:
        import pdfplumber

        output = {
            "organizer_sections": [],
            "documents": [],
            "unclassified_fields": [],
            "metadata": {"errors": []},
            "toc": [],
            "pages": [],
            # New keys for one-time ingest:
            "topic_index": [],
            "forms": [],
            "parsed_topic_index": [],
        }
        try:
            with pdfplumber.open(input_path) as pdf:
                # --- Page Inventory ---
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    lines = text.splitlines()
                    # Bottom label: look for 'PAGE N' at the end
                    bottom_label = None
                    for line in reversed(lines):
                        m = re.match(r"PAGE\s+(\d+)", line.strip(), re.IGNORECASE)
                        if m:
                            bottom_label = line.strip()
                            break
                    # Top label: first non-empty line (could be form code/title)
                    top_label = None
                    for line in lines:
                        if line.strip():
                            top_label = line.strip()
                            break
                    # Short preview (first 200 chars)
                    preview = text[:200].replace("\n", " ")
                    # Flag if this page contains '6A' (for demo)
                    contains_6A = "6A" in text
                    output["pages"].append(
                        {
                            "pdf_page_index": i,
                            "bottom_label": bottom_label,
                            "top_label": top_label,
                            "text_preview": preview,
                            "contains_6A": contains_6A,
                            "text": text,
                        }
                    )
                # --- Improved Topic Index Parsing ---
                toc_page_idx = None
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if "Topic Index" in text:
                        toc_page_idx = i
                        break
                parsed_topic_index = []
                if toc_page_idx is not None:
                    toc_text = pdf.pages[toc_page_idx].extract_text() or ""
                    lines = toc_text.splitlines()
                    parent_topic = None
                    for line in lines:
                        # Skip title/header lines
                        if not line.strip() or "Topic Index" in line or "Form" in line:
                            continue
                        # Try to split into two columns by large whitespace gap or at midpoint
                        split = None
                        m = re.search(r"\s{8,}", line)
                        if m:
                            split = m.start()
                        elif len(line) > 40:
                            split = len(line) // 2
                        columns = [line]
                        if split:
                            columns = [line[:split].rstrip(), line[split:].lstrip()]
                        for col in columns:
                            col = col.strip()
                            if not col:
                                continue
                            if col.endswith(":"):
                                parent_topic = col[:-1].strip()
                                continue
                            # Match: Form Name ~~~~~~ Code(s)
                            m = re.match(r"(.+?)[~.]+\s*([\dA-Za-z, ]+)$", col)
                            if m:
                                form_name = m.group(1).strip()
                                codes = [
                                    x.strip()
                                    for x in m.group(2).split(",")
                                    if x.strip()
                                ]
                                parsed_topic_index.append(
                                    {
                                        "topic_name": parent_topic,
                                        "form_name": form_name,
                                        "form_codes": codes,
                                    }
                                )
                output["parsed_topic_index"] = parsed_topic_index
                # --- Build forms array: for each form code, find all pages with matching top_label ---
                forms = []
                # Build a mapping from form code to topic name for easy lookup
                code_to_topic = {}
                for topic in parsed_topic_index:
                    for code in topic["form_codes"]:
                        code_to_topic[code] = topic["topic_name"]
                # For each page, check if its top_label contains any form code
                for page in output["pages"]:
                    for code, topic_name in code_to_topic.items():
                        if code and code in (page["top_label"] or ""):
                            forms.append(
                                {
                                    "form_code": code,
                                    "topic_name": topic_name,
                                    "pdf_page_index": page["pdf_page_index"],
                                    "top_label": page["top_label"],
                                    "bottom_label": page["bottom_label"],
                                    "text_preview": page["text_preview"],
                                    "notes": "",
                                }
                            )
                output["forms"] = forms
                # --- Existing section extraction logic (unchanged) ---
                toc_flat = []
                for toc in parsed_topic_index:
                    for code in toc["form_codes"]:
                        toc_flat.append(
                            {
                                "name": toc["topic_name"],
                                "code": code,
                                "page_number": int(code) if code.isdigit() else code,
                            }
                        )
                output["toc"] = toc_flat
                for toc in toc_flat:
                    section = {
                        "name": toc["name"],
                        "page_number": toc["page_number"],
                        "fields": [],
                        "complete": False,
                    }
                    if isinstance(toc["page_number"], int) and 0 < toc[
                        "page_number"
                    ] <= len(pdf.pages):
                        page_idx = toc["page_number"] - 1
                        page = pdf.pages[page_idx]
                        text = page.extract_text() or ""
                        lines = text.splitlines()
                        for line in lines:
                            if ":" in line:
                                label, value = line.split(":", 1)
                                section["fields"].append(
                                    {
                                        "label": label.strip(),
                                        "value": value.strip(),
                                        "type": "text",
                                        "line_number": None,
                                        "notes": "",
                                    }
                                )
                            elif "\t" in line:
                                parts = line.split("\t")
                                if len(parts) == 2:
                                    section["fields"].append(
                                        {
                                            "label": parts[0].strip(),
                                            "value": parts[1].strip(),
                                            "type": "text",
                                            "line_number": None,
                                            "notes": "",
                                        }
                                    )
                                else:
                                    output["unclassified_fields"].append(
                                        {
                                            "text": line,
                                            "page_number": toc["page_number"],
                                        }
                                    )
                            elif re.search(r"\s{2,}", line):
                                parts = re.split(r"\s{2,}", line)
                                if len(parts) == 2:
                                    section["fields"].append(
                                        {
                                            "label": parts[0].strip(),
                                            "value": parts[1].strip(),
                                            "type": "text",
                                            "line_number": None,
                                            "notes": "",
                                        }
                                    )
                                else:
                                    output["unclassified_fields"].append(
                                        {
                                            "text": line,
                                            "page_number": toc["page_number"],
                                        }
                                    )
                            else:
                                output["unclassified_fields"].append(
                                    {"text": line, "page_number": toc["page_number"]}
                                )
                        section["complete"] = len(section["fields"]) > 0
                    else:
                        output["metadata"]["errors"].append(
                            {
                                "section": toc["name"],
                                "page": toc["page_number"],
                                "field": None,
                                "reason": "Page not found or not an integer page number",
                            }
                        )
                    output["organizer_sections"].append(section)
        except Exception as e:
            output["metadata"]["errors"].append(
                {
                    "section": None,
                    "page": None,
                    "field": None,
                    "reason": f"Exception: {e}",
                }
            )
        return output

    @staticmethod
    def normalize_data(raw_data: Dict) -> Dict:
        # For now, just return the raw_data (already structured)
        return raw_data


# Register the parser
ParserRegistry.register_parser("tax_workbook", TaxWorkbookParser)

# CLI/test entrypoint
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python tax_workbook_parser.py <PDF_PATH>")
        sys.exit(1)
    result = TaxWorkbookParser.parse_file(sys.argv[1])
    # Save improved topic index sample
    with open("debug_outputs/parsed_topic_index_sample.json", "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result["parsed_topic_index"], indent=2))
    print(
        f"\nSummary: {len(result['parsed_topic_index'])} parsed topic index entries, {len(result['organizer_sections'])} sections, {len(result['unclassified_fields'])} unclassified fields, {len(result['metadata']['errors'])} errors, {len(result['pages'])} pages, {len(result['forms'])} forms."
    )
