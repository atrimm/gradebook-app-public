import pandas as pd
from datetime import datetime
import shutil
from pathlib import Path

from grading_config import GRADE_THRESHOLDS


def make_current_scores_wide(gradebook):
    """
    Returns one row per student with peak score on each standard.
    """

    assessment_rows = gradebook[
        gradebook["score"].notna()
    ].copy()

    current_scores = (
        assessment_rows
        .groupby(
            ["student_id", "first_name", "last_name", "standard"],
            as_index=False
        )["score"]
        .max()
    )

    wide = current_scores.pivot_table(
        index=["student_id", "first_name", "last_name"],
        columns="standard",
        values="score",
        aggfunc="max"
    ).reset_index()

    wide.columns.name = None

    return wide

def compute_letter_grade(current_scores):
    """
    current_scores = list of peak standard scores
    """

    n = len(current_scores)

    if n == 0:
        return "NC"

    fractions = {
        "frac1": sum(s >= 1 for s in current_scores) / n,
        "frac2": sum(s >= 2 for s in current_scores) / n,
        "frac3": sum(s >= 3 for s in current_scores) / n,
        "frac4": sum(s >= 4 for s in current_scores) / n,
    }

    for letter in ["A", "B", "C", "C-"]:
        requirements = GRADE_THRESHOLDS[letter]

        if all(
            fractions[key] >= required_value
            for key, required_value in requirements.items()
        ):
            return letter

    return "D"
    
def compute_all_semester_grades(gradebook):
    """
    Computes semester letter grades for all students using peak scores
    on each standard.
    """

    current_scores_wide = make_current_scores_wide(gradebook)

    standard_columns = [
        col for col in current_scores_wide.columns
        if col not in ["student_id", "first_name", "last_name"]
    ]

    rows = []

    for _, row in current_scores_wide.iterrows():
        scores = row[standard_columns].dropna().tolist()

        rows.append({
            "student_id": row["student_id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "semester_grade": compute_letter_grade(scores)
        })

    return pd.DataFrame(rows)

def get_score_history(gradebook, student_id):
    """
    Returns scored assessment evidence for a student.
    Excludes general comments.
    """

    history = gradebook[
        (gradebook["student_id"] == student_id)
        & (gradebook["entry_type"].astype(str).str.strip() != "general_comment")
    ].copy()

    columns = [
        "date",
        "assignment_name",
        "standard",
        "score",
        "comment",
    ]

    return history[columns].sort_values(
        "date",
        ascending=False
    )

def get_general_comments(gradebook, student_id):
    """
    Returns general comments for a student, newest first.
    For comments on the same date, keeps newest entered comment first.
    """

    comments = gradebook[
        (gradebook["student_id"] == student_id)
        & (gradebook["entry_type"].astype(str).str.strip() == "general_comment")
    ].copy()

    comments["_original_order"] = comments.index

    columns = [
        "date",
        "comment",
    ]

    return comments.sort_values(
        ["date", "_original_order"],
        ascending=[False, True],
    )[columns]

def get_assignment_view(gradebook, assignment_name):
    assignment_rows = gradebook[
        gradebook["assignment_name"] == assignment_name
    ].copy()

    if assignment_rows.empty:
        return assignment_rows

    assignment_rows = assignment_rows.sort_values(
        by=["last_name", "first_name", "standard"]
    )

    columns_to_show = [
        "student_id",
        "first_name",
        "last_name",
        "mod",
        "date",
        "assignment_name",
        "assignment_type",
        "standard",
        "score",
        "comment",
    ]

    existing_columns = [
        col for col in columns_to_show if col in assignment_rows.columns
    ]

    return assignment_rows[existing_columns]

def append_evidence_row(
    gradebook,
    student_id,
    first_name,
    last_name,
    mod,
    date,
    entry_type,
    assignment_name,
    assignment_type,
    standard,
    score,
    comment,
    absent=False,
    absence_reason="",
    progress_check_eligible=True,
    eligibility_reason="",
):
    new_row = {
        "student_id": student_id,
        "first_name": first_name,
        "last_name": last_name,
        "mod": mod,
        "date": date,
        "entry_type": entry_type,
        "assignment_name": assignment_name,
        "assignment_type": assignment_type,
        "standard": standard,
        "score": score,
        "comment": comment,
        "absent": absent,
        "absence_reason": absence_reason,
        "progress_check_eligible": progress_check_eligible,
        "eligibility_reason": eligibility_reason,
    }

    return pd.concat(
        [gradebook, pd.DataFrame([new_row])],
        ignore_index=True,
    )

def append_evidence_rows(gradebook, new_rows):
    new_rows_df = pd.DataFrame(new_rows)

    return pd.concat(
        [gradebook, new_rows_df],
        ignore_index=True,
    )

def get_progress_check_eligibility_issues(gradebook, student_id):
    student_rows = gradebook[
        gradebook["student_id"] == student_id
    ].copy()

    if "progress_check_eligible" not in student_rows.columns:
        return student_rows.iloc[0:0]

    issues = student_rows[
        student_rows["progress_check_eligible"] == False
    ].copy()

    if issues.empty:
        return issues

    issues = issues.sort_values("date", ascending=False)

    columns_to_show = [
        "date",
        "assignment_name",
        "assignment_type",
        "standard",
        "score",
        "eligibility_reason",
    ]

    existing_columns = [
        col for col in columns_to_show if col in issues.columns
    ]

    return issues[existing_columns]

def get_assessment_absence_history(gradebook, student_id):
    student_rows = gradebook[
        gradebook["student_id"] == student_id
    ].copy()

    if "absent" not in student_rows.columns:
        return student_rows.iloc[0:0]

    absences = student_rows[
        student_rows["absent"] == True
    ].copy()

    if absences.empty:
        return absences

    absences = absences.sort_values("date", ascending=False)

    columns_to_show = [
        "date",
        "assignment_name",
        "assignment_type",
        "standard",
        "absence_reason",
    ]

    existing_columns = [
        col for col in columns_to_show if col in absences.columns
    ]

    return absences[existing_columns]

def get_student_level_fractions(current_scores):
    score_columns = [
        col for col in current_scores.columns
        if col not in ["student_id", "first_name", "last_name", "semester_grade"]
    ]

    scores = current_scores[score_columns].iloc[0]
    total_standards = len(scores)

    rows = []

    for level in [1, 2, 3, 4]:
        fraction_met = (scores >= level).sum() / total_standards

        threshold_met = "Below C-"

        for letter_grade in ["A", "B", "C", "C-"]:
            thresholds = GRADE_THRESHOLDS[letter_grade]
            frac_key = f"frac{level}"

            if frac_key not in thresholds:
                threshold_met = letter_grade
                break

            if fraction_met >= thresholds[frac_key]:
                threshold_met = letter_grade
                break

        rows.append(
            {
                "Level": f"{level} or above",
                "Fraction Met": round(fraction_met, 2),
                "Threshold Met": threshold_met,
            }
        )

    return pd.DataFrame(rows)

def color_mastery_scores(val):
    try:
        score = int(val)
    except (ValueError, TypeError):
        return ""

    if score == 4:
        return "background-color: #00ff00"
    elif score == 3:
        return "background-color: #b7e1cd"
    elif score == 2:
        return "background-color: #ffff00"
    elif score == 1:
        return "background-color: #ff9900"
    elif score == 0:
        return "background-color: #ff0000"

    return ""

def style_mastery_dataframe(df):
    styled_df = df.style

    score_columns = []

    for col in df.columns:
        unique_values = set(df[col].dropna().unique())

        if unique_values.issubset({0, 1, 2, 3, 4}):
            score_columns.append(col)

    if score_columns:
        styled_df = styled_df.map(
            color_mastery_scores,
            subset=score_columns,
        )

        format_dict = {
            col: "{:.0f}"
            for col in score_columns
        }

        styled_df = styled_df.format(format_dict)

        if "semester_grade" in df.columns:
            styled_df = styled_df.map(
                color_letter_grade,
                subset=["semester_grade"],
            )

    return styled_df

def color_letter_grade(val):
    if val == "A":
        return "background-color: #00ff00"
    elif val == "B":
        return "background-color: #b7e1cd"
    elif val == "C":
        return "background-color: #ffff00"
    elif val == "C-":
        return "background-color: #ff9900"
    elif val == "D":
        return "background-color: #ff0000"

    return ""

def style_grade_determination_dataframe(df):
    styled_df = df.style

    if "Fraction Met" in df.columns:
        styled_df = styled_df.format(
            {"Fraction Met": "{:.0%}"}
        )

    if "Threshold Met" in df.columns:
        styled_df = styled_df.map(
            color_letter_grade,
            subset=["Threshold Met"],
        )

    return styled_df

def backup_gradebook(csv_path, max_backups=50):
    backup_dir = csv_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"gradebook_{timestamp}.csv"

    shutil.copy2(csv_path, backup_path)

    cleanup_old_backups(backup_dir, max_backups=max_backups)

    return backup_path


def cleanup_old_backups(backup_dir, max_backups=50):
    backup_files = sorted(
        backup_dir.glob("gradebook_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    old_backups = backup_files[max_backups:]

    for old_backup in old_backups:
        old_backup.unlink()

def list_gradebook_backups(csv_path):
    backup_dir = csv_path.parent / "backups"

    if not backup_dir.exists():
        return pd.DataFrame()

    backup_files = sorted(
        backup_dir.glob("gradebook_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    rows = []

    for path in backup_files:
        rows.append(
            {
                "filename": path.name,
                "modified": datetime.fromtimestamp(path.stat().st_mtime),
                "age": format_backup_age(datetime.fromtimestamp(path.stat().st_mtime)),
                "size_kb": round(path.stat().st_size / 1024, 1),
                "path": str(path),
            }
        )

    return pd.DataFrame(rows)


def restore_gradebook_backup(backup_path, csv_path):
    backup_path = Path(backup_path)

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    backup_gradebook(csv_path)

    shutil.copy2(backup_path, csv_path)

    return csv_path

def summarize_gradebook_csv(csv_path):
    df = pd.read_csv(csv_path)

    summary = {
        "rows": len(df),
        "students": df["student_id"].nunique() if "student_id" in df.columns else None,
        "mods": df["mod"].nunique() if "mod" in df.columns else None,
        "assignments": df["assignment_name"].nunique() if "assignment_name" in df.columns else None,
        "standards": df["standard"].nunique() if "standard" in df.columns else None,
    }

    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce")
        summary["earliest_date"] = dates.min()
        summary["latest_date"] = dates.max()

    return pd.DataFrame([summary])

def compare_gradebook_csvs(current_csv_path, backup_csv_path):
    current_df = pd.read_csv(current_csv_path)
    backup_df = pd.read_csv(backup_csv_path)

    comparison = {
        "current_rows": len(current_df),
        "backup_rows": len(backup_df),
        "row_difference": len(backup_df) - len(current_df),
    }

    if "student_id" in current_df.columns and "student_id" in backup_df.columns:
        comparison["current_students"] = current_df["student_id"].nunique()
        comparison["backup_students"] = backup_df["student_id"].nunique()
        comparison["student_difference"] = (
            backup_df["student_id"].nunique()
            - current_df["student_id"].nunique()
        )

    if "assignment_name" in current_df.columns and "assignment_name" in backup_df.columns:
        comparison["current_assignments"] = current_df["assignment_name"].nunique()
        comparison["backup_assignments"] = backup_df["assignment_name"].nunique()
        comparison["assignment_difference"] = (
            backup_df["assignment_name"].nunique()
            - current_df["assignment_name"].nunique()
        )

    return pd.DataFrame([comparison])

def get_gradebook_diff_counts(current_csv_path, backup_csv_path):
    current_df = pd.read_csv(current_csv_path)
    backup_df = pd.read_csv(backup_csv_path)

    current_rows = set(
        current_df.astype(str).fillna("").agg("|".join, axis=1)
    )

    backup_rows = set(
        backup_df.astype(str).fillna("").agg("|".join, axis=1)
    )

    return pd.DataFrame(
        [
            {
                "rows_only_in_current": len(current_rows - backup_rows),
                "rows_only_in_backup": len(backup_rows - current_rows),
            }
        ]
    )

def get_rows_only_in_current(current_csv_path, backup_csv_path):
    current_df = pd.read_csv(current_csv_path)
    backup_df = pd.read_csv(backup_csv_path)

    current_keys = current_df.astype(str).fillna("").agg("|".join, axis=1)
    backup_keys = set(
        backup_df.astype(str).fillna("").agg("|".join, axis=1)
    )

    rows_only_mask = ~current_keys.isin(backup_keys)

    return current_df.loc[rows_only_mask].copy()

def get_rows_only_in_backup(current_csv_path, backup_csv_path):
    current_df = pd.read_csv(current_csv_path)
    backup_df = pd.read_csv(backup_csv_path)

    backup_keys = backup_df.astype(str).fillna("").agg("|".join, axis=1)
    current_keys = set(
        current_df.astype(str).fillna("").agg("|".join, axis=1)
    )

    rows_only_mask = ~backup_keys.isin(current_keys)

    return backup_df.loc[rows_only_mask].copy()

def format_backup_age(modified_time):
    now = datetime.now()
    age = now - modified_time

    total_seconds = int(age.total_seconds())

    if total_seconds < 60:
        return "just now"

    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes} minutes ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hours ago"

    days = hours // 24
    if days == 1:
        return "yesterday"

    return f"{days} days ago"

def get_most_recent_backup(csv_path):
    backups = list_gradebook_backups(csv_path)

    if backups.empty:
        return None

    newest_backup = backups.sort_values(
        by="modified",
        ascending=False,
    ).iloc[0]

    return newest_backup["path"]

def get_progress_check_dashboard(gradebook, mod=None):
    """
    Returns rows with progress check eligibility issues.
    """

    dashboard = gradebook[
        gradebook["progress_check_eligible"] == False
    ].copy()

    if mod is not None:
        dashboard = dashboard[dashboard["mod"] == mod]

    dashboard["student"] = (
        dashboard["last_name"].astype(str)
        + ", "
        + dashboard["first_name"].astype(str)
    )

    columns = [
        "student",
        "mod",
        "date",
        "assignment_name",
        "standard",
        "eligibility_reason",
    ]

    existing_columns = [
        col for col in columns if col in dashboard.columns
    ]

    return dashboard[existing_columns].sort_values(
        ["student", "standard", "date"],
        ascending=[True, True, False],
    )

def add_student_to_gradebook(
    gradebook,
    student_id,
    first_name,
    last_name,
    mod,
):
    """
    Adds a new student and initializes score-0 evidence
    for every existing standard in the selected mod.
    """

    standards = sorted(
        gradebook.loc[
            (gradebook["mod"] == mod)
            & (gradebook["standard"].notna())
            & (gradebook["standard"].astype(str).str.strip() != ""),
            "standard",
        ].unique()
    )

    new_rows = []

    new_rows.append({
        "student_id": student_id,
        "first_name": first_name,
        "last_name": last_name,
        "mod": mod,
        "date": "",
        "entry_type": "roster_add",
        "assignment_name": "",
        "assignment_type": "",
        "standard": "",
        "score": 0,
        "comment": "Student added to roster.",
        "absent": False,
        "absence_reason": "",
        "progress_check_eligible": True,
        "eligibility_reason": "",
    })

    for standard in standards:
        new_rows.append({
            "student_id": student_id,
            "first_name": first_name,
            "last_name": last_name,
            "mod": mod,
            "date": "",
            "entry_type": "roster_initial_score",
            "assignment_name": "Roster Initialization",
            "assignment_type": "other",
            "standard": standard,
            "score": 0,
            "comment": "Initialized to 0 when student was added.",
            "absent": False,
            "absence_reason": "",
            "progress_check_eligible": True,
            "eligibility_reason": "",
        })

    return pd.concat(
        [gradebook, pd.DataFrame(new_rows)],
        ignore_index=True,
    )

def drop_student_from_gradebook(
    gradebook,
    student_id,
    drop_date,
    reason="",
):
    """
    Adds a roster_drop row for a student.
    Does not delete any existing evidence.
    """

    student_rows = gradebook[
        gradebook["student_id"] == student_id
    ]

    if student_rows.empty:
        return gradebook

    latest_student_row = student_rows.iloc[-1]

    new_row = {
        "student_id": latest_student_row["student_id"],
        "first_name": latest_student_row["first_name"],
        "last_name": latest_student_row["last_name"],
        "mod": latest_student_row["mod"],
        "date": drop_date,
        "entry_type": "roster_drop",
        "assignment_name": "",
        "assignment_type": "",
        "standard": "",
        "score": 0,
        "comment": reason,
        "absent": False,
        "absence_reason": "",
        "progress_check_eligible": True,
        "eligibility_reason": "",
    }

    return pd.concat(
        [gradebook, pd.DataFrame([new_row])],
        ignore_index=True,
    )

def get_active_student_ids(gradebook):
    """
    Returns student IDs whose latest roster event is not roster_drop.
    Students with no roster events are treated as active.
    """

    gradebook = gradebook.copy()
    gradebook["student_id"] = gradebook["student_id"].astype(str)
    gradebook["entry_type"] = gradebook["entry_type"].astype(str).str.strip()

    roster_events = gradebook[
        gradebook["entry_type"].isin(["roster_add", "roster_drop"])
    ].copy()

    if roster_events.empty:
        return gradebook["student_id"].dropna().unique().tolist()

    roster_events["_original_order"] = roster_events.index

    latest_roster_events = (
        roster_events
        .sort_values(["student_id", "_original_order"])
        .groupby("student_id")
        .tail(1)
    )

    dropped_ids = latest_roster_events[
        latest_roster_events["entry_type"] == "roster_drop"
    ]["student_id"].tolist()

    return [
        student_id
        for student_id in gradebook["student_id"].dropna().unique().tolist()
        if student_id not in dropped_ids
    ]

def make_student_text_report(
    student_name,
    mod,
    generated_at,
    semester_grade,
    grade_determination_df,
    current_scores_df,
    score_history_df,
    general_comments_df,
    assessment_absences_df,
    progress_check_issues_df,
):
    report_lines = []

    report_lines.append(f"Student Report: {student_name}")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append(f"Mod: {mod}")
    report_lines.append(f"Generated: {generated_at}")
    report_lines.append(f"Semester Grade: {semester_grade}")
    report_lines.append("")

    sections = [
        ("Grade Determination", grade_determination_df),
        ("Current Scores", current_scores_df),
        ("Score History", score_history_df),
        ("General Comments", general_comments_df),
        ("Assessment Absences", assessment_absences_df),
        ("Progress Check Eligibility Issues", progress_check_issues_df),
    ]

    for section_title, df in sections:
        report_lines.append(section_title)
        report_lines.append("-" * len(section_title))

        if df is None or df.empty:
            report_lines.append("None")
        else:
            cleaned_df = df.copy()

            for col in cleaned_df.columns:
                cleaned_df[col] = cleaned_df[col].fillna("")

            report_lines.append(cleaned_df.to_string(index=False))

        report_lines.append("")

    return "\n".join(report_lines)

def make_student_html_report(
    student_name,
    mod,
    generated_at,
    semester_grade,
    grade_determination_df,
    current_scores_df,
    score_history_df,
    general_comments_df,
    assessment_absences_df,
    progress_check_issues_df,
):
    html = f"""
    <html>
    <head>
        <title>Student Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
            }}

            h1 {{
                margin-bottom: 0;
            }}

            h2 {{
                margin-top: 30px;
            }}

            table {{
                border-collapse: collapse;
                width: 100%;
            }}

            th, td {{
                border: 1px solid #cccccc;
                padding: 6px;
                text-align: left;
            }}

            th {{
                background-color: #f2f2f2;
            }}
        </style>
    </head>
    <body>

    <h1>{student_name}</h1>

    <p>
    <strong>Mod:</strong> {mod}<br>
    <strong>Generated:</strong> {generated_at}<br>
    <strong>Semester Grade:</strong> {semester_grade}
    </p>
    """

    sections = [
        ("Grade Determination", grade_determination_df),
        ("Current Scores", current_scores_df),
        ("Score History", score_history_df),
        ("General Comments", general_comments_df),
        ("Assessment Absences", assessment_absences_df),
        ("Progress Check Eligibility Issues", progress_check_issues_df),
    ]

    for title, df in sections:
        html += f"<h2>{title}</h2>"

        if df is None or df.empty:
            html += "<p>None</p>"
        else:
            html += df.fillna("").to_html(index=False)

    html += """
    </body>
    </html>
    """

    return html

def rename_assignment_in_gradebook(
    gradebook,
    selected_mod,
    old_assignment_name,
    new_assignment_name,
):
    updated_gradebook = gradebook.copy()

    mask = (
        (updated_gradebook["mod"].astype(str) == str(selected_mod))
        & (
            updated_gradebook["assignment_name"].fillna("").astype(str)
            == str(old_assignment_name)
        )
    )

    updated_gradebook.loc[mask, "assignment_name"] = new_assignment_name

    return updated_gradebook

def delete_assignment_from_gradebook(
    gradebook,
    selected_mod,
    assignment_name,
):
    updated_gradebook = gradebook.copy()

    mask = (
        (updated_gradebook["mod"].astype(str) == str(selected_mod))
        & (
            updated_gradebook["assignment_name"].fillna("").astype(str)
            == str(assignment_name)
        )
    )

    updated_gradebook = updated_gradebook.loc[~mask].copy()

    return updated_gradebook

def get_student_dashboard_data(gradebook, student_id):
    student_rows = gradebook[
        gradebook["student_id"].astype(str) == str(student_id)
    ].copy()

    student_grade_table = compute_all_semester_grades(student_rows)

    semester_grade = student_grade_table["semester_grade"].iloc[0]

    student_current_scores = make_current_scores_wide(student_rows)

    level_fractions = get_student_level_fractions(student_current_scores)

    score_history = get_score_history(student_rows, student_id)

    eligibility_issues = get_progress_check_eligibility_issues(
        student_rows,
        student_id,
    )

    absence_history = get_assessment_absence_history(
        student_rows,
        student_id,
    )

    general_comments = get_general_comments(
        student_rows,
        student_id,
    )

    return {
        "student_rows": student_rows,
        "semester_grade": semester_grade,
        "current_scores": student_current_scores,
        "level_fractions": level_fractions,
        "score_history": score_history,
        "eligibility_issues": eligibility_issues,
        "absence_history": absence_history,
        "general_comments": general_comments,
    }

def read_csv_from_google_drive(file_name, folder_id):
    import io

    import pandas as pd
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )

    service = build("drive", "v3", credentials=credentials)

    query = (
        f"name = '{file_name}' "
        f"and '{folder_id}' in parents "
        f"and trashed = false"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = results.get("files", [])

    if not files:
        raise FileNotFoundError(f"Could not find {file_name} in Google Drive folder.")

    file_id = files[0]["id"]

    request = service.files().get_media(fileId=file_id)

    file_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_buffer.seek(0)

    return pd.read_csv(file_buffer)

def write_csv_to_google_drive(df, file_name, folder_id):
    import io

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    import streamlit as st

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    service = build("drive", "v3", credentials=credentials)

    query = (
        f"name = '{file_name}' "
        f"and '{folder_id}' in parents "
        f"and trashed = false"
    )

    results = service.files().list(
        q=query,
        fields="files(id, name)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = results.get("files", [])

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    media = MediaIoBaseUpload(
        io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
        mimetype="text/csv",
        resumable=False,
    )

    if files:
        file_id = files[0]["id"]
        service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()
    else:
        file_metadata = {
            "name": file_name,
            "parents": [folder_id],
            "mimeType": "text/csv",
        }

        service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()

def save_gradebook_to_google_drive(gradebook):
    import streamlit as st

    write_csv_to_google_drive(
        gradebook,
        "gradebook.csv",
        st.secrets["DRIVE_FOLDER_ID"],
    )

def backup_gradebook_to_google_drive():
    from datetime import datetime

    import streamlit as st

    gradebook = read_csv_from_google_drive(
        "gradebook.csv",
        st.secrets["DRIVE_FOLDER_ID"],
    )

    backups_folder_id = st.secrets["BACKUPS_FOLDER_ID"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_name = f"gradebook_backup_{timestamp}.csv"

    write_csv_to_google_drive(
        gradebook,
        backup_file_name,
        backups_folder_id,
    )

    keep_most_recent_google_drive_backups(max_backups=50)

    return backup_file_name

def list_google_drive_backups():
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )

    service = build("drive", "v3", credentials=credentials)

    results = service.files().list(
        q=(
            f"'{st.secrets['BACKUPS_FOLDER_ID']}' in parents "
            f"and trashed = false"
        ),
        fields="files(id,name,createdTime)",
        orderBy="createdTime desc",
        pageSize=100,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    return results.get("files", [])

def restore_google_drive_backup(backup_file_id):
    import io

    import pandas as pd
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    service = build("drive", "v3", credentials=credentials)

    request = service.files().get_media(
        fileId=backup_file_id,
        supportsAllDrives=True,
    )

    file_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_buffer.seek(0)
    restored_gradebook = pd.read_csv(file_buffer)

    backup_gradebook_to_google_drive()
    save_gradebook_to_google_drive(restored_gradebook)

    return restored_gradebook

def restore_latest_google_drive_backup():
    backups = list_google_drive_backups()

    if not backups:
        raise FileNotFoundError("No backups found.")

    latest_backup = backups[0]

    restore_google_drive_backup(latest_backup["id"])

    return latest_backup["name"]

def read_google_drive_backup_by_id(backup_file_id):
    import io

    import pandas as pd
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )

    service = build("drive", "v3", credentials=credentials)

    request = service.files().get_media(
        fileId=backup_file_id,
        supportsAllDrives=True,
    )

    file_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_buffer.seek(0)

    return pd.read_csv(file_buffer)


def compare_current_gradebook_to_google_drive_backup(backup_file_id):
    import streamlit as st

    current_gradebook = read_csv_from_google_drive(
        "gradebook.csv",
        st.secrets["DRIVE_FOLDER_ID"],
    )

    backup_gradebook = read_google_drive_backup_by_id(backup_file_id)

    current_rows = current_gradebook.astype(str)
    backup_rows = backup_gradebook.astype(str)

    rows_only_in_current = current_rows.merge(
        backup_rows.drop_duplicates(),
        how="left",
        indicator=True,
    )
    rows_only_in_current = rows_only_in_current[
        rows_only_in_current["_merge"] == "left_only"
    ].drop(columns=["_merge"])

    rows_only_in_backup = backup_rows.merge(
        current_rows.drop_duplicates(),
        how="left",
        indicator=True,
    )
    rows_only_in_backup = rows_only_in_backup[
        rows_only_in_backup["_merge"] == "left_only"
    ].drop(columns=["_merge"])

    return rows_only_in_current, rows_only_in_backup

def keep_most_recent_google_drive_backups(max_backups=50):
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    backups = list_google_drive_backups()

    if len(backups) <= max_backups:
        return 0

    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )

    service = build("drive", "v3", credentials=credentials)

    backups_to_delete = backups[max_backups:]

    for backup in backups_to_delete:
        service.files().delete(
            fileId=backup["id"],
            supportsAllDrives=True,
        ).execute()

    return len(backups_to_delete)