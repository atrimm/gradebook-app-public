from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from grading_config import GRADEBOOK_CSV_PATH, GRADE_THRESHOLDS, GRADING_RUBRIC

from gradebook_logic import (
    get_student_dashboard_data,
    style_grade_determination_dataframe,
    style_mastery_dataframe,
)

from gradebook_logic import read_csv_from_google_drive

STUDENT_LOOKUP_CSV_PATH = Path("demo_data/student_lookup_demo.csv")

st.set_page_config(
    page_title="Student Grade Portal",
    layout="wide",
)

if not st.user.get("is_logged_in", False):
    st.title("Student Grade Portal")
    st.write("Please sign in with your IMSA Google account.")
    
    if st.button("Sign in with Google"):
        st.login("google")
    
    st.stop()


st.title("Student Grade Portal")

@st.cache_data(ttl=60)
def load_gradebook():
    return read_csv_from_google_drive(
        "gradebook.csv",
        st.secrets["DRIVE_FOLDER_ID"],
    )


@st.cache_data(ttl=300)
def load_student_lookup():
    return read_csv_from_google_drive(
        "student_lookup.csv",
        st.secrets["DRIVE_FOLDER_ID"],
    )


gradebook = load_gradebook()
student_lookup = load_student_lookup()

test_email = st.user["email"].strip().lower()

if not test_email.endswith("@imsa.edu"):
    st.error("Please sign in with your IMSA Google account.")
    st.stop()

st.sidebar.header("Signed in")
st.sidebar.write(test_email)

is_admin = test_email == "atrimm@imsa.edu"
show_diagnostics = False

if is_admin:
    show_diagnostics = st.sidebar.checkbox("Show diagnostics")

if st.sidebar.button("Sign out"):
    st.logout()

if is_admin and show_diagnostics:

    st.title("Admin Diagnostics")

    st.write(f"Signed in as: {test_email}")

    st.metric("Gradebook rows", len(gradebook))
    st.metric("Student lookup rows", len(student_lookup))

    st.subheader("Students in lookup file")
    st.dataframe(student_lookup)

    st.subheader("Gradebook preview")
    st.dataframe(gradebook.tail(20))

    st.stop()

student_lookup["email_normalized"] = (
    student_lookup["email"]
    .astype(str)
    .str.strip()
    .str.lower()
)

matching_rows = student_lookup[
    student_lookup["email_normalized"] == test_email
]

if matching_rows.empty:
    st.error(
        "Your Google account is not currently linked to a student record. "
        "Please contact your instructor."
    )
    st.stop()

student_id = matching_rows.iloc[0]["student_id"]

student_rows = gradebook[gradebook["student_id"] == student_id].copy()

if student_rows.empty:
    st.error("No gradebook rows found for this student_id.")
    st.stop()

student_name_row = (
    student_rows[["first_name", "last_name", "mod"]]
    .dropna()
    .drop_duplicates()
    .iloc[0]
)

first_name = student_name_row["first_name"]
last_name = student_name_row["last_name"]
student_mod = student_name_row["mod"]

st.subheader(f"{first_name} {last_name}")
st.write(f"**Mod:** {student_mod}")
st.write(f"**Email:** {test_email}")
st.write(f"**Student ID:** {student_id}")

dashboard_data = get_student_dashboard_data(gradebook, student_id)

semester_grade = dashboard_data["semester_grade"]
student_current_scores = dashboard_data["current_scores"]
level_fractions = dashboard_data["level_fractions"]
score_history = dashboard_data["score_history"]
eligibility_issues = dashboard_data["eligibility_issues"]
absence_history = dashboard_data["absence_history"]
general_comments = dashboard_data["general_comments"]

st.subheader("Semester Grade")
st.markdown(f"# {semester_grade}")


st.subheader("Current Scores")

if student_current_scores.empty:
    st.info("No current scores found.")
else:
    display_scores = student_current_scores.drop(
        columns=["student_id", "first_name", "last_name", "mod"],
        errors="ignore",
    )

    st.dataframe(
        style_mastery_dataframe(display_scores),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("### Rubric")
st.markdown("Each standard is scored according to the following rubric.")
    
rubric_rows = [
    {
         "Score": score,
         "Level": rubric_item["level"],
         "Description": rubric_item["description"],
    }
    for score, rubric_item in GRADING_RUBRIC.items()
]
    
rubric_df = pd.DataFrame(rubric_rows)
    
st.dataframe(
    rubric_df,
    use_container_width=True,
    hide_index=True,
)

st.subheader("Semester Grade Determination")

st.markdown(
    "Your current percentages are shown in the first row. "
    "To earn a letter grade, your percentages must meet or exceed every required entry in that letter grade row."
)

current_percentages = {
    "Grade": "Your Current Percentage",
    "1 or above": "—",
    "2 or above": "—",
    "3 or above": "—",
    "4 or above": "—",
}

for _, row in level_fractions.iterrows():
    level = row["Level"]
    percentage = row["Percentage of Standards Met"]
    current_percentages[level] = f"{int(round(100 * percentage))}%"

threshold_rows = [current_percentages]

for letter_grade, thresholds in GRADE_THRESHOLDS.items():
    row = {"Grade": f"{letter_grade} Threshold"}

    for level_number in [1, 2, 3, 4]:
        column_name = f"{level_number} or above"
        fraction = thresholds.get(f"frac{level_number}", None)

        if fraction is None:
            row[column_name] = "—"
        else:
            row[column_name] = f"{int(round(100 * fraction))}%"

    threshold_rows.append(row)

threshold_df = pd.DataFrame(threshold_rows)

def color_threshold_rows(row):
    grade_label = row["Grade"]

    if grade_label == "Your Current Percentage":
        return ["font-weight: bold;"] * len(row)

    if grade_label.startswith("A"):
        return ["background-color: #00ff00;"] * len(row)
    if grade_label.startswith("B"):
        return ["background-color: #b7e1cd;"] * len(row)
    if grade_label.startswith("C-"):
        return ["background-color: #ff9900;"] * len(row)
    if grade_label.startswith("C"):
        return ["background-color: #ffff00;"] * len(row)

    return [""] * len(row)

st.dataframe(
    threshold_df.style.apply(color_threshold_rows, axis=1),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Score History")

st.dataframe(
    style_mastery_dataframe(score_history),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Progress Check Eligibility")
st.markdown("A progress check is given approximately one week after the initial check is returned. The final exam will serve as a final progress check on all standards.")
st.markdown("""To be eligible for a progress check on a given standard, a student must:
- Complete all corresponding classwork and homework assignments *before* the initial check. 
- Complete corrections of the initial check. 
- Complete all additional practice assigned to help prepare for the progress check.

If any of these requirements are not met, then the student is not eligible for the progress check and their next and final attempt on that standard will be on the final exam.""")

if eligibility_issues.empty:
    st.success("You are eligible for all upcoming progress checks.")
else:
    st.info(
        "You are currently ineligible for progress checks on the following standards. "
        "Your next attempt on these standards will be on the final exam."
    )

    display_df = eligibility_issues[
        ["standard", "eligibility_reason"]
    ].copy()

    display_df.columns = [
        "Standard",
        "Incomplete Assignment",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

st.subheader("General Comments")

if general_comments.empty:
    st.info("No general comments yet.")
else:
    st.dataframe(
        general_comments,
        use_container_width=True,
        hide_index=True,
    )

   