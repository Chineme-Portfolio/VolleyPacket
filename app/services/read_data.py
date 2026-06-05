import pandas as pd


import os


def detect_header_row(file_path, max_scan=20):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        raw = pd.read_csv(file_path, header=None, nrows=max_scan)
    else:
        raw = pd.read_excel(file_path, header=None, nrows=max_scan)
    best_row = 0
    best_filled = 0
    for i, row in raw.iterrows():
        filled = row.notna().sum() - (row.astype(str).str.strip() == "").sum()
        if filled > best_filled:
            best_filled = filled
            best_row = i
    return best_row


def load_data(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    header_row = detect_header_row(file_path)
    if ext == ".csv":
        data_frame = pd.read_csv(file_path, header=header_row)
    else:
        # Read all cells as strings first to preserve original formatting
        # (prevents pandas from turning "08065140173" into 8065140173.0
        # and "June 8, 2026" into 2026-06-08 00:00:00)
        data_frame = pd.read_excel(file_path, header=header_row, dtype=str)

    data_frame.columns = data_frame.columns.str.strip()

    # --- Fuzzy column normalization ---
    # Each canonical column has a list of keywords; if ANY keyword appears
    # in the lowered column name, it maps to that canonical name.
    # Order matters: first match wins, so more specific rules come first.

    CANONICAL_RULES = [
        ("ExamNo",      ["exam number", "examination number", "examno", "exam no"]),
        ("ExamDate",    ["exam date", "examination date", "examdate", "exam_date"]),
        ("PhotoLink",   ["photo link", "photolink", "photo_link", "photo url", "photo"]),
        ("Email",       ["email"]),
        ("PhoneNumber", ["phone", "mobile", "cell", "tel"]),
    ]

    # Name is special — we need to detect first/last splits
    FIRST_NAME_KEYWORDS = ["first name", "firstname", "first_name", "given name", "forename"]
    LAST_NAME_KEYWORDS  = ["last name", "lastname", "last_name", "surname", "family name"]
    NAME_KEYWORDS        = ["name"]  # catch-all for single name column

    rename_map = {}
    first_name_col = None
    last_name_col = None
    matched_cols = set()

    lowered = {col: col.strip().lower() for col in data_frame.columns}

    # Pass 1: detect first name / last name columns
    for orig, low in lowered.items():
        if orig in matched_cols:
            continue
        for kw in FIRST_NAME_KEYWORDS:
            if kw in low:
                first_name_col = orig
                matched_cols.add(orig)
                break
        for kw in LAST_NAME_KEYWORDS:
            if kw in low:
                last_name_col = orig
                matched_cols.add(orig)
                break

    # Pass 2: detect a single "name" column (only if no first/last split)
    if not first_name_col and not last_name_col:
        for orig, low in lowered.items():
            if orig in matched_cols:
                continue
            for kw in NAME_KEYWORDS:
                if kw in low:
                    rename_map[orig] = "Name"
                    matched_cols.add(orig)
                    break
            if orig in matched_cols:
                break

    # Pass 3: match the rest of the canonical columns
    for canonical, keywords in CANONICAL_RULES:
        for orig, low in lowered.items():
            if orig in matched_cols:
                continue
            for kw in keywords:
                if kw in low:
                    rename_map[orig] = canonical
                    matched_cols.add(orig)
                    break
            if canonical in rename_map.values():
                break

    # Apply renames
    data_frame = data_frame.rename(columns=rename_map)

    # Merge first + last name into "Name"
    if first_name_col and last_name_col:
        data_frame["Name"] = (
            data_frame[first_name_col].astype(str).str.strip()
            + " "
            + data_frame[last_name_col].astype(str).str.strip()
        ).str.strip()
        data_frame = data_frame.drop(columns=[first_name_col, last_name_col])
    elif first_name_col:
        data_frame = data_frame.rename(columns={first_name_col: "Name"})
    elif last_name_col:
        data_frame = data_frame.rename(columns={last_name_col: "Name"})

    # Convert datetime columns to readable strings BEFORE fillna
    # Pandas auto-detects dates from Excel and turns them into datetime64,
    # which renders as "2026-06-08 00:00:00" instead of "June, 8 2026".
    for col in data_frame.columns:
        if pd.api.types.is_datetime64_any_dtype(data_frame[col]):
            # Format dates cleanly — drop the time component if it's midnight
            data_frame[col] = data_frame[col].apply(
                lambda x: x.strftime("%B %d, %Y") if pd.notna(x) else ""
            )

    data_frame = data_frame.fillna('')

    return data_frame
