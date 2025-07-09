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
import sys
from dataextractai.utils.ai import extract_structured_data_from_image
import re


# Helper to robustly detect garbage/empty label values
def is_garbage_label(val):
    if val is None:
        return True
    s = str(val).strip()
    if s in ("", "{}", "None"):
        return True
    # Match patterns like {"Form_Label": ''} or {"Wide_Form_Label": ''}
    import re

    if re.match(r"^\{\s*'\w+_?\w*'\s*:\s*''\s*\}$", s):
        return True
    return False


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
                pages_info.append(
                    {
                        "page_number": i + 1,
                        "pdf_path": page_pdf_path,
                        # We'll add png_path, thumbnail_path, and raw_text_file below
                    }
                )
        except Exception as e:
            self.errors.append(f"Page splitting failed: {e}")
        return pages_info

    def generate_thumbnails_and_images(self, pages_info: List[Dict[str, Any]]):
        try:
            images = convert_from_path(self.pdf_path, dpi=self.thumbnail_dpi)
            for i, image in enumerate(images):
                thumb_path = os.path.join(self.output_dir, f"thumb_{i+1}.png")
                png_path = os.path.join(self.output_dir, f"page_{i+1}.png")
                image.save(thumb_path, "PNG")
                image.save(png_path, "PNG")
                pages_info[i]["thumbnail_path"] = thumb_path
                pages_info[i]["png_path"] = png_path
        except Exception as e:
            self.warnings.append(f"Thumbnail/image generation failed: {e}")

    def extract_raw_text_per_page(self, pages_info: List[Dict[str, Any]]):
        from PyPDF2 import PdfReader

        reader = PdfReader(self.pdf_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            fname = f"page_{i+1}.txt"
            fpath = os.path.join(self.output_dir, fname)
            with open(fpath, "w") as f:
                f.write(text)
            pages_info[i]["raw_text_file"] = fpath
        logging.info(f"Extracted raw text for {len(pages_info)} pages.")

    def write_toc_inventory(self, toc, path=None):
        """Write the TOC inventory as valid JSON (no debug output)."""
        if path is None:
            path = os.path.join(self.output_dir, "toc_inventory.json")
        with open(path, "w") as f:
            json.dump(toc, f, indent=2)

    def extract(self) -> Dict[str, Any]:
        """
        Run the full extraction pipeline for a tax organizer PDF.
        This will:
        - Extract the TOC and per-page info
        - Generate thumbnails and raw text
        - Write a TOC inventory JSON
        - Run the all-fields manifest extraction (with LLM/vision extraction)
        - Always produce both a raw manifest (all_fields_manifest.json) and a cleaned manifest (all_fields_manifest_cleaned.json) in the output directory
        - Return the cleaned manifest path as part of the result

        Usage:
            extractor = OrganizerExtractor(pdf_path, output_dir)
            result = extractor.extract()
            print("Cleaned manifest at:", result["cleaned_manifest_path"])
        """
        toc = self.extract_toc()
        pages_info = self.split_pages()
        self.generate_thumbnails_and_images(pages_info)
        self.extract_raw_text_per_page(pages_info)
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
        # --- Always run the all-fields manifest extraction and cleaning step ---
        manifest_result = self.extract_all_fields_manifest()
        cleaned_manifest_path = os.path.join(
            self.output_dir, "all_fields_manifest_cleaned.json"
        )
        return {
            "toc": toc,
            "pages": pages_info,
            "errors": self.errors,
            "warnings": self.warnings,
            "cleaned_manifest_path": cleaned_manifest_path,
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
            extracted_fields = (
                {}
            )  # Always initialize at the top of the loop to avoid NameError
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

    def extract_all_fields_manifest(self, config_path=None, page_numbers=None):
        """
        Robustly extract all fields for each page using fallback logic:
        1. Try narrow crop (Vision LLM)
        2. If no config match, try wide crop (Vision LLM)
        3. If still no match, try raw PDF text (for special pages)
        For standard forms, map label through gold standard to get form ID.
        For special pages, match unique phrases in raw text.
        Log which fallback was used.
        Only process the specified page_numbers if provided.
        Handles split-column (Form 1) logic for correct extraction.
        Supports config-driven prompt_override and unique_search_key for robust fallback.
        """
        import json
        from dataextractai.utils.ai import extract_structured_data_from_image
        from PIL import Image
        import os

        # Always extract raw text for all pages before processing
        print("[DEBUG] Extracting raw PDF text for all pages...")
        self.extract_raw_text_per_page(self.split_pages())
        print("[DEBUG] Raw PDF text extraction complete.")

        # Load config
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "special_page_configs.json"
            )
        with open(config_path, "r") as f:
            config = json.load(f)
        default_fields = config.get("default", {})
        label_crop = default_fields.get("Form_Label", {}).get("crop")
        # Use Wide_Form_Label if present
        wide_label_crop = None
        if config["default"].get("Wide_Form_Label"):
            wide_label_crop = config["default"]["Wide_Form_Label"]["crop"]
        pages_info = self.split_pages()
        self.generate_thumbnails_and_images(pages_info)
        self.extract_raw_text_per_page(pages_info)
        # Now filter pages_info if page_numbers is provided
        if page_numbers is not None:
            page_numbers_set = set(page_numbers)
            pages_info = [p for p in pages_info if p["page_number"] in page_numbers_set]
        manifest = []
        for page in pages_info:
            print(
                f"[DEBUG] Page {page['page_number']}: initial state: label=None, label_source=None, extraction_method=None"
            )
            extracted_fields = (
                {}
            )  # Always initialize at the top of the loop to avoid NameError
            page_number = page["page_number"]
            page_image_path = page.get("png_path") or page.get("thumbnail_file")
            if not page_image_path:
                print(
                    f"[WARNING] Page {page_number}: No 'png_path' or 'thumbnail_file' found in page dict. Skipping image-based extraction for this page."
                )
            raw_text = page.get("raw_text", "")
            label = None
            label_source = None
            crop_used = None
            crop_img_path = None
            wide_crop_img_path = None
            config_key = None
            prompt_override = None
            extraction_method = None  # <-- New field for user-friendly provenance
            # 1. Try default (narrow) crop
            if label_crop:
                img = Image.open(page_image_path)
                w, h = img.size
                left = int(label_crop["left"] * w)
                right = int(label_crop["right"] * w)
                top = int(label_crop["top"] * h)
                bottom = int(label_crop["bottom"] * h)
                crop_img = img.crop((left, top, right, bottom))
                crop_img_path = os.path.join(
                    self.output_dir, f"label_narrow_page_{page_number}.png"
                )
                crop_img.save(crop_img_path)
                try:
                    result = extract_structured_data_from_image(
                        crop_img_path, "Extract the Form_Label from this region."
                    )
                    label = result.get("Form_Label") or str(result)
                    print(f"[DEBUG] Page {page_number}: label set to: {label}")
                    if label and label.strip():
                        label_source = "Form_Label (narrow)"
                        crop_used = "Form_Label"
                    else:
                        label = None
                except Exception as e:
                    print(
                        f"[LABEL EXTRACTION] Vision LLM (narrow) failed for page {page_number}: {e}"
                    )
            # 2. If not found, try wide crop if available
            if (not label or not label.strip()) and wide_label_crop:
                left = int(wide_label_crop["left"] * w)
                right = int(wide_label_crop["right"] * w)
                top = int(wide_label_crop["top"] * h)
                bottom = int(wide_label_crop["bottom"] * h)
                wide_crop_img = img.crop((left, top, right, bottom))
                wide_crop_img_path = os.path.join(
                    self.output_dir, f"label_wide_page_{page_number}.png"
                )
                wide_crop_img.save(wide_crop_img_path)
                try:
                    result = extract_structured_data_from_image(
                        wide_crop_img_path, "Extract the Form_Label from this region."
                    )
                    label = result.get("Form_Label") or str(result)
                    if label and label.strip():
                        label_source = "Wide_Form_Label (wide)"
                        crop_used = "Wide_Form_Label"
                    else:
                        label = None
                except Exception as e:
                    print(
                        f"[LABEL EXTRACTION] Vision LLM (wide) failed for page {page_number}: {e}"
                    )
            # 3. If still not found, scan raw text for unique_search_key from config
            print(
                f"[DEBUG] Page {page_number}: label before fallback check: {label!r} (type: {type(label)})"
            )
            # PATCH: Always run search key fallback if label is None, empty, or not a valid config key
            if not label or not str(label).strip() or str(label).strip() not in config:
                print(
                    f"[DEBUG] Page {page_number}: Entering search key fallback block (label: {label!r})"
                )
                # Try all config sections with unique_search_key
                raw_text_path = os.path.join(self.output_dir, f"page_{page_number}.txt")
                raw_text = ""
                if os.path.exists(raw_text_path):
                    with open(raw_text_path, "r") as f:
                        raw_text = f.read()
                # Normalize raw text for matching
                raw_text_normalized = (
                    raw_text.replace("\n", "").replace("\r", "").strip().lower()
                )
                for key, entry in config.items():
                    if isinstance(entry, dict) and entry.get("unique_search_key"):
                        search_key = (
                            entry["unique_search_key"]
                            .replace("\n", "")
                            .replace("\r", "")
                            .strip()
                            .lower()
                        )
                        print(
                            f"[DEBUG] Page {page_number}: Comparing search_key '{search_key}' to raw_text_normalized (first 200 chars): '{raw_text_normalized[:200]}'"
                        )
                        if search_key in raw_text_normalized:
                            config_key = key
                            prompt_override = entry.get("prompt_override")
                            print(
                                f"[DEBUG] Page {page_number}: unique_search_key '{entry['unique_search_key']}' matched in raw text. Using config_key: {config_key}"
                            )
                            extraction_method = "Text Only"  # Fallback to text search
                            break
                        else:
                            print(
                                f"[DEBUG] Page {page_number}: unique_search_key '{entry['unique_search_key']}' NOT found in raw text."
                            )
                # If still not set, mark as config fallback
                if extraction_method is None:
                    extraction_method = "Config Fallback"
            # After search key fallback, inject label and label_source if config_key was found and label is empty/garbage
            garbage_labels = [None, "", "{}", "None", "{'Form_Label': ''"]
            if is_garbage_label(label) and config_key:
                label = config_key
                label_source = "config_fallback"
            # 4. Use 'Title' for display, but config_key for lookup
            title_for_manifest = config.get(label, {}).get("Title") or label
            # Log which crop was used
            print(
                f"[INFO] Page {page_number}: Label extracted using {label_source} ({crop_used} crop): {label}"
            )
            print(
                f"[DEBUG] Page {page_number}: config_key={config_key}, form_code={label if label and label in config else config_key}, title_for_manifest={title_for_manifest}"
            )
            # Determine form_code: prefer label if in config, else use config_key, else default
            form_code = None
            if label and label in config:
                form_code = label
                prompt_override = (
                    config[label].get("prompt_override")
                    if config[label].get("prompt_override")
                    else prompt_override
                )
            elif config_key:
                form_code = config_key
            page_config = (
                config.get(form_code)
                if form_code and form_code in config
                else default_fields
            )
            if page_config is default_fields:
                print(
                    f"[DEBUG] Page {page_number}: Falling back to default_fields for extraction."
                )
            print(
                f"[DEBUG] Page {page_number}: Fields to process: {list(page_config.keys())}"
            )
            for field, field_info in page_config.items():
                # Only process fields where field_info is a dict and has a 'method' key
                if not isinstance(field_info, dict) or "method" not in field_info:
                    continue
                method = field_info.get("method")
                split_column = field_info.get("split_column", False)
                crop_left = field_info.get("crop_left")
                crop_right = field_info.get("crop_right")
                crop = field_info.get("crop")
                field_prompt_override = (
                    field_info.get("prompt_override") or prompt_override
                )
                # --- Special handling for Cover and Signature pages: full page extraction ---
                if (
                    form_code in ("Cover_Sheet", "Signature_Page")
                    and field == "Full_Page"
                ):
                    from PIL import Image

                    img = Image.open(page_image_path)
                    full_img_path = os.path.join(
                        self.output_dir, f"full_page_{page_number}.png"
                    )
                    img.save(full_img_path)
                    # Try to load raw PDF text for this page
                    raw_text_path = os.path.join(
                        self.output_dir, f"page_{page_number}.txt"
                    )
                    raw_text = ""
                    if os.path.exists(raw_text_path):
                        with open(raw_text_path, "r") as f:
                            raw_text = f.read()
                    prompt = field_prompt_override or (
                        "Extract all fields/regions from this tax organizer cover/signature page. "
                        "If helpful, use the following raw PDF text as context: "
                        + raw_text
                    )
                    try:
                        result = extract_structured_data_from_image(
                            full_img_path, prompt
                        )
                        llm_response_path = os.path.join(
                            self.output_dir,
                            f"field_{field}_page_{page_number}_llm_response.json",
                        )
                        with open(llm_response_path, "w") as f:
                            json.dump(result, f, indent=2)
                        print(f"[LLM RESPONSE] {llm_response_path}: {result}")
                        extracted_fields[field] = {
                            "value": result,
                            "source": "vision_llm_full_page",
                            "full_img": full_img_path,
                        }
                    except Exception as e:
                        print(
                            f"[LLM ERROR] {field} page {page_number} (full page): {e}"
                        )
                        extracted_fields[field] = {
                            "value": None,
                            "source": "vision_llm_full_page_failed",
                            "full_img": full_img_path,
                            "error": str(e),
                        }
                    continue
                # --- Split-column aggregation fix ---
                if split_column and crop_left and crop_right:
                    all_col_results = []
                    for col_idx, col_crop in enumerate([crop_left, crop_right]):
                        l = int(col_crop["left"] * w)
                        r = int(col_crop["right"] * w)
                        t = int(col_crop["top"] * h)
                        b = int(col_crop["bottom"] * h)
                        col_img = img.crop((l, t, r, b))
                        col_img_path = os.path.join(
                            self.output_dir,
                            f"field_{field}_page_{page_number}_col{col_idx+1}.png",
                        )
                        col_img.save(col_img_path)
                        try:
                            prompt = field_prompt_override or (
                                "Extract all {description, value} pairs from this column of a split-column tax organizer form. "
                                "Return as a list of objects with keys 'description' and 'value'. Ignore empty or header rows."
                            )
                            result = extract_structured_data_from_image(
                                col_img_path, prompt
                            )
                            llm_response_path = os.path.join(
                                self.output_dir,
                                f"field_{field}_page_{page_number}_col{col_idx+1}_llm_response.json",
                            )
                            with open(llm_response_path, "w") as f:
                                json.dump(result, f, indent=2)
                            print(f"[LLM RESPONSE] {llm_response_path}: {result}")
                            # Accept either a list or dict with 'data' key
                            col_values = (
                                result.get("data")
                                if isinstance(result, dict) and "data" in result
                                else result
                            )
                            if isinstance(col_values, list):
                                all_col_results.extend(col_values)
                            elif isinstance(col_values, dict):
                                all_col_results.append(col_values)
                        except Exception as e:
                            print(
                                f"[LLM ERROR] {field} page {page_number} col {col_idx+1}: {e}"
                            )
                    # Aggregate both columns into a single list under 'data'
                    extracted_fields[field] = {
                        "data": all_col_results,
                        "source": "vision_llm_split_column",
                        "columns": 2,
                    }
                    continue
                # --- Standard extraction for all other fields ---
                if method == "vision" and crop:
                    left = int(crop["left"] * w)
                    right = int(crop["right"] * w)
                    top = int(crop["top"] * h)
                    bottom = int(crop["bottom"] * h)
                    field_crop_img = img.crop((left, top, right, bottom))
                    field_crop_img_path = os.path.join(
                        self.output_dir, f"field_{field}_page_{page_number}.png"
                    )
                    field_crop_img.save(field_crop_img_path)
                    # Save raw OCR text for debug
                    try:
                        import pytesseract

                        ocr_text = pytesseract.image_to_string(field_crop_img)
                        ocr_txt_path = field_crop_img_path.replace(".png", "_ocr.txt")
                        with open(ocr_txt_path, "w") as f:
                            f.write(ocr_text)
                        print(f"[DEBUG] Saved OCR text to {ocr_txt_path}")
                    except Exception as e:
                        print(f"[WARN] Could not save OCR text: {e}")
                    prompt = (
                        field_prompt_override
                        or f"Extract the {field} from this region."
                    )
                    print(
                        f"[DEBUG] Sending PNG to Vision LLM: {field_crop_img_path} with prompt: {prompt}"
                    )
                    try:
                        result = extract_structured_data_from_image(
                            field_crop_img_path, prompt
                        )
                        llm_response_path = os.path.join(
                            self.output_dir,
                            f"field_{field}_page_{page_number}_llm_response.json",
                        )
                        with open(llm_response_path, "w") as f:
                            json.dump(result, f, indent=2)
                        print(f"[LLM RESPONSE] {llm_response_path}: {result}")
                        # Patch: Always use native JSON object if possible
                        value = result.get(field)
                        if value is None:
                            # If result itself is a dict or list, use it directly
                            if isinstance(result, (dict, list)):
                                value = result
                            else:
                                value = str(result)
                        extracted_fields[field] = {
                            "value": value,
                            "source": "vision_llm",
                            "crop": crop,
                            "crop_img": field_crop_img_path,
                        }
                    except Exception as e:
                        print(f"[LLM ERROR] {field} page {page_number}: {e}")
                        extracted_fields[field] = {
                            "value": None,
                            "source": "vision_llm_failed",
                            "crop": crop,
                            "crop_img": field_crop_img_path,
                            "error": str(e),
                        }
            if not extracted_fields or (
                isinstance(extracted_fields, dict)
                and all(not v for v in extracted_fields.values())
            ):
                print(
                    f"[WARN] No extracted fields for page {page_number} (label={label})"
                )
            # Add file name fields for manifest (do not change any other logic)
            pdf_page_file = os.path.basename(
                os.path.join(self.output_dir, f"page_{page_number}.pdf")
            )
            thumbnail_file = os.path.basename(page_image_path)
            raw_text_file = os.path.basename(
                os.path.join(self.output_dir, f"page_{page_number}.txt")
            )
            # After label is set, set extraction_method for region-based extraction
            if label_source == "Form_Label (narrow)":
                extraction_method = "Regions + Text"
                print(
                    f"[DEBUG] Page {page_number}: extraction_method set to 'Regions + Text' due to region-based extraction."
                )
            # If extraction_method is still None, set to 'Extraction Method Unknown'
            if extraction_method is None:
                extraction_method = "Extraction Method Unknown"
                print(
                    f"[DEBUG] Page {page_number}: extraction_method was None, set to 'Extraction Method Unknown'."
                )
            # Print extraction_method for debug
            print(
                f"[DEBUG] Page {page_number}: extraction_method before manifest append: {extraction_method}"
            )
            manifest.append(
                {
                    "page_number": page_number,
                    "label": label,
                    "label_source": label_source,
                    "label_crop_img": crop_img_path,
                    "Title": title_for_manifest,
                    "extracted_fields": extracted_fields,
                    "pdf_page_file": pdf_page_file,
                    "thumbnail_file": thumbnail_file,
                    "raw_text_file": raw_text_file,
                    "extracted_with": extraction_method,
                }
            )
        # Save manifest
        manifest_path = os.path.join(self.output_dir, "all_fields_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"[DONE] Saved all-fields manifest to {manifest_path}")
        # --- Built-in cleaning step: always run after manifest generation ---
        try:
            from dataextractai.parsers.clean_manifest import clean_manifest

            cleaned_manifest_path = os.path.join(
                self.output_dir, "all_fields_manifest_cleaned.json"
            )
            clean_manifest(
                input_path=manifest_path,
                output_path=cleaned_manifest_path,
                pdf_path=self.pdf_path,
            )
            print(f"[DONE] Cleaned manifest written to {cleaned_manifest_path}")
        except Exception as e:
            print(f"[ERROR] Cleaning step failed: {e}")
        # NOTE: Only Python scripts should be committed to git. Do NOT commit debug_outputs/ or JSON output files.


class PrefilledDataDetector:
    """
    Detects prefilled/user data on each page using LLMs. Can be run as part of the pipeline or standalone.
    Supports exclusion of false positive terms via a config file (dataextractai/parsers/prefilled_exclude_terms.txt).
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
        self.model_env_keys = model_env_keys
        # Always use the new path
        self.exclude_terms_path = exclude_terms_path or os.path.join(
            os.path.dirname(__file__), "prefilled_exclude_terms.txt"
        )
        load_dotenv()
        self.models = [os.getenv(k) for k in self.model_env_keys if os.getenv(k)]
        if not self.models:
            raise RuntimeError("No LLM models found in .env for prefilled detection.")
        # Load exclusion terms from file
        try:
            with open(self.exclude_terms_path, "r") as f:
                self.exclude_terms = set(
                    line.strip().lower() for line in f if line.strip()
                )
        except Exception:
            self.exclude_terms = set()

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


def fail_fast_env_check():
    required_envs = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL_OCR",
        "OPENAI_MODEL_FAST",
        "OPENAI_MODEL_PRECISE",
    ]
    missing = [k for k in required_envs if not os.getenv(k)]
    if missing:
        print(
            f"[FATAL] Missing required environment variables: {', '.join(missing)}.\nCheck your .env file and model configuration."
        )
        sys.exit(1)
    print("[CHECK] All required environment variables are set.")
    print(
        f"[MODELS] OCR: {os.getenv('OPENAI_MODEL_OCR')}, FAST: {os.getenv('OPENAI_MODEL_FAST')}, PRECISE: {os.getenv('OPENAI_MODEL_PRECISE')}"
    )
    sys.stdout.flush()


def extract_labels_for_all_pages(pdf_path, config, output_dir):
    """
    For a given PDF, split to pages and extract the label for every page using the default Form_Label crop.
    Save the crop image and log the result for every page.
    Returns a list of dicts: [{page_number, label, crop_img_path, ...}]
    """
    import os
    import logging
    from pdf2image import convert_from_path
    from dataextractai.utils.ai import extract_structured_data_from_image
    from PIL import Image

    os.makedirs(os.path.join(output_dir, "crops"), exist_ok=True)
    images = convert_from_path(pdf_path, dpi=300)
    results = []
    for i, img in enumerate(images, 1):
        crop = config["default"]["Form_Label"]["crop"]
        w, h = img.size
        left = int(crop["left"] * w)
        right = int(crop["right"] * w)
        top = int(crop["top"] * h)
        bottom = int(crop["bottom"] * h)
        crop_img = img.crop((left, top, right, bottom))
        crop_img_path = os.path.join(output_dir, "crops", f"page_{i}_Form_Label.png")
        crop_img.save(crop_img_path)
        prompt = "Extract the Form_Label from this region."
        result = extract_structured_data_from_image(crop_img_path, prompt)
        logging.info(
            f"[LABEL EXTRACTION] Page {i}: label='{result.get('Form_Label')}' | crop={crop} | img={crop_img_path}"
        )
        results.append(
            {
                "page_number": i,
                "label": result.get("Form_Label"),
                "crop_img_path": crop_img_path,
                "crop": crop,
            }
        )
    return results


if __name__ == "__main__":
    load_dotenv()
    fail_fast_env_check()
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--extract_all_fields_manifest", action="store_true")
    parser.add_argument(
        "--page", type=int, help="Process only this page number (1-based)"
    )
    parser.add_argument(
        "--pages", type=str, help="Comma-separated list of page numbers to process"
    )
    args = parser.parse_args()
    output_dir = (
        args.output_dir
        or f"debug_outputs/organizer_test/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    os.makedirs(output_dir, exist_ok=True)
    setup_logging(output_dir)
    logging.info("--- OrganizerExtractor Label Extraction Only ---")
    logging.info(f"PDF: {args.pdf_path}")
    logging.info(f"Output dir: {output_dir}")
    # Load config
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), "special_page_configs.json")
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    if args.extract_all_fields_manifest:
        page_numbers = None
        if args.page:
            page_numbers = [args.page]
        elif args.pages:
            page_numbers = [int(x) for x in args.pages.split(",") if x.strip()]
        extractor = OrganizerExtractor(args.pdf_path, args.output_dir)
        extractor.extract_all_fields_manifest(page_numbers=page_numbers)
        exit(0)
    # Run label extraction for all pages
    label_results = extract_labels_for_all_pages(args.pdf_path, config, output_dir)
    for res in label_results:
        logging.info(
            f"[LABEL RESULT] Page {res['page_number']}: label='{res['label']}' | crop_img={res['crop_img_path']}"
        )
    logging.info("--- Label Extraction Complete ---")
    # (Skip legacy extraction for this test run)
    extractor = OrganizerExtractor(args.pdf_path, args.output_dir)
    extractor.extract()  # fallback to original pipeline

from dataextractai.parsers_core.registry import ParserRegistry

ParserRegistry.register_parser("organizer_extractor", OrganizerExtractor)
