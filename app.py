import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

from gradebook_logic import (
    make_current_scores_wide,
    compute_all_semester_grades,
    get_score_history,
    get_general_comments,
    get_assignment_view,
    append_evidence_row,
    append_evidence_rows,
    get_progress_check_eligibility_issues,
    get_assessment_absence_history,
    get_student_level_fractions,
    color_mastery_scores,
    style_mastery_dataframe,
    backup_gradebook,
    backup_gradebook_to_google_drive,
    list_google_drive_backups,
    save_gradebook_to_google_drive,
    summarize_gradebook_csv,
    compare_gradebook_csvs,
    get_gradebook_diff_counts,
    get_rows_only_in_current,
    get_rows_only_in_backup,
    get_progress_check_dashboard,
    add_student_to_gradebook,
    drop_student_from_gradebook,
    get_active_student_ids,
    make_student_text_report,
    make_student_html_report,
    rename_assignment_in_gradebook,
    delete_assignment_from_gradebook,
    read_csv_from_google_drive,
    restore_google_drive_backup,
    restore_latest_google_drive_backup,
    compare_current_gradebook_to_google_drive_backup,
    make_grading_rubric_dataframe,
    make_semester_grade_threshold_dataframe,
    style_semester_grade_threshold_dataframe,
)

from grading_config import GRADE_THRESHOLDS, GRADING_RUBRIC

#st.set_page_config(
 #   page_title="Standards-Based Gradebook",
  #  layout="wide",
#)

if not st.user.get("is_logged_in", False):
    st.title("Teacher Gradebook")
    st.write("Please sign in with your IMSA Google account.")

    if st.button("Sign in with Google"):
        st.login("google")

    st.stop()

teacher_email = st.user["email"].strip().lower()

if teacher_email != "atrimm@imsa.edu":
    st.error("You are not authorized to access this app.")
    st.stop()

gradebook = read_csv_from_google_drive(
    "gradebook.csv",
    st.secrets["DRIVE_FOLDER_ID"],
)

required_columns = {
    "absent": False,
    "absence_reason": "",
    "progress_check_eligible": True,
    "eligibility_reason": "",
}

for col, default_value in required_columns.items():
    if col not in gradebook.columns:
        gradebook[col] = default_value

st.title("Standards-Based Gradebook")

mods = sorted(gradebook["mod"].dropna().unique())

selected_mod = st.sidebar.selectbox("Mod", mods)

role = st.sidebar.selectbox(
    "Role",
    [
        "Teacher",
        "Admin",
    ],
)

if role == "Teacher":
    view_options = [
        "Gradebook",
        "Student",
        "Assignment",
        "Progress Check Dashboard",
        "Data Entry",
    ]
else:
    view_options = [
        "Row Editor",
        "Assignment Manager",
        "Roster Manager",
        "Backup Manager",
    ]

view = st.sidebar.selectbox(
    "View",
    view_options,
)

st.sidebar.divider()

st.sidebar.header("Signed in")
st.sidebar.write(teacher_email)

if st.sidebar.button("Sign out"):
    st.logout()

mod_gradebook = gradebook[gradebook["mod"] == selected_mod].copy()

active_student_ids = get_active_student_ids(mod_gradebook)

active_mod_gradebook = mod_gradebook[
    mod_gradebook["student_id"].astype(str).isin(active_student_ids)
].copy()

st.header(f"{view} — {selected_mod}")

if view == "Gradebook":
    show_dropped_students = st.checkbox(
        "Show dropped students",
        value=False,
    )

    gradebook_source = mod_gradebook if show_dropped_students else active_mod_gradebook

    current_scores_wide = make_current_scores_wide(gradebook_source)
    semester_grades = compute_all_semester_grades(gradebook_source)

    gradebook_view = semester_grades.merge(
        current_scores_wide,
        on=["student_id", "first_name", "last_name"],
        how="left"
    )

    for extra_column in ["phone_slot", "pronunciation"]:
        if extra_column in gradebook_source.columns:
            extra_values = (
                gradebook_source[["student_id", extra_column]]
                .drop_duplicates(subset=["student_id"])
            )

            gradebook_view = gradebook_view.merge(
                extra_values,
                on="student_id",
                how="left",
            )
        else:
            gradebook_view[extra_column] = ""

    gradebook_view = gradebook_view.sort_values(
        by=["last_name", "first_name"],
        ascending=[True, True],
    )

    desired_order = [
        "phone_slot",
        "last_name",
        "first_name",
        "pronunciation",
        "student_id",
    ]

    remaining_columns = [
        col for col in gradebook_view.columns
        if col not in desired_order
    ]

    gradebook_view = gradebook_view[
        desired_order + remaining_columns
    ]

    st.dataframe(
        style_mastery_dataframe(gradebook_view),
        use_container_width=True,
        hide_index=True,
    )

elif view == "Student":

    students = (
        active_mod_gradebook[
            ["student_id", "first_name", "last_name"]
        ]
        .drop_duplicates()
        .sort_values(["last_name", "first_name"])
    )

    student_options = {
        f"{row['last_name']}, {row['first_name']}": row["student_id"]
        for _, row in students.iterrows()
    }

    if not student_options:
        st.info("No active students in this mod.")
    else:
        selected_student_name = st.selectbox(
            "Student",
            list(student_options.keys())
        )

        selected_student_id = student_options[selected_student_name]

        student_rows = active_mod_gradebook[
            active_mod_gradebook["student_id"].astype(str) == str(selected_student_id)
        ].copy()

        student_grade_table = compute_all_semester_grades(student_rows)

        semester_grade = student_grade_table["semester_grade"].iloc[0]

        st.subheader("Semester Grade")
        st.markdown(f"# {semester_grade}")

        student_current_scores = make_current_scores_wide(student_rows)

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

        level_fractions = get_student_level_fractions(student_current_scores)

        st.markdown("### Rubric")
        st.markdown("Each standard is scored according to the following rubric.")

        rubric_df = make_grading_rubric_dataframe(GRADING_RUBRIC)

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

        st.subheader("Progress Check Eligibility")

        eligibility_issues = get_progress_check_eligibility_issues(
            active_mod_gradebook,
            selected_student_id,
        )
        
        if eligibility_issues.empty:
            st.info("You are eligible for all upcoming progress checks.")
        else:
            st.info(
                "You are currently ineligible for progress checks on the following standards. "
                "Your next attempt on these standards will be on the final exam."
            )
        
            display_eligibility_issues = eligibility_issues.rename(
                columns={
                    "standard": "Standard",
                    "eligibility_reason": "Incomplete Assignment",
                }
            )
        
            display_eligibility_issues = display_eligibility_issues[
                ["Standard", "Incomplete Assignment"]
            ]
        
            st.dataframe(
                display_eligibility_issues,
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("Assessment Absences")

        absence_history = get_assessment_absence_history(
            active_mod_gradebook,
            selected_student_id,
        )

        if absence_history.empty:
            st.info("No assessment absences recorded.")
        else:
            st.dataframe(
                absence_history,
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("General Comments")

        general_comments = get_general_comments(
            active_mod_gradebook,
            selected_student_id
        )

        if general_comments.empty:
            st.info("No general comments yet.")
        else:
            st.dataframe(
                general_comments,
                use_container_width=True,
                hide_index=True
            )

        st.subheader("Score History")

        score_history = get_score_history(
            active_mod_gradebook,
            selected_student_id
        )

        st.dataframe(
            style_mastery_dataframe(score_history),
            use_container_width=True,
            hide_index=True,
        )

        student_report_text = make_student_text_report(
            student_name=selected_student_name,
            mod=selected_mod,
            generated_at=datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            semester_grade=semester_grade,
            grade_determination_df=level_fractions,
            current_scores_df=student_current_scores,
            score_history_df=score_history,
            general_comments_df=general_comments,
            assessment_absences_df=absence_history,
            progress_check_issues_df=eligibility_issues,
        )

        student_report_html = make_student_html_report(
            student_name=selected_student_name,
            mod=selected_mod,
            generated_at=datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            semester_grade=semester_grade,
            grade_determination_df=level_fractions,
            current_scores_df=student_current_scores,
            score_history_df=score_history,
            general_comments_df=general_comments,
            assessment_absences_df=absence_history,
            progress_check_issues_df=eligibility_issues,
        )

        with st.expander("Student Report Export"):
            st.text_area(
                "Preview",
                student_report_text,
                height=400,
            )

            safe_student_name = selected_student_name.replace(",", "").replace(" ", "_")

            st.download_button(
                "Download Student Report",
                data=student_report_text,
                file_name=f"{safe_student_name}_student_report.txt",
                mime="text/plain",
            )

            st.download_button(
                "Download Student Report as HTML",
                data=student_report_html,
                file_name=f"{safe_student_name}_student_report.html",
                mime="text/html",
            )

elif view == "Assignment":

    mod_gradebook = gradebook[gradebook["mod"] == selected_mod].copy()

    assignment_names = sorted(
        [
            a
            for a in active_mod_gradebook["assignment_name"]
            .dropna()
            .astype(str)
            .unique()
            if a.strip() and a != "Roster Initialization"
        ]
    )

    if len(assignment_names) == 0:
        st.info("No assignments found for this mod.")
    else:
        selected_assignment = st.selectbox(
            "Select Assignment",
            assignment_names,
        )

        assignment_view = get_assignment_view(
            mod_gradebook,
            selected_assignment,
        )

        st.dataframe(
            style_mastery_dataframe(assignment_view),
            use_container_width=True,
            hide_index=True,
        )

elif view == "Assignment Manager":

    assignment_names = sorted(
        [
            a
            for a in active_mod_gradebook["assignment_name"]
            .dropna()
            .astype(str)
            .unique()
            if a.strip()
        ]
    )

    if not assignment_names:
        st.info("No assignments found.")
    else:
        selected_assignment = st.selectbox(
            "Assignment",
            assignment_names,
        )

        assignment_rows = active_mod_gradebook[
            active_mod_gradebook["assignment_name"].astype(str)
            == str(selected_assignment)
        ].copy()

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Affected Rows",
                len(assignment_rows),
            )

        with col2:
            st.metric(
                "Affected Students",
                assignment_rows["student_id"].nunique(),
            )

        standards = sorted(
            assignment_rows["standard"]
            .dropna()
            .astype(str)
            .unique()
        )

        st.write("Standards")

        if standards:
            st.write(", ".join(standards))
        else:
            st.write("None")

        st.subheader("Preview")

        st.dataframe(
            assignment_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Rename Assignment")

        st.write(f"Current assignment: **{selected_assignment}**")

        new_assignment_name = st.text_input(
            "New assignment name",
        )

        if new_assignment_name.strip():
            st.write(
                f"Rename: **{selected_assignment}** → **{new_assignment_name.strip()}**"
            )

        confirm_rename = st.checkbox(
            "I understand this will rename this assignment for all matching rows in the selected mod."
        )

        if st.button("Rename Assignment"):
            if not new_assignment_name.strip():
                st.error("New assignment name cannot be blank.")
            elif new_assignment_name == selected_assignment:
                st.info("The new assignment name is the same as the current name.")
            elif not confirm_rename:
                st.error("Please check the confirmation box before renaming.")
            else:
                backup_gradebook_to_google_drive()

                updated_gradebook = rename_assignment_in_gradebook(
                    gradebook,
                    selected_mod,
                    selected_assignment,
                    new_assignment_name.strip(),
                )

                save_gradebook_to_google_drive(updated_gradebook)

                st.success("Assignment renamed successfully.")
                st.rerun()

        st.subheader("Delete Assignment")

        st.warning(
            "This will permanently remove all matching rows for this assignment in the selected mod. "
            "A backup will be created first."
        )

        st.write(f"Assignment to delete: **{selected_assignment}**")
        st.write(f"Rows to delete: **{len(assignment_rows)}**")
        st.write(f"Affected students: **{assignment_rows['student_id'].nunique()}**")

        delete_confirmation_text = st.text_input(
            "Type the assignment name exactly to confirm deletion",
        )

        confirm_delete = st.checkbox(
            "I understand this action cannot be undone except by restoring a backup."
        )

        if st.button("Delete Assignment"):
            if delete_confirmation_text != selected_assignment:
                st.error("The typed assignment name does not match.")
            elif not confirm_delete:
                st.error("Please check the confirmation box before deleting.")
            else:
                backup_gradebook_to_google_drive()

                updated_gradebook = delete_assignment_from_gradebook(
                    gradebook,
                    selected_mod,
                    selected_assignment,
                )

                save_gradebook_to_google_drive(updated_gradebook)

                st.success("Assignment deleted successfully.")
                st.rerun()

elif view == "Progress Check Dashboard":

    dashboard = get_progress_check_dashboard(
        gradebook,
        mod=selected_mod,
    )

    if dashboard.empty:
        st.success("No progress check eligibility issues found.")
    else:
        st.write(f"{len(dashboard)} issue(s) found.")

        st.dataframe(
            dashboard,
            use_container_width=True,
            hide_index=True,
        )

elif view == "Data Entry":

    students = (
        active_mod_gradebook[["student_id", "first_name", "last_name"]]
        .drop_duplicates()
        .sort_values(["last_name", "first_name"])
    )

    single_tab, bulk_tab, roster_tab = st.tabs(
    ["Student Entry", "Class Entry", "Roster Info"]
)

    with single_tab:
        st.subheader("Student Entry")

        if students.empty:
            st.info("No active students in this mod.")
        else:
            student_options = {
                f"{row.last_name}, {row.first_name}": row.student_id
                for row in students.itertuples(index=False)
            }

            selected_student_label = st.selectbox(
                "Student",
                list(student_options.keys()),
            )

            selected_entry_student_id = student_options[selected_student_label]

            selected_student_row = students[
                students["student_id"].astype(str) == str(selected_entry_student_id)
            ].iloc[0]

            entry_date = st.date_input("Date")

            entry_type = st.selectbox(
                "Entry Type",
                [
                    "assessment",
                    "general_comment",
                    "assessment_absence",
                    "progress_check_eligibility",
                ],
            )

            assignment_name = ""
            assignment_type = ""
            standard = ""
            score = 0
            absent = False
            absence_reason = ""
            progress_check_eligible = True
            eligibility_reason = ""

            if entry_type == "assessment":
                assignment_name = st.text_input(
                    "Assignment Name",
                    key="single_assignment_name",
                )

                assignment_type = st.selectbox(
                    "Assignment Type",
                    ["initial_check", "progress_check", "reassessment", "other"],
                    key="single_assignment_type",
                )

                existing_standards = sorted(
                    mod_gradebook["standard"]
                    .dropna()
                    .unique()
                )

                standard_choice = st.selectbox(
                    "Standard",
                    ["<New Standard>"] + existing_standards,
                    key="single_standard_choice",
                )

                if standard_choice == "<New Standard>":
                    standard = st.text_input(
                        "New Standard",
                        key="single_new_standard",
                    )
                else:
                    standard = standard_choice

                score = st.number_input(
                    "Score",
                    min_value=0,
                    max_value=4,
                    step=1,
                )

            elif entry_type == "assessment_absence":
                assignment_name = st.text_input(
                    "Assignment Name",
                    key="absence_assignment_name",
                )

                assignment_type = st.selectbox(
                    "Assignment Type",
                    ["initial_check", "progress_check", "reassessment", "other"],
                    key="absence_assignment_type",
                )

                existing_standards = sorted(
                    mod_gradebook["standard"]
                    .dropna()
                    .unique()
                )

                standard_choice = st.selectbox(
                    "Standard",
                    ["<New Standard>"] + existing_standards,
                    key="absence_standard_choice",
                )

                if standard_choice == "<New Standard>":
                    standard = st.text_input(
                        "New Standard",
                        key="absence_new_standard",
                    )
                else:
                    standard = standard_choice

                absent = True
                absence_reason = st.text_input("Absence Reason")

            elif entry_type == "progress_check_eligibility":
                existing_standards = sorted(
                    mod_gradebook["standard"]
                    .dropna()
                    .unique()
                )

                standard_choice = st.selectbox(
                    "Standard",
                    ["<New Standard>"] + existing_standards,
                    key="eligibility_standard_choice",
                )

                if standard_choice == "<New Standard>":
                    standard = st.text_input(
                        "New Standard",
                        key="eligibility_new_standard",
                    )
                else:
                    standard = standard_choice

                progress_check_eligible = st.checkbox(
                    "Eligible for Progress Check",
                    value=True,
                )

                if not progress_check_eligible:
                    eligibility_reason = st.text_input("Incomplete Assignment")

            if entry_type in ["assessment", "general_comment"]:
                comment = st.text_area("Comment")
            else:
                comment = ""

            if st.button("Append Row"):
                updated_gradebook = append_evidence_row(
                    gradebook=gradebook,
                    student_id=selected_entry_student_id,
                    first_name=selected_student_row["first_name"],
                    last_name=selected_student_row["last_name"],
                    mod=selected_mod,
                    date=entry_date,
                    entry_type=entry_type,
                    assignment_name=assignment_name,
                    assignment_type=assignment_type,
                    standard=standard,
                    score=score,
                    comment=comment,
                    absent=absent,
                    absence_reason=absence_reason,
                    progress_check_eligible=progress_check_eligible,
                    eligibility_reason=eligibility_reason,
                )

                backup_gradebook_to_google_drive()

                save_gradebook_to_google_drive(updated_gradebook)

                st.success("Row appended and saved to CSV.")

                st.dataframe(
                    updated_gradebook.tail(1),
                    use_container_width=True,
                    hide_index=True,
                )

    with bulk_tab:
        st.subheader("Class Entry")

        if students.empty:
            st.info("No active students in this mod.")
        else:
            bulk_date = st.date_input("Assessment Date")

            bulk_assignment_name = st.text_input(
                "Assignment Name",
                key="bulk_assignment_name",
            )

            bulk_assignment_type = st.selectbox(
                "Assignment Type",
                ["initial_check", "progress_check", "reassessment", "other"],
                key="bulk_assignment_type",
            )

            existing_standards = sorted(
                mod_gradebook["standard"]
                .dropna()
                .unique()
            )

            standard_choice = st.selectbox(
                "Standard",
                ["<New Standard>"] + existing_standards,
                key="bulk_standard_choice",
            )

            if standard_choice == "<New Standard>":
                bulk_standard = st.text_input(
                    "New Standard",
                    key="bulk_new_standard",
                )
            else:
                bulk_standard = standard_choice

            entry_table = students.copy()
            entry_table["score"] = None
            entry_table["absent"] = False
            entry_table["absence_reason"] = ""
            entry_table["progress_check_eligible"] = True
            entry_table["eligibility_reason"] = ""
            entry_table["comment"] = ""

            entry_table = entry_table[
                [
                    "student_id",
                    "first_name",
                    "last_name",
                    "score",
                    "comment",
                    "absent",
                    "absence_reason",
                    "progress_check_eligible",
                    "eligibility_reason",
                ]
            ]

            edited_table = st.data_editor(
                entry_table,
                column_config={
                    "student_id": st.column_config.TextColumn("Student ID", disabled=True),
                    "first_name": st.column_config.TextColumn("First Name", disabled=True),
                    "last_name": st.column_config.TextColumn("Last Name", disabled=True),
                    "score": st.column_config.NumberColumn(
                        "Score",
                        min_value=0,
                        max_value=4,
                        step=1,
                    ),
                    "comment": st.column_config.TextColumn("Comment"),
                    "absence_reason": st.column_config.TextColumn("Absence Reason"),
                    "eligibility_reason": st.column_config.TextColumn("Eligibility Reason"),
                },
                hide_index=True,
                use_container_width=True,
            )

            if st.button("Save Assessment"):
                new_rows = []

                for row in edited_table.itertuples(index=False):
                    if row.score is None or pd.isna(row.score):
                        continue

                    new_rows.append(
                        {
                            "student_id": row.student_id,
                            "first_name": row.first_name,
                            "last_name": row.last_name,
                            "mod": selected_mod,
                            "date": bulk_date,
                            "entry_type": "assessment",
                            "assignment_name": bulk_assignment_name,
                            "assignment_type": bulk_assignment_type,
                            "standard": bulk_standard,
                            "score": row.score,
                            "comment": row.comment,
                            "absent": row.absent,
                            "absence_reason": row.absence_reason,
                            "progress_check_eligible": row.progress_check_eligible,
                            "eligibility_reason": row.eligibility_reason,
                        }
                    )

                if len(new_rows) == 0:
                    st.warning("No scores entered.")
                else:
                    updated_gradebook = append_evidence_rows(
                        gradebook,
                        new_rows,
                    )

                    backup_gradebook_to_google_drive()

                    save_gradebook_to_google_drive(updated_gradebook)

                    st.success(f"Saved {len(new_rows)} assessment rows to CSV.")

                    st.dataframe(
                        pd.DataFrame(new_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

        with roster_tab:
            st.subheader("Roster Info")

            if students.empty:
                st.info("No active students in this mod.")
            else:
                roster_info_table = students.copy()

                for col in ["phone_slot", "pronunciation"]:
                    if col in active_mod_gradebook.columns:
                        latest_values = (
                            active_mod_gradebook[
                                ["student_id", "date", col]
                            ]
                            .dropna(subset=[col])
                            .sort_values("date")
                            .drop_duplicates(subset=["student_id"], keep="last")
                            [["student_id", col]]
                        )

                        roster_info_table = roster_info_table.merge(
                            latest_values,
                            on="student_id",
                            how="left",
                        )
                    else:
                        roster_info_table[col] = ""

                roster_info_table["phone_slot"] = (
                    roster_info_table["phone_slot"]
                    .fillna("")
                    .astype(str)
                )

                roster_info_table["pronunciation"] = (
                    roster_info_table["pronunciation"]
                    .fillna("")
                    .astype(str)
                )

                roster_info_table = roster_info_table.sort_values(
                    by=["last_name", "first_name"],
                    ascending=[True, True],
                )

                roster_info_table = roster_info_table[
                    [
                        "phone_slot",
                        "last_name",
                        "first_name",
                        "pronunciation",
                        "student_id",
                    ]
                ]

                edited_roster_info = st.data_editor(
                    roster_info_table,
                    column_config={
                        "phone_slot": st.column_config.TextColumn("Phone Slot"),
                        "last_name": st.column_config.TextColumn(
                            "Last Name",
                            disabled=True,
                        ),
                        "first_name": st.column_config.TextColumn(
                            "First Name",
                            disabled=True,
                        ),
                        "pronunciation": st.column_config.TextColumn(
                            "Pronunciation"
                        ),
                        "student_id": st.column_config.TextColumn(
                            "Student ID",
                            disabled=True,
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

                if st.button("Save Roster Info"):
                    new_rows = []

                    for row in edited_roster_info.itertuples(index=False):
                        new_rows.append(
                            {
                                "student_id": row.student_id,
                                "first_name": row.first_name,
                                "last_name": row.last_name,
                                "mod": selected_mod,
                                "date": pd.Timestamp.today().date(),
                                "entry_type": "roster_info",
                                "assignment_name": "",
                                "assignment_type": "",
                                "standard": "",
                                "score": 0,
                                "comment": "",
                                "absent": False,
                                "absence_reason": "",
                                "progress_check_eligible": True,
                                "eligibility_reason": "",
                                "phone_slot": row.phone_slot,
                                "pronunciation": row.pronunciation,
                            }
                        )

                    updated_gradebook = append_evidence_rows(
                        gradebook,
                        new_rows,
                    )

                    backup_gradebook_to_google_drive()

                    save_gradebook_to_google_drive(updated_gradebook)

                    st.success(
                        f"Saved roster info for {len(new_rows)} students."
                    )

                    
elif view == "Row Editor":
    #st.header("Row Editor")

    st.warning(
        "This edits existing rows directly and saves over the CSV. "
        "Use carefully."
    )

    mod_gradebook = gradebook[gradebook["mod"] == selected_mod].copy()

    filtered_gradebook = mod_gradebook.copy()

    student_options = ["All"] + sorted(
        filtered_gradebook.apply(
            lambda row: f"{row['last_name']}, {row['first_name']}",
            axis=1,
        )
        .dropna()
        .unique()
    )
    
    selected_student_filter = st.selectbox(
        "Filter by Student",
        student_options,
        key="row_editor_student_filter",
    )
    
    if selected_student_filter != "All":
        last_name, first_name = selected_student_filter.split(", ", 1)
    
        filtered_gradebook = filtered_gradebook[
            (filtered_gradebook["last_name"] == last_name)
            & (filtered_gradebook["first_name"] == first_name)
        ]
    
    assignment_options = ["All"] + sorted(
        filtered_gradebook["assignment_name"]
        .dropna()
        .unique()
    )
    
    selected_assignment_filter = st.selectbox(
        "Filter by Assignment",
        assignment_options,
        key="row_editor_assignment_filter",
    )
    
    if selected_assignment_filter != "All":
        filtered_gradebook = filtered_gradebook[
            filtered_gradebook["assignment_name"] == selected_assignment_filter
        ]
    
    standard_options = ["All"] + sorted(
        filtered_gradebook["standard"]
        .dropna()
        .unique()
    )
    
    selected_standard_filter = st.selectbox(
        "Filter by Standard",
        standard_options,
        key="row_editor_standard_filter",
    )
    
    if selected_standard_filter != "All":
        filtered_gradebook = filtered_gradebook[
            filtered_gradebook["standard"] == selected_standard_filter
        ]
    
    entry_type_options = ["All"] + sorted(
        filtered_gradebook["entry_type"]
        .dropna()
        .unique()
    )
    
    selected_entry_type_filter = st.selectbox(
        "Filter by Entry Type",
        entry_type_options,
        key="row_editor_entry_type_filter",
    )
    
    if selected_entry_type_filter != "All":
        filtered_gradebook = filtered_gradebook[
            filtered_gradebook["entry_type"] == selected_entry_type_filter
        ]
    
    st.write(f"Showing {len(filtered_gradebook)} rows.")
    
    rows_to_edit = filtered_gradebook.copy()
    rows_to_edit["original_index"] = rows_to_edit.index

    columns_to_show = [
    "original_index",
    "student_id",
    "first_name",
    "last_name",
    "mod",
    "date",
    "entry_type",
    "assignment_name",
    "assignment_type",
    "standard",
    "score",
    "comment",
    "absent",
    "absence_reason",
    "progress_check_eligible",
    "eligibility_reason",
]

    existing_columns = [
        col for col in columns_to_show if col in rows_to_edit.columns
    ]

    rows_to_edit = rows_to_edit[existing_columns]

    text_columns = [
        "comment",
        "absence_reason",
        "eligibility_reason",
    ]

    for col in text_columns:
        if col in rows_to_edit.columns:
            rows_to_edit[col] = rows_to_edit[col].fillna("").astype(str)
            rows_to_edit[col] = rows_to_edit[col].replace("nan", "")

    edited_rows = st.data_editor(
        rows_to_edit,
        disabled=["original_index", "student_id", "first_name", "last_name", "mod"],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "comment": st.column_config.TextColumn("Comment"),
            "absence_reason": st.column_config.TextColumn("Absence Reason"),
            "eligibility_reason": st.column_config.TextColumn("Eligibility Reason"),
        },
    )

    if st.button("Save Edited Rows"):
        updated_gradebook = gradebook.copy()

        for col in text_columns:
            if col in updated_gradebook.columns:
                updated_gradebook[col] = updated_gradebook[col].fillna("").astype(str)
                updated_gradebook[col] = updated_gradebook[col].replace("nan", "")
        
        for _, edited_row in edited_rows.iterrows():
            original_index = int(edited_row["original_index"])

            for col in edited_rows.columns:
                if col == "original_index":
                    continue

                updated_gradebook.loc[original_index, col] = edited_row[col]

        backup_gradebook_to_google_drive()
        
        save_gradebook_to_google_drive(updated_gradebook)

        st.success("Edited rows saved to CSV.")

elif view == "Roster Manager":

    st.subheader("Add Student")

    new_student_id = st.text_input("Student ID")
    new_first_name = st.text_input("First Name")
    new_last_name = st.text_input("Last Name")

    if st.button("Add Student"):
        if not new_student_id or not new_first_name or not new_last_name:
            st.error("Enter student ID, first name, and last name.")
        else:
            updated_gradebook = add_student_to_gradebook(
                gradebook=gradebook,
                student_id=new_student_id,
                first_name=new_first_name,
                last_name=new_last_name,
                mod=selected_mod,
            )

            backup_gradebook_to_google_drive()

            save_gradebook_to_google_drive(updated_gradebook)

            st.success("Student added to roster.")

            st.dataframe(
                updated_gradebook.tail(1),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    st.subheader("Drop Student")

    roster_students = (
        active_mod_gradebook[["student_id", "first_name", "last_name"]]
        .drop_duplicates()
        .sort_values(["last_name", "first_name"])
    )

    student_options = {
        f"{row['last_name']}, {row['first_name']} ({row['student_id']})": row["student_id"]
        for _, row in roster_students.iterrows()
    }

    if not student_options:
        st.info("No students available to drop.")
    else:
        selected_drop_student = st.selectbox(
            "Student to Drop",
            list(student_options.keys()),
        )

        drop_date = st.date_input("Drop Date")
        drop_reason = st.text_input("Reason for Drop")

        confirm_drop = st.checkbox(
            "I understand this will mark the student as dropped but will not delete any data."
        )

        if st.button("Drop Student"):
            if not confirm_drop:
                st.error("Check the confirmation box before dropping the student.")
            else:
                updated_gradebook = drop_student_from_gradebook(
                    gradebook=gradebook,
                    student_id=student_options[selected_drop_student],
                    drop_date=drop_date,
                    reason=drop_reason,
                )

                backup_gradebook_to_google_drive()

                save_gradebook_to_google_drive(updated_gradebook)

                st.success("Student marked as dropped.")

                st.dataframe(
                    updated_gradebook.tail(1),
                    use_container_width=True,
                    hide_index=True,
                )

elif view == "Backup Manager":

    st.subheader("Backup Manager")

    backups = list_google_drive_backups()

    st.write(f"Found {len(backups)} backups.")

    if backups:

        backup_options = {
            f"{backup['name']} — {backup['createdTime']}": backup["id"]
            for backup in backups
        }

        st.subheader("Backup Selection")

        selected_backup_label = st.selectbox(
            "Backup",
            list(backup_options.keys()),
        )

        if st.button("Compare Current Gradebook to Selected Backup"):
            rows_only_in_current, rows_only_in_backup = (
                compare_current_gradebook_to_google_drive_backup(
                    backup_options[selected_backup_label]
                )
            )

            st.subheader("Rows in Current Gradebook but Not in Backup")
            st.write(f"{len(rows_only_in_current)} rows")
            st.dataframe(
                rows_only_in_current,
                use_container_width=True,
            )

            st.subheader("Rows in Backup but Not in Current Gradebook")
            st.write(f"{len(rows_only_in_backup)} rows")
            st.dataframe(
                rows_only_in_backup,
                use_container_width=True,
            )

        st.warning(
            "Restoring a selected backup will replace the current gradebook. "
            "A backup of the current gradebook will be created first."
        )

        confirm_restore = st.checkbox(
            "I understand and want to restore the selected backup."
        )

        if st.button("Restore Selected Backup"):
            if confirm_restore:
                restore_google_drive_backup(
                    backup_options[selected_backup_label]
                )
                st.success("Backup restored.")
                st.rerun()
            else:
                st.error(
                    "Check the confirmation box before restoring."
                )

        st.divider()

    else:
        st.info("No backups found.")

    st.subheader("Undo Last Save")

    st.warning(
        "This restores the most recent backup and replaces the current gradebook. "
        "A backup of the current gradebook will be created first."
    )

    confirm_undo = st.checkbox(
        "I understand and want to undo the last save."
    )

    if st.button("Undo Last Save"):
        if confirm_undo:
            restored_backup_name = restore_latest_google_drive_backup()
            st.success(
                f"Restored latest backup: {restored_backup_name}"
            )
            st.rerun()
        else:
            st.error(
                "Check the confirmation box before undoing the last save."
            )