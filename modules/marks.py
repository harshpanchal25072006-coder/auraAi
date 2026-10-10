import streamlit as st
import pandas as pd


def show_marks():

    st.markdown(
        '<div class="main-title">🎓 Student Marks & Scholarship</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Enter student details and marks to calculate percentage, grade, result and scholarship eligibility.'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="calculator-box">',
        unsafe_allow_html=True
    )

    st.subheader("👨‍🎓 Student Information")

    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input(
            "Student Name",
            placeholder="Enter student name"
        )

        age = st.number_input(
            "Age",
            min_value=1,
            max_value=100,
            value=18
        )

    with col2:
        course = st.text_input(
            "Course Name",
            placeholder="Example: BCA"
        )

    st.markdown("---")

    st.subheader("📚 Enter Subject Marks")

    col1, col2, col3 = st.columns(3)

    with col1:
        english = st.number_input(
            "English Marks",
            min_value=0,
            max_value=100,
            value=0
        )

        hindi = st.number_input(
            "Hindi Marks",
            min_value=0,
            max_value=100,
            value=0
        )

    with col2:
        math = st.number_input(
            "Math Marks",
            min_value=0,
            max_value=100,
            value=0
        )

        science = st.number_input(
            "Science Marks",
            min_value=0,
            max_value=100,
            value=0
        )

    with col3:
        physics = st.number_input(
            "Physics Marks",
            min_value=0,
            max_value=100,
            value=0
        )

    st.markdown("---")

    calculate_student = st.button(
        "📊 Calculate Result",
        use_container_width=True
    )

    if calculate_student:

        if name.strip() == "":
            st.warning("Please enter student name.")

        elif course.strip() == "":
            st.warning("Please enter course name.")

        else:

            total_marks = (
                english +
                hindi +
                math +
                science +
                physics
            )

            MAXIMUM_MARKS = 500

            percentage = (
                total_marks / MAXIMUM_MARKS
            ) * 100

            if percentage >= 40:
                result = "PASS"
            else:
                result = "FAIL"

            if percentage >= 90:
                grade = "A+"
            elif percentage >= 75:
                grade = "A"
            elif percentage >= 60:
                grade = "B"
            elif percentage >= 40:
                grade = "C"
            else:
                grade = "F"

            scholarship_eligible = (
                percentage >= 75
                and age > 18
                and age < 25
            )

            st.markdown("---")
            st.subheader("📋 Student Result")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Total Marks",
                    f"{total_marks}/500"
                )

            with col2:
                st.metric(
                    "Percentage",
                    f"{percentage:.2f}%"
                )

            with col3:
                st.metric(
                    "Grade",
                    grade
                )

            with col4:
                st.metric(
                    "Result",
                    result
                )

            if result == "PASS":
                st.success(
                    f"🎉 {name}, you have PASSED!"
                )
            else:
                st.error(
                    f"❌ {name}, you have FAILED."
                )

            if grade == "A+":
                st.success(
                    "🏆 Excellent! You got A+ grade."
                )
            elif grade == "A":
                st.success(
                    "🔥 Great performance! You got A grade."
                )
            elif grade == "B":
                st.info(
                    "👍 Good performance! You got B grade."
                )
            elif grade == "C":
                st.warning(
                    "📚 You passed, but there is room for improvement."
                )
            else:
                st.error(
                    "You need to improve your marks."
                )

            st.markdown("---")
            st.subheader("🎓 Scholarship")

            if scholarship_eligible:

                st.success(
                    "✅ You are eligible for the scholarship!"
                )

                st.write(
                    "Eligibility: Percentage ≥ 75% and age between 19 and 24."
                )

                scholarship_code = st.text_input(
                    "Enter Scholarship Code",
                    type="password",
                    placeholder="Example: sch100"
                )

                scholarship_codes = [
                    "sch100",
                    "sch200",
                    "sch300"
                ]

                if st.button(
                    "🎁 Verify Scholarship Code",
                    use_container_width=True
                ):

                    if scholarship_code in scholarship_codes:
                        st.success(
                            "🎉 Scholarship verified successfully!"
                        )
                        st.balloons()

                        st.metric(
                            "Scholarship Benefit",
                            "20% OFF"
                        )

                    else:
                        st.error(
                            "❌ Invalid scholarship code."
                        )

            else:

                st.info(
                    "You are not eligible for the scholarship."
                )

                st.write(
                    "Required: Percentage ≥ 75% and age must be between 19 and 24."
                )

            st.markdown("---")
            st.subheader("📊 Subject-wise Performance")

            subject_data = pd.DataFrame(
                {
                    "Subject": [
                        "English",
                        "Hindi",
                        "Math",
                        "Science",
                        "Physics"
                    ],
                    "Marks": [
                        english,
                        hindi,
                        math,
                        science,
                        physics
                    ]
                }
            )

            st.bar_chart(
                subject_data.set_index("Subject")
            )

            st.markdown("---")
            st.subheader("📝 Student Summary")

            st.write(f"**Name:** {name}")
            st.write(f"**Age:** {age}")
            st.write(f"**Course:** {course}")
            st.write(f"**Total Marks:** {total_marks}/500")
            st.write(f"**Percentage:** {percentage:.2f}%")
            st.write(f"**Grade:** {grade}")
            st.write(f"**Result:** {result}")

    st.markdown(
        '</div>',
        unsafe_allow_html=True
    )