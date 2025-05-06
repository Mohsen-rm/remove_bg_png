import os
import base64
import uuid
from io import BytesIO
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from PIL import Image
from rembg import remove
from rembg.session_factory import new_session

app = Flask(__name__, static_folder="static")
app.secret_key = "replace-with-a-secure-random-key"

# مجلد مؤقت لحفظ الرفع
UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# تجهيز جلسة rembg
session = new_session(model_name="u2net")

# تعيين حد أقصى لحجم الطلب (50 ميجابايت)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024


def remove_bg_highres_pil(img: Image.Image) -> Image.Image:
    """يأخذ PIL Image ويعيدها بعد إزالة الخلفية"""
    orig_size = img.size

    # تحديد حجم معالجة مناسب (1024 كحد أقصى)
    max_dim = max(orig_size)
    if max_dim > 1024:
        scale = 1024 / max_dim
        new_size = (int(orig_size[0] * scale), int(orig_size[1] * scale))
        high_res = img.resize(new_size, Image.LANCZOS)
    else:
        high_res = img

    # إزالة الخلفية
    result_hr = remove(
        high_res,
        session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10
    )

    # إعادة تحجيم للحجم الأصلي إذا تم تغييره
    if max_dim > 1024:
        final = result_hr.resize(orig_size, Image.LANCZOS)
    else:
        final = result_hr

    return final


def apply_background(foreground, bg_type, bg_value=None):
    """تطبيق الخلفية على الصورة بعد إزالة الخلفية"""
    # التأكد من أن الصورة في وضع RGBA
    if foreground.mode != 'RGBA':
        foreground = foreground.convert('RGBA')

    width, height = foreground.size

    if bg_type == "transparent":
        # الإبقاء على الشفافية
        return foreground

    elif bg_type == "color":
        # إنشاء خلفية بلون معين
        background = Image.new('RGBA', (width, height), bg_value or "#FFFFFF")
        # دمج الصورتين
        composite = Image.alpha_composite(background, foreground)
        return composite

    elif bg_type == "image" and bg_value:
        try:
            # محاولة فتح صورة الخلفية
            bg_img = Image.open(BytesIO(bg_value))

            # تغيير حجم صورة الخلفية لتناسب الصورة الأمامية
            bg_img = bg_img.resize((width, height), Image.LANCZOS)

            # تحويل الصورة إلى RGBA إذا لزم الأمر
            if bg_img.mode != 'RGBA':
                bg_img = bg_img.convert('RGBA')

            # دمج الصور
            composite = Image.alpha_composite(bg_img, foreground)
            return composite
        except Exception as e:
            print(f"خطأ في تطبيق الخلفية: {e}")
            # إرجاع الصورة الشفافة في حالة الخطأ
            return foreground

    # الإرجاع الافتراضي هو الصورة الشفافة
    return foreground


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process_image():
    try:
        # التحقق من وجود الصورة
        if "image" not in request.files and "image_data" not in request.form:
            return jsonify({"error": "لم يتم اختيار أي ملف"}), 400

        # الحصول على الصورة
        if "image" in request.files:
            file = request.files["image"]
            if file.filename == "":
                return jsonify({"error": "لم يتم اختيار أي ملف"}), 400
            img = Image.open(file.stream).convert("RGBA")
        else:
            # الحصول على الصورة من البيانات المشفرة بـ Base64
            image_data = request.form["image_data"]
            if image_data.startswith('data:image'):
                # إزالة بادئة البيانات
                img_format, img_str = image_data.split(';base64,')
                img_data = base64.b64decode(img_str)
                img = Image.open(BytesIO(img_data)).convert("RGBA")
            else:
                return jsonify({"error": "صيغة الصورة غير صالحة"}), 400

        # إزالة الخلفية
        result = remove_bg_highres_pil(img)

        # معالجة الخلفية المطلوبة
        bg_type = request.form.get("bg_type", "transparent")

        bg_value = None
        if bg_type == "color":
            bg_value = request.form.get("bg_color", "#FFFFFF")
        elif bg_type == "image" and "bg_image" in request.files:
            bg_file = request.files["bg_image"]
            if bg_file.filename != "":
                bg_value = bg_file.read()

        # تطبيق الخلفية
        final_image = apply_background(result, bg_type, bg_value)

        # إنشاء معرف فريد للصورة المعالجة
        unique_id = uuid.uuid4().hex
        filename = f"no_bg_{unique_id}.png"
        file_path = os.path.join(PROCESSED_FOLDER, filename)

        # حفظ الصورة النهائية
        final_image.save(file_path, format="PNG")

        # تحويل الصورة النهائية إلى بيانات للإرجاع
        buf = BytesIO()
        final_image.save(buf, format="PNG")
        buf.seek(0)

        # تشفير الصورة بـ Base64 للإرجاع عبر JSON
        img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        data_uri = f"data:image/png;base64,{img_str}"

        return jsonify({
            "success": True,
            "image": data_uri,
            "file_id": unique_id  # إرسال معرف الملف للتنزيل لاحقاً
        })

    except Exception as e:
        print(f"خطأ أثناء المعالجة: {e}")
        return jsonify({"error": f"خطأ أثناء المعالجة: {e}"}), 500


@app.route("/download/<file_id>", methods=["GET"])
def download_image_by_id(file_id):
    """تنزيل الصورة المعالجة باستخدام المعرف"""
    try:
        # التحقق من سلامة المدخلات (منع path traversal)
        if not file_id or '../' in file_id or '/' in file_id:
            return jsonify({"error": "معرف ملف غير صالح"}), 400

        # بناء اسم الملف
        filename = f"no_bg_{file_id}.png"
        file_path = os.path.join(PROCESSED_FOLDER, filename)

        # التحقق من وجود الملف
        if not os.path.exists(file_path):
            return jsonify({"error": "الملف غير موجود"}), 404

        # إرسال الملف للتحميل
        return send_file(
            file_path,
            mimetype="image/png",
            as_attachment=True,
            download_name="no_bg.png"
        )
    except Exception as e:
        print(f"خطأ أثناء التحميل: {e}")
        return jsonify({"error": f"خطأ أثناء التحميل: {e}"}), 500


@app.route("/api/remove-bg", methods=["POST"])
def api_remove_bg():
    """واجهة برمجية لإزالة الخلفية"""
    try:
        if "image" not in request.files:
            return jsonify({"error": "لم يتم اختيار أي ملف"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"error": "لم يتم اختيار أي ملف"}), 400

        # معالجة الخلفية المطلوبة
        bg_type = request.form.get("bg_type", "transparent")
        bg_value = None

        if bg_type == "color":
            bg_value = request.form.get("bg_color", "#FFFFFF")
        elif bg_type == "image" and "bg_image" in request.files:
            bg_file = request.files["bg_image"]
            if bg_file.filename != "":
                bg_value = bg_file.read()

        # افتح الصورة كـ PIL
        img = Image.open(file.stream).convert("RGBA")

        # إزالة الخلفية
        result = remove_bg_highres_pil(img)

        # تطبيق الخلفية
        final_image = apply_background(result, bg_type, bg_value)

        # حوّل الصورة إلى بايت للرد
        buf = BytesIO()
        final_image.save(buf, format="PNG")
        buf.seek(0)

        return send_file(
            buf,
            mimetype="image/png",
            as_attachment=True,
            download_name="no_bg.png"
        )
    except Exception as e:
        return jsonify({"error": f"خطأ أثناء المعالجة: {e}"}), 500


def cleanup_old_files():
    """تنظيف الملفات القديمة"""
    # يمكن استدعاء هذه الوظيفة دورياً (مثلاً بواسطة APScheduler)
    cleanup_dir(UPLOAD_FOLDER, max_age_hours=1)
    cleanup_dir(PROCESSED_FOLDER, max_age_hours=1)


def cleanup_dir(directory, max_age_hours=1):
    """حذف الملفات القديمة من مجلد معين"""
    import time
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        file_modified = os.path.getmtime(file_path)
        if current_time - file_modified > max_age_seconds:
            try:
                os.remove(file_path)
                print(f"تم حذف الملف القديم: {file_path}")
            except Exception as e:
                print(f"خطأ أثناء حذف الملف {file_path}: {e}")


if __name__ == "__main__":
    # تنظيف الملفات القديمة عند بدء التشغيل
    cleanup_old_files()

    # تشغيل التطبيق
    app.run(debug=True)