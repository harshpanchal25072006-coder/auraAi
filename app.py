import streamlit as st


from modules.marks import show_marks
from modules.performance import show_performance
from modules.house_price import show_house_price
from modules.calculator import show_calculator
from modules.todo import show_todo
from modules.ai_assistant import show_ai_assistant
from modules.image_optimizer import show_image_optimizer
from modules.quiz import show_quiz


from login import require_login

APP_PASSWORD = "aura@123"


require_login(APP_PASSWORD)
st.set_page_config(
    page_title="AURA",
    page_icon="🤖",
    layout="wide"
)

with st.sidebar:

    st.title("🤖 AURA")

    st.write("Personal AI Student Assistant")

    selected_page = st.radio(
        "Navigation",
        [
            "Home",
            "To Do List",
            "Student Marks",
            "Performance Stats",
            "House Price Predict",
            "Image Optimizer",
            "Quiz",
            "Calculator"
        ]
    )


if selected_page == "Home":
    show_ai_assistant()

elif selected_page == "Student Marks":
    show_marks()

elif selected_page == "Performance Stats":
    show_performance()

elif selected_page == "House Price Predict":
    show_house_price()

elif selected_page == "Image Optimizer":
    show_image_optimizer()

elif selected_page == "Quiz":
    show_quiz()

elif selected_page == "Calculator":
    show_calculator()

elif selected_page == "To Do List":
    show_todo()