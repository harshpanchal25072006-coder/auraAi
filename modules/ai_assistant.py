import os
import re
import ast
import json
import time
import operator
import pandas as pd
import streamlit as st
from openai import OpenAI

BUILD = "v10 (no-API calculator + greetings + AI toggle)"
TODO_FILE = "todos.csv"
STUDENT_FILE = "students.csv"
MODEL = "openrouter/free"
COLUMNS = ["id", "task", "status", "created_at"]

SUBJECTS = ["english", "hindi", "math", "science", "physics"]
MAX_MARKS = 500
PASS_PERCENT = 40
SCHOLARSHIP_PERCENT = 75
SCHOLARSHIP_AGE_MIN = 19
SCHOLARSHIP_AGE_MAX = 24
MAX_TABLE_ROWS = 30

QUOTED = re.compile(r'["“”](.+?)["“”]')
PRONOUNS = re.compile(r"\b(it|this|that|isko|usko|ise|wahi|last|ye|yeh|wo|vo)\b", re.I)

PERF_HINT = (
    "\n\n---\n📈 Zyada stats (charts, grade distribution, student search) ke liye "
    "**Performance tab** pe jao. Tumhari file wahan auto-load mil jayegi."
)


def add_perf_hint(answer):
    # student actions jab sahi chalte hain tab flag set karte hain
    if st.session_state.pop("perf_hint", False):
        return answer + PERF_HINT
    return answer


def load_todos():
    if os.path.exists(TODO_FILE):
        return pd.read_csv(TODO_FILE)
    return pd.DataFrame(columns=COLUMNS)


def save_todos(todos):
    todos.to_csv(TODO_FILE, index=False)


def todos_as_text():
    todos = load_todos()
    if todos.empty:
        return "No tasks."
    return "\n".join(
        f"{int(r['id'])}. {r['task']} — {r['status']}"
        for _, r in todos.iterrows()
    )


def clean_title(raw, user_text=""):
    # agar user ne double quotes me naam diya hai to wahi task hai
    for source in (user_text, raw or ""):
        quoted = QUOTED.search(source)
        if quoted and quoted.group(1).strip():
            return quoted.group(1).strip()

    title = (raw or "").strip()
    title = re.sub(r"^(by\s+(the\s+)?name\s+of|named|called|naam\s+se)\s+", "", title, flags=re.I)
    title = re.sub(r"\s+(ke\s+)?naam\s+se$", "", title, flags=re.I)
    title = re.sub(r"\s+(and\s+)?(its\s+)?(incomplete|pending)$", "", title, flags=re.I)
    return title.strip(" \"'“”‘’")


def find_task(todos, task=None, task_id=None, use_last=False):
    if todos.empty:
        return None, "Tumhari To-Do list khali hai."

    if task_id is not None:
        try:
            tid = int(task_id)
        except (TypeError, ValueError):
            return None, "Task number samajh nahi aaya."
        m = todos[todos["id"] == tid]
        if m.empty:
            return None, f"Task number {tid} nahi mila."
        return m.index[0], None

    if task:
        m = todos[
            todos["task"].astype(str).str.contains(
                task, case=False, na=False, regex=False
            )
        ]
        if m.empty:
            return None, f'"{task}" naam ka koi task nahi mila.'
        if len(m) > 1:
            names = ", ".join(f"{int(r['id'])}. {r['task']}" for _, r in m.iterrows())
            return None, f"Kai tasks match hue: {names}. Task number batao."
        return m.index[0], None

    # "it", "isko" jaise words ke liye last wala task
    if use_last:
        last_id = st.session_state.get("last_task_id")
        if last_id is not None:
            m = todos[todos["id"] == last_id]
            if not m.empty:
                return m.index[0], None
        # last task yaad nahi, par list me sirf ek hi task hai to wahi hoga
        if len(todos) == 1:
            return todos.index[0], None

    lines = "\n".join(
        f"{int(r['id'])}. {r['task']} — {r['status']}" for _, r in todos.iterrows()
    )
    return None, "Kaunsa task? Naam ya number batao.\n\n" + lines


def locate(p):
    todos = load_todos()
    idx, err = find_task(todos, p.get("task"), p.get("task_id"), p.get("use_last"))
    return todos, idx, err


def act_add_task(p):
    title = clean_title(p.get("task"), p.get("raw", ""))
    if not title:
        return "Task ka naam samajh nahi aaya. Dobara batao, jaise: add task \"Python padhna\""

    todos = load_todos()
    new_id = 1 if todos.empty else int(todos["id"].max()) + 1
    row = pd.DataFrame([{
        "id": new_id,
        "task": title,
        "status": "Pending",
        "created_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }])
    save_todos(pd.concat([todos, row], ignore_index=True))

    saved = load_todos()
    if saved[saved["id"] == new_id].empty:
        return "❌ Task save nahi ho paya. Kuch change nahi hua."

    st.session_state.last_task_id = new_id
    return f'✅ Task add ho gaya: "{title}" (#{new_id})'


def set_status(p, status):
    todos, idx, err = locate(p)
    if err:
        return err
    tid = int(todos.loc[idx, "id"])
    name = todos.loc[idx, "task"]
    todos.loc[idx, "status"] = status
    save_todos(todos)

    check = load_todos()
    now = check.loc[check["id"] == tid, "status"]
    if now.empty or now.iloc[0] != status:
        return "❌ Status save nahi ho paya. Kuch change nahi hua."

    st.session_state.last_task_id = tid
    return f'✅ "{name}" ab {status} hai.'


def act_complete_task(p):
    return set_status(p, "Completed")


def act_pending_task(p):
    return set_status(p, "Pending")


def act_delete_task(p):
    todos, idx, err = locate(p)
    if err:
        return err
    tid = int(todos.loc[idx, "id"])
    name = todos.loc[idx, "task"]
    save_todos(todos.drop(idx).reset_index(drop=True))

    check = load_todos()
    if not check[check["id"] == tid].empty:
        return "❌ Delete nahi ho paya. Kuch change nahi hua."

    st.session_state.last_task_id = None
    return f'🗑 "{name}" delete ho gaya.'


def act_delete_all(p):
    todos = load_todos()
    if todos.empty:
        return "Delete karne ke liye koi task hai hi nahi."
    save_todos(pd.DataFrame(columns=COLUMNS))
    st.session_state.last_task_id = None
    return "🗑 Saare tasks delete ho gaye."


def act_rename_task(p):
    new_title = clean_title(p.get("new_task"), "")
    if not new_title:
        return "Naya naam samajh nahi aaya."
    todos, idx, err = locate(p)
    if err:
        return err
    old = todos.loc[idx, "task"]
    todos.loc[idx, "task"] = new_title
    save_todos(todos)
    st.session_state.last_task_id = int(todos.loc[idx, "id"])
    return f'✏️ "{old}" ka naam ab "{new_title}" hai.'


def act_show_tasks(p):
    todos = load_todos()
    if todos.empty:
        return "📋 To-Do list abhi khali hai."
    total = len(todos)
    done = int((todos["status"] == "Completed").sum())
    header = f"📋 Total {total} tasks (Pending: {total - done}, Completed: {done})"

    raw = (p.get("raw") or "").lower()
    shown = todos
    if re.search(r"\bpending\b|\bincomplete\b", raw):
        shown = todos[todos["status"] == "Pending"]
    elif re.search(r"\bcompleted\b|\bdone\b", raw):
        shown = todos[todos["status"] == "Completed"]

    if shown.empty:
        return header + "\n\nIs filter me koi task nahi hai."
    lines = "\n".join(
        f"{int(r['id'])}. {r['task']} — {r['status']}" for _, r in shown.iterrows()
    )
    return header + "\n\n" + lines


def act_task_status(p):
    todos, idx, err = locate(p)
    if err:
        return err
    r = todos.loc[idx]
    return f'"{r["task"]}" ka status: {r["status"]}'


def act_download_csv(p):
    st.session_state.attach = "todos"
    if load_todos().empty:
        return "📥 CSV abhi khali hai (sirf headings hain). Button neeche hai."
    return "📥 CSV tayyar hai, neeche button se download karo."


# =====================================================
# STUDENTS
# =====================================================

ALIASES = {
    "name": "name", "student": "name", "student_name": "name", "studentname": "name", "full_name": "name",
    "age": "age",
    "course": "course", "course_name": "course",
    "english": "english", "english_marks": "english", "eng": "english",
    "hindi": "hindi", "hindi_marks": "hindi",
    "math": "math", "maths": "math", "mathematics": "math", "math_marks": "math", "maths_marks": "math",
    "science": "science", "science_marks": "science", "sci": "science",
    "physics": "physics", "physics_marks": "physics", "phy": "physics",
}

SAMPLE_CSV = (
    "name,age,course,english,hindi,math,science,physics\n"
    "Rahul Sharma,20,BCA,80,70,90,85,75\n"
    "Priya Singh,22,BCA,92,88,95,90,94\n"
    "Amit Kumar,26,BCA,78,80,82,79,81\n"
    "Neha Verma,19,BCA,35,40,30,38,33\n"
)

NO_STUDENTS = "📂 Abhi koi student CSV load nahi hai. Upar \"Student marks CSV upload karo\" se file daalo."


def fmt(x):
    if pd.isna(x):
        return "-"
    x = float(x)
    return str(int(x)) if x == int(x) else f"{x:.1f}"


def normalize_students(raw):
    mapping = {}
    for col in raw.columns:
        key = re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_")
        canon = ALIASES.get(key)
        if canon and canon not in mapping.values():
            mapping[col] = canon

    df = raw[list(mapping)].rename(columns=mapping)
    missing = [c for c in ["name"] + SUBJECTS if c not in df.columns]
    if missing:
        found = ", ".join(str(c) for c in raw.columns)
        return None, (
            f"❌ Ye columns nahi mile: {', '.join(missing)}. "
            f"Tumhari file me ye columns hain: {found}. "
            "Chahiye: name, english, hindi, math, science, physics (age aur course optional)."
        )

    if "age" not in df.columns:
        df["age"] = float("nan")
    if "course" not in df.columns:
        df["course"] = ""

    df = df.dropna(how="all").reset_index(drop=True)
    df["name"] = df["name"].fillna("").astype(str).str.strip()
    df["course"] = df["course"].fillna("").astype(str).str.strip()
    return df[["name", "age", "course"] + SUBJECTS], None


def load_students():
    if not os.path.exists(STUDENT_FILE):
        return None
    try:
        df = pd.read_csv(STUDENT_FILE)
    except Exception:
        return None
    df["name"] = df["name"].fillna("").astype(str)
    df["course"] = df["course"].fillna("").astype(str)
    return df


def grade_of(p):
    if pd.isna(p):
        return "-"
    if p >= 90:
        return "A+"
    if p >= 75:
        return "A"
    if p >= 60:
        return "B"
    if p >= 40:
        return "C"
    return "F"


def scholarship_of(percentage, age, problem):
    # marks.py wala hi rule: percentage >= 75 aur 18 < age < 25
    if problem:
        return "Unknown", "data me problem hai"
    if pd.isna(age):
        return "Unknown", "age CSV me nahi hai"
    reasons = []
    if percentage < SCHOLARSHIP_PERCENT:
        reasons.append(f"percentage {percentage:.2f}% hai, {SCHOLARSHIP_PERCENT}% ya zyada chahiye")
    if not (SCHOLARSHIP_AGE_MIN - 1 < age < SCHOLARSHIP_AGE_MAX + 1):
        reasons.append(f"age {fmt(age)} hai, {SCHOLARSHIP_AGE_MIN} se {SCHOLARSHIP_AGE_MAX} ke beech chahiye")
    if reasons:
        return "Not eligible", " aur ".join(reasons)
    return "Eligible", (
        f"percentage {SCHOLARSHIP_PERCENT}% ya zyada hai aur age {SCHOLARSHIP_AGE_MIN}-{SCHOLARSHIP_AGE_MAX} hai"
    )


def compute_results(df):
    out = df.copy()
    for sub in SUBJECTS:
        out[sub] = pd.to_numeric(out[sub], errors="coerce")
    out["age"] = pd.to_numeric(out["age"], errors="coerce")

    problems = []
    for _, r in out.iterrows():
        issues = []
        if not str(r["name"]).strip():
            issues.append("name missing")
        for sub in SUBJECTS:
            v = r[sub]
            if pd.isna(v):
                issues.append(f"{sub} marks missing")
            elif v < 0 or v > 100:
                issues.append(f"{sub} marks invalid ({fmt(v)})")
        problems.append("; ".join(issues))
    out["problem"] = problems

    ok = out["problem"] == ""
    out["total"] = out[SUBJECTS].sum(axis=1).where(ok)
    out["percentage"] = out["total"] / MAX_MARKS * 100
    out["grade"] = out["percentage"].map(grade_of)
    out["result"] = out["percentage"].map(
        lambda p: "Invalid data" if pd.isna(p) else ("PASS" if p >= PASS_PERCENT else "FAIL")
    )

    sch = [scholarship_of(r["percentage"], r["age"], r["problem"]) for _, r in out.iterrows()]
    out["scholarship"] = [x[0] for x in sch]
    out["scholarship_reason"] = [x[1] for x in sch]
    return out


def student_results():
    df = load_students()
    if df is None or df.empty:
        return None
    return compute_results(df)


def results_csv_bytes():
    res = student_results()
    if res is None:
        return b""
    cols = ["name", "age", "course"] + SUBJECTS + ["total", "percentage", "grade", "result", "scholarship", "problem"]
    out = res[cols].copy()
    out["percentage"] = out["percentage"].round(2)
    return out.to_csv(index=False).encode("utf-8")


def ingest_upload(uploaded):
    filename = str(getattr(uploaded, "name", "")).lower()
    try:
        if filename.endswith((".xlsx", ".xls")):
            raw = pd.read_excel(uploaded)
        else:
            try:
                raw = pd.read_csv(uploaded)
            except UnicodeDecodeError:
                uploaded.seek(0)
                raw = pd.read_csv(uploaded, encoding="latin-1")
    except ImportError:
        return False, "❌ Excel padhne ke liye `pip install openpyxl` chalao, ya file ko CSV me save karke daalo."
    except Exception as e:
        return False, f"❌ File padh nahi paya: {e}"

    # sirf student-marks file hi students.csv banegi, baaki CSV yahin reject ho jayegi
    df, err = normalize_students(raw)
    if err:
        return False, err
    if df.empty:
        return False, "❌ CSV me koi student row nahi mili."

    df.to_csv(STUDENT_FILE, index=False)
    res = compute_results(df)
    bad = int((res["problem"] != "").sum())

    msg = f"✅ {len(df)} students load ho gaye."
    msg += " 📈 Ye file Performance tab me bhi auto-load ho jayegi."
    if bad:
        msg += f" ⚠️ {bad} rows me data problem hai (marks missing ya 0-100 se bahar), unka result nahi niklega."
    if df["age"].isna().all():
        msg += " ⚠️ age column nahi mila, isliye scholarship check nahi ho payega."
    return True, msg


def name_key(text):
    cleaned = str(text).lower().replace("'s", "").replace("’s", "")
    return " ".join(re.findall(r"[^\s,.;:!?\"'()\[\]{}|/\\-]+", cleaned))


def student_matches(df, text):
    if df is None or df.empty:
        return []
    norm = name_key(text)
    words = set(norm.split())

    exact = []
    for i, n in df["name"].items():
        key = name_key(n)
        if key and f" {key} " in f" {norm} ":
            exact.append((len(key), i))
    if exact:
        longest = max(length for length, _ in exact)
        return [i for length, i in exact if length == longest]

    scored = []
    for i, n in df["name"].items():
        tokens = [t for t in name_key(n).split() if len(t) >= 3]
        score = sum(1 for t in tokens if t in words)
        if score:
            scored.append((score, i))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    return [i for score, i in scored if score == best]


def describe(df, i):
    r = df.loc[i]
    extra = ", ".join(x for x in [f"age {fmt(r['age'])}" if not pd.isna(r["age"]) else "", r["course"]] if x)
    return f"{r['name']}" + (f" ({extra})" if extra else "")


def resolve_student(df, p):
    raw = p.get("raw", "")
    asked = p.get("student")
    cand = student_matches(df, str(asked)) if asked else []
    if not cand:
        cand = student_matches(df, raw)

    last = st.session_state.get("last_student")
    if not cand and not asked and last and PRON_STU.search(raw.lower()):
        cand = student_matches(df, last)

    if not cand:
        if asked:
            return None, f'"{asked}" naam ka koi student CSV me nahi mila.'
        return None, "Kaunsa student? CSV me jo naam hai wahi batao."
    if len(cand) > 1:
        names = ", ".join(describe(df, i) for i in cand[:6])
        return None, (
            f"Kai students match hue: {names}. Poora naam batao. "
            "(Agar naam bilkul same hain to CSV me alag kar do, taaki galat student ka data na bataun.)"
        )
    return cand[0], None


def md_table(headers, rows):
    def cell(x):
        return str(x).replace("|", "\\|")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def short_names(names, limit=10):
    names = list(names)
    text = ", ".join(names[:limit])
    if len(names) > limit:
        text += f" (+{len(names) - limit} aur)"
    return text


def class_stats(res):
    ok = res[res["problem"] == ""]
    if ok.empty:
        return ["Kisi student ka data poora nahi hai, isliye stats nahi nikle."]

    passed = ok[ok["result"] == "PASS"]
    failed = ok[ok["result"] == "FAIL"]
    eligible = ok[ok["scholarship"] == "Eligible"]
    unknown = int((ok["scholarship"] == "Unknown").sum())
    top = ok["percentage"].max()
    low = ok["percentage"].min()

    lines = [f"- ✅ Pass: {len(passed)} | ❌ Fail: {len(failed)}"]
    if len(failed):
        lines.append(f"- Fail hue: {short_names(failed['name'])}")
    lines.append(
        f"- 🎓 Scholarship milegi: {len(eligible)}"
        + (f" — {short_names(eligible['name'])}" if len(eligible) else "")
    )
    if unknown:
        lines.append(f"- ⚠️ {unknown} students ki scholarship check nahi hui (age CSV me nahi hai)")
    lines.append(f"- Average: {ok['percentage'].mean():.2f}%")
    lines.append(f"- Topper: {short_names(ok.loc[ok['percentage'] == top, 'name'], 3)} ({top:.2f}%)")
    lines.append(f"- Sabse kam: {short_names(ok.loc[ok['percentage'] == low, 'name'], 3)} ({low:.2f}%)")
    return lines


def act_calculate_results(p):
    res = student_results()
    if res is None:
        return NO_STUDENTS
    st.session_state.perf_hint = True
    st.session_state.attach = "results"

    bad = int((res["problem"] != "").sum())
    head = f"📊 {len(res)} students ka result"
    if bad:
        head += f" ({bad} rows me data problem, unka result nahi nikla)"

    rows = []
    for _, r in res.head(MAX_TABLE_ROWS).iterrows():
        if r["problem"]:
            rows.append([r["name"] or "(naam nahi)", "-", "-", "-", f"⚠️ {r['problem']}", "-"])
        else:
            rows.append([
                r["name"], f"{fmt(r['total'])}/{MAX_MARKS}", f"{r['percentage']:.2f}%",
                r["grade"], r["result"], r["scholarship"],
            ])
    table = md_table(["Name", "Total", "%", "Grade", "Result", "Scholarship"], rows)

    more = ""
    if len(res) > MAX_TABLE_ROWS:
        more = f"\n\nAur {len(res) - MAX_TABLE_ROWS} students hain. Poora result neeche CSV me hai."
    return head + "\n\n" + "\n".join(class_stats(res)) + "\n\n" + table + more


def act_students_summary(p):
    res = student_results()
    if res is None:
        return NO_STUDENTS
    st.session_state.perf_hint = True
    bad = int((res["problem"] != "").sum())
    head = f"📊 Total {len(res)} students" + (f" ({bad} ka data adhura hai)" if bad else "")
    return head + "\n\n" + "\n".join(class_stats(res))


def act_scholarship_list(p):
    res = student_results()
    if res is None:
        return NO_STUDENTS
    st.session_state.perf_hint = True
    want = "Not eligible" if p.get("which") == "not_eligible" else "Eligible"
    rows = res[res["scholarship"] == want]
    unknown = int((res["scholarship"] == "Unknown").sum())

    title = "✅ Scholarship ke liye eligible students" if want == "Eligible" else "❌ Scholarship ke liye eligible nahi"
    if rows.empty:
        text = f"{title}: koi nahi."
    else:
        lines = []
        for _, r in rows.iterrows():
            if want == "Eligible":
                lines.append(f"- {r['name']} — {r['percentage']:.2f}%, age {fmt(r['age'])}")
            else:
                lines.append(f"- {r['name']} — {r['scholarship_reason']}")
        text = f"{title} ({len(rows)}):\n\n" + "\n".join(lines)
    if unknown:
        text += f"\n\n⚠️ {unknown} students ka data adhura hai (marks ya age missing), unki eligibility nahi nikal sakta."
    return text


def act_student_info(p):
    df = load_students()
    if df is None or df.empty:
        return NO_STUDENTS
    i, err = resolve_student(df, p)
    if err:
        return err

    res = compute_results(df)
    r = res.loc[i]
    st.session_state.last_student = r["name"]

    title = f"👨‍🎓 **{describe(df, i)}**"
    if r["problem"]:
        return (
            f"{title}\n\n⚠️ Is student ke data me problem hai: {r['problem']}. "
            "Isliye result, grade aur scholarship nahi nikal sakta. CSV theek karke dobara upload karo."
        )

    st.session_state.perf_hint = True

    field = p.get("field")
    first = {
        "scholarship": {
            "Eligible": f"{r['name']} scholarship ke liye **ELIGIBLE** hai ✅",
            "Not eligible": f"{r['name']} scholarship ke liye **eligible nahi** hai ❌",
            "Unknown": f"{r['name']} ki scholarship eligibility nahi nikal sakta ⚠️",
        }[r["scholarship"]],
        "marks": f"{r['name']} ke total marks {fmt(r['total'])}/{MAX_MARKS} hain ({r['percentage']:.2f}%).",
        "result": f"{r['name']} ka result: **{r['result']}** ({r['percentage']:.2f}%, grade {r['grade']}).",
    }.get(field)

    marks = ", ".join(f"{sub.capitalize()} {fmt(r[sub])}" for sub in SUBJECTS)
    lines = [
        f"- **Marks:** {marks}",
        f"- **Total:** {fmt(r['total'])}/{MAX_MARKS} | **Percentage:** {r['percentage']:.2f}% | **Grade:** {r['grade']} | **Result:** {r['result']}",
    ]
    sign = {"Eligible": "✅", "Not eligible": "❌", "Unknown": "⚠️"}[r["scholarship"]]
    lines.append(f"- **Scholarship:** {sign} {r['scholarship']} ({r['scholarship_reason']})")
    if r["scholarship"] == "Eligible":
        lines.append("- Scholarship code verify karna ho to \"Student Marks\" page pe karo.")

    body = "\n".join(lines)
    return (first + "\n\n" if first else "") + title + "\n\n" + body


def act_download_results(p):
    res = student_results()
    if res is None:
        return NO_STUDENTS
    st.session_state.attach = "results"
    return "📥 Result CSV tayyar hai, neeche button se download karo."


def act_help(p):
    return (
        "🤖 Main ye kar sakta hu:\n\n"
        "**To-Do:** `add task \"Python padhna\"`, `mark it as done`, `undo`, `delete task 2`, "
        "`delete all tasks`, `show tasks`, `csv download karo`\n\n"
        "**Student data:** chat box ke 📎 se CSV ya Excel attach karo, phir poochho: "
        "`kitne pass kitne fail`, `kitno ko scholarship mil rhi h`, `topper kaun hai`, "
        "`Rahul ke marks kitne aaye`, `sabka result calculate karo`, `student result csv download karo`\n\n"
        "**Calculator:** `25*4+10 kitna hua`\n\n"
        "Jo kaam isme nahi hai, uske liye saaf bol dunga ki nahi ho sakta."
    )


def act_upload_help(p):
    return (
        "📎 Haan! Chat box ke left me **📎 (attach)** icon hai. Usse student CSV ya Excel (.xlsx) attach karo, "
        "aur chaho to saath me sawaal bhi likho, jaise: `isme kitne fail hain, kitno ko scholarship milegi`.\n\n"
        "File me ye columns chahiye: name, english, hindi, math, science, physics (age optional, scholarship ke liye zaroori).\n\n"
        "Agar 📎 icon nahi dikh raha to Streamlit purana hai: `pip install -U streamlit` chalao. "
        "Tab tak page ke upar \"📂 Student marks CSV upload karo\" wala uploader use karo."
    )


OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


# eval() use nahi kiya, ye sirf numbers aur operators allow karta hai
def safe_eval(node):
    if isinstance(node, ast.Expression):
        return safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left = safe_eval(node.left)
        right = safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise OverflowError("power bahut bada hai")
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](safe_eval(node.operand))
    raise ValueError("unsupported expression")


def clean_expr(expr):
    # "03483094" jaise leading zero Python me error dete hain, unhe hata do (1.05 aur 0.5 safe rehte hain)
    expr = expr.replace("^", "**")
    return re.sub(r"(?<![\d.])0+(?=\d)", "", expr).strip()


def evaluate(expr):
    return safe_eval(ast.parse(clean_expr(expr), mode="eval"))


WORD_OPS = (
    (r"\bmultiplied\s+by\b|\btimes\b", "*"),
    (r"\bdivided\s+by\b", "/"),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
)
DATE_LIKE = re.compile(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b")
EXPR_CHUNK = re.compile(r"[\d.(][\d\s.+\-*/%()]*")
HAS_OPERATION = re.compile(r"[\d)]\s*(?:\*\*|[+\-*/%])\s*[\d(\-]")


def extract_expression(text):
    # message me se math expression nikalta hai (bina API ke). Na mile to None.
    t = text.lower()
    for pat, sym in WORD_OPS:
        t = re.sub(pat, f" {sym} ", t)
    t = t.replace("×", "*").replace("÷", "/").replace("^", "**")
    t = re.sub(r"(?<=\d)\s*x\s*(?=\d)", " * ", t)
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", t)

    if DATE_LIKE.search(t):
        return None

    best = None
    for m in EXPR_CHUNK.finditer(t):
        chunk = re.sub(r"\s+", " ", m.group(0).strip().rstrip("+-*/% "))
        if not HAS_OPERATION.search(chunk):
            continue
        try:
            evaluate(chunk)
        except (ZeroDivisionError, OverflowError):
            pass  # sahi expression hai, act_calculate saaf message dega
        except Exception:
            continue
        if best is None or len(chunk) > len(best):
            best = chunk
    return best


def act_calculate(p):
    expr = (p.get("expression") or "").strip()
    if not expr:
        return "Kya calculate karna hai? Expression samajh nahi aaya."
    try:
        result = evaluate(expr)
    except ZeroDivisionError:
        return "🧮 Zero se divide nahi ho sakta."
    except OverflowError:
        return "🧮 Ye number bahut bada hai, calculate nahi kar sakta."
    except Exception:
        return f'"{expr}" calculate nahi ho paya. Sirf numbers aur + - * / ** % chalte hain.'

    if isinstance(result, float):
        result = round(result, 10)
        if result.is_integer():
            result = int(result)

    text = f"🧮 {expr} = {result}"
    if isinstance(result, int) and abs(result) >= 1000:
        text += f" ({result:,})"
    return text


# ---------- greetings: bina API ke jawab ----------

GREETING = re.compile(
    r"^\s*(?:hi+|hello+|hey+|hlo|helo|namaste|namaskar|sup|yo|"
    r"good\s+(?:morning|afternoon|evening))\b[\s,!.?]*(?:aura|bhai|yaar|ji)?[\s!.?]*$",
    re.I,
)
THANKS = re.compile(
    r"^\s*(?:thanks?|thank\s+you|thx|ty|thanku|shukriya|dhanyavaad|dhanyawad)\b[\s,!.]*(?:aura|bhai|yaar)?[\s!.]*$",
    re.I,
)
BYE = re.compile(r"^\s*(?:bye+|goodbye|good\s*night|tata|alvida|see\s+you)\b[\s!.]*$", re.I)


def act_greet(p):
    raw = p.get("raw") or ""
    if THANKS.match(raw):
        return "😊 Koi baat nahi! Aur kuch chahiye to bolo."
    if BYE.match(raw):
        return "👋 Bye! Phir milte hain."
    return (
        "👋 Hello! Main AURA hu. Tasks manage kar sakta hu, student CSV ka result aur scholarship bata sakta hu, "
        "aur calculator bhi hu. `help` likho to poori list dikhaunga."
    )


# naya feature jodna ho to upar function likho aur yahan ek line add kar do
ACTIONS = {
    "add_task": (act_add_task, "naya task add karna. params: task"),
    "complete_task": (act_complete_task, "task ko done/complete mark karna. params: task | task_id | use_last"),
    "pending_task": (act_pending_task, "task ko wapas pending karna / undo. params: task | task_id | use_last"),
    "delete_task": (act_delete_task, "ek task delete karna. params: task | task_id | use_last"),
    "delete_all_tasks": (act_delete_all, "saare tasks delete karna"),
    "rename_task": (act_rename_task, "task ka naam badalna. params: task | task_id | use_last, new_task"),
    "show_tasks": (act_show_tasks, "task list dikhana, total tasks batana"),
    "task_status": (act_task_status, "kisi task ka status poochna (done hai ya nahi). params: task | task_id | use_last"),
    "download_csv": (act_download_csv, "todos ki CSV file download karna"),
    "calculate_results": (act_calculate_results, "uploaded student CSV ka sabka result calculate karna (total, percentage, grade, pass/fail, scholarship)"),
    "student_info": (act_student_info, "kisi ek student ke marks / result / scholarship eligibility batana. params: student (naam), field (scholarship | marks | result | all)"),
    "scholarship_list": (act_scholarship_list, "kaun kaun scholarship ke liye eligible hai ya nahi hai. params: which (eligible | not_eligible)"),
    "students_summary": (act_students_summary, "class ka summary: topper, kitne pass/fail, average, total students"),
    "download_results": (act_download_results, "student results ki CSV download karna"),
    "help": (act_help, "user poochhe ki tum kya kya kar sakte ho / help / features"),
    "upload_help": (act_upload_help, "user poochhe ki file/CSV attach ya upload kaise karte hain, ya kar sakte hain ya nahi"),
    "calculate": (act_calculate, "math calculation. params: expression (sirf numbers aur + - * / ** %)"),
    "greet": (act_greet, "hello / hi / thanks / bye jaisi chhoti greeting"),
}

NEEDS_TARGET = {"complete_task", "pending_task", "task_status", "rename_task"}
VALID_ACTIONS = set(ACTIONS) | {"chat", "unsupported"}

NOT_UNDERSTOOD = (
    "❌ Mujhe ye command samajh nahi aayi, isliye maine kuch change nahi kiya. "
    "Thoda seedha bolo, jaise: add task \"Python padhna\" / WAKE UP task done kar do / "
    "delete task 2 / csv download karo."
)


# ---------- rules: clear commands yahin pakad lete hain ----------

ADD_START = re.compile(
    r"^\s*(?:(?:ok|okay|please|plz|pls|hey|aura|bhai|yaar)[,\s]+)*"
    r"(?:add|create|ek\s+(?:naya\s+)?task|naya\s+task|new\s+task|task\s+add)\b",
    re.I,
)

ADD_PATTERNS = [
    r"(?:add|create)\s+(?:a\s+|an\s+)?(?:new\s+)?task\s+(?:named\s+|called\s+|by\s+(?:the\s+)?name\s+of\s+)?(.+)",
    r"(?:add|create)\s+(.+?)\s+(?:to|in)\s+my\s+(?:to-?do|to do)(?:\s+list)?",
    r"(?:add|create)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:todo|to-?do)\s+(.+)",
    r"task\s+add\s*(?:kr\s?de|kar\s?de|karde|krde|kro|karo)?\s+(.+)",
    r"(?:ek\s+)?(?:naya\s+)?task\s+(?:add\s+)?(?:kr\s?de|kar\s?de|karde|krde|kro|karo)\s+(.+)",
    r"(?:add|create)\s+(.+)",
]

OTHER_VERBS = re.compile(r"\b(delete|remove|undo|pending|done|complete\w*|finish\w*)\b", re.I)

STATUS_Q = re.compile(
    r"\bstatus\b"
    r"|\b(is|was)\b.*\b(done|completed|complete|pending)\b"
    r"|\b(done|completed|complete|pending)\s*(hai|h|hua)?\s*(ya|or)\s*(not|nahi|nhi|nahin)\b",
    re.I,
)

LIST_STRONG = re.compile(r"\b(show|list|display|view|see|dikha\w*|total|how\s+many|kitne|count)\b", re.I)
LIST_WEAK = re.compile(r"\b(batao|bta\w*|tell|give|dekh\w*)\b", re.I)
TASK_NOUN = re.compile(r"\b(tasks?|todos?|to-?do|to do)\b|\blist\b", re.I)


DOWNLOAD_VERBS = re.compile(
    r"\b(download|export|save|get|give|send|want|chahiye|de|do|dedo|bhej\w*|nikal\w*|dikha\w*)\b"
)
STUDENT_WORDS = re.compile(
    r"\b(students?|marks|result|results|scholarship|percentage|grade|toppers?|pass|fail|passed|failed|"
    r"score|scores|eligible|eligibility|rank)\b"
)
LOOKUP_WORDS = re.compile(r"\b(ka|ke|ki|kya|kitne|kitna|bta\w*|batao|details?|data|info|dikha\w*|show|tell)\b")
PRON_STU = re.compile(r"\b(iske|iska|iski|isko|uske|uska|uski|usko|his|her|him|ye|yeh|wo|vo)\b")
CALC_WORDS = re.compile(r"\b(calculate|calc|compute|nikal\w*)\b")
COUNT_WORDS = re.compile(r"\b(kitne|kitno|kitni|kitna|how\s+many|count|number\s+of)\b")
SUMMARY_WORDS = re.compile(
    r"\b(toppers?|top|highest|lowest|rank\w*|average|avg|best|summary|kitne\s+(?:pass|fail|students?)|"
    r"how\s+many|total\s+students)\b"
)


def ask_field(outside):
    sch = re.search(r"\b(scholarship|eligible|eligibility)\b", outside)
    mk = re.search(r"\b(marks|score|scores|total|percentage|grade|number|kitne\s+aaye|kitne\s+aaya)\b", outside)
    rs = re.search(r"\b(result|pass|fail|passed|failed)\b", outside)
    asked = [name for name, hit in (("scholarship", sch), ("marks", mk), ("result", rs)) if hit]
    return asked[0] if len(asked) == 1 else "all"


def student_rule(text, outside):
    df = load_students()
    has_words = STUDENT_WORDS.search(outside)

    if has_words and re.search(r"\bcsv\b", outside) and DOWNLOAD_VERBS.search(outside):
        return {"action": "download_results"}

    named = student_matches(df, text) if df is not None else []
    if not has_words and not (named and LOOKUP_WORDS.search(outside)):
        return None

    if named:
        return {"action": "student_info", "field": ask_field(outside)}

    if st.session_state.get("last_student") and PRON_STU.search(outside) and not CALC_WORDS.search(outside):
        return {"action": "student_info", "field": ask_field(outside)}

    if COUNT_WORDS.search(outside) and not re.search(r"\bmarks\b", outside):
        return {"action": "students_summary"}

    if re.search(r"\b(scholarship|eligible|eligibility)\b", outside):
        negative = re.search(r"\b(not|nahi|nhi|nahin|ineligible)\b", outside)
        return {"action": "scholarship_list", "which": "not_eligible" if negative else "eligible"}

    if SUMMARY_WORDS.search(outside):
        return {"action": "students_summary"}

    if re.search(r"\b(result|results|students?|marks)\b", outside) and (
        CALC_WORDS.search(outside) or re.search(r"\b(sabka|saare|sare|all|dikha\w*|show|list)\b", outside)
    ):
        return {"action": "calculate_results"}

    return None


UPLOAD_Q = re.compile(
    r"\b(attach|upload|import)\w*\b|\bfile\b.*\b(kaise|how|able|can|sakte|sakta|skte|skta|possible)\b", re.I
)
HELP_Q = re.compile(
    r"\b(what\s+can\s+you\s+do|kya\s+kya\s+(?:kar|kr)\s*(?:sakte|sakta|skte|skta)|"
    r"tum\s+kya\s+(?:kar|kr)|features|commands|capabilities)\b|^\s*help\s*[?!.]*\s*$",
    re.I,
)


def extract_new_title(text):
    quoted = QUOTED.search(text)
    if quoted and quoted.group(1).strip():
        return quoted.group(1).strip()
    for pat in ADD_PATTERNS:
        m = re.search(pat, text, flags=re.I)
        if m:
            title = clean_title(m.group(1))
            if title and re.match(r"^up\b", title, re.I) and "task" not in text.lower():
                continue
            if title:
                return title
    return None


# in actions ko "Kaunsa task?" ke baad follow-up jawab mil sakta hai ("python wala", "1st")
TARGET_ACTIONS = {"complete_task", "pending_task", "delete_task", "task_status"}

# command ke ye words task ka naam nahi hote, inhe word-match me ignore karte hain
STOPWORDS = {
    "make", "mark", "set", "task", "tasks", "todo", "todos", "list", "status", "done", "complete",
    "completed", "incomplete", "pending", "undo", "undone", "delete", "remove", "del", "the", "and",
    "for", "please", "plz", "pls", "okay", "kar", "karo", "kardo", "krde", "karde", "dena", "dedo",
    "isko", "usko", "iska", "uska", "wala", "wali", "waala", "wale", "this", "that", "hai", "hain",
    "kya", "kitne", "kitna", "batao", "bata", "bta", "tell", "show", "wapas", "reopen", "khatam",
    "finish", "finished", "hata", "hatao", "mita", "mitao", "mein", "mera", "meri", "mere", "abhi",
    "all", "not", "nahi", "nhi", "yeh", "wahi", "last",
}

ORDINAL_WORDS = {
    "first": 1, "pehla": 1, "pahla": 1,
    "second": 2, "dusra": 2, "doosra": 2,
    "third": 3, "teesra": 3, "tisra": 3,
    "fourth": 4, "chautha": 4,
    "fifth": 5,
}
ORDINAL_NUM = re.compile(r"\b(\d+)\s*(?:st|nd|rd|th)\b", re.I)


def ordinal_position(low):
    # "1st", "2nd", "first", "pehla" -> list me kitne number pe hai
    m = ORDINAL_NUM.search(low)
    if m:
        return int(m.group(1))
    for w in re.findall(r"[a-z]+", low):
        if w in ORDINAL_WORDS:
            return ORDINAL_WORDS[w]
    return None


def match_task_by_words(low, todos):
    # "python wala task" -> "study python" (koi bhi ek shabd match ho jaye to chalega)
    words = {w for w in re.findall(r"[a-z0-9]+", low) if len(w) >= 3 and w not in STOPWORDS}
    if not words or todos.empty:
        return None
    scored = []
    for _, r in todos.iterrows():
        tokens = {t for t in re.findall(r"[a-z0-9]+", str(r["task"]).lower()) if len(t) >= 3}
        score = len(words & tokens)
        if score:
            scored.append((score, int(r["id"])))
    if not scored:
        return None
    best = max(s for s, _ in scored)
    top = [tid for s, tid in scored if s == best]
    return top[0] if len(top) == 1 else None


def pick_target(text):
    out = {"task": None, "task_id": None, "use_last": False}
    low = text.lower()
    todos = load_todos()

    m = re.search(r"(?:task\s*(?:no\.?|number|num|#)?\s*|#|\bno\.?\s*|\bnumber\s*)(\d+)", text, re.I)
    m = m or re.search(r"\b(\d+)\s*(?:number|no\b)", text, re.I)
    if m:
        out["task_id"] = int(m.group(1))
        return out

    pos = ordinal_position(low)
    if pos is not None:
        if 1 <= pos <= len(todos):
            out["task_id"] = int(todos.iloc[pos - 1]["id"])
        else:
            out["task_id"] = pos
        return out

    quoted = QUOTED.search(text)
    if quoted and quoted.group(1).strip():
        out["task"] = quoted.group(1).strip()
        return out

    names = [str(t) for t in todos["task"] if str(t).strip() and str(t).lower() in low]
    if names:
        out["task"] = max(names, key=len)
        return out

    tid = match_task_by_words(low, todos)
    if tid is not None:
        out["task_id"] = tid
        return out

    if PRONOUNS.search(low):
        out["use_last"] = True
        return out

    lone = re.fullmatch(r"\D*?(\d+)\D*", low)
    if lone:
        out["task_id"] = int(lone.group(1))
    return out


def rule_intent(text):
    low = text.lower()
    outside = QUOTED.sub(" ", low)

    clear_all = (
        r"\b(delete|remove|clear|hata\w*|mita\w*)\b\s+(?:all|saare|sare|sabhi|everything|my\s+entire|the\s+entire|entire)\b",
        r"\b(all|saare|sare|sabhi)\s+(?:the\s+)?(?:tasks?|todos?)\s+(?:delete|remove|clear|hata\w*|mita\w*)",
        r"\bclear\s+(?:my\s+)?(?:to-?do|to do)",
    )
    if any(re.search(p, outside) for p in clear_all):
        return {"action": "delete_all_tasks"}

    if ADD_START.search(text):
        title = extract_new_title(text)
        if title:
            return {"action": "add_task", "task": title}
        return None

    if HELP_Q.search(outside):
        return {"action": "help"}

    if GREETING.match(text) or THANKS.match(text) or BYE.match(text):
        return {"action": "greet"}

    if UPLOAD_Q.search(outside):
        return {"action": "upload_help"}

    # math expression mile to seedha calculator, API ki zaroorat nahi
    expr = extract_expression(low)
    if expr:
        return {"action": "calculate", "expression": expr}

    found = student_rule(text, outside)
    if found:
        return found

    if re.search(r"\bcsv\b", outside) and DOWNLOAD_VERBS.search(outside):
        return {"action": "download_csv"}

    if STATUS_Q.search(outside):
        return {"action": "task_status", **pick_target(text)}

    if TASK_NOUN.search(outside) and (
        LIST_STRONG.search(outside) or (LIST_WEAK.search(outside) and not OTHER_VERBS.search(outside))
    ):
        return {"action": "show_tasks"}

    if re.search(r"\b(undo|undone|pending|incomplete|reopen|wapas)\b", outside) or "not done" in outside:
        return {"action": "pending_task", **pick_target(text)}

    if re.search(r"\b(done|complete\w*|finish\w*|khatam)\b", outside):
        return {"action": "complete_task", **pick_target(text)}

    if re.search(r"\b(delete|remove|del|hata\w*|mita\w*)\b", outside):
        return {"action": "delete_task", **pick_target(text)}

    # "are you sure" jaise sawal pe asli list dikha do, LLM se pooch ke bhatakne se better
    if st.session_state.get("last_action") in ACTIONS and re.search(
        r"\b(are you sure|pakka|confirm|verify|check again|dobara check|sach\s*me)\b|sure\s*\?", outside
    ):
        return {"action": "show_tasks"}

    return None


# ---------- LLM: rules na pakad paye to ----------

STUDENT_HINT = (
    "❌ Student ke data pe main guess nahi karta. Aise poocho: \"Rahul ke marks kitne aaye\" / "
    "\"Rahul scholarship ke liye eligible hai?\" / \"sabka result calculate karo\" / \"topper kaun hai\"."
)


def build_router_prompt():
    action_lines = "\n".join(f"- {name}: {desc}" for name, (_, desc) in ACTIONS.items())
    return f"""Tum AURA ke liye ek INTENT PARSER ho. User Hinglish, Hindi ya English me likhta hai.
Tumhara kaam sirf user ka message samajhkar JSON banana hai. Kuch aur mat likho.

Available actions:
{action_lines}
- chat: general sawaal / baatcheet jo upar ke kisi action se related nahi (padhai, concepts, hello, etc.)
- unsupported: user kuch aisa maang raha hai jo upar ke actions se nahi ho sakta (jaise alarm, email, call, internet se kuch). "reason" me chhota sa kaaran likho.

Output format (sirf JSON):
{{"action": "...", "task": null, "task_id": null, "use_last": false, "new_task": null, "expression": null, "student": null, "field": null, "which": null, "reason": null}}

Rules:
1. "task" me SIRF task ka title likho. Ye phrases task me mat daalo: "by name of", "naam se", "ke naam se", "named", "add kar", "krde", "task", "to my todo".
   Agar user ne quotes me naam diya hai to wahi title hai.
2. Agar user "it", "ye", "isko", "usko", "wahi", "last wala" bole -> task=null, use_last=true.
3. Agar user "task 2" / "2 number wala" bole -> task_id=2.
4. "done hai ya nahi?", "status bta" jaise SAWAAL hain -> task_status, complete_task NAHI.
5. "undo" ya "wapas pending kar" -> pending_task.
6. Task list / CSV / tasks se related koi bhi kaam ho to kabhi "chat" mat bolo. Ya to upar ka action chuno, ya unsupported.
7. Student ke marks / result / scholarship / topper se related koi bhi kaam ho to kabhi "chat" mat bolo, student wale actions chuno.
   Student ka naam "student" me likho, jaise "Rahul ka scholarship?" -> student_info, student="Rahul", field="scholarship".
8. Agar pakka nahi ho -> action="chat".
9. File / CSV / Excel upload SUPPORTED hai (chat box ke attach icon se). Kabhi mat bolo ki file upload nahi ho sakta -> upload_help.
10. Jo kaam list me nahi hai, usko kisi action me force mat karo -> unsupported.

Examples:
"hii" -> {{"action":"chat"}}
"python wala complete kar de" -> {{"action":"complete_task","task":"python"}}
"task 3 ka naam gym rakh de" -> {{"action":"rename_task","task_id":3,"new_task":"gym"}}
"Priya ke marks kitne aaye" -> {{"action":"student_info","student":"Priya","field":"marks"}}
"kaun kaun scholarship pa sakta hai" -> {{"action":"scholarship_list","which":"eligible"}}
"25*4+10 kitna hua" -> {{"action":"calculate","expression":"25*4+10"}}
"kal subah 6 baje alarm laga de" -> {{"action":"unsupported","reason":"alarm lagana mere paas nahi hai"}}

Current To-Do list (task naam match karne ke liye):
{todos_as_text()}
"""


LLM_COOLDOWN_SECONDS = 600


def is_rate_limit(e):
    return getattr(e, "status_code", None) == 429 or "429" in str(e)


def llm_ready():
    if not st.session_state.get("use_ai", True):
        return False
    return time.time() >= st.session_state.get("llm_blocked_until", 0)


def llm_off_message():
    if not st.session_state.get("use_ai", True):
        return (
            "🔌 AI fallback abhi band hai (upar toggle OFF hai), isliye ye sawaal nahi ho sakta. "
            "Task, student data, calculator aur greetings bina AI ke chalte hain."
        )
    return (
        "⏳ AI ki free limit abhi khatam hai (OpenRouter 429), isliye ye sawaal abhi nahi ho sakta. "
        "Task, student data, calculator aur greetings bina AI ke chalte hain. "
        "Thodi der baad try karo, ya naya key / credits lagao."
    )


def llm_call(client, **kwargs):
    # saari API calls yahin se jaati hain: gini jaati hain, aur 429 aane pe 10 minute ke liye ruk jaati hain
    if not llm_ready():
        raise RuntimeError("AI abhi band hai")
    st.session_state.api_calls = st.session_state.get("api_calls", 0) + 1
    try:
        return client.chat.completions.create(model=MODEL, **kwargs)
    except Exception as e:
        if is_rate_limit(e):
            st.session_state.llm_blocked_until = time.time() + LLM_COOLDOWN_SECONDS
        raise


def parse_intent(client, user_text):
    for _ in range(2):
        if not llm_ready():
            return None
        try:
            resp = llm_call(
                client,
                temperature=0,
                messages=[
                    {"role": "system", "content": build_router_prompt()},
                    {"role": "user", "content": user_text},
                ],
            )
            raw = resp.choices[0].message.content or ""
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                continue
            data = json.loads(match.group(0))
            if isinstance(data, dict) and data.get("action") in VALID_ACTIONS:
                return data
        except Exception as e:
            if is_rate_limit(e):
                return None
            continue
    return None


CLAIM_OR_DENIAL = re.compile(
    r"\b(marked|added|deleted|removed|completed|updated|renamed|ho gaya|kar diya|kar di|"
    r"cannot|can't|can’t|unable|not able|don't have|don’t have|do not have|nahi kar sakta|nahi ho sakta)\b",
    re.I,
)
ABOUT_TASKS = re.compile(r"\btasks?\b|to-?do|\bcsv\b|your list", re.I)


def looks_wrong(answer):
    return bool(CLAIM_OR_DENIAL.search(answer) and ABOUT_TASKS.search(answer))


def normal_chat(client):
    system = (
        "Tum AURA ho, ek BCA student ke personal assistant. "
        "User ki bhasha (Hinglish/Hindi/English) me chhota aur seedha jawab do. "
        "Todo list, CSV aur student ke marks/result/scholarship ka kaam Python karta hai, tum nahi. "
        "Tumhare paas kisi student ka data nahi hai, isliye kisi student ke marks, result ya scholarship ke bare me kabhi kuch mat batana. "
        "Kabhi mat bolna ki tumne koi task add/complete/delete/change kiya, "
        "aur kabhi mat bolna ki ye kaam AURA nahi kar sakta. "
        "Agar user task ya CSV ka kaam maang raha hai to bolo ki use seedha command me likhe.\n\n"
        f"Current To-Do list:\n{todos_as_text()}"
    )
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_history[-6:]
    ]
    resp = llm_call(
        client,
        messages=[{"role": "system", "content": system}, *history],
    )
    answer = resp.choices[0].message.content or ""
    if looks_wrong(answer):
        return NOT_UNDERSTOOD
    return answer


def handle_message(client, user_text):
    # pichli baar bot ne "Kaunsa task?" poocha tha to uska jawab yahan pakdenge
    awaiting = st.session_state.pop("awaiting_target", None)

    intent = rule_intent(user_text)
    source = "rule"

    if intent is None and awaiting and len(user_text.split()) <= 6:
        target = pick_target(user_text)
        if target["task"] or target["task_id"] is not None:
            intent = {"action": awaiting, **target}
            source = "followup"

    if intent is None:
        intent = parse_intent(client, user_text)
        source = "llm"

    if intent is None:
        # LLM bhi parse nahi kar paya: seedha error ki jagah normal baatcheet me daal do
        intent = {"action": "chat"}
        source = "llm-failed"

    action = intent["action"]
    route = f"{source}:{action}"
    intent["raw"] = user_text

    if action in NEEDS_TARGET and not (
        intent.get("task") or intent.get("task_id") or intent.get("use_last")
    ):
        intent["use_last"] = True

    if action in ACTIONS:
        st.session_state.last_action = action
        st.session_state.perf_hint = False
        try:
            result = ACTIONS[action][0](intent)
        except Exception as e:
            return f"❌ Ye kaam nahi ho paya. Reason: {e}", route
        if action in TARGET_ACTIONS and result.startswith(("Kaunsa task?", "Kai tasks match")):
            st.session_state.awaiting_target = action
        return add_perf_hint(result), route

    if action == "unsupported":
        reason = intent.get("reason") or "ye feature abhi mere paas nahi hai"
        return f"❌ Ye mujhse nahi ho sakta: {reason}", route

    st.session_state.last_action = "chat"
    if student_matches(load_students(), user_text):
        return STUDENT_HINT, route
    if not llm_ready():
        return llm_off_message(), route
    try:
        return normal_chat(client), route
    except Exception as e:
        if is_rate_limit(e):
            return llm_off_message(), route
        return f"❌ AI se jawab nahi aaya. Reason: {e}", route


def handle_input(client, text, files):
    text = (text or "").strip()
    if not files:
        return handle_message(client, text)

    ok, upload_msg = ingest_upload(files[0])
    if not ok:
        return upload_msg + "\n\nFile load nahi hui, isliye purane data pe jawab nahi de raha.", "upload:failed"

    st.session_state.last_student = None
    if not text:
        st.session_state.perf_hint = False
        summary = act_students_summary({})
        return (
            upload_msg + "\n\n" + add_perf_hint(summary)
            + "\n\nPoora result chahiye to bolo: \"sabka result calculate karo\"."
        ), "upload:summary"

    answer, route = handle_message(client, text)
    return upload_msg + "\n\n" + answer, "upload+" + route


def csv_bytes():
    return load_todos().to_csv(index=False).encode("utf-8")


def student_upload_box():
    with st.expander("📂 Student marks CSV upload karo", expanded=load_students() is None):
        st.caption(
            "Columns chahiye: name, english, hindi, math, science, physics. "
            "age aur course optional hain, par age ke bina scholarship check nahi hoga."
        )
        st.download_button(
            "⬇️ Sample CSV",
            data=SAMPLE_CSV.encode("utf-8"),
            file_name="sample_students.csv",
            mime="text/csv",
            key="sample_csv",
        )
        uploaded = st.file_uploader("CSV file", type=["csv"], key="student_upload")
        sig = f"{uploaded.name}-{uploaded.size}" if uploaded is not None else None

        if uploaded is not None and st.session_state.get("student_sig") != sig:
            ok, msg = ingest_upload(uploaded)
            st.session_state.student_sig = sig if ok else None
            st.session_state.upload_msg = (ok, msg)
            if ok:
                st.session_state.last_student = None

        note = st.session_state.get("upload_msg")
        if note:
            (st.success if note[0] else st.error)(note[1])

        df = load_students()
        if df is not None:
            st.write(f"📚 Abhi loaded: {len(df)} students")
            if st.button("🗑 Student data hatao", key="clear_students"):
                os.remove(STUDENT_FILE)
                st.session_state.student_sig = sig
                st.session_state.upload_msg = None
                st.session_state.last_student = None
                st.rerun()


def show_ai_assistant():
    st.title("🤖 AURA AI Assistant")
    st.caption(f"AURA assistant build: {BUILD}")
    st.write("Mujhse Hinglish me baat karo. Jo kar sakta hu karunga, jo nahi kar sakta wo saaf bol dunga.")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        st.error("OpenRouter API key not found.")
        return

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, max_retries=0)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_task_id" not in st.session_state:
        st.session_state.last_task_id = None

    student_upload_box()

    left, right = st.columns([3, 1])
    with left:
        st.toggle("🛠 Debug (kaunsa action chala dikhao)", value=True, key="debug")
        st.toggle("🤖 AI fallback use karo (OFF = sirf rules, API call zero)", value=True, key="use_ai")
        if st.session_state.get("debug"):
            st.caption(f"🔌 AI API calls is session me: {st.session_state.get('api_calls', 0)}")
    with right:
        if st.button("🧹 Chat saaf karo", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.last_task_id = None
            st.session_state.last_action = None
            st.session_state.last_student = None
            st.session_state.awaiting_target = None
            st.rerun()

    for i, m in enumerate(st.session_state.chat_history):
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m.get("download") == "todos":
                st.download_button(
                    "⬇️ Download todos.csv",
                    data=csv_bytes(),
                    file_name="todos.csv",
                    mime="text/csv",
                    key=f"dl_{i}",
                )
            elif m.get("download") == "results":
                st.download_button(
                    "⬇️ Download student_results.csv",
                    data=results_csv_bytes(),
                    file_name="student_results.csv",
                    mime="text/csv",
                    key=f"dl_{i}",
                )
            if m.get("route") and st.session_state.get("debug"):
                st.caption(f"route: {m['route']}")

    try:
        prompt = st.chat_input(
            "AURA se kuch bhi bolo... (📎 se student CSV/Excel attach kar sakte ho)",
            accept_file=True,
            file_type=["csv", "xlsx"],
        )
    except TypeError:
        st.caption("ℹ️ Chat me 📎 attach ke liye Streamlit update karo: pip install -U streamlit. Tab tak upar wala uploader use karo.")
        prompt = st.chat_input("AURA se kuch bhi bolo...")

    if not prompt:
        return

    if isinstance(prompt, str):
        user_text, files = prompt, []
    else:
        user_text = getattr(prompt, "text", None) or prompt.get("text", "") or ""
        files = list(getattr(prompt, "files", None) or prompt.get("files", []) or [])

    shown = (f"📎 {files[0].name}\n\n" if files else "") + user_text
    st.session_state.chat_history.append({"role": "user", "content": shown.strip()})
    st.session_state.attach = None

    with st.spinner("AURA samajh raha hai..."):
        answer, route = handle_input(client, user_text, files)

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer,
        "route": route,
        "download": st.session_state.pop("attach", None),
    })
    st.rerun()