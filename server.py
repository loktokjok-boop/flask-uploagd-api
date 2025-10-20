from flask import Flask, request, jsonify, render_template_string, send_from_directory
from datetime import datetime, time
from zoneinfo import ZoneInfo
import os, json, uuid

app = Flask(__name__)

# Папка для сохранения сканов
SAVE_FOLDER = "received_json"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Валидные коды
VALID = {
    "ABC1": {"type": "Էվն Իգազարյան"},
    "ABC2": {"type": "Նարեկ Թովմասյան"},
    "ABC3": {"type": "Արտյոմ Եղիազարյան"},
    "ABC4 ": {"type": "Վահե Այվազյան"}
}

# --- Сохранение записи ---
def save_record(rec):
    fname = f"scan_{datetime.now(ZoneInfo('Asia/Yerevan')).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    path = os.path.join(SAVE_FOLDER, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON file: {path}")
    return fname

# --- Поиск последнего скана по коду ---
def get_last_record_by_code(code):
    files = sorted(os.listdir(SAVE_FOLDER), reverse=True)
    for file in files:
        if file.endswith(".json"):
            path = os.path.join(SAVE_FOLDER, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("code") == code:
                    return data, file
    return None, None

# --- Основной маршрут ---
@app.route("/upload", methods=["GET", "POST"])
def upload():
    erevan_now = datetime.now(ZoneInfo("Asia/Yerevan"))

    if request.method == "POST":
        if not request.is_json:
            return jsonify({"status": "error", "msg": "expected JSON"}), 400

        payload = request.get_json()
        print("Received JSON:", payload)

        # --- Парсим данные ---
        raw_code = payload.get("code", "{}")
        try:
            code_data = json.loads(raw_code) if isinstance(raw_code, str) else raw_code
        except json.JSONDecodeError:
            code_data = {}

        code = code_data.get("id") or ""
        user_type = code_data.get("type") or "unknown"
        device = payload.get("device", "unknown")
        time_sent = payload.get("time") or erevan_now.isoformat()

        # Если код известен, подставляем пользователя из VALID
        if code in VALID:
            user_type = VALID[code]["type"]

        on_time = erevan_now.time() <= time(8, 20)

        record = {
            "code": code,
            "user_type": user_type,
            "device": device,
            "time_sent": time_sent,
            "received_at": erevan_now.isoformat(),
            "on_time": on_time
        }

        filename = save_record(record)

        msg = "Пройдено вовремя ✅" if on_time else "Опоздание ❌"
        allowed = on_time if code in VALID else False

        return jsonify({
            "status": "ok" if code in VALID else "error",
            "allowed": allowed,
            "msg": msg,
            "record": record,
            "file": f"/files/{filename}"
        }), 200

    else:  # GET
        code = (request.args.get("id") or "").strip()
        record, filename = get_last_record_by_code(code)
        if not record:
            return f"<p>Нет записей для кода {code}</p>", 404

        html_template = """
        <h2>Результат проверки QR</h2>
        <p>Код: {{ record['code'] }}</p>
        <p>Пользователь: {{ record['user_type'] }}</p>
        <p>Устройство: {{ record['device'] }}</p>
        <p>Время отправки: {{ record['time_sent'] }}</p>
        <p>Время получения (Ереван): {{ record['received_at'] }}</p>
        <p>Статус: {% if record['on_time'] %}Пройдено вовремя ✅{% else %}Опоздание ❌{% endif %}</p>
        <p><a href="/files/{{ filename }}" target="_blank">📄 Скачать JSON</a></p>
        """
        return render_template_string(html_template, record=record, filename=filename)

# --- Отдача файлов ---
@app.route("/files/<filename>")
def get_file(filename):
    return send_from_directory(SAVE_FOLDER, filename, as_attachment=True)

# --- Список всех файлов ---
@app.route("/files", methods=["GET"])
def list_files():
    files = os.listdir(SAVE_FOLDER)
    return jsonify({"files": files})

# --- Все сканы ---
@app.route("/all_scans_view", methods=["GET"])
def all_scans_view():
    all_records = []
    files = sorted(os.listdir(SAVE_FOLDER), reverse=True)
    for file in files:
        if file.endswith(".json"):
            path = os.path.join(SAVE_FOLDER, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_records.append(data)

    html = "<h2>Все сканы</h2><table border='1'><tr><th>Код</th><th>Пользователь</th><th>Устройство</th><th>Время</th><th>Статус</th></tr>"
    for r in all_records:
        status = "✅" if r.get("on_time") else "❌"
        html += f"<tr><td>{r.get('code')}</td><td>{r.get('user_type')}</td><td>{r.get('device')}</td><td>{r.get('received_at')}</td><td>{status}</td></tr>"
    html += "</table>"
    return html

# --- Запуск сервера ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
