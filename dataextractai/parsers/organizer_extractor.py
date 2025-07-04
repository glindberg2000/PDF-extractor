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
    OrganizerExtractor: Modular pipeline for extracting and linking Table of Contents (TOC), Topic Index, page thumbnails, and metadata from professional tax organizer PDFs (e.g., UltraTax, Lacerte, Drake).

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
                            # Debug: print type and attributes of item
                            print(
                                f"DEBUG: TOC item type: {type(item)}, attributes: {dir(item)}"
                            )
                            # Try to resolve page number
                            try:
                                # Use get_destination_page_number for Destination objects
                                page_num = reader.get_destination_page_number(item) + 1
                                # Debug: print resolved page_num
                                print(
                                    f"DEBUG: Resolved page_num for '{title}': {page_num}"
                                )
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


if __name__ == "__main__":
    # Demo: extract and split Topic Index columns for the sample PDF
    extractor = OrganizerExtractor(
        "data/_examples/workbooks/22I_VALENTI_T_Organizer_V1_13710.PDF",
        "debug_outputs/organizer_test",
    )
    col_paths = extractor.extract_topic_index_columns()
    if col_paths:
        print(f"Extracted Topic Index columns: {col_paths}")
        pairs = extractor.extract_topic_index_pairs()
        if pairs:
            print("Extracted form_code/description pairs:")
            for pair in pairs:
                print(pair)
        else:
            print("No pairs extracted from columns.")
    else:
        print("No Topic Index columns extracted.")

    pairs = extractor.extract_topic_index_pairs_vision()
    if pairs:
        print("Extracted form_code/description pairs (Vision API):")
        for pair in pairs:
            print(pair)
        print(f"Saved to: debug_outputs/organizer_test/topic_index_pairs_vision.json")
    else:
        print("No pairs extracted from columns (Vision API).")

    # Run the full pipeline
    extractor.extract()  # ensures TOC/pages/thumbnails
    pairs = extractor.extract_topic_index_pairs_vision()
    # Use new TOC-driven merge
    toc_driven = extractor.toc_driven_merge_with_topic_index()
    print(f"TOC-driven output: {len(toc_driven)} entries. Example:")
    print(toc_driven[0] if len(toc_driven) > 0 else "No entries.")
