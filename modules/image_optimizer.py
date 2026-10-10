import io
import zipfile

import streamlit as st
from PIL import Image, ImageOps

try:
    __import__("pillow_avif")
except ImportError:
    pass

Image.init()

MAX_FILES = 10

FORMAT_EXT = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "AVIF": "avif",
    "BMP": "bmp",
    "TIFF": "tiff",
    "GIF": "gif",
    "ICO": "ico",
}

FORMAT_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "AVIF": "image/avif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
    "GIF": "image/gif",
    "ICO": "image/x-icon",
}

LOSSY_FORMATS = ("JPEG", "WEBP", "AVIF")

RESIZE_PRESETS = {
    "Original size (no resize)": ("none", None),
    "Thumbnail (150 px)": ("width", 150),
    "Mobile / Small (480 px)": ("width", 480),
    "Blog / Content (800 px)": ("width", 800),
    "Desktop / Banner (1200 px)": ("width", 1200),
    "Full HD / Hero (1920 px)": ("width", 1920),
    "Custom size": ("custom", None),
}


def format_size(num_bytes):
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{size:.0f} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024


def has_transparency(img):
    if "A" in img.getbands():
        return True
    return img.mode == "P" and "transparency" in img.info


def convert_mode(img, target_format):
    transparent = has_transparency(img)

    if target_format in ("JPEG", "BMP"):
        if not transparent:
            return img.convert("RGB")
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background

    return img.convert("RGBA" if transparent else "RGB")


def resize_image(img, mode, width, height, keep_ratio):
    old_w, old_h = img.size

    if mode == "none":
        return img

    if mode == "width":
        if old_w <= width:
            return img
        new_h = max(1, round(old_h * width / old_w))
        return img.resize((width, new_h), Image.LANCZOS)

    if not keep_ratio:
        return img.resize((width, height), Image.LANCZOS)

    scale = min(width / old_w, height / old_h)
    if scale >= 1:
        return img
    new_size = (max(1, round(old_w * scale)), max(1, round(old_h * scale)))
    return img.resize(new_size, Image.LANCZOS)


def make_preview(img, max_side=700):
    preview = img.copy()
    if preview.mode not in ("RGB", "RGBA"):
        preview = preview.convert("RGBA")
    preview.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    preview.save(buffer, format="PNG")
    return buffer.getvalue()


def pick_format(chosen, original):
    if chosen:
        return chosen

    original = (original or "").upper()
    if original == "MPO":
        original = "JPEG"
    if original in FORMAT_EXT and original in Image.SAVE:
        return original
    return "WEBP"


def save_options(fmt, img, quality, lossless):
    if fmt == "JPEG":
        options = {"quality": quality, "optimize": True, "progressive": True}
        if quality >= 90:
            options["subsampling"] = 0
        return options

    if fmt == "WEBP":
        if lossless:
            return {"lossless": True, "quality": 100, "method": 6}
        return {"quality": quality, "method": 6}

    if fmt == "AVIF":
        return {"quality": quality}

    if fmt == "PNG":
        return {"optimize": True, "compress_level": 9}

    if fmt == "TIFF":
        return {"compression": "tiff_lzw"}

    if fmt == "ICO":
        return {"sizes": [img.size]}

    return {}


def optimize_image(file_bytes, filename, chosen_format, quality, lossless,
                   resize_mode, width, height, keep_ratio):
    img = Image.open(io.BytesIO(file_bytes))
    original_format = img.format
    img.load()
    img = ImageOps.exif_transpose(img)

    original_dimensions = img.size
    original_preview = make_preview(img)

    fmt = pick_format(chosen_format, original_format)

    img = convert_mode(img, fmt)
    img = resize_image(img, resize_mode, width, height, keep_ratio)

    if fmt == "ICO":
        img.thumbnail((256, 256))

    buffer = io.BytesIO()
    img.save(buffer, format=fmt, **save_options(fmt, img, quality, lossless))
    output = buffer.getvalue()

    new_preview = make_preview(Image.open(io.BytesIO(output)))
    stem = filename.rsplit(".", 1)[0]

    return {
        "name": filename,
        "out_name": f"{stem}_optimized.{FORMAT_EXT[fmt]}",
        "format": fmt,
        "orig_size": len(file_bytes),
        "new_size": len(output),
        "orig_dimensions": original_dimensions,
        "new_dimensions": img.size,
        "data": output,
        "orig_preview": original_preview,
        "new_preview": new_preview,
    }


def build_zip(results):
    archive = io.BytesIO()
    seen = {}

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in results:
            name = item["out_name"]
            if name in seen:
                seen[name] += 1
                base, ext = name.rsplit(".", 1)
                name = f"{base}_{seen[name]}.{ext}"
            else:
                seen[name] = 0
            zf.writestr(name, item["data"])

    return archive.getvalue()


def show_image_optimizer():

    st.title("🖼️ Image Optimizer")
    st.subheader("Convert, resize and compress images for a faster website.")

    st.markdown("---")

    format_options = {
        "WEBP ⭐ (Recommended for websites)": "WEBP",
        "JPEG / JPG": "JPEG",
        "PNG": "PNG",
    }
    if "AVIF" in Image.SAVE:
        format_options["AVIF (smallest size, newer format)"] = "AVIF"
    format_options.update({
        "BMP": "BMP",
        "TIFF": "TIFF",
        "GIF": "GIF",
        "ICO": "ICO",
        "Same as original": None,
    })

    upload_types = ["jpg", "jpeg", "png", "webp", "bmp", "gif", "tiff", "tif", "ico"]
    if "AVIF" in Image.OPEN:
        upload_types.append("avif")

    with st.expander("💡 Recommended settings for website speed"):
        st.markdown(
            """
**Why WebP?** WebP files are usually **25-35% smaller** than JPEG/PNG at the
same visible quality, and they support transparency. All modern browsers
support it.

| Use case | Recommended width | Format | Quality |
|---|---|---|---|
| Thumbnail / product card | 150 - 300 px | WebP | 75 - 80 |
| Mobile image | 480 px | WebP | 75 - 80 |
| Blog / content image | 800 px | WebP | 80 |
| Desktop banner | 1200 px | WebP | 80 - 85 |
| Hero / full width | 1920 px | WebP | 80 - 85 |
| Logo / icon with transparency | as needed | WebP (lossless) / PNG | - |

**More tips**
- Quality between **75 and 85** looks almost the same to the eye but saves a lot of size.
- Aim for **under 100-200 KB** per image.
- Don't upload a 4000 px photo for an 800 px box.
- Add `loading="lazy"` and `width` / `height` attributes in your HTML.
            """
        )

    uploaded_files = st.file_uploader(
        f"Upload images (max {MAX_FILES})",
        type=upload_types,
        accept_multiple_files=True,
    )

    if uploaded_files and len(uploaded_files) > MAX_FILES:
        st.warning(
            f"Only {MAX_FILES} images are allowed at a time. "
            f"The first {MAX_FILES} will be processed."
        )
        uploaded_files = uploaded_files[:MAX_FILES]

    st.markdown("---")
    st.subheader("⚙️ Optimization Settings")

    col1, col2 = st.columns(2)

    with col1:
        format_label = st.selectbox(
            "Output format",
            list(format_options.keys()),
            index=0,
        )
    chosen_format = format_options[format_label]

    with col2:
        size_label = st.selectbox(
            "Resize",
            list(RESIZE_PRESETS.keys()),
            index=4,
            help="Small images are never enlarged.",
        )
    resize_mode, width = RESIZE_PRESETS[size_label]
    height = None
    keep_ratio = True

    if resize_mode == "custom":
        w_col, h_col, ratio_col = st.columns(3)
        with w_col:
            width = st.number_input("Width (px)", min_value=1, max_value=10000, value=1000)
        with h_col:
            height = st.number_input("Height (px)", min_value=1, max_value=10000, value=1000)
        with ratio_col:
            keep_ratio = st.checkbox(
                "Keep aspect ratio",
                value=True,
                help="When on, the image fits inside the box without stretching.",
            )

    lossless = False
    quality = 80

    if chosen_format == "WEBP":
        lossless = st.checkbox(
            "Lossless WebP (for logos / screenshots, makes bigger files)",
            value=False,
        )

    uses_quality = chosen_format is None or chosen_format in LOSSY_FORMATS

    if uses_quality and not lossless:
        quality = st.slider(
            "Quality",
            min_value=40,
            max_value=100,
            value=80,
            help="75-85 is the sweet spot. Above 90 the files grow a lot.",
        )
        st.caption(
            "75-85: hardly any visible loss, big savings  |  "
            "90+: very high quality, larger files  |  "
            "below 65: artifacts may become visible"
        )
    elif chosen_format in ("PNG", "BMP", "TIFF", "GIF", "ICO"):
        st.info(
            f"{chosen_format} has no quality setting, so the size drops mainly "
            "from resizing. For photos, WebP or JPEG works much better."
        )

    run = st.button("🚀 Optimize Images", type="primary", disabled=not uploaded_files)

    if not uploaded_files:
        st.info("Upload some images and click Optimize.")

    if run and uploaded_files:
        results = []
        errors = []
        progress = st.progress(0.0, text="Optimizing...")

        for index, uploaded in enumerate(uploaded_files, start=1):
            try:
                results.append(optimize_image(
                    uploaded.getvalue(),
                    uploaded.name,
                    chosen_format,
                    quality,
                    lossless,
                    resize_mode,
                    int(width) if width else None,
                    int(height) if height else None,
                    keep_ratio,
                ))
            except Exception as exc:
                errors.append(f"{uploaded.name}: {exc}")
            progress.progress(
                index / len(uploaded_files),
                text=f"Optimizing {index}/{len(uploaded_files)}",
            )

        progress.empty()
        st.session_state["image_results"] = results
        st.session_state["image_errors"] = errors

    results = st.session_state.get("image_results")
    errors = st.session_state.get("image_errors", [])

    for message in errors:
        st.error(f"❌ {message}")

    if not results:
        return

    st.markdown("---")
    st.subheader("✅ Results")

    total_before = sum(r["orig_size"] for r in results)
    total_after = sum(r["new_size"] for r in results)
    total_saved = (1 - total_after / total_before) * 100 if total_before else 0

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Original total", format_size(total_before))
    with m2:
        st.metric("Optimized total", format_size(total_after))
    with m3:
        st.metric("Saved", f"{total_saved:.1f}%")

    st.download_button(
        "📦 Download all (ZIP)",
        data=build_zip(results),
        file_name="optimized_images.zip",
        mime="application/zip",
    )

    for index, item in enumerate(results):
        saved = (1 - item["new_size"] / item["orig_size"]) * 100
        marker = "🟢" if saved >= 0 else "🟠"

        with st.expander(
            f"{marker} {item['name']}  →  {item['out_name']}  ({saved:+.1f}% size)",
            expanded=(index == 0),
        ):
            left, right = st.columns(2)

            with left:
                ow, oh = item["orig_dimensions"]
                st.image(
                    item["orig_preview"],
                    caption=f"Original - {ow}x{oh} px, {format_size(item['orig_size'])}",
                    use_container_width=True,
                )
            with right:
                nw, nh = item["new_dimensions"]
                st.image(
                    item["new_preview"],
                    caption=(
                        f"Optimized ({item['format']}) - {nw}x{nh} px, "
                        f"{format_size(item['new_size'])}"
                    ),
                    use_container_width=True,
                )

            if saved < 0:
                st.warning(
                    "The output is bigger than the original. Try a lower quality, "
                    "WebP, or a smaller resize."
                )

            st.download_button(
                f"⬇️ Download {item['out_name']}",
                data=item["data"],
                file_name=item["out_name"],
                mime=FORMAT_MIME[item["format"]],
                key=f"download_{index}",
            )

    st.caption("Note: for animated GIF/WebP files only the first frame is processed.")