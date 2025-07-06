import os
import json
from typing import List, Dict, Any, Optional, Tuple
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from dotenv import load_dotenv
import openai
from openai import OpenAI
import base64
from rapidfuzz import fuzz, process
from pydantic import BaseModel, RootModel
import logging
import argparse
import datetime
import shutil
from logging.handlers import RotatingFileHandler


class MergedEntry(BaseModel):
    form_code: str
    description: str
    page_number: Optional[int]
    pdf_path: Optional[str]
    thumbnail_path: Optional[str]
    matched_title: Optional[str]


class MergedList(BaseModel):
    items: List[MergedEntry]

    def to_list(self):
        return [item.model_dump() for item in self.items]

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]

    def dict(self, *args, **kwargs):
        # Only pass valid arguments to model_dump (exclude 'indent' and any json.dumps args)
        model_dump_args = {}
        for k, v in kwargs.items():
            if k in (
                "mode",
                "include",
                "exclude",
                "by_alias",
                "exclude_unset",
                "exclude_defaults",
                "exclude_none",
            ):  # valid model_dump args
                model_dump_args[k] = v
        return [item.model_dump(**model_dump_args) for item in self.items]

    def json(self, *args, **kwargs):
        import json

        # Separate json.dumps args from model_dump args
        json_args = {}
        model_dump_args = {}
        for k, v in kwargs.items():
            if k in (
                "indent",
                "separators",
                "sort_keys",
                "ensure_ascii",
            ):  # valid json.dumps args
                json_args[k] = v
            elif k in (
                "mode",
                "include",
                "exclude",
                "by_alias",
                "exclude_unset",
                "exclude_defaults",
                "exclude_none",
            ):
                model_dump_args[k] = v
        return json.dumps(self.dict(**model_dump_args), **json_args)

    def save(self, path):
        with open(path, "w") as f:
            f.write(self.json(indent=2))

    @classmethod
    def from_list(cls, data):
        return cls(items=[MergedEntry(**item) for item in data])


class OrganizerExtractor:
    """
    OrganizerExtractor: Modular pipeline for extracting and linking Table of Contents (TOC), Topic Index, page thumbnails, raw text, and metadata from professional tax organizer PDFs (e.g., UltraTax, Lacerte, Drake).

    Usage (CLI):
        python3 -m dataextractai.parsers.organizer_extractor --pdf_path <input.pdf>
        # Test mode (use cached JSONs):
        python3 -m dataextractai.parsers.organizer_extractor --pdf_path <input.pdf> --test_mode
        # Prefilled data detection only:
        python3 -m dataextractai.parsers.organizer_extractor --pdf_path <input.pdf> --detect_prefilled
        # Skip prefilled detection:
        python3 -m dataextractai.parsers.organizer_extractor --pdf_path <input.pdf> --skip_prefilled
        # Custom output directory:
        python3 -m dataextractai.parsers.organizer_extractor --pdf_path <input.pdf> --output_dir <output_dir>

    Output Directory Structure:
        - toc_llm_merged.json: Main manifest (one entry per TOC page)
        - toc_llm_merged_prefilled.json: Manifest with prefilled data fields
        - page_{n}.pdf, page_{n}.png, page_{n}.txt: Per-page PDF, thumbnail, and raw text

    Manifest Schema:
        Each entry includes:
            - page_number: int
            - toc_title: str (from TOC)
            - topic_index_match: {"form_code": str, "description": str} or null
            - pdf_page_file: str (filename)
            - thumbnail_file: str (filename)
            - raw_text_file: str (filename)
            - matching_method: str ("llm" or "none")
            - has_prefilled_data: bool
            - prefilled_fields: dict or null
            - prefilled_model: str (LLM model used)

    Logging:
        - Logs all file paths, output directories, and LLM model usage.
        - At the end, logs the location of the final output manifest (e.g., toc_llm_merged_prefilled.json).

    Troubleshooting:
        - If you see OpenAI API errors, check your .env and model settings.
        - If files are missing, check the output directory and logs for details.
        - For debugging, use --test_mode to skip PDF/Vision extraction and use cached JSONs.

    Integration:
        - can_parse static method allows auto-detection in a parser registry.
        - Output is a custom schema (not the standard ParserOutput model).
        - See README.md for more details.

    **Integration Notes:**
    - This parser does NOT return the standard `ParserOutput` Pydantic model used by other modular parsers.
    - Instead, the main output is a list of dicts (or a JSON array) with the following schema:
        {
            "page_number": int,
            "toc_title": str,
            "topic_index_match": {"form_code": str, "description": str} | null,
            "pdf_page_file": str,  # filename only
            "thumbnail_file": str, # filename only
            "raw_text_file": str, # filename only
            "matching_method": str  # 'llm' or 'none'
        }
    - Upstream consumers should expect this schema and handle ingestion accordingly.
    - This parser is best used for professional tax organizer PDFs, not for standard bank/credit card statements.

    **can_parse method:**
    - Use `OrganizerExtractor.can_parse(file_path)` to check if a file is likely an organizer PDF.
    - This is a simple heuristic: returns True if the filename or first page contains 'Organizer' or 'Tax Organizer'.
    - For registry integration, register this parser with your parser registry and call can_parse for auto-detection.

    Workflow Overview:
    ------------------
    1. **TOC Extraction**: Extracts the PDF bookmarks (TOC) and resolves each entry to its page number.
    2. **Page Splitting**: Splits the PDF into single-page PDFs, saving each as `page_{N}.pdf` in the output directory.
    3. **Thumbnail Generation**: Generates high-resolution PNG thumbnails for each page as `thumb_{N}.png`.
    4. **TOC Inventory**: Links each TOC entry to its page and thumbnail, saving the inventory as `toc_inventory.json`.
    5. **Topic Index Extraction**:
       - Locates the Topic Index page visually.
       - Splits it into left/right columns and saves as images.
       - Uses OpenAI Vision LLM to extract `{form_code, description}` pairs from each column, merging results into `topic_index_pairs_vision.json`.
    6. **Merging Topic Index with TOC**:
       - Merges Topic Index pairs with TOC inventory using exact, fuzzy, or LLM-based matching.
       - Outputs:
         - `topic_index_merged.json` (exact match)
         - `topic_index_merged_fuzzy.json` (fuzzy match)
         - `topic_index_merged_llm.json` (LLM schema-based, recommended)
    7. **LLM Merge Output**:
       - The final, robust output is `topic_index_merged_llm.json`, a JSON object with a single key `items`, whose value is an array of objects with:
         - `form_code`, `description`, `page_number`, `pdf_path`, `thumbnail_path`, `matched_title`
       - This file is saved in the specified output directory.

    Output Files:
    -------------
    - `toc_inventory.json`: List of TOC/bookmark entries with page and file links.
    - `page_{N}.pdf`: Single-page PDFs for each page.
    - `thumb_{N}.png`: Thumbnails for each page.
    - `topic_index_left_col.png`, `topic_index_right_col.png`: Column images of the Topic Index.
    - `topic_index_pairs_vision.json`: Extracted Topic Index pairs from Vision LLM.
    - `topic_index_merged.json`: Merged Topic Index and TOC (exact match).
    - `topic_index_merged_fuzzy.json`: Merged Topic Index and TOC (fuzzy match).
    - `topic_index_merged_llm.json`: **Final merged output** (LLM schema-based, recommended for integration).

    Usage Example:
    --------------
    >>> extractor = OrganizerExtractor("input.pdf", "output_dir")
    >>> extractor.extract()  # Extracts TOC, splits pages, generates thumbnails
    >>> extractor.extract_topic_index_pairs_vision()  # Extracts Topic Index pairs using Vision LLM
    >>> extractor.merge_with_llm()  # Produces topic_index_merged_llm.json

    See the __main__ block for a full demo pipeline.
    """

    def __init__(self, pdf_path: str, output_dir: str, thumbnail_dpi: int = 200):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.thumbnail_dpi = thumbnail_dpi
        os.makedirs(self.output_dir, exist_ok=True)
        self.errors = []
        self.warnings = []
        load_dotenv()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model_ocr = os.getenv("OPENAI_MODEL_OCR", "gpt-4o")
        openai.api_key = self.openai_api_key
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
        )

    def extract_toc(self) -> List[Dict[str, Any]]:
        toc = []
        try:
            reader = PdfReader(self.pdf_path)
            outlines = getattr(reader, "outline", None)
            if outlines:

                def walk(outlines, parent=None):
                    for item in outlines:
                        if isinstance(item, list):
                            walk(item, parent)
                        else:
                            title = getattr(item, "title", str(item))
                            page_num = None
                            # Try to resolve page number
                            try:
                                # Use get_destination_page_number for Destination objects
                                page_num = reader.get_destination_page_number(item) + 1
                            except Exception as e:
                                print(
                                    f"DEBUG: Exception resolving page_num for '{title}': {e}"
                                )
                            toc.append(
                                {
                                    "title": title,
                                    "page_number": page_num,
                                    "parent": parent,
                                }
                            )
                            logging.info(f"TOC: '{title}' resolved to page {page_num}")

                walk(outlines)
        except Exception as e:
            self.errors.append(f"TOC extraction failed: {e}")
        return toc

    def split_pages(self) -> List[Dict[str, Any]]:
        pages_info = []
        try:
            reader = PdfReader(self.pdf_path)
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                page_pdf_path = os.path.join(self.output_dir, f"page_{i+1}.pdf")
                with open(page_pdf_path, "wb") as f:
                    writer.write(f)
                pages_info.append({"page_number": i + 1, "pdf_path": page_pdf_path})
        except Exception as e:
            self.errors.append(f"Page splitting failed: {e}")
        return pages_info

    def generate_thumbnails(self, pages_info: List[Dict[str, Any]]):
        try:
            images = convert_from_path(self.pdf_path, dpi=self.thumbnail_dpi)
            for i, image in enumerate(images):
                thumb_path = os.path.join(self.output_dir, f"thumb_{i+1}.png")
                image.save(thumb_path, "PNG")
                pages_info[i]["thumbnail_path"] = thumb_path
        except Exception as e:
            self.warnings.append(f"Thumbnail generation failed: {e}")

    def write_toc_inventory(self, toc, path=None):
        """Write the TOC inventory as valid JSON (no debug output)."""
        if path is None:
            path = os.path.join(self.output_dir, "toc_inventory.json")
        with open(path, "w") as f:
            json.dump(toc, f, indent=2)

    def extract(self) -> Dict[str, Any]:
        toc = self.extract_toc()
        pages_info = self.split_pages()
        self.generate_thumbnails(pages_info)
        # Link TOC entries to page and thumbnail paths
        for entry in toc:
            page_num = entry.get("page_number")
            if page_num:
                entry["pdf_path"] = os.path.join(
                    self.output_dir, f"page_{page_num}.pdf"
                )
                entry["thumbnail_path"] = os.path.join(
                    self.output_dir, f"thumb_{page_num}.png"
                )
            else:
                entry["pdf_path"] = None
                entry["thumbnail_path"] = None
        # Write valid JSON TOC inventory
        self.write_toc_inventory(toc)
        return {
            "toc": toc,
            "pages": pages_info,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def extract_topic_index_columns(self) -> Optional[List[str]]:
        """
        Find the Topic Index page, render it as an image, split into left/right columns, and save.
        Returns list of file paths to the column images, or None if not found.
        """
        # 1. Find the TOC page by searching for 'Topic Index' in the text
        toc_page_num = None
        reader = PdfReader(self.pdf_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if "Topic Index" in text:
                toc_page_num = i + 1  # pdf2image is 1-based
                break
        if toc_page_num is None:
            self.warnings.append("No 'Topic Index' page found.")
            return None
        # 2. Render the page as a high-res image
        images = convert_from_path(
            self.pdf_path, dpi=300, first_page=toc_page_num, last_page=toc_page_num
        )
        toc_image = images[0]
        width, height = toc_image.size
        # 3. Split the image vertically
        left_col = toc_image.crop((0, 0, width // 2, height))
        right_col = toc_image.crop((width // 2, 0, width, height))
        # 4. Save the column images
        left_path = os.path.join(self.output_dir, f"topic_index_left_col.png")
        right_path = os.path.join(self.output_dir, f"topic_index_right_col.png")
        left_col.save(left_path, "PNG")
        right_col.save(right_path, "PNG")
        return [left_path, right_path]

    def extract_topic_index_pairs(self) -> Optional[List[Dict[str, str]]]:
        """
        OCR the left and right column images of the Topic Index, extract form numbers and descriptions.
        Returns a list of {form_code, description} dicts.
        """
        col_paths = self.extract_topic_index_columns()
        if not col_paths:
            return None
        pairs = []
        for idx, col_path in enumerate(col_paths):
            text = pytesseract.image_to_string(col_path)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            # Find the header 'Form' in the left column, skip lines above it
            data_start = 0
            if idx == 0:  # left column
                for i, line in enumerate(lines):
                    if line.lower().startswith("form"):
                        data_start = i + 1
                        break
            else:
                data_start = 0  # right column has no header, just use all lines
            for line in lines[data_start:]:
                # Try to extract form code (first word) and description (rest)
                parts = line.split(maxsplit=1)
                if (
                    len(parts) == 2
                    and parts[0]
                    .replace("-", "")
                    .replace("A", "")
                    .replace("B", "")
                    .replace("C", "")
                    .replace("D", "")
                    .replace("E", "")
                    .replace("F", "")
                    .replace("G", "")
                    .replace("H", "")
                    .replace("I", "")
                    .replace("J", "")
                    .replace("K", "")
                    .replace("L", "")
                    .replace("M", "")
                    .replace("N", "")
                    .replace("O", "")
                    .replace("P", "")
                    .replace("Q", "")
                    .replace("R", "")
                    .replace("S", "")
                    .replace("T", "")
                    .replace("U", "")
                    .replace("V", "")
                    .replace("W", "")
                    .replace("X", "")
                    .replace("Y", "")
                    .replace("Z", "")
                    .isdigit()
                ):
                    form_code, description = parts
                    pairs.append({"form_code": form_code, "description": description})
        return pairs

    def extract_topic_index_pairs_vision(
        self, save_json: bool = True
    ) -> Optional[List[Dict[str, str]]]:
        """
        Use OpenAI GPT-4o Vision API to extract {form_code, description} pairs from each Topic Index column image.
        Merges results and saves to a JSON file if requested.
        Returns the merged list.
        """
        col_paths = self.extract_topic_index_columns()
        if not col_paths:
            return None
        prompt = (
            "Here is a column from a tax organizer's table of contents. "
            "Please extract a list of objects with form_code and description for each entry. "
            "Ignore any page numbers, dates, or footers. "
            "The form code is usually a number or a number with a letter (e.g., 5A, 14A, 9, 10E). "
            "The description is the text to the right of the form code. "
            "Return the result as a JSON array."
        )
        merged_pairs = []
        client = OpenAI(api_key=self.openai_api_key)
        for col_path in col_paths:
            with open(col_path, "rb") as img_file:
                img_bytes = img_file.read()
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                image_content = {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                }
                try:
                    response = client.chat.completions.create(
                        model=self.openai_model_ocr,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that extracts structured data from images.",
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    image_content,
                                ],
                            },
                        ],
                        max_tokens=1024,
                        temperature=0.0,
                    )
                    import re
                    import ast

                    content = response.choices[0].message.content
                    match = re.search(r"\[.*?\]", content, re.DOTALL)
                    if match:
                        try:
                            pairs = json.loads(match.group(0))
                        except Exception:
                            try:
                                pairs = ast.literal_eval(match.group(0))
                            except Exception:
                                pairs = []
                    else:
                        pairs = []
                    merged_pairs.extend(pairs)
                except Exception as e:
                    self.errors.append(f"Vision API call failed for {col_path}: {e}")
        if save_json:
            save_path = os.path.join(self.output_dir, "topic_index_pairs_vision.json")
            with open(save_path, "w") as f:
                json.dump(merged_pairs, f, indent=2)
        return merged_pairs

    def merge_topic_index_with_toc(
        self, topic_index_path=None, toc_path=None, save_json=True
    ):
        """
        Merge the Vision LLM Topic Index pairs with the TOC/bookmark inventory using exact (case-insensitive, stripped) matching.
        Save the merged result as topic_index_merged.json.
        Print a summary of unmatched entries.
        """
        # Load Topic Index pairs
        if topic_index_path is None:
            topic_index_path = os.path.join(
                self.output_dir, "topic_index_pairs_vision.json"
            )
        with open(topic_index_path, "r") as f:
            topic_pairs = json.load(f)
        # Load TOC/bookmark inventory
        if toc_path is None:
            toc_path = os.path.join(self.output_dir, "toc.json")
        if not os.path.exists(toc_path):
            # Fallback: use self.extract_toc()
            toc = self.extract_toc()
        else:
            with open(toc_path, "r") as f:
                toc = json.load(f)
        # Build a lookup for TOC titles (case-insensitive, stripped)
        toc_lookup = {t["title"].strip().lower(): t for t in toc}
        merged = []
        unmatched = []
        for pair in topic_pairs:
            desc_key = pair["description"].strip().lower()
            toc_entry = toc_lookup.get(desc_key)
            if toc_entry:
                merged.append(
                    {
                        "form_code": pair.get("form_code"),
                        "description": pair.get("description"),
                        "page_number": toc_entry.get("page_number"),
                        "pdf_path": toc_entry.get("pdf_path"),
                        "thumbnail_path": toc_entry.get("thumbnail_path"),
                    }
                )
            else:
                merged.append(
                    {
                        "form_code": pair.get("form_code"),
                        "description": pair.get("description"),
                        "page_number": None,
                        "pdf_path": None,
                        "thumbnail_path": None,
                    }
                )
                unmatched.append(pair)
        if save_json:
            save_path = os.path.join(self.output_dir, "topic_index_merged.json")
            with open(save_path, "w") as f:
                json.dump(merged, f, indent=2)
        print(f"Merged {len(merged)} entries. Unmatched: {len(unmatched)}")
        if unmatched:
            print("Unmatched entries:")
            for u in unmatched:
                print(u)
        return merged

    def merge_topic_index_with_toc_fuzzy(
        self, topic_index_path=None, toc_path=None, save_json=True, threshold=80
    ):
        """
        Merge Topic Index pairs with TOC using fuzzy matching. For each Topic Index entry, find the TOC title with the highest similarity.
        Save as topic_index_merged_fuzzy.json. Print summary of matches and unmatched.
        """
        # Load Topic Index pairs
        if topic_index_path is None:
            topic_index_path = os.path.join(
                self.output_dir, "topic_index_pairs_vision.json"
            )
        with open(topic_index_path, "r") as f:
            topic_index = json.load(f)
        # Load TOC
        if toc_path is None:
            toc_path = os.path.join(self.output_dir, "toc_inventory.json")
        with open(toc_path, "r") as f:
            toc = json.load(f)
        toc_titles = [entry["title"] for entry in toc]
        merged = []
        unmatched = []
        for entry in topic_index:
            desc = entry["description"]
            # Find best fuzzy match
            best_match, score, idx = process.extractOne(
                desc, toc_titles, scorer=fuzz.token_sort_ratio
            )
            if score >= threshold:
                toc_entry = toc[idx]
                merged.append(
                    {
                        **entry,
                        "page_number": toc_entry["page_number"],
                        "pdf_path": toc_entry["pdf_path"],
                        "thumbnail_path": toc_entry["thumbnail_path"],
                        "match_score": score,
                        "matched_title": toc_entry["title"],
                    }
                )
            else:
                unmatched.append(
                    {**entry, "match_score": score, "matched_title": best_match}
                )
        if save_json:
            out_path = os.path.join(self.output_dir, "topic_index_merged_fuzzy.json")
            with open(out_path, "w") as f:
                json.dump(merged, f, indent=2)
            print(
                f"Fuzzy merged {len(merged)} entries, {len(unmatched)} unmatched. Saved to {out_path}"
            )
            if unmatched:
                print("Unmatched entries (showing up to 10):")
                for u in unmatched[:10]:
                    print(u)
        return merged, unmatched

    def merge_with_llm(self, topic_index_path=None, toc_path=None, save_json=True):
        """
        Use GPT-4o to match each {form_code, description} to the best TOC entry (title/page/pdf_path/thumbnail_path).
        Save the merged result as topic_index_merged_llm.json.
        """
        import openai
        import os
        import json
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL_OCR", "gpt-4o")
        if topic_index_path is None:
            topic_index_path = os.path.join(
                self.output_dir, "topic_index_pairs_vision.json"
            )
        if toc_path is None:
            toc_path = os.path.join(self.output_dir, "toc_inventory.json")
        with open(topic_index_path) as f:
            topic_index = json.load(f)
        with open(toc_path) as f:
            toc = json.load(f)
        prompt = (
            "You are a data assistant. Match each {form_code, description} from the Topic Index to the best TOC entry (title/page/pdf_path/thumbnail_path). "
            "Return a JSON object with a single key 'items', whose value is an array of objects, each with: form_code, description, page_number, pdf_path, thumbnail_path, matched_title. "
            "If no good match, leave page_number/pdf_path/thumbnail_path/matched_title as null. "
            f"\n\nTopic Index:\n{json.dumps(topic_index)}\n\nTOC Inventory:\n{json.dumps(toc)}"
        )
        client = openai.OpenAI(api_key=api_key)
        completion = client.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=MergedList,
        )
        merged = completion.choices[0].message.parsed
        if save_json:
            merged.save(os.path.join(self.output_dir, "topic_index_merged_llm.json"))
        return merged

    def toc_driven_merge_with_topic_index(
        self, topic_index_path=None, toc_path=None, save_json=True, fuzzy_threshold=80
    ):
        """
        TOC-driven merge: For each TOC entry, attempt to assign a form_code/description from the Topic Index (using exact, then fuzzy match).
        Output only TOC-present forms enriched with form_code/description if matched.
        """
        # Load TOC/bookmark inventory
        if toc_path is None:
            toc_path = os.path.join(self.output_dir, "toc_inventory.json")
        with open(toc_path, "r") as f:
            toc = json.load(f)
        # Load Topic Index pairs
        if topic_index_path is None:
            topic_index_path = os.path.join(
                self.output_dir, "topic_index_pairs_vision.json"
            )
        with open(topic_index_path, "r") as f:
            topic_pairs = json.load(f)
        # Build lookup for exact match (case-insensitive, stripped)
        topic_lookup = {p["description"].strip().lower(): p for p in topic_pairs}
        topic_descs = [p["description"] for p in topic_pairs]
        from rapidfuzz import fuzz, process

        output = []
        for entry in toc:
            title = entry.get("title", "").strip()
            title_lc = title.lower()
            # Try exact match
            topic = topic_lookup.get(title_lc)
            match_type = None
            match_score = None
            matched_topic_desc = None
            form_code = None
            description = None
            if topic:
                form_code = topic.get("form_code")
                description = topic.get("description")
                match_type = "exact"
                matched_topic_desc = topic.get("description")
                match_score = 100
            else:
                # Fuzzy match
                best_match, score, idx = process.extractOne(
                    title, topic_descs, scorer=fuzz.token_sort_ratio
                )
                if score >= fuzzy_threshold:
                    topic = topic_pairs[idx]
                    form_code = topic.get("form_code")
                    description = topic.get("description")
                    match_type = "fuzzy"
                    matched_topic_desc = best_match
                    match_score = score
            output.append(
                {
                    "form_code": form_code,
                    "description": description,
                    "page_number": entry.get("page_number"),
                    "pdf_path": entry.get("pdf_path"),
                    "thumbnail_path": entry.get("thumbnail_path"),
                    "title": title,
                    "matched_topic_index_description": matched_topic_desc,
                    "match_type": match_type,
                    "match_score": match_score,
                }
            )
        if save_json:
            save_path = os.path.join(self.output_dir, "toc_driven_output.json")
            with open(save_path, "w") as f:
                json.dump(output, f, indent=2)
        return output

    def extract_raw_text_per_page(self):
        """
        Extracts raw text for each page and saves as page_{n}.txt in output_dir.
        Returns a list of filenames.
        """
        from PyPDF2 import PdfReader

        reader = PdfReader(self.pdf_path)
        raw_text_files = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            fname = f"page_{i+1}.txt"
            fpath = os.path.join(self.output_dir, fname)
            with open(fpath, "w") as f:
                f.write(text)
            raw_text_files.append(fname)
        logging.info(f"Extracted raw text for {len(raw_text_files)} pages.")
        return raw_text_files

    def merge_llm_toc_driven(
        self, topic_index_path=None, toc_path=None, save_json=True, test_mode=False
    ):
        """
        For each TOC entry, use LLM to find the best matching form_code (using all associated descriptions for each code).
        Output is a list of dicts, each with:
          - toc_title: the TOC entry title
          - topic_index_match: {form_code, description} or null
          - page_number, pdf_path, thumbnail_path
          - matching_method: 'llm' or 'none'
        If test_mode is True, use pre-generated JSON files for TOC and Topic Index.
        """
        # Determine file paths
        if test_mode:
            toc_path = toc_path or os.path.abspath(
                "debug_outputs/organizer_test/toc_inventory.json"
            )
            topic_index_path = topic_index_path or os.path.abspath(
                "debug_outputs/organizer_test/topic_index_pairs_vision.json"
            )
            logging.info(f"[TEST MODE] Using pre-generated TOC: {toc_path}")
            logging.info(
                f"[TEST MODE] Using pre-generated Topic Index: {topic_index_path}"
            )
        else:
            toc_path = toc_path or os.path.abspath(
                os.path.join(self.output_dir, "toc_inventory.json")
            )
            topic_index_path = topic_index_path or os.path.abspath(
                os.path.join(self.output_dir, "topic_index_pairs_vision.json")
            )
            logging.info(f"[LIVE MODE] Using TOC: {toc_path}")
            logging.info(f"[LIVE MODE] Using Topic Index: {topic_index_path}")
        # Load TOC
        with open(toc_path, "r") as f:
            toc = json.load(f)
        logging.info(f"Loaded {len(toc)} TOC entries from {toc_path}")
        # Load Topic Index
        with open(topic_index_path, "r") as f:
            topic_index = json.load(f)
        logging.info(
            f"Loaded {len(topic_index)} Topic Index pairs from {topic_index_path}"
        )
        # Build form_code -> [descriptions] mapping
        from collections import defaultdict

        form_code_to_desc = defaultdict(list)
        for entry in topic_index:
            codes = [c.strip() for c in entry["form_code"].split(",")]
            for code in codes:
                form_code_to_desc[code].append(entry["description"])
        # Build enhanced topic index: [{form_code, descriptions: [..]}]
        enhanced_topic_index = [
            {"form_code": code, "descriptions": descs}
            for code, descs in form_code_to_desc.items()
        ]
        # Load raw text files (assume page_{n}.txt in output_dir)
        raw_text_files = [f"page_{i+1}.txt" for i in range(len(toc))]
        output = []
        for i, toc_entry in enumerate(toc):
            toc_title = toc_entry.get("title")
            page_number = toc_entry.get("page_number")
            pdf_path = toc_entry.get("pdf_path")
            thumbnail_path = toc_entry.get("thumbnail_path")
            raw_text_file = raw_text_files[i] if i < len(raw_text_files) else None
            match = self.llm_match_topic_index_multi(toc_title, enhanced_topic_index)
            if match:
                topic_index_match = {
                    "form_code": match["form_code"],
                    "description": match["description"],
                }
                matching_method = "llm"
            else:
                topic_index_match = None
                matching_method = "none"
            pdf_page_file = os.path.basename(pdf_path) if pdf_path else None
            thumbnail_file = (
                os.path.basename(thumbnail_path) if thumbnail_path else None
            )
            output.append(
                {
                    "page_number": page_number,
                    "toc_title": toc_title,
                    "topic_index_match": topic_index_match,
                    "pdf_page_file": pdf_page_file,
                    "thumbnail_file": thumbnail_file,
                    "raw_text_file": raw_text_file,
                    "matching_method": matching_method,
                }
            )
        if save_json:
            out_path = os.path.abspath(
                os.path.join(self.output_dir, "toc_llm_merged.json")
            )
            with open(out_path, "w") as f:
                json.dump(output, f, indent=2)
            logging.info(f"Saved TOC-driven LLM output to {out_path}")
        return output

    def llm_match_topic_index_multi(self, toc_title, enhanced_topic_index):
        """
        Use OpenAI LLM to select the best matching form_code (with all associated descriptions) for a given TOC title.
        Returns a dict with form_code and description (the best-matching description), or None if no good match.
        """
        import openai
        import os
        import json
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL_OCR", "gpt-4o")
        prompt = (
            f"You are a data assistant. Given a TOC entry title and a list of form codes, each with all associated descriptions, "
            f"select the best matching form_code for the TOC title. "
            f"For the best match, also return the most relevant description. "
            f"If no good match, return null.\n"
            f"TOC Title: {toc_title}\n"
            f"Form Codes with Descriptions: {json.dumps(enhanced_topic_index)}\n"
            f"Return a JSON object with keys: form_code, description. If no good match, return null."
        )
        try:
            client = openai.OpenAI(api_key=api_key)
            completion = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.0,
            )
            import re
            import ast

            content = completion.choices[0].message.content
            # Try to extract a JSON object or null
            match = re.search(r"\{.*?\}|null", content, re.DOTALL)
            if match:
                if match.group(0) == "null":
                    return None
                try:
                    result = json.loads(match.group(0))
                    if (
                        isinstance(result, dict)
                        and "form_code" in result
                        and "description" in result
                    ):
                        return result
                except Exception:
                    try:
                        result = ast.literal_eval(match.group(0))
                        if (
                            isinstance(result, dict)
                            and "form_code" in result
                            and "description" in result
                        ):
                            return result
                    except Exception:
                        pass
            return None
        except Exception as e:
            logging.warning(f"LLM match failed for '{toc_title}': {e}")
            return None

    @staticmethod
    def can_parse(file_path: str) -> bool:
        """
        Returns True if the file is likely a professional tax organizer PDF (by filename or first page text).
        """
        if not file_path.lower().endswith(".pdf"):
            return False
        fname = os.path.basename(file_path).lower()
        if "organizer" in fname:
            return True
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(file_path)
            first_page = reader.pages[0]
            text = first_page.extract_text() or ""
            if "organizer" in text.lower() or "tax organizer" in text.lower():
                return True
        except Exception:
            pass
        return False


class PrefilledDataDetector:
    """
    Detects prefilled/user data on each page using LLMs. Can be run as part of the pipeline or standalone.
    Supports exclusion of false positive terms via a config file (prefilled_exclude_terms.txt) in the project root or config directory.
    Any field or value matching a term in this file (case-insensitive, one per line) will be ignored as fillable data.
    """

    def __init__(
        self,
        manifest_path,
        raw_text_dir,
        output_path=None,
        model_env_keys=None,
        exclude_terms_path=None,
    ):
        self.manifest_path = manifest_path
        self.raw_text_dir = raw_text_dir
        self.output_path = output_path or manifest_path.replace(
            ".json", "_with_prefilled.json"
        )
        self.model_env_keys = model_env_keys or [
            "OPENAI_MODEL_FAST",
            "OPENAI_MODEL_PRECISE",
            "OPENAI_MODEL_OCR",
        ]
        load_dotenv()
        self.models = [os.getenv(k) for k in self.model_env_keys if os.getenv(k)]
        if not self.models:
            raise RuntimeError("No LLM models found in .env for prefilled detection.")
        # Load exclude terms from module-level config
        self.exclude_terms = set()
        config_paths = [
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "../../prefilled_exclude_terms.txt",
            ),
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "../prefilled_exclude_terms.txt",
            ),
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "prefilled_exclude_terms.txt",
            ),
            os.path.abspath("prefilled_exclude_terms.txt"),
        ]
        found = False
        for path in config_paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    self.exclude_terms = set(
                        line.strip().lower() for line in f if line.strip()
                    )
                found = True
                break
        if not found:
            # Default common false positives
            self.exclude_terms = {
                "on file",
                "on-file",
                "master",
                "footer",
                "does not expire",
            }
            logging.warning(
                "No prefilled_exclude_terms.txt found at module level. Using built-in defaults."
            )

    def _filter_excluded(self, fields):
        # Recursively filter out any field/value matching exclude_terms
        if isinstance(fields, dict):
            return {
                k: self._filter_excluded(v)
                for k, v in fields.items()
                if k.strip().lower() not in self.exclude_terms
                and (
                    isinstance(v, str)
                    and v.strip().lower() not in self.exclude_terms
                    or not isinstance(v, str)
                )
            }
        elif isinstance(fields, list):
            return [
                self._filter_excluded(v)
                for v in fields
                if not (isinstance(v, str) and v.strip().lower() in self.exclude_terms)
            ]
        else:
            return fields

    def detect(self):
        import openai

        logging.info(f"Starting prefilled data detection.")
        logging.info(f"Manifest path: {self.manifest_path}")
        logging.info(f"Raw text directory: {self.raw_text_dir}")
        logging.info(f"Output path: {self.output_path}")
        with open(self.manifest_path, "r") as f:
            manifest = json.load(f)
        updated = []
        page_count = 0
        for entry in manifest:
            page_number = entry.get("page_number")
            raw_text_file = entry.get("raw_text_file")
            if not raw_text_file:
                logging.warning(f"No raw_text_file for page {entry.get('page_number')}")
                continue
            raw_text_path = os.path.join(self.raw_text_dir, raw_text_file)
            logging.info(f"[Page {page_number}] Loading raw text from: {raw_text_path}")
            try:
                with open(raw_text_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
            except Exception as e:
                logging.error(
                    f"Failed to load raw text for page {entry.get('page_number')}: {e}"
                )
                entry["has_prefilled_data"] = None
                entry["prefilled_fields"] = None
                entry["prefilled_model"] = None
                continue
            logging.info(f"[Page {page_number}] Calling LLM for prefilled detection...")
            result, model_used = self._llm_detect_prefilled(raw_text)
            # Filter out excluded terms from prefilled_fields
            filtered_fields = (
                self._filter_excluded(result.get("prefilled_fields"))
                if result.get("prefilled_fields")
                else None
            )
            has_prefilled = bool(filtered_fields) if filtered_fields else False
            entry["has_prefilled_data"] = has_prefilled
            entry["prefilled_fields"] = filtered_fields
            entry["prefilled_model"] = model_used
            n_fields = (
                len(filtered_fields)
                if filtered_fields and isinstance(filtered_fields, dict)
                else 0
            )
            logging.info(
                f"[Page {page_number}] Model: {model_used} | has_prefilled_data: {has_prefilled} | Fields: {n_fields}"
            )
            updated.append(entry)
            page_count += 1
        logging.info(f"Writing manifest with prefilled data to {self.output_path}")
        with open(self.output_path, "w") as f:
            json.dump(updated, f, indent=2)
        logging.info(
            f"Prefilled data detection complete. Processed {page_count} pages."
        )
        logging.info(f"Final output written to: {self.output_path}")

    def _llm_detect_prefilled(self, page_text):
        import openai
        import json

        prompt = (
            "You are an expert at reading tax organizer PDFs. Given the following page text, does it contain any user-specific or prefilled data (such as names, SSNs, addresses, or prior year values)? "
            'If so, extract the fields and values as a JSON object. If not, return {"has_prefilled_data": false, "prefilled_fields": null}.\n\n'
            'Page text:\n"""\n' + page_text + '\n"""'
        )
        for model in self.models:
            try:
                response = openai.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=512,
                )
                content = response.choices[0].message.content
                try:
                    result = json.loads(content)
                    if "has_prefilled_data" in result:
                        return result, model
                except Exception as e:
                    logging.warning(f"Failed to parse LLM JSON for model {model}: {e}")
            except Exception as e:
                logging.warning(f"LLM model {model} failed: {e}")
        # Fallback: no detection
        return {"has_prefilled_data": False, "prefilled_fields": None}, None


def setup_logging(output_dir):
    log_file = os.path.join(output_dir, "organizer_pipeline.log")
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    # Remove all handlers
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    # Rotating file handler
    fh = RotatingFileHandler(log_file, maxBytes=2 * 1024 * 1024, backupCount=2)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logging.info(f"Logging to {log_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf_path", type=str, help="Path to input PDF")
    parser.add_argument(
        "--output_dir", type=str, help="Output directory (default: timestamped)"
    )
    parser.add_argument(
        "--test_mode",
        action="store_true",
        help="Use pre-generated JSON files for TOC and Topic Index",
    )
    parser.add_argument(
        "--detect_prefilled",
        action="store_true",
        help="Run only prefilled data detection on existing manifest/raw text",
    )
    parser.add_argument(
        "--skip_prefilled",
        action="store_true",
        help="Skip prefilled data detection step",
    )
    args = parser.parse_args()
    output_dir = (
        args.output_dir
        or f"debug_outputs/organizer_test/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)
    setup_logging(output_dir)
    logging.info("--- OrganizerExtractor Pipeline Started ---")
    logging.info(f"PDF: {args.pdf_path}")
    logging.info(f"Output dir: {output_dir}")
    extractor = OrganizerExtractor(pdf_path=args.pdf_path, output_dir=output_dir)
    if args.test_mode:
        logging.info(
            "[TEST MODE] Skipping all PDF/Vision extraction. Using cached JSONs only."
        )
        llm_toc_merged = extractor.merge_llm_toc_driven(test_mode=True)
        print(f"TOC-driven LLM output: {len(llm_toc_merged)} entries. Example:")
        print(llm_toc_merged[0] if len(llm_toc_merged) > 0 else "No entries.")
    else:
        logging.info("[LIVE MODE] Running full extraction pipeline.")
        extractor.extract()
        logging.info("[TOPIC INDEX] Extracting topic index pairs with Vision LLM...")
        pairs = extractor.extract_topic_index_pairs_vision()
        logging.info("[RAW TEXT] Extracting raw text per page...")
        extractor.extract_raw_text_per_page()
        logging.info("[LLM MERGE] Merging TOC and Topic Index with LLM...")
        llm_toc_merged = extractor.merge_llm_toc_driven()
        manifest_path = os.path.join(output_dir, "toc_llm_merged.json")
        raw_text_dir = output_dir
        detector = PrefilledDataDetector(manifest_path, raw_text_dir)
        logging.info("[PREFILLED] Running prefilled data detection step...")
        detector.detect()
        prefilled_manifest_path = manifest_path.replace(".json", "_with_prefilled.json")
        from dataextractai.parsers.organizer_vision_enhancer import (
            enhance_manifest_with_vision,
        )

        vision_output_path = os.path.join(output_dir, "toc_llm_merged_vision.json")
        # --- Robust PNG generation before Vision overlay ---
        with open(prefilled_manifest_path, "r") as f:
            manifest = json.load(f)
        missing_pngs = []
        for entry in manifest:
            page_num = entry.get("page_number")
            png_path = os.path.join(output_dir, f"page_{page_num}_full.png")
            if not os.path.exists(png_path):
                missing_pngs.append(page_num)
        if missing_pngs:
            from pdf2image import convert_from_path

            logging.info(
                f"[VISION][PNG] Generating {len(missing_pngs)} missing full-page PNGs..."
            )
            images = convert_from_path(args.pdf_path, dpi=300)
            for i, img in enumerate(images):
                png_path = os.path.join(output_dir, f"page_{i+1}_full.png")
                if (i + 1) in missing_pngs:
                    img.save(png_path)
            logging.info(f"[VISION][PNG] PNG generation complete.")
        # --- Vision overlay as before ---
        logging.info(
            f"[VISION] Enhancing manifest with Vision LLM: {prefilled_manifest_path} -> {vision_output_path}"
        )
        enhance_manifest_with_vision(prefilled_manifest_path, vision_output_path)
        logging.info(
            f"[VISION] Vision-enhanced manifest written to {vision_output_path}"
        )
        # Always use the vision-enhanced manifest as the final output
        final_manifest_path = vision_output_path
        logging.info(f"[FINAL] Final manifest for upstream: {final_manifest_path}")
    if args.detect_prefilled:
        # Only run prefilled detection on existing manifest/raw text
        manifest_path = os.path.join(output_dir, "toc_llm_merged.json")
        raw_text_dir = output_dir
        detector = PrefilledDataDetector(manifest_path, raw_text_dir)
        detector.detect()
        exit(0)
    if not args.skip_prefilled:
        manifest_path = os.path.join(output_dir, "toc_llm_merged.json")
        raw_text_dir = output_dir
        detector = PrefilledDataDetector(manifest_path, raw_text_dir)
        detector.detect()
    logging.info("--- OrganizerExtractor Pipeline Finished ---")
