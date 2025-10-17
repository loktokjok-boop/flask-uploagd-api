from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, time
import os, json, uuid

app = Flask(__name__)

# Папка для хранения JSON-файлов
SAVE_FOLDER = "received_json"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Список допустимых кодов и их типы
VALID = {
    "ABC123": {"type": "user1"},
    "XYZ789": {"type": "user2"}
}

# Функция для сохранения JSON-файла
def save_record(rec):
    fname = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    path = os.path.join(SAVE_FOLDER, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON file: {path}")
    return fname

# Основной маршрут
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if not request.is_json:
            return jsonify({"status": "error", "msg": "expected JSON"}), 400

        payload = request.get_json()
        print("Received JSON:", payload)  # для логов

        code = (payload.get("id") or "").strip()
        user_type = payload.get("type", "unknown")
        device = payload.get("device", "unknown")
        time_sent = payload.get("time") or datetime.now().isoformat()

        # Автоопределение user_type по таблице VALID
        if user_type == "unknown" and code in VALID:
            user_type = VALID[code]["type"]

    else:
        # Если пришёл GET-запрос (например, при открытии QR в браузере)
        code = request.args.get("id", "").strip()
        user_type = VALID[code]["type"] if code in VALID else "unknown"
        device = "browser"
        time_sent = datetime.now().isoformat()

    # Проверка на опоздание (до 08:20)
    now = datetime.now().time()
    on_time = now <= time(8, 20)

    # Сохраняем запись
    record = {
        "code": code,
        "user_type": user_type,
        "device": device,
        "time_sent": time_sent,
        "received_at": datetime.now().isoformat(),
        "on_time": on_time
    }
    filename = save_record(record)

    # Формируем ответ
    if code in VALID:
        name = VALID[code]["type"]
        msg = "Пройдено вовремя ✅" if on_time else "Опоздание ❌"
        allowed = on_time
    else:
        name = None
        msg = "Код не найден ❌"
        allowed = False

    if request.method == "GET":
        return f"""
        <h2>Результат проверки QR</h2>
        <p>Код: {code}</p>
        <p>Пользователь: {user_type}</p>
        <p>Статус: {msg}</p>
        <p><a href="/files/{filename}" target="_blank">📄 Скачать JSON</a></p>
        """, 200

    return jsonify({
        "status": "ok" if name else "error",
        "allowed": allowed,
        "msg": msg,
        "name": name,
        "file": f"/files/{filename}"
    }), 200

# Отдача сохранённых JSON-файлов
@app.route("/files/<filename>")
def get_file(filename):
    return send_from_directory(SAVE_FOLDER, filename)

# Список всех JSON-файлов (удобно для проверки)
@app.route("/files", methods=["GET"])
def list_files():
    files = os.listdir(SAVE_FOLDER)
    return jsonify({"files": files})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
