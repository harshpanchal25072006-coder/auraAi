import streamlit as st
import pandas as pd
from datetime import datetime
import os


def show_todo():

    st.title("TODO TEST")

    todos = load_todos()
    
TODO_FILE = "todos.csv"


def load_todos():

    if os.path.exists(TODO_FILE):

        return pd.read_csv(TODO_FILE)

    return pd.DataFrame(
        columns=[
            "id",
            "task",
            "status",
            "created_at"
        ]
    )


def save_todos(todos):

    todos.to_csv(
        TODO_FILE,
        index=False
    )


def show_todo():

    todos = load_todos()

    st.markdown(
        '<div class="main-title">My Todo List</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Manage your tasks and keep track of what is pending.'
        '</div>',
        unsafe_allow_html=True
    )

    st.subheader("➕ Add New Task")

    with st.form("add_task_form", clear_on_submit=True):

        col1, col2 = st.columns([4, 1])

        with col1:

            task_name = st.text_input(
                "Task",
                placeholder="Example: Complete Python assignment"
            )

        with col2:

            add_task = st.form_submit_button(
                "Add Task",
                use_container_width=True
            )

        if add_task:

            if task_name.strip() == "":

                st.warning("Please enter a task.")

            else:

                new_id = 1

                if not todos.empty:

                    new_id = int(todos["id"].max()) + 1

                new_task = pd.DataFrame(
                    [{
                        "id": new_id,
                        "task": task_name.strip(),
                        "status": "Pending",
                        "created_at": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    }]
                )

                todos = pd.concat(
                    [todos, new_task],
                    ignore_index=True
                )

                save_todos(todos)

                st.success("Task added successfully!")

                st.rerun()

    total_tasks = len(todos)

    pending_tasks = len(
        todos[todos["status"] == "Pending"]
    )

    completed_tasks = len(
        todos[todos["status"] == "Completed"]
    )

    st.markdown("---")

    st.subheader("📊 Task Statistics")

    stat_col1, stat_col2, stat_col3 = st.columns(3)

    with stat_col1:

        st.metric(
            "Total Tasks",
            total_tasks
        )

    with stat_col2:

        st.metric(
            "Pending",
            pending_tasks
        )

    with stat_col3:

        st.metric(
            "Completed",
            completed_tasks
        )

    st.markdown("---")

    st.subheader("📈 Task Statistics Graph")

    chart_data = pd.DataFrame({
        "Status": [
            "Total Tasks",
            "Pending",
            "Completed"
        ],
        "Tasks": [
            total_tasks,
            pending_tasks,
            completed_tasks
        ]
    })

    st.bar_chart(
        chart_data.set_index("Status"),
        use_container_width=True
    )

    st.markdown("---")

    search_col, filter_col = st.columns([2, 1])

    with search_col:

        search = st.text_input(
            "🔎 Search Task",
            placeholder="Search your task..."
        )

    with filter_col:

        filter_status = st.selectbox(
            "Filter",
            ["All", "Pending", "Completed"]
        )

    display_df = todos.copy()

    if search.strip():

        display_df = display_df[
            display_df["task"].str.contains(
                search,
                case=False,
                na=False
            )
        ]

    if filter_status != "All":

        display_df = display_df[
            display_df["status"] == filter_status
        ]

    st.markdown("---")

    st.subheader("📋 Your Tasks")

    if display_df.empty:

        st.info("No tasks found.")

    else:

        for _, row in display_df.iterrows():

            task_id = int(row["id"])
            task = row["task"]
            status = row["status"]
            created_at = row["created_at"]

            st.markdown(
                f"### {task}"
            )

            st.caption(
                f"Created: {created_at}"
            )

            if status == "Pending":

                st.warning("🟡 Pending")

            else:

                st.success("🟢 Completed")

            col1, col2 = st.columns(2)

            with col1:

                button_text = (
                    "✓ Done"
                    if status == "Pending"
                    else "↩ Undo"
                )

                if st.button(
                    button_text,
                    key=f"status_{task_id}",
                    use_container_width=True
                ):

                    new_status = (
                        "Completed"
                        if status == "Pending"
                        else "Pending"
                    )

                    todos.loc[
                        todos["id"] == task_id,
                        "status"
                    ] = new_status

                    save_todos(todos)

                    st.rerun()

            with col2:

                if st.button(
                    "🗑 Delete",
                    key=f"delete_{task_id}",
                    use_container_width=True
                ):

                    todos = todos[
                        todos["id"] != task_id
                    ].reset_index(drop=True)

                    save_todos(todos)

                    st.rerun()

            st.markdown("---")

    st.subheader("💾 CSV Data")

    st.write(
        "Your Todo List is automatically stored in `todos.csv`."
    )

    csv_data = todos.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="⬇️ Download Todo CSV",
        data=csv_data,
        file_name="todos.csv",
        mime="text/csv",
        use_container_width=True
    )

    with st.expander("📄 View CSV Data"):

        if todos.empty:

            st.info("CSV is currently empty.")

        else:

            st.dataframe(
                todos,
                use_container_width=True,
                hide_index=True
            )

