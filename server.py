from flask import Flask, request, jsonify
from datetime import datetime, time
import os, json, uuid

app = Flask(__name__)

# Папка для хранения JSON
SAVE_FOLDER = "received_json"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Список допустимых QR‑кодов
VALID = {
    "ABC123": {"type": "user1"},
    "XYZ789": {"type": "user2"}
}

# Функция для сохранения данных в отдельный файл
def save_record(rec):
    fname = os.path.join(
        SAVE_FOLDER,
        f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    )
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return fname

@app.route("/upload", methods=["GET", "POST"])
def upload():
    # Определяем код из POST JSON или GET параметра
    if request.method == "POST":
        if not request.is_json:
            return jsonify({"status": "error", "msg": "expected JSON"}), 400
        payload = request.get_json()
        code = (payload.get("id") or "").strip()
        user_type = payload.get("type", "unknown")
        device = payload.get("device", "unknown")
        time_sent = payload.get("time") or datetime.now().isoformat()
    else:
        # GET-запрос через браузер / QR
        code = request.args.get("id", "").strip()
        user_type = "unknown"
        device = "unknown"
        time_sent = datetime.now().isoformat()

    now = datetime.now().time()
    limit_time = time(8, 20)
    on_time = now <= limit_time

    record = {
        "code": code,
        "user_type": user_type,
        "device": device,
        "time_sent": time_sent,
        "received_at": datetime.now().isoformat(),
        "on_time": on_time
    }
    save_record(record)

    # Проверка QR-кода
    if code in VALID:
        name = VALID[code]["type"]
        msg = "Пройдено вовремя ✅" if on_time else "Опоздание ❌ (после 8:20)"
        allowed = on_time
    else:
        name = None
        msg = "Код не найден ❌"
        allowed = False

    # GET-запрос — возвращаем HTML для браузера
    if request.method == "GET":
        return f"""
        <h2>Результат проверки QR</h2>
        <p>Код: {code}</p>
        <p>Статус: {msg}</p>
        """, 200

    # POST — возвращаем JSON
    return jsonify({
        "status": "ok" if name else "error",
        "allowed": allowed,
        "msg": msg,
        "name": name
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Server running on http://0.0.0.0:{port}/upload")
    app.run(host='0.0.0.0', port=port, debug=True)
