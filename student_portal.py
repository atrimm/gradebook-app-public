from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from grading_config import GRADEBOOK_CSV_PATH, GRADE_THRESHOLDS, GRADING_RUBRIC

from standards import COURSE_STANDARDS

from gradebook_logic import (
    get_student_dashboard_data,
    style_mastery_dataframe,
    make_grading_rubric_dataframe,
    make_semester_grade_threshold_dataframe,
    style_semester_grade_threshold_dataframe,
)

from gradebook_logic import read_csv_from_google_drive

STUDENT_LOOKUP_CSV_PATH = Path("demo_data/student_lookup_demo.csv")

st.set_page_config(
    page_title="Student Grade Portal",
    layout="wide",
)

if not st.user.get("is_logged_in", False):
    st.title("Student Grade Portal")
    st.write(
    "Students: Please sign in with your IMSA Google account. ")
    st.write("Parents / Guardians: Please sign in with the Google account linked to your email address on file."
)
    
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


@st.cache_data(ttl=300)
def load_parent_lookup():
    return read_csv_from_google_drive(
        "parent_lookup.csv",
        st.secrets["DRIVE_FOLDER_ID"],
    )


parent_lookup = load_parent_lookup()

test_email = st.user["email"].strip().lower()

st.sidebar.header("Signed in")
st.sidebar.write(test_email)

is_admin = test_email == "atrimm@imsa.edu"
show_diagnostics = False

if is_admin:
    show_diagnostics = st.sidebar.checkbox("Show diagnostics")

if st.sidebar.button("Sign out"):
    st.logout()

student_lookup["email_normalized"] = (
    student_lookup["email"]
    .astype(str)
    .str.strip()
    .str.lower()
)

parent_lookup["email_normalized"] = (
    parent_lookup["parent_email"]
    .astype(str)
    .str.strip()
    .str.lower()
)

student_matches = student_lookup[
    student_lookup["email_normalized"] == test_email
]

parent_matches = parent_lookup[
    parent_lookup["email_normalized"] == test_email
]

if student_matches.empty and parent_matches.empty:
    st.error(
        "Your Google account is not currently linked to a student record. "
        "Please contact your instructor."
    )
    st.stop()

if not student_matches.empty:
    student_id = student_matches.iloc[0]["student_id"]
    viewer_role = "student"
else:
    student_id = parent_matches.iloc[0]["student_id"]
    viewer_role = "parent"

if is_admin and show_diagnostics:

    st.title("Admin Diagnostics")

    st.write(f"Signed in as: {test_email}")
    st.write(f"Viewer role: {viewer_role}")

    st.metric("Gradebook rows", len(gradebook))
    st.metric("Student lookup rows", len(student_lookup))
    st.metric("Parent lookup rows", len(parent_lookup))

    st.subheader("Students in lookup file")
    st.dataframe(student_lookup)

    st.subheader("Parents in lookup file")
    st.dataframe(parent_lookup)

    st.subheader("Gradebook preview")
    st.dataframe(gradebook.tail(20))

    st.stop()

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

st.markdown(
    f"Viewing as: {'Parent / Guardian' if viewer_role == 'parent' else 'Student'}"
)
first_name = student_name_row["first_name"]
last_name = student_name_row["last_name"]
student_mod = student_name_row["mod"]

st.subheader(f"{first_name} {last_name}")
st.write(f"**Mod:** {str(student_mod).replace('Mod ', '')}")
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

st.markdown("This is the current semester grade, based on standards assessed so far. ")
st.markdown("Note that the current semester grade is **not** an average. Instead, it is determined by the 'Semester Grade Determination' table below.")
st.markdown("In particular, no matter the current semester grade, it is possible to achieve an 'A' up until the end of the semester by eventually meeting the course standards at the levels described below.")


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
st.markdown("This table shows the highest observed performance on each standard. Every course standard will be assessed multiple times throughout the semester, with the highest score counting toward the semester grade.")

st.markdown("### Rubric")
st.markdown("Each standard is scored according to the following rubric.")

rubric_df = make_grading_rubric_dataframe(GRADING_RUBRIC)

st.dataframe(
    rubric_df,
    use_container_width=True,
    hide_index=True,
)

st.subheader("Assessed Standards")

metadata_columns = {
    "student_id",
    "first_name",
    "last_name",
    "mod",
}

assessed_standards = [
    col for col in student_current_scores.columns
    if col not in metadata_columns
]

standards_df = pd.DataFrame(
    [
        {
            "Standard": standard,
            "Description": COURSE_STANDARDS.get(
                standard,
                "Description not yet available.",
            ),
        }
        for standard in assessed_standards
    ]
)

if standards_df.empty:
    st.info("No standards have been assessed yet.")
else:
    st.dataframe(
        standards_df,
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Semester Grade Determination")

st.markdown(
    "Your current percentages are shown in the first row. "
    "To earn a letter grade, your percentages must meet or exceed every required entry in that letter grade row."
)

threshold_df = make_semester_grade_threshold_dataframe(
    level_fractions,
    GRADE_THRESHOLDS,
)

st.dataframe(
    style_semester_grade_threshold_dataframe(
        threshold_df,
        GRADE_THRESHOLDS,
    ),
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

   