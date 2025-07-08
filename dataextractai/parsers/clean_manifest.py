import os
import json
import argparse
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input manifest JSON")
    parser.add_argument(
        "--output", required=True, help="Path to output cleaned manifest JSON"
    )
    args = parser.parse_args()

    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model_fast = os.getenv("OPENAI_MODEL_FAST", "gpt-4.1-mini")

    exclude_terms = load_terms(
        os.path.join(os.path.dirname(__file__), "prefilled_exclude_terms.txt")
    )
    include_terms = load_terms(
        os.path.join(os.path.dirname(__file__), "prefilled_include_terms.txt")
    )

    with open(args.input, "r") as f:
        manifest = json.load(f)

    cleaned = []
    for entry in manifest:
        # Clean and flatten extracted fields
        data = clean_extracted_fields(
            entry.get("extracted_fields", {}), entry.get("label")
        )
        cleaned_entry = {
            "page_number": entry.get("page_number"),
            "label": entry.get("label"),
            "pdf_page_file": entry.get("pdf_page_file"),
            "thumbnail_file": entry.get("thumbnail_file"),
            "raw_text_file": entry.get("raw_text_file"),
            "data": data,
        }
        # Try LLM summary
        summary, has_user_data = None, None
        if openai_api_key:
            summary, has_user_data = llm_summarize(
                cleaned_entry, openai_api_key, openai_model_fast
            )
        # Fallback if LLM fails
        if summary is None:
            has_user_data, user_fields, included_found = detect_user_data(
                data,
                exclude_terms=exclude_terms,
                include_terms=include_terms,
            )
            summary = f"Page {cleaned_entry['page_number']} ({cleaned_entry.get('label','')}): "
            if has_user_data:
                summary += f"Contains user data fields: {', '.join(user_fields)}."
                if included_found:
                    summary += f" Included terms found: {', '.join(included_found)}."
            else:
                summary += "No user data detected."
        cleaned_entry["summary"] = summary
        cleaned_entry["has_user_data"] = (
            has_user_data if has_user_data is not None else False
        )
        cleaned.append(cleaned_entry)

    with open(args.output, "w") as f:
        json.dump(cleaned, f, indent=2)
    print(f"Cleaned manifest written to {args.output}. {len(cleaned)} pages processed.")


if __name__ == "__main__":
    main()
