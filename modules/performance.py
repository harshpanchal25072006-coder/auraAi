import os
import streamlit as st
import pandas as pd

# AURA chat jo file save karta hai (AURA file ke STUDENT_FILE jaisa hi naam)
AURA_STUDENT_FILE = "students.csv"

# marks.py wala hi rule: percentage >= 75 aur 18 < age < 25
SCHOLARSHIP_PERCENT = 75
SCHOLARSHIP_AGE_MIN = 19
SCHOLARSHIP_AGE_MAX = 24


def scholarship_status(percentage, age):
    if pd.isna(age):
        return "Age missing", "age nahi mili"
    reasons = []
    if percentage < SCHOLARSHIP_PERCENT:
        reasons.append(
            f"percentage {percentage:.2f}% hai, {SCHOLARSHIP_PERCENT}% ya zyada chahiye"
        )
    if not (SCHOLARSHIP_AGE_MIN - 1 < age < SCHOLARSHIP_AGE_MAX + 1):
        reasons.append(
            f"age {age:g} hai, {SCHOLARSHIP_AGE_MIN} se {SCHOLARSHIP_AGE_MAX} ke beech chahiye"
        )
    if reasons:
        return "Not eligible", " aur ".join(reasons)
    return "Eligible", "percentage aur age dono criteria pass"


def load_aura_students(subjects):
    if not os.path.exists(AURA_STUDENT_FILE):
        return None, 0
    try:
        raw = pd.read_csv(AURA_STUDENT_FILE)
    except Exception:
        return None, 0

    data = raw.rename(
        columns={"name": "Student", "age": "Age", **{s.lower(): s for s in subjects}}
    )
    needed = ["Student"] + subjects
    if any(c not in data.columns for c in needed):
        return None, 0

    keep = needed + (["Age"] if "Age" in data.columns else [])
    data = data[keep].copy()
    if "Age" in data.columns:
        data["Age"] = pd.to_numeric(data["Age"], errors="coerce")
    for s in subjects:
        data[s] = pd.to_numeric(data[s], errors="coerce")

    valid = (
        data[subjects].notna().all(axis=1)
        & data[subjects].ge(0).all(axis=1)
        & data[subjects].le(100).all(axis=1)
        & data["Student"].astype(str).str.strip().ne("")
    )
    return data[valid].reset_index(drop=True), int((~valid).sum())


def show_performance():

    st.markdown(
        '<div class="main-title">📊 Performance Dashboard</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Analyze student performance using marks, grades and performance statistics.'
        '</div>',
        unsafe_allow_html=True
    )

    subjects = [
        "English",
        "Hindi",
        "Math",
        "Science",
        "Physics"
    ]

    aura_data, aura_skipped = load_aura_students(subjects)

    options = ["🎲 Random Data", "📁 Import CSV"]
    if aura_data is not None and not aura_data.empty:
        options.insert(0, "🤖 AURA Chat File")   # pehla option = default

    st.subheader("📂 Select Data Source")

    data_source = st.radio(
        "Choose how you want to load student data:",
        options,
        horizontal=True
    )

    if data_source == "🤖 AURA Chat File":

        data = aura_data

        st.success(
            f"✅ AURA chat se aayi file auto-load hui — {len(data)} students."
        )

        if aura_skipped:
            st.warning(
                f"⚠️ {aura_skipped} rows skip hui (marks missing ya 0-100 se bahar)."
            )

    elif data_source == "🎲 Random Data":

        data = pd.DataFrame({
            "Student": [
                "Harsh",
                "Rahul",
                "Aman",
                "Priya",
                "Neha",
                "Rohit",
                "Anjali",
                "Karan"
            ],
            "English": [82, 65, 78, 91, 88, 55, 76, 69],
            "Hindi": [75, 72, 81, 89, 92, 60, 84, 70],
            "Math": [90, 68, 74, 95, 86, 58, 80, 73],
            "Science": [85, 70, 79, 88, 90, 62, 78, 75],
            "Physics": [88, 64, 76, 93, 85, 57, 82, 71],
            "Age": [21, 20, 26, 22, 19, 18, 23, 24]
        })

    else:

        uploaded_file = st.file_uploader(
            "Upload Student CSV File",
            type=["csv"]
        )

        if uploaded_file is not None:

            data = pd.read_csv(uploaded_file)

            required_columns = [
                "Student",
                "English",
                "Hindi",
                "Math",
                "Science",
                "Physics"
            ]

            missing_columns = [
                column
                for column in required_columns
                if column not in data.columns
            ]

            if missing_columns:

                st.error(
                    "Missing columns: "
                    + ", ".join(missing_columns)
                )

                st.info(
                    "CSV must contain: "
                    + ", ".join(required_columns)
                )

                st.stop()

            # age column optional hai (Age / age / AGE sab chalega)
            age_col = next(
                (c for c in data.columns if str(c).strip().lower() == "age"),
                None
            )
            age_values = (
                pd.to_numeric(data[age_col], errors="coerce")
                if age_col is not None
                else None
            )

            data = data[required_columns].copy()

            if age_values is not None:
                data["Age"] = age_values

            for subject in subjects:
                data[subject] = pd.to_numeric(
                    data[subject],
                    errors="coerce"
                )

            if data[subjects].isnull().any().any():

                st.error(
                    "Some marks are invalid. "
                    "Please check your CSV file."
                )

                st.stop()

            st.success(
                f"✅ CSV imported successfully — {len(data)} students found."
            )

        else:

            st.info(
                "Please upload a CSV file to display the dashboard."
            )

            st.stop()

    data["Total"] = data[subjects].sum(axis=1)

    data["Percentage"] = (
        data["Total"] / (len(subjects) * 100)
    ) * 100

    def get_grade(percentage):

        if percentage >= 90:
            return "A+"

        elif percentage >= 75:
            return "A"

        elif percentage >= 60:
            return "B"

        elif percentage >= 40:
            return "C"

        else:
            return "F"

    data["Grade"] = data["Percentage"].apply(get_grade)

    data["Result"] = data["Percentage"].apply(
        lambda x: "Pass" if x >= 40 else "Fail"
    )

    # age mili to scholarship nikalo
    has_age = "Age" in data.columns and data["Age"].notna().any()

    if has_age:
        data["Age"] = pd.to_numeric(data["Age"], errors="coerce")
        scholarship_info = [
            scholarship_status(p, a)
            for p, a in zip(data["Percentage"], data["Age"])
        ]
        data["Scholarship"] = [s[0] for s in scholarship_info]
        data["Reason"] = [s[1] for s in scholarship_info]

    st.markdown("---")

    st.subheader("🎯 Performance Overview")

    total_students = len(data)

    passed_students = len(
        data[data["Result"] == "Pass"]
    )

    failed_students = len(
        data[data["Result"] == "Fail"]
    )

    average_percentage = data["Percentage"].mean()

    highest_percentage = data["Percentage"].max()

    lowest_percentage = data["Percentage"].min()

    pass_rate = (
        passed_students / total_students
    ) * 100

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Students",
            total_students
        )

    with col2:
        st.metric(
            "Average Percentage",
            f"{average_percentage:.2f}%"
        )

    with col3:
        st.metric(
            "Pass Rate",
            f"{pass_rate:.2f}%"
        )

    with col4:
        st.metric(
            "Highest Score",
            f"{highest_percentage:.2f}%"
        )

    st.markdown("---")

    st.subheader("🎓 Scholarship Eligibility")

    st.caption(
        f"Rule: percentage ≥ {SCHOLARSHIP_PERCENT}% aur age "
        f"{SCHOLARSHIP_AGE_MIN} se {SCHOLARSHIP_AGE_MAX} ke beech."
    )

    if has_age:

        eligible_df = data[data["Scholarship"] == "Eligible"]

        not_eligible_count = int(
            (data["Scholarship"] == "Not eligible").sum()
        )

        age_missing_count = int(
            (data["Scholarship"] == "Age missing").sum()
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Eligible",
                len(eligible_df)
            )

        with col2:
            st.metric(
                "Not Eligible",
                not_eligible_count
            )

        with col3:
            st.metric(
                "Age Missing",
                age_missing_count
            )

        if eligible_df.empty:

            st.info(
                "Is data me koi student scholarship ke liye eligible nahi hai."
            )

        else:

            st.success(
                f"🎉 {len(eligible_df)} students ko scholarship mil rahi hai."
            )

            st.dataframe(
                eligible_df[
                    [
                        "Student",
                        "Age",
                        "Percentage",
                        "Grade"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

        with st.expander("❌ Eligible nahi wale students aur wajah"):

            st.dataframe(
                data[data["Scholarship"] != "Eligible"][
                    [
                        "Student",
                        "Age",
                        "Percentage",
                        "Scholarship",
                        "Reason"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

    else:

        st.info(
            "Is data me age column nahi mila, isliye scholarship check nahi ho sakta. "
            "CSV me `Age` column jodo, to yahan apne aap dikhne lagega."
        )

    st.markdown("---")

    st.subheader("📋 Student Performance")

    table_columns = ["Student"]

    if has_age:
        table_columns.append("Age")

    table_columns += ["Total", "Percentage", "Grade", "Result"]

    if has_age:
        table_columns.append("Scholarship")

    st.dataframe(
        data[table_columns],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    st.subheader("📈 Student Percentage")

    student_chart = data[
        ["Student", "Percentage"]
    ].set_index("Student")

    st.bar_chart(student_chart)

    st.markdown("---")

    st.subheader("📚 Subject Performance")

    subject_average = data[subjects].mean()

    subject_chart = pd.DataFrame({
        "Average Marks": subject_average
    })

    st.bar_chart(subject_chart)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:

        st.subheader("🏆 Top Performer")

        top_student = data.loc[
            data["Percentage"].idxmax()
        ]

        st.success(
            f"**{top_student['Student']}**"
        )

        st.write(
            f"Percentage: {top_student['Percentage']:.2f}%"
        )

        st.write(
            f"Grade: {top_student['Grade']}"
        )

        st.write(
            f"Total Marks: {top_student['Total']}/{len(subjects) * 100}"
        )

    with col2:

        st.subheader("📊 Grade Distribution")

        grade_counts = data["Grade"].value_counts()

        grade_chart = pd.DataFrame({
            "Students": grade_counts
        })

        st.bar_chart(grade_chart)

    st.markdown("---")

    st.subheader("🔎 Student Search")

    selected_student = st.selectbox(
        "Select a student",
        data["Student"].tolist()
    )

    student = data[
        data["Student"] == selected_student
    ].iloc[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Percentage",
            f"{student['Percentage']:.2f}%"
        )

    with col2:
        st.metric(
            "Grade",
            student["Grade"]
        )

    with col3:
        st.metric(
            "Total Marks",
            f"{student['Total']}/{len(subjects) * 100}"
        )

    if has_age:

        if student["Scholarship"] == "Eligible":
            st.success(
                f"🎓 {selected_student} scholarship ke liye ELIGIBLE hai "
                f"(age {student['Age']:g}, {student['Percentage']:.2f}%)."
            )

        elif student["Scholarship"] == "Not eligible":
            st.error(
                f"❌ {selected_student} scholarship ke liye eligible nahi hai: "
                f"{student['Reason']}."
            )

        else:
            st.warning(
                f"⚠️ {selected_student} ki age nahi mili, isliye scholarship check nahi hua."
            )

    student_subjects = pd.DataFrame({
        "Subject": subjects,
        "Marks": [
            student["English"],
            student["Hindi"],
            student["Math"],
            student["Science"],
            student["Physics"]
        ]
    })

    st.subheader(
        f"📚 {selected_student}'s Subject Performance"
    )

    st.bar_chart(
        student_subjects.set_index("Subject")
    )

    st.markdown("---")

    st.subheader("📊 Additional Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Passed",
            passed_students
        )

    with col2:
        st.metric(
            "Failed",
            failed_students
        )

    with col3:
        st.metric(
            "Lowest Score",
            f"{lowest_percentage:.2f}%"
        )

    with col4:
        st.metric(
            "Average Marks",
            f"{data[subjects].mean().mean():.2f}"
        )