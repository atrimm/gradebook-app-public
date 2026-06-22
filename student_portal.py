from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from grading_config import GRADEBOOK_CSV_PATH, GRADE_THRESHOLDS, GRADING_RUBRIC

from gradebook_logic import (
    get_student_dashboard_data,
    make_student_html_report,
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

st.metric("Semester Grade", semester_grade)

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

st.subheader("Grade Determination")

st.dataframe(
    style_grade_determination_dataframe(level_fractions),
    use_container_width=True,
    hide_index=True,
)



st.subheader("Grading Information")

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
    
st.markdown("### Semester Grade Determination")

    
threshold_rows = []
    
for letter_grade, thresholds in GRADE_THRESHOLDS.items():
    row = {"Grade": letter_grade}

    for level_number in [1, 2, 3, 4]:
        fraction = thresholds.get(f"frac{level_number}", None)

        if fraction is None:
            row[f"Level {level_number}"] = "—"
        else:
            row[f"Level {level_number}"] = (
                f"{int(round(100 * fraction))}%"
            )

    threshold_rows.append(row)

threshold_df = pd.DataFrame(threshold_rows)

st.markdown("A student must complete the entire row of the following table to earn the corresponding letter grade.")
st.markdown("Each entry shows the percentage of standards which must be met at the corresponding level.")

st.dataframe(
    threshold_df,
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
st.markdown("To be eligible for a progress check, all corresponding classwork and homework assignments must be complete before the initial check, corrections of the intial check must be made, and all assigned additional practice completed.")

if eligibility_issues.empty:
    st.info("You are eligible for all upcoming progress checks.")
else:
    st.dataframe(
        eligibility_issues,
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

student_display_name = f"{last_name}, {first_name}"

student_report_html = make_student_html_report(
    student_name=student_display_name,
    mod=student_mod,
    generated_at=datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    semester_grade=semester_grade,
    grade_determination_df=level_fractions,
    current_scores_df=student_current_scores,
    score_history_df=score_history,
    general_comments_df=general_comments,
    assessment_absences_df=absence_history,
    progress_check_issues_df=eligibility_issues,
)

st.download_button(
    "Download Grade Report",
    data=student_report_html,
    file_name=f"{student_id}_student_report.html",
    mime="text/html",
)   