from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, time
from zoneinfo import ZoneInfo
import os, json, uuid

app = Flask(__name__)

# === Настройки ===
SAVE_FOLDER = "received_json"
os.makedirs(SAVE_FOLDER, exist_ok=True)

VALID = {
    "ABC123": {"type": "user1"},
    "XYZ789": {"type": "user2"}
}

# === Сохранение файла ===
def save_record(rec):
    fname = f"scan_{datetime.now(ZoneInfo('Asia/Yerevan')).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    path = os.path.join(SAVE_FOLDER, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON file: {path}")
    return fname

# === Поиск последнего скана по коду ===
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

# === Основной маршрут ===
@app.route("/upload", methods=["GET", "POST"])
def upload():
    erevan_now = datetime.now(ZoneInfo("Asia/Yerevan"))

    if request.method == "POST":
        if not request.is_json:
            return jsonify({"status": "error", "msg": "expected JSON"}), 400

        payload = request.get_json()
        print("Received JSON:", payload)

        code = (payload.get("id") or "").strip()
        user_type = payload.get("type", "unknown")
        device = payload.get("device", "unknown")
        time_sent = payload.get("time") or erevan_now.isoformat()

        if user_type == "unknown" and code in VALID:
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
            "name": user_type if code in VALID else None,
            "file": f"/files/{filename}"
        }), 200

    else:  # GET-запрос
        code = (request.args.get("id") or "").strip()
        record, filename = get_last_record_by_code(code)

        if not record:
            return f"<p>Нет записей для кода {code}</p>", 404

        return f"""
        <h2>Результат проверки QR</h2>
        <p>Код: {record['code']}</p>
        <p>Пользователь: {record['user_type']}</p>
        <p>Устройство: {record['device']}</p>
        <p>Время отправки: {record['time_sent']}</p>
        <p>Время получения (Ереван): {record['received_at']}</p>
        <p>Статус: {"Пройдено вовремя ✅" if record['on_time'] else "Опоздание ❌"}</p>
        <p><a href="/files/{filename}" target="_blank">📄 Скачать JSON</a></p>
        """, 200

# === Отдача файлов ===
@app.route("/files/<filename>")
def get_file(filename):
    return send_from_directory(SAVE_FOLDER, filename)

# === Список всех файлов ===
@app.route("/files", methods=["GET"])
def list_files():
    files = os.listdir(SAVE_FOLDER)
    return jsonify({"files": files})

# === Запуск ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
