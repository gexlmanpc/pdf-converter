# PDF ↔ Word Converter — دليل الرفع على Render.com

## الملفات المطلوبة
```
📁 مجلدك
 ├── app.py
 ├── requirements.txt
 └── Procfile
```

---

## خطوات الرفع (10 دقائق فقط)

### 1️⃣ أنشئ حساب GitHub
- روح: https://github.com
- سجّل حساب مجاني

### 2️⃣ ارفع الملفات على GitHub
- اضغط زر "+" ← "New repository"
- سمّه: `pdf-converter`
- اضغط "Create repository"
- ارفع الملفات الثلاثة (app.py, requirements.txt, Procfile)

### 3️⃣ أنشئ حساب Render.com
- روح: https://render.com
- سجّل بحساب GitHub مباشرة

### 4️⃣ أنشئ Web Service
- اضغط "New +" ← "Web Service"
- اختر repository اسمه `pdf-converter`
- الإعدادات:
  - **Name**: pdf-converter
  - **Runtime**: Python 3
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- اضغط "Create Web Service"

### 5️⃣ انتظر الـ Deploy (3-5 دقائق)
بعد ما يخلص، ستحصل على رابط مثل:
`https://pdf-converter-xxxx.onrender.com`

---

## ⚠️ ملاحظة مهمة
- الخطة المجانية في Render تنام بعد 15 دقيقة من عدم الاستخدام
- أول طلب بعد النوم يأخذ ~30 ثانية للاستيقاظ
- تحويل Word←PDF يحتاج LibreOffice على السيرفر (مثبت تلقائياً)

---

## هل تواجه مشكلة؟
راسل على GitHub Issues أو تواصل مع المطور.
