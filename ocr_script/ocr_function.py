import re
from PIL import Image
import pytesseract
import os

# Configure pytesseract with the correct path
pytesseract.pytesseract.tesseract_cmd = "E:\\Aditya\\tesseract.exe"


def extract_text_from_image(image_path):
    """
    Opens an image and extracts text using pytesseract OCR.
    """
    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"Error opening image {image_path}: {e}")
        return ""
    text = pytesseract.image_to_string(image)
    return text


def extract_test_result_from_line(line):
    """
    Tokenizes a candidate test line and returns a tuple (test_name, test_value)
    by taking the first token that resembles a numeric value.
    Commas are removed so that numbers like "5,100" become "5100".
    If no valid numeric token is found, returns None.
    """
    tokens = line.split()
    for i, token in enumerate(tokens):
        token_norm = token.strip(",:;").replace(",", "")
        token_norm = re.sub(r'^[‘"“”\']+', "", token_norm)
        token_clean = re.sub(r"[^\d\.<>]", "", token_norm)
        if re.fullmatch(r"[<>]?\d+(?:\.\d+)?", token_clean):
            test_value = token_clean
            test_name = " ".join(tokens[:i]).strip()
            test_name = re.sub(r'^[‘"“”\']+', "", test_name).rstrip(" ,.:")
            if test_name.lower() in {"male", "female", "males", "females"}:
                return None
            return test_name, test_value
    return None


def extract_age_sex(text):
    """
    Attempts to extract age and sex from the full report text.
    It first uses combined patterns (such as:
      "SEX/ AGE: MALE /23", "Age/Sex :27YRS/M", or
      "Age 2y10m26d Sex. Female") so that the full age string is returned.
    If combined patterns fail, it then scans line-by-line and finally uses
    separate full-text lookups.
    """
    age, sex = None, None
    # Pattern 1: "SEX/ AGE: MALE /23"
    m = re.search(r"SEX\s*/\s*AGE\s*(?:[:=])?\s*(Male|Female)\s*/\s*(\d+)",
                  text, re.IGNORECASE)
    if m:
        sex = m.group(1).strip().title()
        age = m.group(2).strip()
        return age, sex
    # Pattern 2: "Age/Sex :27YRS/M" or "Age/Gender :20/Male"
    m = re.search(r"Age(?:/Gender|/Sex)\s*(?:[:=])?\s*([^\n]+?)\s*/\s*([MF]|Male|Female)",
                  text, re.IGNORECASE)
    if m:
        age_raw = m.group(1).strip()
        if re.search(r"[A-Za-z]", age_raw):
            age = age_raw
        else:
            num = re.search(r"(\d+)", age_raw)
            age = num.group(1) if num else age_raw
        grp = m.group(2).strip()
        if grp.upper() in {"M", "MALE"}:
            sex = "Male"
        elif grp.upper() in {"F", "FEMALE"}:
            sex = "Female"
        return age, sex
    # Pattern 3: Using positive lookahead e.g. "Age 2y10m26d Sex. Female"
    m = re.search(r"Age\s*(?:[:=])?\s*(?P<age>[^\n]+?)(?=\s+Sex[.:]?\s+(?P<sex>Male|Female))",
                  text, re.IGNORECASE)
    if m:
        age = m.group("age").strip()
        sex = m.group("sex").strip().title()
        return age, sex
    # Fallback: Line-by-line scan.
    for line in text.splitlines():
        line = line.strip()
        m_age = re.search(r"Age\s*(?:[:=])?\s*([^\n]+)", line, re.IGNORECASE)
        m_sex = re.search(r"(Sex|Gender)\s*(?:[:=])?\s*(Male|Female)", line, re.IGNORECASE)
        if m_age and m_sex:
            age_str = m_age.group(1).strip()
            if re.search(r"[A-Za-z]", age_str):
                age = age_str.split("\n")[0].strip()
            else:
                num = re.search(r"(\d+)", age_str)
                age = num.group(1) if num else age_str
            sex = m_sex.group(2).strip().title()
            return age, sex
    # Final fallback: Separate full-text lookup.
    m = re.search(r"Age\s*(?:[:=])?\s*([\dA-Za-z\s\-]+)", text, re.IGNORECASE)
    if m:
        age_str = m.group(1).strip()
        if "\n" in age_str:
            age_str = age_str.split("\n")[0].strip()
        if re.search(r"[A-Za-z]", age_str):
            age = age_str
        else:
            num = re.search(r"(\d+)", age_str)
            age = num.group(1) if num else age_str
    m = re.search(r"(Sex|Gender)\s*(?:[:=])?\s*(Male|Female)", text, re.IGNORECASE)
    if m:
        sex = m.group(2).strip().title()
    return age, sex


def parse_lab_report(text):
    """
    Parses the full lab report text to extract patient details (registration number, name,
    age, sex) and test results from the CBC section.
    """
    data = {}
    # Preprocess text: Normalize smart quotes.
    text = text.replace("‘", " ").replace("’", " ")
    text = text.replace("“", "\"").replace("”", "\"")

    # Registration Number Extraction
    reg_num = None
    reg_patterns = [
        r"PUID\s+(\S+)",
        r"Regd\.?\s*No\.?\s*[:\-]?\s*(\S+)",
        r"Reg\.?\s*no\.?\s*(\S+)",
        r"UHID\s*[:\-]?\s*(\S+)",
        r"Patient\s*ID\s*[:\-]?\s*(\S+)",
        r"PID\s*[.:]?\s*(\S+)",
        r"Patient\s+Code\s*[:\-]?\s*(\S+)"
    ]
    for pat in reg_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if (("Regd" in pat or re.search(r"Reg\.?\s*no\.?", pat, re.IGNORECASE))
                    and not candidate.isdigit()):
                continue
            reg_num = candidate
            break
    data["registration_no"] = reg_num

    # Patient Name Extraction
    name = None
    # (1) Look for "PATIENT NAME : <NAME>" ending before "SEX" or "Age"
    m = re.search(r"PATIENT\s+NAME\s*[:=-]+\s*(.*?)\s+(?:SEX|Age)",
                  text, re.IGNORECASE | re.DOTALL)
    if m:
        name = m.group(1).strip()
        name = re.split(r"\s+PUID\s+", name, flags=re.IGNORECASE)[0].strip()
    # (2) Look for a line starting with "NAME:" that stops at "Patient ID"
    if not name:
        m = re.search(r"NAME\s*:\s*([A-Za-z\s,]+)(?:\s+Patient\s+ID\b|$)",
                      text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
    # (3) Look for a line ending with "Sample Collected By"
    if not name:
        m = re.search(r"^(?P<name>[A-Za-z][A-Za-z\s,]+?)\s+Sample Collected By",
                      text, re.IGNORECASE | re.MULTILINE)
        if m:
            name = m.group("name").strip()
    # (4) Look for "Name : <NAME> Patient ID" pattern
    if not name:
        m = re.search(r"Name\s*[:\-]?\s*([\w\.\s,]+?)\s+Patient\s+ID",
                      text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
    # (5) Generic fallback: use any "Name:" pattern.
    if not name:
        m = re.search(r"Name\s*[:\-]?\s*([A-Za-z\.,\s]+)",
                      text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            name = re.split(r"\s+(Patient|Age)", candidate, flags=re.IGNORECASE)[0].strip()
    # (6) Use the line immediately preceding an "Age" field.
    if not name:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"Age\s*(?:[:=])", line, re.IGNORECASE) and i > 0:
                candidate = lines[i - 1].strip()
                candidate = re.sub(r"^Name\s+", "", candidate, flags=re.IGNORECASE).strip()
                if candidate and not re.search(
                        r"(Registered on|Sample Collected|UHID|Investigation|Complete Blood Count)",
                        candidate, re.IGNORECASE):
                    name = candidate
                    break
    # (7) Last resort: Title-based fallback.
    if not name:
        m = re.search(r"^(Mr\.|Mrs\.|Ms\.)\s+([A-Za-z\s,]+)",
                      text, re.IGNORECASE | re.MULTILINE)
        if m:
            name = f"{m.group(1)} {m.group(2)}".strip()
    if name and "PUID" in name:
        name = name.split("PUID")[0].strip()
    data["name"] = name

    # Age and Sex Extraction
    age, sex = extract_age_sex(text)
    if age and "\n" in age:
        age = age.split("\n")[0].strip()
    data["age"] = age
    data["sex"] = sex

    # Test Results Extraction
    tests = {}
    lines = text.splitlines()
    header_candidates = [
        r"COMPLETE\s+BLOOD\s+COUNT", r"\bCBC\b", r"\bTEST\b", r"\bINVESTIGATION\b"
    ]
    start_index = None
    for i, line in enumerate(lines):
        for pat in header_candidates:
            if re.search(pat, line, re.IGNORECASE):
                start_index = i + 1
                break
        if start_index is not None:
            break

    footer_pattern = r"(CLINICAL\s+NOTES|DOCTOR:|Auth\.|Signature|Technician|MBBS|MD|Dr\.|ADVISED:|NOTE|End of Report)"
    end_index = None
    if start_index is not None:
        for i, line in enumerate(lines[start_index:], start=start_index):
            if re.search(footer_pattern, line, re.IGNORECASE):
                end_index = i
                break

    if start_index is not None and end_index is not None and start_index < end_index:
        test_section_lines = lines[start_index:end_index]
    elif start_index is not None:
        test_section_lines = lines[start_index:]
    else:
        test_section_lines = []

    exclude_keywords = {
        "NAME", "AGE", "SEX", "REGD", "PUID", "DATE", "DOCTOR", "ORDER",
        "COMPLETE", "ANALYTE", "VALUE", "REFERENCE", "REMARKS", "UNIT",
        "BRI/RANGE", "AUTH", "SIGNATURE", "TECHNICIAN", "MBBS", "MCI",
        "DR.", "INVESTIGATION", "CLINICAL", "NOTES", "RESULT", "Est",
    }
    for line in test_section_lines:
        if not line.strip():
            continue
        if any(kw in line.upper() for kw in exclude_keywords):
            continue
        result = extract_test_result_from_line(line)
        if result:
            test_name, test_value = result
            test_name = test_name.replace("*", "").replace("+", "").strip().rstrip(".,:")
            if test_name:
                tests[test_name] = test_value
    data["tests"] = tests

    return data


if __name__ == "__main__":
    # For testing the module independently
    image_path = "images/56.webp"  # Update this path as needed
    extracted_text = extract_text_from_image(image_path)
    print("Extracted Text:")
    print(extracted_text)
    parsed_data = parse_lab_report(extracted_text)
    print("\nParsed Data:")
    print(parsed_data)
