from flask import Flask, request, jsonify
from datetime import datetime, time
import os, json, uuid, socket

app = Flask(__name__)

# Папка для хранения JSON
SAVE_FOLDER = "received_json"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Список допустимых QR‑кодов
VALID = {
    "ABC123": {"type": "user1"},
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
    if request.method == "POST":
        if not request.is_json:
            return jsonify({"status": "error", "msg": "expected json"}), 400

        payload = request.get_json()
        # print("Получен payload:", payload)

        code = (payload.get("id") or "").strip()
        user_type = payload.get("type", "unknown")
        device = payload.get("device", "unknown")
        time_sent = payload.get("time") or datetime.now().isoformat()

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

        # ---- Блок с проверкой ----
        if code in VALID:
            name = VALID[code]["type"]
            if on_time:
                result = {
                    "status": "ok",
                    "allowed": True,
                    "msg": "Пройдено вовремя ✅",
                    "name": name
                }
            else:
                result = {
                    "status": "ok",
                    "allowed": False,
                    "msg": "Опоздание ❌ (после 8:20)",
                    "name": name
                }
        else:
            result = {
                "status": "error",
                "allowed": False,
                "msg": "Код не найден ❌"
            }

        return jsonify(result), 200

    return jsonify({"status": "error", "msg": "Invalid method"}), 405


if __name__ == '__main__':
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Server running on: http://{local_ip}:5000/upload")
    app.run(host='0.0.0.0', port=5000)


import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
