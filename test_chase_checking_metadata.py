import os
import json
from dataextractai.parsers.chase_checking import ChaseCheckingParser

# If you have a dedicated account extractor, import and use it here
# from dataextractai.parsers.chase_checking import extract_account_number


def extract_account_number(text):
    match = re.search(r"\b\d{12,}\b", text)
    if match:
        return match.group(0)
    return None


def extract_name_and_address(first_page_text):
    skip_phrases = {
        "CUSTOMER SERVICE INFORMATION",
        "CHECKING SUMMARY",
        "TRANSACTION DETAIL",
    }
    customer_service_phrases = [
        "We accept operator relay calls",
        "International Calls",
        "Service Center:",
        "Para Espanol:",
        "1-713-262-1679",
        "1-888-262-4273",
    ]
    lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
    cleaned_lines = [re.sub(r"\s+", " ", l.replace("\xa0", " ")).strip() for l in lines]

    def strip_customer_service(line):
        for phrase in customer_service_phrases:
            line = line.replace(phrase, "")
        return line.strip()

    address = None
    address_idx = None
    for idx in range(len(cleaned_lines) - 1):
        street = cleaned_lines[idx]
        cityzip = cleaned_lines[idx + 1]
        if re.match(r"^\d+ .+", street) and re.search(r"\d{5}(-\d{4})?", cityzip):
            address = street + " " + cityzip
            address_idx = idx
            break
    all_caps_names = []
    if address_idx is not None:
        for l in cleaned_lines[max(0, address_idx - 10) : address_idx]:
            l_stripped = strip_customer_service(l)
            matches = re.findall(r"[A-Z][A-Z .,'-]{2,}", l_stripped)
            for m in matches:
                if m not in skip_phrases and len(m.split()) >= 2:
                    all_caps_names.append(m)
    name = " ".join(all_caps_names) if all_caps_names else None
    return name, address


def extract_statement_period(text):
    match = re.search(
        r"([A-Z][a-z]+ \d{1,2}, \d{4}) through ([A-Z][a-z]+ \d{1,2}, \d{4})", text
    )
    if match:
        return match.group(1), match.group(2)
    return None, None


def extract_statement_date_from_filename(filename):
    base = os.path.basename(filename)
    date_str = base.split("-")[0]
    if len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return None


def extract_metadata(pdf_path):
    reader = PdfReader(pdf_path)
    first_page = reader.pages[0].extract_text()
    all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    meta = {}
    meta["bank_name"] = "Chase"
    meta["account_type"] = "checking"
    meta["parser_name"] = "chase_checking"
    meta["file_type"] = "pdf"
    meta["account_number"] = extract_account_number(all_text)
    meta["statement_date"] = extract_statement_date_from_filename(pdf_path)
    name, address = extract_name_and_address(first_page)
    meta["account_holder_name"] = name
    meta["address"] = address
    period_start, period_end = extract_statement_period(first_page)
    meta["statement_period_start"] = period_start
    meta["statement_period_end"] = period_end
    return meta


def main():
    directory = "data/clients/chase_test/input/chase_checking"
    pdf_files = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(".pdf")
    ]
    parser = ChaseCheckingParser()
    for pdf_path in sorted(pdf_files):
        print(f"\n=== METADATA FOR: {pdf_path} ===")
        try:
            meta = parser.extract_metadata(pdf_path)
            print(json.dumps(meta, indent=2))
        except Exception as e:
            print(f"[ERROR] Failed to process {pdf_path}: {e}")


if __name__ == "__main__":
    main()
