import json
import os
import random
import time

import requests
import streamlit as st

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
MAX_QUESTIONS = 30
LETTERS = "ABCD"

DIFFICULTY_GUIDE = {
    "Easy": (
        "Easy: direct recall of facts, definitions and basic ideas. "
        "The correct answer should be fairly obvious and wrong options clearly different."
    ),
    "Intermediate": (
        "Intermediate: needs understanding, not just memory. Mix of concept and "
        "application questions, with wrong options that look reasonable."
    ),
    "Hard": (
        "Hard: needs analysis, inference or multi-step thinking. "
        "Wrong options should be very close to the right one and tempting."
    ),
}

PENALTY_OPTIONS = {
    "1/4 mark (0.25)": 0.25,
    "1/3 mark (0.33)": 0.33,
    "1/2 mark (0.50)": 0.5,
    "1 mark (1.00)": 1.0,
}


def read_setting(name):
    try:
        value = st.secrets[name]
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name)


def get_api_key():
    return read_setting("GEMINI_API_KEY") or read_setting("GOOGLE_API_KEY")


def get_models():
    custom = read_setting("GEMINI_MODEL")
    if custom:
        return [custom]
    return DEFAULT_MODELS


def build_prompt(topic, difficulty, count):
    return f"""Create a multiple choice quiz.

Source material or topic given by the student:
\"\"\"
{topic}
\"\"\"

Rules:
- Write exactly {count} questions.
- Difficulty level -> {DIFFICULTY_GUIDE[difficulty]}
- If the source looks like a passage, base the questions on it. If it is only a topic or a short description, use your general knowledge of that topic.
- Every question has exactly 4 options and exactly one correct option.
- No "all of the above" or "none of the above" options.
- Do not repeat questions.
- Give a one or two line explanation for the correct answer.

Reply with only a JSON array and nothing else. Each item must look like:
{{"question": "...", "options": ["...", "...", "...", "..."], "answer_index": 0, "explanation": "..."}}"""


def parse_questions(raw_text):
    text = raw_text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("The model did not return a question list.")

    items = json.loads(text[start:end + 1])
    questions = []

    for item in items:
        try:
            question = str(item["question"]).strip()
            options = [str(o).strip() for o in item["options"]]
            answer_index = int(item["answer_index"])
        except (KeyError, TypeError, ValueError):
            continue

        if not question or len(options) != 4 or len(set(options)) != 4:
            continue
        if not 0 <= answer_index < 4:
            continue

        correct_text = options[answer_index]
        random.shuffle(options)

        questions.append({
            "question": question,
            "options": options,
            "answer": options.index(correct_text),
            "explanation": str(item.get("explanation", "")).strip(),
        })

    return questions


def generate_questions(topic, difficulty, count):
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Add it to .streamlit/secrets.toml "
            "or set it as an environment variable."
        )

    payload = {
        "systemInstruction": {
            "parts": [{"text": "You are a careful quiz writer. You reply only with valid JSON."}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": build_prompt(topic, difficulty, count)}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 12000,
            "responseMimeType": "application/json",
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    last_error = "Unknown error"

    for model in get_models():
        try:
            response = requests.post(
                GEMINI_URL.format(model=model),
                headers=headers,
                json=payload,
                timeout=120,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not reach Gemini: {exc}")

        if response.status_code == 200:
            data = response.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
            except (KeyError, IndexError):
                last_error = "Gemini returned an empty answer."
                continue
            raw_text = "".join(part.get("text", "") for part in parts)
            questions = parse_questions(raw_text)
            if not questions:
                last_error = "Could not create questions from the reply."
                continue
            return questions[:count]

        try:
            last_error = response.json()["error"]["message"]
        except Exception:
            last_error = f"HTTP {response.status_code}"

        if response.status_code in (404, 429, 500, 503):
            continue
        raise RuntimeError(last_error)

    raise RuntimeError(last_error)


def calculate_result(questions, answers, negative_marking, penalty):
    correct = 0
    wrong = 0

    for index, question in enumerate(questions):
        if index not in answers:
            continue
        if answers[index] == question["answer"]:
            correct += 1
        else:
            wrong += 1

    total = len(questions)
    skipped = total - correct - wrong
    deduction = wrong * penalty if negative_marking else 0
    score = correct - deduction
    percentage = max(score, 0) / total * 100 if total else 0

    return {
        "correct": correct,
        "wrong": wrong,
        "skipped": skipped,
        "total": total,
        "deduction": deduction,
        "score": score,
        "percentage": percentage,
    }


def reset_quiz():
    for key in list(st.session_state.keys()):
        if key.startswith("quiz_"):
            del st.session_state[key]


def finish_quiz(reason):
    st.session_state["quiz_end_reason"] = reason
    st.session_state["quiz_finished_at"] = time.time()
    st.session_state["quiz_stage"] = "result"
    st.session_state["quiz_confirm_end"] = False
    st.rerun()


def clear_answer(index):
    st.session_state["quiz_answers"].pop(index, None)
    st.session_state.pop(f"quiz_q_{index}", None)


def timer_display(end_time):
    remaining = int(end_time - time.time())

    if remaining <= 0:
        finish_quiz("Time is up")

    minutes, seconds = divmod(remaining, 60)
    st.metric("⏱️ Time left", f"{minutes:02d}:{seconds:02d}")


if hasattr(st, "fragment"):
    timer_display = st.fragment(run_every=1)(timer_display)


def show_setup():
    st.subheader("📝 Create your quiz")

    topic = st.text_area(
        "Topic or paragraph for the quiz",
        height=160,
        placeholder=(
            "Paste a paragraph or describe a topic. "
            "Example: Photosynthesis is the process by which plants make food using sunlight..."
        ),
    )

    difficulty = st.radio(
        "Difficulty",
        ["Easy", "Intermediate", "Hard"],
        horizontal=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        count = st.number_input(
            "Number of questions",
            min_value=1,
            max_value=MAX_QUESTIONS,
            value=5,
            step=1,
        )

    with col2:
        timer_on = st.checkbox("Enable timer", value=True)
        minutes = None
        if timer_on:
            minutes = st.number_input(
                "Time limit (minutes)",
                min_value=1,
                max_value=180,
                value=max(2, int(count)),
                step=1,
            )

    negative_marking = st.checkbox("Enable negative marking", value=False)
    penalty = 0.0

    if negative_marking:
        penalty_label = st.selectbox(
            "Marks deducted for each wrong answer",
            list(PENALTY_OPTIONS.keys()),
        )
        penalty = PENALTY_OPTIONS[penalty_label]
        st.caption("Each correct answer gives +1. Skipped questions get 0.")
    else:
        st.caption("Each correct answer gives +1. Wrong or skipped answers get 0.")

    start = st.button("▶️ Start Quiz", type="primary", use_container_width=True)

    if not start:
        return

    if len(topic.strip()) < 10:
        st.warning("Please enter a topic or paragraph first.")
        return

    try:
        with st.spinner("Preparing your questions..."):
            questions = generate_questions(topic.strip(), difficulty, int(count))
    except Exception as exc:
        st.error(f"Could not create the quiz: {exc}")
        return

    if len(questions) < int(count):
        st.info(f"Only {len(questions)} valid questions could be created.")

    reset_quiz()
    st.session_state["quiz_questions"] = questions
    st.session_state["quiz_settings"] = {
        "difficulty": difficulty,
        "negative_marking": negative_marking,
        "penalty": penalty,
        "end_time": time.time() + minutes * 60 if timer_on else None,
        "started_at": time.time(),
    }
    st.session_state["quiz_answers"] = {}
    st.session_state["quiz_current"] = 0
    st.session_state["quiz_confirm_end"] = False
    st.session_state["quiz_stage"] = "running"
    st.rerun()


def show_running():
    questions = st.session_state["quiz_questions"]
    settings = st.session_state["quiz_settings"]
    answers = st.session_state["quiz_answers"]
    current = st.session_state["quiz_current"]
    total = len(questions)

    end_time = settings["end_time"]
    if end_time and time.time() >= end_time:
        finish_quiz("Time is up")

    top1, top2, top3 = st.columns(3)

    with top1:
        st.metric("Question", f"{current + 1} / {total}")
    with top2:
        st.metric("Answered", f"{len(answers)} / {total}")
    with top3:
        if end_time:
            timer_display(end_time)
        else:
            st.metric("⏱️ Time left", "No limit")

    st.progress((current + 1) / total)
    st.markdown("---")

    question = questions[current]
    st.markdown(f"### Q{current + 1}. {question['question']}")

    choice = st.radio(
        "Choose your answer",
        options=list(range(4)),
        format_func=lambda i: f"{LETTERS[i]}.  {question['options'][i]}",
        index=answers.get(current),
        key=f"quiz_q_{current}",
        label_visibility="collapsed",
    )

    if choice is not None:
        answers[current] = choice

    if current in answers:
        st.button(
            "Clear my answer",
            key=f"quiz_clear_{current}",
            on_click=clear_answer,
            args=(current,),
        )

    st.markdown("---")

    prev_col, next_col, end_col = st.columns(3)

    with prev_col:
        if st.button("⬅️ Previous", disabled=current == 0, use_container_width=True):
            st.session_state["quiz_current"] = current - 1
            st.rerun()

    with next_col:
        if current < total - 1:
            if st.button("Next ➡️", use_container_width=True):
                st.session_state["quiz_current"] = current + 1
                st.rerun()
        else:
            if st.button("✅ Submit", type="primary", use_container_width=True):
                finish_quiz("Submitted")

    with end_col:
        if st.button("🛑 End Quiz", use_container_width=True):
            st.session_state["quiz_confirm_end"] = True
            st.rerun()

    if st.session_state.get("quiz_confirm_end"):
        st.warning(
            f"End the quiz now? You have answered {len(answers)} of {total} questions. "
            "The rest will be counted as skipped."
        )
        yes_col, no_col = st.columns(2)
        with yes_col:
            if st.button("Yes, end quiz", use_container_width=True):
                finish_quiz("Ended early")
        with no_col:
            if st.button("No, continue", use_container_width=True):
                st.session_state["quiz_confirm_end"] = False
                st.rerun()


def show_result():
    questions = st.session_state["quiz_questions"]
    settings = st.session_state["quiz_settings"]
    answers = st.session_state["quiz_answers"]
    reason = st.session_state.get("quiz_end_reason", "Submitted")

    result = calculate_result(
        questions,
        answers,
        settings["negative_marking"],
        settings["penalty"],
    )

    st.subheader("🏁 Quiz Result")
    st.caption(f"{settings['difficulty']} level  |  {reason}")

    if result["percentage"] >= 80:
        st.success("🌟 Excellent work!")
    elif result["percentage"] >= 50:
        st.info("👍 Good effort, keep practising.")
    else:
        st.warning("📚 Needs more practice. Check the answers below.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Score", f"{result['score']:.2f} / {result['total']}")
    with c2:
        st.metric("Percentage", f"{result['percentage']:.1f}%")
    with c3:
        finished_at = st.session_state.get("quiz_finished_at", time.time())
        if settings["end_time"]:
            finished_at = min(finished_at, settings["end_time"])
        taken = max(0, int(finished_at - settings["started_at"]))
        st.metric("Time taken", f"{taken // 60:02d}:{taken % 60:02d}")

    c4, c5, c6, c7 = st.columns(4)
    with c4:
        st.metric("✅ Correct", result["correct"])
    with c5:
        st.metric("❌ Wrong", result["wrong"])
    with c6:
        st.metric("⚪ Skipped", result["skipped"])
    with c7:
        st.metric("➖ Negative marks", f"{result['deduction']:.2f}")

    st.markdown("---")
    st.subheader("📖 Review answers")

    for index, question in enumerate(questions):
        given = answers.get(index)

        if given is None:
            marker = "⚪"
        elif given == question["answer"]:
            marker = "✅"
        else:
            marker = "❌"

        with st.expander(f"{marker} Q{index + 1}. {question['question']}"):
            for position, option in enumerate(question["options"]):
                line = f"{LETTERS[position]}. {option}"
                if position == question["answer"]:
                    st.markdown(f"**{line}  ✔ correct answer**")
                elif position == given:
                    st.markdown(f"~~{line}~~  ← your answer")
                else:
                    st.markdown(line)

            if given is None:
                st.caption("You skipped this question.")
            if question["explanation"]:
                st.info(question["explanation"])

    st.markdown("---")
    again_col, new_col = st.columns(2)

    with again_col:
        if st.button("🔁 Retake same quiz", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key.startswith("quiz_q_"):
                    del st.session_state[key]
            minutes_total = None
            if settings["end_time"]:
                minutes_total = settings["end_time"] - settings["started_at"]
            settings["started_at"] = time.time()
            settings["end_time"] = time.time() + minutes_total if minutes_total else None
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_current"] = 0
            st.session_state["quiz_stage"] = "running"
            st.rerun()

    with new_col:
        if st.button("🆕 New quiz", type="primary", use_container_width=True):
            reset_quiz()
            st.rerun()


def show_quiz():

    st.title("🧠 Quiz")
    st.subheader("Turn any topic or paragraph into a practice quiz.")

    st.markdown("---")

    stage = st.session_state.get("quiz_stage", "setup")

    if stage != "setup" and "quiz_questions" not in st.session_state:
        reset_quiz()
        stage = "setup"

    if stage == "running":
        show_running()
    elif stage == "result":
        show_result()
    else:
        show_setup()