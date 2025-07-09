import os
import json
import argparse
import hashlib
from dotenv import load_dotenv


# Helper to robustly detect user data (with exclude/include terms)
def detect_user_data(fields, exclude_terms=None, include_terms=None):
    user_keys = {
        "name",
        "address",
        "ssn",
        "social",
        "dob",
        "date of birth",
        "taxpayer",
        "spouse",
    }
    found = set()
    included_found = set()

    def search(d):
        if isinstance(d, dict):
            for k, v in d.items():
                v_str = str(v).strip().upper()
                if any(uk in k.lower() for uk in user_keys):
                    if exclude_terms and v_str in exclude_terms:
                        continue
                    found.add(k)
                if include_terms and any(inc in v_str for inc in include_terms):
                    included_found.add(v_str)
                search(v)
        elif isinstance(d, list):
            for v in d:
                search(v)

    search(fields)
    has_user_data = bool(found or included_found)
    return has_user_data, list(found), list(included_found)


def llm_summarize(page, openai_api_key, model):
    import openai

    prompt = f"""
You are a helpful assistant. Given the following extracted data from a tax organizer PDF page, provide:
1. A one-sentence summary of what this page contains (e.g., 'Signature page with taxpayer and preparer info, no user data detected').
2. Whether the page contains any user-specific or prefilled data (names, addresses, SSNs, etc). Respond as JSON with keys: summary, has_user_data.

Page number: {page['page_number']}
Label: {page.get('label')}
Data: {json.dumps(page.get('data', {}))}
"""
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        return result.get("summary", ""), result.get("has_user_data", False)
    except Exception as e:
        return None, None


def llm_file_summary(page_summaries, openai_api_key, model):
    import openai

    prompt = f"""
You are a helpful assistant. Given the following list of page summaries from a tax organizer PDF, provide:
1. A concise, high-level summary of the entire document, including what sections/pages are present, what is missing, and any notable findings.
2. If possible, list any detected user data or sensitive information.

Page summaries:
{json.dumps(page_summaries, indent=2)}
"""
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return None


def load_terms(path):
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return set(line.strip().upper() for line in f if line.strip())


def clean_extracted_fields(extracted_fields, label):
    # Consolidate and flatten extracted fields for client output
    data = {}
    # 1. Prefer Full_Page/value if present
    full_page = extracted_fields.get("Full_Page")
    if (
        isinstance(full_page, dict)
        and "value" in full_page
        and isinstance(full_page["value"], dict)
    ):
        data.update(full_page["value"])
    # 2. Add any other fields with a 'value' key, except label/crop/debug fields
    for k, v in extracted_fields.items():
        if k in ("Full_Page", "Form_Label", "Wide_Form_Label"):
            continue
        if isinstance(v, dict) and "value" in v:
            val = v["value"]
            if isinstance(val, dict) or isinstance(val, list):
                if val:
                    data[k] = val
            elif val not in (None, "", "{}", "None"):
                data[k] = val
        elif isinstance(v, (str, int, float)) and v not in (None, "", "{}", "None"):
            data[k] = v
    # 3. Add the best label as 'label' in data if not redundant
    # (skip: label is already at top level)
    return data


def compute_file_hash(pdf_path):
    BUF_SIZE = 65536
    sha256 = hashlib.sha256()
    try:
        with open(pdf_path, "rb") as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha256.update(data)
        return sha256.hexdigest()
    except Exception as e:
        print(f"[WARN] Could not compute file hash: {e}")
        return None


def clean_manifest(
    input_path,
    output_path,
    pdf_path=None,
    openai_api_key=None,
    openai_model_fast=None,
    openai_model_precise=None,
    exclude_terms_path=None,
    include_terms_path=None,
):
    """
    Clean and normalize an organizer manifest for client consumption.
    Adds file_hash, file_summary, and extracted_with at the top level.
    Args:
        input_path (str): Path to input manifest JSON.
        output_path (str): Path to output cleaned manifest JSON.
        pdf_path (str, optional): Path to the original PDF file (for hashing).
        openai_api_key (str, optional): OpenAI API key for LLM summaries.
        openai_model_fast (str, optional): Model name for LLM summaries.
        openai_model_precise (str, optional): Model name for high-quality file summary.
        exclude_terms_path (str, optional): Path to exclusion terms file.
        include_terms_path (str, optional): Path to inclusion terms file.
    Output manifest schema:
        {
            "file_hash": str,
            "file_summary": str or null,
            "pages": [
                {
                    "page_number": int,
                    "label": str,
                    "extracted_with": str,  # Provenance of extraction method
                    "pdf_page_file": str,
                    "thumbnail_file": str,
                    "raw_text_file": str,
                    "data": dict,
                    "summary": str,
                    "user_data_detected": bool
                },
                ...
            ]
        }
    """
    load_dotenv()
    if openai_api_key is None:
        openai_api_key = os.getenv("OPENAI_API_KEY")
    # Try OCR model first if present
    openai_model_ocr = os.getenv("OPENAI_MODEL_OCR")
    if openai_model_ocr:
        openai_model_fast = openai_model_ocr
        openai_model_precise = openai_model_ocr
    if openai_model_fast is None:
        openai_model_fast = os.getenv("OPENAI_MODEL_FAST", "gpt-4.1-mini")
    if openai_model_precise is None:
        openai_model_precise = os.getenv("OPENAI_MODEL_PRECISE", openai_model_fast)
    if exclude_terms_path is None:
        exclude_terms_path = os.path.join(
            os.path.dirname(__file__), "prefilled_exclude_terms.txt"
        )
    if include_terms_path is None:
        include_terms_path = os.path.join(
            os.path.dirname(__file__), "prefilled_include_terms.txt"
        )
    exclude_terms = load_terms(exclude_terms_path)
    include_terms = load_terms(include_terms_path)
    try:
        with open(input_path, "r") as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load input manifest: {e}")
        raise
    cleaned = []
    page_summaries = []
    for entry in manifest:
        data = clean_extracted_fields(
            entry.get("extracted_fields", {}), entry.get("label")
        )
        cleaned_page = {
            "page_number": entry.get("page_number"),
            "label": entry.get("label"),
            "Title": entry.get("Title"),
            "extracted_with": entry.get(
                "extracted_with"
            ),  # Add extraction method provenance
            "pdf_page_file": entry.get("pdf_page_file"),
            "thumbnail_file": entry.get("thumbnail_file"),
            "raw_text_file": entry.get("raw_text_file"),
            "data": data,
        }
        summary, has_user_data = None, None
        if openai_api_key:
            try:
                summary, has_user_data = llm_summarize(
                    cleaned_page, openai_api_key, openai_model_fast
                )
            except Exception as e:
                print(f"[LLM ERROR] Per-page summary failed: {e}")
        if summary is None:
            try:
                has_user_data, user_fields, included_found = detect_user_data(
                    data, exclude_terms=exclude_terms, include_terms=include_terms
                )
                summary = f"Page {cleaned_page['page_number']} ({cleaned_page.get('label','')}): "
                if has_user_data:
                    summary += f"Contains user data fields: {', '.join(user_fields)}."
                    if included_found:
                        summary += (
                            f" Included terms found: {', '.join(included_found)}."
                        )
                else:
                    summary += "No user data detected."
            except Exception as e:
                print(f"[ERROR] Rule-based summary failed: {e}")
                summary = "Summary unavailable."
                has_user_data = False
        cleaned_page["summary"] = summary
        cleaned_page["has_user_data"] = (
            has_user_data if has_user_data is not None else False
        )
        cleaned.append(cleaned_page)
        page_summaries.append(summary)
    # Compute file hash if pdf_path is provided
    file_hash = compute_file_hash(pdf_path) if pdf_path else None
    # Generate whole file summary using best available LLM
    file_summary = None
    if openai_api_key and page_summaries:
        try:
            file_summary = llm_file_summary(
                page_summaries, openai_api_key, openai_model_precise
            )
        except Exception as e:
            print(f"[LLM ERROR] File-level summary failed: {e}")
    output = {"file_hash": file_hash, "file_summary": file_summary, "pages": cleaned}
    try:
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(
            f"Cleaned manifest written to {output_path}. {len(cleaned)} pages processed."
        )
    except Exception as e:
        print(f"[ERROR] Failed to write cleaned manifest: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Clean and normalize an organizer manifest for client consumption. Adds file_hash and file_summary."
    )
    parser.add_argument("--input", required=True, help="Path to input manifest JSON")
    parser.add_argument(
        "--output", required=True, help="Path to output cleaned manifest JSON"
    )
    parser.add_argument(
        "--pdf", required=False, help="Path to original PDF file (for hashing)"
    )
    args = parser.parse_args()
    clean_manifest(args.input, args.output, pdf_path=args.pdf)


if __name__ == "__main__":
    main()
