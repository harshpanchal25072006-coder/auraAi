import streamlit as st


def show_calculator():

    st.markdown(
        '<div class="main-title">🧮 Calculator</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Simple calculator using Python and Streamlit.'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:

        num1 = st.number_input(
            "Enter your first number",
            value=0.0
        )

    with col2:

        num2 = st.number_input(
            "Enter your second number",
            value=0.0
        )

    choice = st.selectbox(
        "Select your operation",
        [
            "Addition",
            "Subtraction",
            "Multiplication",
            "Division"
        ]
    )

    calculate = st.button(
        "🧮 Calculate",
        use_container_width=True
    )

    if calculate:

        if choice == "Addition":

            answer = num1 + num2

            st.success(
                f"YOUR ANSWER IS: {answer}"
            )

        elif choice == "Subtraction":

            answer = num1 - num2

            st.success(
                f"YOUR ANSWER IS: {answer}"
            )

        elif choice == "Multiplication":

            answer = num1 * num2

            st.success(
                f"YOUR ANSWER IS: {answer}"
            )

        elif choice == "Division":

            if num2 == 0:

                st.error(
                    "Cannot divide by zero!"
                )

            else:

                answer = num1 / num2

                st.success(
                    f"YOUR ANSWER IS: {answer}"
                )