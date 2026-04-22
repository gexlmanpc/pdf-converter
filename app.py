"""
PDF ↔ Word Converter — Flask Web Application
يشتغل على Render.com / Railway.app مجاناً
"""

import os
import uuid
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename

# ── Optional imports (graceful fallback for deploy check) ──────────
try:
    from pdf2docx import Converter as PDF2DOCXConverter
    HAS_PDF2DOCX = True
except ImportError:
    HAS_PDF2DOCX = False

try:
    import docx2pdf
    HAS_DOCX2PDF = True
except ImportError:
    HAS_DOCX2PDF = False

# ══════════════════════════════════════════════════════════════════
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload

UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("outputs")
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

# Track conversion jobs: job_id → {status, progress, output_path, error}
jobs: dict = {}
jobs_lock = threading.Lock()

# ══════════════════════════════════════════════════════════════════
#  HTML TEMPLATE — Single-page app
# ══════════════════════════════════════════════════════════════════
HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PDF ↔ Word Converter</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:        #0d1117;
    --surface:   #161b22;
    --card:      #1c2333;
    --border:    #30363d;
    --accent:    #0ea5e9;
    --accent2:   #38bdf8;
    --success:   #22c55e;
    --error:     #ef4444;
    --text:      #e6edf3;
    --muted:     #8b949e;
    --radius:    16px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Tajawal', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  /* ── Background glow ── */
  body::before {
    content: '';
    position: fixed;
    top: -200px; left: 50%;
    transform: translateX(-50%);
    width: 800px; height: 600px;
    background: radial-gradient(ellipse, rgba(14,165,233,.12) 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
  }

  .container {
    width: 100%; max-width: 560px;
    padding: 24px 20px 60px;
    position: relative; z-index: 1;
  }

  /* ── Header ── */
  header {
    text-align: center;
    padding: 40px 0 32px;
  }
  .logo {
    font-size: 52px;
    display: inline-block;
    filter: drop-shadow(0 0 24px rgba(14,165,233,.5));
    animation: float 3s ease-in-out infinite;
  }
  @keyframes float {
    0%,100% { transform: translateY(0); }
    50%      { transform: translateY(-8px); }
  }
  header h1 {
    font-size: 28px; font-weight: 900;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 12px 0 6px;
  }
  header p { color: var(--muted); font-size: 15px; }

  /* ── Card ── */
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    margin-bottom: 16px;
  }

  /* ── Mode Toggle ── */
  .mode-toggle {
    display: grid;
    grid-template-columns: 1fr 1fr;
    background: var(--surface);
    border-radius: 12px;
    padding: 4px;
    gap: 4px;
    margin-bottom: 24px;
  }
  .mode-btn {
    border: none; cursor: pointer;
    padding: 12px;
    border-radius: 10px;
    font-family: 'Tajawal', sans-serif;
    font-size: 15px; font-weight: 700;
    transition: all .25s;
    background: transparent;
    color: var(--muted);
  }
  .mode-btn.active {
    background: var(--accent);
    color: #fff;
    box-shadow: 0 4px 16px rgba(14,165,233,.35);
  }

  /* ── Drop Zone ── */
  .drop-zone {
    border: 2px dashed var(--border);
    border-radius: 14px;
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
    transition: all .25s;
    background: rgba(14,165,233,.03);
    position: relative;
  }
  .drop-zone:hover, .drop-zone.dragover {
    border-color: var(--accent);
    background: rgba(14,165,233,.08);
    transform: scale(1.01);
  }
  .drop-zone input[type=file] {
    position: absolute; inset: 0;
    opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .drop-icon { font-size: 44px; margin-bottom: 12px; }
  .drop-zone h3 { font-size: 17px; margin-bottom: 6px; }
  .drop-zone p  { color: var(--muted); font-size: 13px; }

  /* ── File preview ── */
  .file-preview {
    display: none;
    align-items: center;
    gap: 14px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 18px;
    margin-top: 14px;
  }
  .file-preview.show { display: flex; }
  .file-preview .icon { font-size: 28px; }
  .file-preview .info { flex: 1; min-width: 0; }
  .file-preview .name {
    font-weight: 700; font-size: 14px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .file-preview .size { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .remove-btn {
    background: none; border: none; cursor: pointer;
    color: var(--muted); font-size: 20px; padding: 4px;
    border-radius: 6px; transition: color .2s;
  }
  .remove-btn:hover { color: var(--error); }

  /* ── Convert Button ── */
  .convert-btn {
    width: 100%; padding: 16px;
    background: linear-gradient(135deg, var(--accent), #0284c7);
    color: #fff; border: none; cursor: pointer;
    border-radius: 12px;
    font-family: 'Tajawal', sans-serif;
    font-size: 17px; font-weight: 700;
    margin-top: 20px;
    transition: all .25s;
    box-shadow: 0 4px 20px rgba(14,165,233,.3);
  }
  .convert-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(14,165,233,.45);
  }
  .convert-btn:disabled {
    opacity: .6; cursor: not-allowed; transform: none;
  }

  /* ── Progress ── */
  .progress-wrap { margin-top: 20px; display: none; }
  .progress-wrap.show { display: block; }
  .progress-bar-bg {
    background: var(--surface);
    border-radius: 999px;
    height: 10px; overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 999px;
    width: 0%;
    transition: width .4s ease;
  }
  .progress-label {
    display: flex; justify-content: space-between;
    font-size: 13px; color: var(--muted);
    margin-bottom: 8px;
  }

  /* ── Status ── */
  .status {
    text-align: center;
    padding: 14px;
    border-radius: 12px;
    margin-top: 16px;
    font-weight: 700;
    font-size: 15px;
    display: none;
  }
  .status.show { display: block; }
  .status.success { background: rgba(34,197,94,.12); color: var(--success); border: 1px solid rgba(34,197,94,.25); }
  .status.error   { background: rgba(239,68,68,.12);  color: var(--error);   border: 1px solid rgba(239,68,68,.25); }
  .status.info    { background: rgba(14,165,233,.10); color: var(--accent);  border: 1px solid rgba(14,165,233,.25); }

  /* ── Download button ── */
  .download-btn {
    display: none;
    width: 100%;
    padding: 15px;
    background: linear-gradient(135deg, var(--success), #16a34a);
    color: #fff; border: none; cursor: pointer;
    border-radius: 12px;
    font-family: 'Tajawal', sans-serif;
    font-size: 17px; font-weight: 700;
    margin-top: 12px;
    text-decoration: none;
    text-align: center;
    transition: all .25s;
    box-shadow: 0 4px 20px rgba(34,197,94,.3);
  }
  .download-btn.show { display: block; }
  .download-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(34,197,94,.45); }

  /* ── Footer ── */
  footer {
    text-align: center;
    color: var(--muted);
    font-size: 13px;
    padding: 20px;
    position: relative; z-index: 1;
  }

  /* ── Responsive ── */
  @media (max-width: 480px) {
    header h1 { font-size: 22px; }
    .card { padding: 20px; }
  }
</style>
</head>
<body>

<div class="container">
  <header>
    <div class="logo">⇄</div>
    <h1>PDF ↔ Word Converter</h1>
    <p>حوّل ملفاتك مجاناً — بدون تثبيت، من أي جهاز</p>
  </header>

  <div class="card">
    <!-- Mode Toggle -->
    <div class="mode-toggle">
      <button class="mode-btn active" onclick="setMode('pdf_to_word')">📄 PDF ← Word</button>
      <button class="mode-btn"        onclick="setMode('word_to_pdf')">📝 Word ← PDF</button>
    </div>

    <!-- Drop Zone -->
    <div class="drop-zone" id="dropZone">
      <input type="file" id="fileInput" accept=".pdf,.docx,.doc" onchange="onFileSelect(this)">
      <div class="drop-icon" id="dropIcon">📂</div>
      <h3>اسحب وأفلت الملف هنا</h3>
      <p id="dropHint">أو اضغط لاختيار ملف PDF</p>
    </div>

    <!-- File Preview -->
    <div class="file-preview" id="filePreview">
      <div class="icon" id="previewIcon">📄</div>
      <div class="info">
        <div class="name" id="previewName"></div>
        <div class="size" id="previewSize"></div>
      </div>
      <button class="remove-btn" onclick="clearFile()">✕</button>
    </div>

    <!-- Convert Button -->
    <button class="convert-btn" id="convertBtn" onclick="startConversion()">
      ⚡ ابدأ التحويل
    </button>

    <!-- Progress -->
    <div class="progress-wrap" id="progressWrap">
      <div class="progress-label">
        <span id="progressText">جاري التحويل...</span>
        <span id="progressPct">0%</span>
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" id="progressFill"></div>
      </div>
    </div>

    <!-- Status -->
    <div class="status" id="statusBox"></div>

    <!-- Download -->
    <a class="download-btn" id="downloadBtn" href="#" download>
      ⬇️ تحميل الملف المحوّل
    </a>
  </div>
</div>

<footer>صُنع بـ ❤️ · يعمل على Render.com مجاناً</footer>

<script>
let currentMode = 'pdf_to_word';
let selectedFile = null;
let pollInterval = null;

// ── Mode switching ────────────────────────────────────────────────
function setMode(mode) {
  currentMode = mode;
  clearFile();
  const btns = document.querySelectorAll('.mode-btn');
  btns[0].classList.toggle('active', mode === 'pdf_to_word');
  btns[1].classList.toggle('active', mode === 'word_to_pdf');

  const hint = document.getElementById('dropHint');
  const input = document.getElementById('fileInput');
  if (mode === 'pdf_to_word') {
    hint.textContent = 'أو اضغط لاختيار ملف PDF';
    input.accept = '.pdf';
  } else {
    hint.textContent = 'أو اضغط لاختيار ملف Word (.docx)';
    input.accept = '.docx,.doc';
  }
}

// ── File selection ────────────────────────────────────────────────
function onFileSelect(input) {
  if (!input.files.length) return;
  const file = input.files[0];
  const ext = file.name.split('.').pop().toLowerCase();

  if (currentMode === 'pdf_to_word' && ext !== 'pdf') {
    showStatus('⚠️ الرجاء اختيار ملف PDF', 'error'); return;
  }
  if (currentMode === 'word_to_pdf' && !['docx','doc'].includes(ext)) {
    showStatus('⚠️ الرجاء اختيار ملف Word (.docx)', 'error'); return;
  }

  selectedFile = file;
  document.getElementById('previewName').textContent = file.name;
  document.getElementById('previewSize').textContent = formatSize(file.size);
  document.getElementById('previewIcon').textContent = ext === 'pdf' ? '📄' : '📝';
  document.getElementById('filePreview').classList.add('show');
  hideStatus(); hideDownload();
}

function clearFile() {
  selectedFile = null;
  document.getElementById('fileInput').value = '';
  document.getElementById('filePreview').classList.remove('show');
  setProgress(0);
  document.getElementById('progressWrap').classList.remove('show');
  hideStatus(); hideDownload();
}

// ── Drag and drop ─────────────────────────────────────────────────
const dropZone = document.getElementById('dropZone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('dragover');
  const dt = e.dataTransfer;
  if (dt.files.length) {
    document.getElementById('fileInput').files = dt.files;
    onFileSelect(document.getElementById('fileInput'));
  }
});

// ── Conversion ────────────────────────────────────────────────────
async function startConversion() {
  if (!selectedFile) { showStatus('⚠️ الرجاء اختيار ملف أولاً', 'error'); return; }

  const btn = document.getElementById('convertBtn');
  btn.disabled = true;
  btn.textContent = '⏳ جاري الرفع...';
  hideStatus(); hideDownload();
  showProgress();
  setProgress(5);

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('mode', currentMode);

  try {
    const res = await fetch('/convert', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || 'فشل الرفع');
    }

    setProgress(20);
    btn.textContent = '⏳ جاري التحويل...';
    pollJob(data.job_id);

  } catch (err) {
    showStatus('❌ ' + err.message, 'error');
    btn.disabled = false;
    btn.textContent = '⚡ ابدأ التحويل';
    hideProgress();
  }
}

function pollJob(jobId) {
  let dots = 0;
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch('/status/' + jobId);
      const data = await res.json();
      dots = (dots + 1) % 4;

      if (data.status === 'done') {
        clearInterval(pollInterval);
        setProgress(100);
        document.getElementById('progressText').textContent = '✅ اكتمل التحويل';
        showStatus('✅ تم التحويل بنجاح! اضغط للتحميل', 'success');
        showDownload('/download/' + jobId, data.filename);
        const btn = document.getElementById('convertBtn');
        btn.disabled = false; btn.textContent = '⚡ ابدأ التحويل';

      } else if (data.status === 'error') {
        clearInterval(pollInterval);
        showStatus('❌ ' + (data.error || 'حدث خطأ'), 'error');
        hideProgress();
        const btn = document.getElementById('convertBtn');
        btn.disabled = false; btn.textContent = '⚡ ابدأ التحويل';

      } else {
        // still processing — animate
        const pct = Math.min(20 + data.progress * 75, 90);
        setProgress(pct);
        document.getElementById('progressText').textContent =
          'جاري التحويل' + '.'.repeat(dots + 1);
      }
    } catch(_) {}
  }, 800);
}

// ── UI Helpers ────────────────────────────────────────────────────
function setProgress(pct) {
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressPct').textContent = Math.round(pct) + '%';
}
function showProgress() { document.getElementById('progressWrap').classList.add('show'); }
function hideProgress()  { document.getElementById('progressWrap').classList.remove('show'); }
function showStatus(msg, type) {
  const el = document.getElementById('statusBox');
  el.textContent = msg; el.className = 'status show ' + type;
}
function hideStatus() {
  document.getElementById('statusBox').className = 'status';
}
function showDownload(url, filename) {
  const btn = document.getElementById('downloadBtn');
  btn.href = url;
  btn.download = filename;
  btn.classList.add('show');
}
function hideDownload() { document.getElementById('downloadBtn').classList.remove('show'); }
function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/1048576).toFixed(2) + ' MB';
}
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/convert", methods=["POST"])
def convert():
    """Receive the uploaded file, spawn background conversion, return job_id."""
    if "file" not in request.files:
        return jsonify({"error": "لم يتم إرسال ملف"}), 400

    file = request.files["file"]
    mode = request.form.get("mode", "pdf_to_word")

    if file.filename == "":
        return jsonify({"error": "اسم الملف فارغ"}), 400

    ext = Path(file.filename).suffix.lower()
    if mode == "pdf_to_word" and ext != ".pdf":
        return jsonify({"error": "يجب أن يكون الملف بصيغة PDF"}), 400
    if mode == "word_to_pdf" and ext not in (".docx", ".doc"):
        return jsonify({"error": "يجب أن يكون الملف بصيغة DOCX"}), 400

    job_id = str(uuid.uuid4())
    safe_name = secure_filename(file.filename)
    input_path = UPLOAD_FOLDER / f"{job_id}_{safe_name}"
    file.save(str(input_path))

    # Determine output path
    if mode == "pdf_to_word":
        out_name = Path(safe_name).stem + ".docx"
    else:
        out_name = Path(safe_name).stem + ".pdf"
    output_path = OUTPUT_FOLDER / f"{job_id}_{out_name}"

    with jobs_lock:
        jobs[job_id] = {
            "status": "processing",
            "progress": 0.0,
            "output_path": str(output_path),
            "filename": out_name,
            "error": None,
        }

    # Spawn background thread
    thread = threading.Thread(
        target=_conversion_worker,
        args=(job_id, str(input_path), str(output_path), mode),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    """Poll conversion status."""
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify({
        "status":   job["status"],
        "progress": job["progress"],
        "filename": job["filename"],
        "error":    job["error"],
    })


@app.route("/download/<job_id>")
def download(job_id):
    """Stream the converted file to the browser."""
    with jobs_lock:
        job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "not ready"}), 404
    return send_file(
        job["output_path"],
        as_attachment=True,
        download_name=job["filename"],
    )


# ══════════════════════════════════════════════════════════════════
#  CONVERSION WORKER
# ══════════════════════════════════════════════════════════════════

def _set_job(job_id, **kwargs):
    with jobs_lock:
        jobs[job_id].update(kwargs)


def _conversion_worker(job_id, src: str, dst: str, mode: str):
    try:
        if mode == "pdf_to_word":
            if not HAS_PDF2DOCX:
                raise RuntimeError("مكتبة pdf2docx غير مثبتة على السيرفر")
            _set_job(job_id, progress=0.1)
            cv = PDF2DOCXConverter(src)
            cv.convert(dst, start=0, end=None)
            cv.close()
            _set_job(job_id, progress=0.95)

        else:  # word_to_pdf
            if not HAS_DOCX2PDF:
                raise RuntimeError("مكتبة docx2pdf غير مثبتة على السيرفر")
            _set_job(job_id, progress=0.1)
            docx2pdf.convert(src, dst)
            _set_job(job_id, progress=0.95)

        _set_job(job_id, status="done", progress=1.0)

    except Exception as exc:
        _set_job(job_id, status="error", error=str(exc))

    finally:
        # Clean up uploaded input file
        try:
            Path(src).unlink(missing_ok=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
