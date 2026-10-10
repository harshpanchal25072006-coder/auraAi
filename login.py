"""AURA login: password ya face match.

app.py me use kaise karna hai:

    from login import require_login
    APP_PASSWORD = "aura@123"          # <- apna password yahan
    st.set_page_config(...)            # (agar hai to pehle ye)
    require_login(APP_PASSWORD)        # <- iske neeche ka poora app tabhi dikhega jab login ho jaye

Face login ke liye:
    1. pip install "opencv-python<5"
    2. project folder me `authorized_faces` naam ka folder banao
    3. usme un logon ki photo rakho jinke face se app khulna chahiye (jpg/png)
"""
import hmac
import os
import threading
import urllib.request

import numpy as np
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "face_models")
AUTHORIZED_DIR = os.path.join(BASE_DIR, "authorized_faces")
MATCH_THRESHOLD = 0.363


CHECK_ALL_FACES = True

MAX_SIDE = 1280
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

MODEL_FILES = {
    "face_detection_yunet_2023mar.onnx": (
        100_000,
        [
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "https://github.com/opencv/opencv_zoo/raw/fd2da740ebc6d0fe489d86cb55133148978cd82e/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        ],
    ),
    "face_recognition_sface_2021dec.onnx": (
        10_000_000,
        [
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
            "https://github.com/opencv/opencv_zoo/raw/fd2da740ebc6d0fe489d86cb55133148978cd82e/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        ],
    ),
}

_LOCK = threading.Lock()

def ensure_model(name):
    min_size, urls = MODEL_FILES[name]
    path = os.path.join(MODEL_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) >= min_size:
        return path

    os.makedirs(MODEL_DIR, exist_ok=True)
    temp = path + ".part"
    last_error = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if len(data) < min_size:
                raise ValueError("file bahut chhoti aayi")
            with open(temp, "wb") as f:
                f.write(data)
            os.replace(temp, path)
            return path
        except Exception as e:
            last_error = e
            if os.path.exists(temp):
                os.remove(temp)

    raise RuntimeError(
        f"{name} download nahi ho paya ({last_error}). "
        f"Isse khud download karke `face_models` folder me isi naam se rakh do: {urls[0]}"
    )


@st.cache_resource(show_spinner="Face model load ho raha hai (pehli baar ~40MB download hoga)...")
def load_models():
    import cv2

    detector_path = ensure_model("face_detection_yunet_2023mar.onnx")
    recognizer_path = ensure_model("face_recognition_sface_2021dec.onnx")
    detector = cv2.FaceDetectorYN.create(detector_path, "", (320, 320), 0.8, 0.3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")
    return detector, recognizer


def decode_image(data):
    import cv2

    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    return img


def face_features(img, largest_only=False):
    detector, recognizer = load_models()
    h, w = img.shape[:2]
    with _LOCK:
        detector.setInputSize((w, h))
        _, faces = detector.detect(img)
        if faces is None or len(faces) == 0:
            return []
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        if largest_only:
            faces = faces[:1]
        return [np.array(recognizer.feature(recognizer.alignCrop(img, f)), copy=True) for f in faces]


def authorized_files():
    if not os.path.isdir(AUTHORIZED_DIR):
        return []
    return sorted(f for f in os.listdir(AUTHORIZED_DIR) if f.lower().endswith(IMAGE_TYPES))


def folder_signature():
  
    return tuple(
        (f, os.path.getmtime(os.path.join(AUTHORIZED_DIR, f))) for f in authorized_files()
    )


@st.cache_resource(show_spinner="Authorized photos load ho rahi hain...")
def load_reference_features(signature):
    features, skipped = [], []
    for fname, _ in signature:
        with open(os.path.join(AUTHORIZED_DIR, fname), "rb") as fh:
            img = decode_image(fh.read())
        found = face_features(img, largest_only=True) if img is not None else []
        if found:
            features.append(found[0])
        else:
            skipped.append(fname)
    return features, skipped


def verify_face(data):
    import cv2

    signature = folder_signature()
    if not signature:
        return False, "❌ `authorized_faces` folder me koi photo nahi hai."

    refs, skipped = load_reference_features(signature)
    if not refs:
        return False, "❌ `authorized_faces` ki kisi photo me face nahi mila. Saaf, seedhe face wali photo rakho."

    img = decode_image(data)
    if img is None:
        return False, "❌ Image padh nahi paya. JPG ya PNG daalo."

    feats = face_features(img, largest_only=not CHECK_ALL_FACES)
    if not feats:
        return False, "❌ Is photo me koi face nahi mila. Saaf, seedhe face wali photo daalo."

    _, recognizer = load_models()
    with _LOCK:
        best = max(
            recognizer.match(ref, feat, cv2.FaceRecognizerSF_FR_COSINE)
            for ref in refs
            for feat in feats
        )

    if best >= MATCH_THRESHOLD:
        return True, f"✅ Face match ho gaya (score {best:.2f})"
    return False, f"❌ Face match nahi hua (score {best:.2f}, chahiye {MATCH_THRESHOLD} ya zyada)"


def password_tab(password):
    if not password:
        st.error("APP_PASSWORD set nahi hai. app.py me password likho.")
        return

    with st.form("aura_password_form"):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("🔓 Login", use_container_width=True)

    if submitted:
        if hmac.compare_digest(entered.encode("utf-8"), password.encode("utf-8")):
            st.session_state.authenticated = True
            st.session_state.login_method = "password"
            st.rerun()
        else:
            st.error("❌ Galat password.")


def face_tab():
    try:
        import cv2  # noqa: F401
    except ImportError:
        st.error('Face login ke liye ye chalao: `pip install "opencv-python<5"`')
        return

    if not authorized_files():
        st.warning(
            "Face login abhi set nahi hai. Project folder me `authorized_faces` naam ka folder banao "
            "aur usme us insaan ki photo (jpg/png) rakho jiske face se app khulna chahiye."
        )
        return

    st.caption("Us insaan ki photo upload karo jiska face `authorized_faces` me hai. Koi bhi photo chalegi jisme face match ho jaye.")

    uploaded = st.file_uploader(
        "📤 Photo upload karo",
        type=["jpg", "jpeg", "png", "webp", "bmp"],
        key="login_upload",
    )

    with st.expander("📷 Ya camera se photo lo"):
        shot = st.camera_input("Camera", key="login_camera")

    data = None
    if uploaded is not None:
        data = uploaded.getvalue()
    elif shot is not None:
        data = shot.getvalue()

    if data is not None:
        st.image(data, width=220)

    if st.button("🔍 Face verify karo", disabled=data is None, use_container_width=True, key="login_face_btn"):
        with st.spinner("Face check ho raha hai..."):
            try:
                ok, message = verify_face(data)
            except Exception as e:
                ok, message = False, f"❌ Face check me error aaya: {e}"
        if ok:
            st.session_state.authenticated = True
            st.session_state.login_method = "face"
            st.rerun()
        else:
            st.error(message)


def require_login(password):
    """Login nahi hua to login screen dikhake app yahin rok deta hai (st.stop)."""
    if st.session_state.get("authenticated"):
        with st.sidebar:
            if st.button("🚪 Logout", key="aura_logout"):
                st.session_state.clear()
                st.rerun()
        return

    st.title("🔐 AURA Login")
    st.write("Aage badhne ke liye login karo.")

    tab_password, tab_face = st.tabs(["🔑 Password", "🙂 Face"])
    with tab_password:
        password_tab(password)
    with tab_face:
        face_tab()

    st.stop()