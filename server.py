from flask import Flask, request, jsonify, render_template_string, send_from_directory, Response
from datetime import datetime, time
from zoneinfo import ZoneInfo
import os, json, uuid, queue, threading

app = Flask(__name__)

SAVE_FOLDER = "received_json"
os.makedirs(SAVE_FOLDER, exist_ok=True)

VALID = {
    "ABC1": {"type": "Էվն Իգազարյան"},
    "ABC2": {"type": "Նարեկ Թովմասյան"},
    "ABC3": {"type": "Արտյոմ Եղիազարյան"},
    "ABC4 ": {"type": "Վահե Այվազյան"},
    "ABC5 ": {"type": "Էրիկ Եղոյան"
                      ""}
}

# --- SSE: очередь событий для подключённых клиентов ---
_sse_listeners: list[queue.Queue] = []
_sse_lock = threading.Lock()


def _broadcast(event_data: dict):
    """Отправляем событие всем подключённым SSE-клиентам."""
    payload = f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_listeners:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_listeners.remove(q)


# --- SSE endpoint ---
@app.route("/events")
def sse_stream():
    q: queue.Queue = queue.Queue(maxsize=20)
    with _sse_lock:
        _sse_listeners.append(q)

    def generate():
        # Первое сообщение — keepalive
        yield ": keepalive\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            with _sse_lock:
                try:
                    _sse_listeners.remove(q)
                except ValueError:
                    pass

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- Сохранение записи ---
def save_record(rec):
    fname = f"scan_{datetime.now(ZoneInfo('Asia/Yerevan')).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    path = os.path.join(SAVE_FOLDER, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print(f"Saved: {path}")
    return fname


# --- Последний скан по коду ---
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


# --- Все сканы (список) ---
def load_all_records():
    all_records = []
    files = sorted(os.listdir(SAVE_FOLDER), reverse=True)
    for file in files:
        if file.endswith(".json"):
            path = os.path.join(SAVE_FOLDER, file)
            with open(path, "r", encoding="utf-8") as f:
                all_records.append(json.load(f))
    return all_records


# --- Основной маршрут ---
@app.route("/upload", methods=["GET", "POST"])
def upload():
    erevan_now = datetime.now(ZoneInfo("Asia/Yerevan"))

    if request.method == "POST":
        if not request.is_json:
            return jsonify({"status": "error", "msg": "expected JSON"}), 400

        payload = request.get_json()
        print("Received JSON:", payload)

        raw_code = payload.get("code", "{}")
        try:
            code_data = json.loads(raw_code) if isinstance(raw_code, str) else raw_code
        except json.JSONDecodeError:
            code_data = {}

        code = code_data.get("id") or ""
        user_type = code_data.get("type") or "unknown"
        device = payload.get("device", "unknown")
        time_sent = payload.get("time") or erevan_now.isoformat()

        if code in VALID:
            user_type = VALID[code]["type"]

        on_time = erevan_now.time() <= time(8, 20)

        record = {
            "code": code,
            "user_type": user_type,
            "device": device,
            "time_sent": time_sent,
            "received_at": erevan_now.isoformat(),
            "on_time": on_time,
        }

        filename = save_record(record)

        # 🔔 Уведомляем всех SSE-клиентов о новом скане
        _broadcast({"event": "new_scan", "record": record, "file": filename})

        msg = "Пройдено вовремя ✅" if on_time else "Опоздание ❌"
        allowed = on_time if code in VALID else False

        return jsonify({
            "status": "ok" if code in VALID else "error",
            "allowed": allowed,
            "msg": msg,
            "record": record,
            "file": f"/files/{filename}",
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


@app.route("/files", methods=["GET"])
def list_files():
    return jsonify({"files": os.listdir(SAVE_FOLDER)})


# --- Все сканы (живая таблица с SSE) ---
ALL_SCANS_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Все сканы — live</title>
<style>
  body { font-family: monospace; background: #0f0f0f; color: #e0e0e0; padding: 20px; }
  h2 { color: #7fff7f; }
  table { border-collapse: collapse; width: 100%; }
  th { background: #1a1a2e; color: #7fff7f; padding: 8px 12px; text-align: left; }
  td { padding: 8px 12px; border-bottom: 1px solid #222; }
  tr:hover td { background: #1a1a1a; }
  .ok  { color: #7fff7f; }
  .bad { color: #ff6b6b; }
  #status { margin-bottom: 12px; font-size: 13px; color: #888; }
  .new-row { animation: flash 1.2s ease-out; }
  @keyframes flash { from { background: #003300; } to { background: transparent; } }
</style>
</head>
<body>
<h2>📡 Все сканы (live)</h2>
<div id="status">Подключаемся...</div>
<table>
  <thead><tr>
    <th>Код</th><th>Пользователь</th><th>Устройство</th>
    <th>Время (Ереван)</th><th>Статус</th>
  </tr></thead>
  <tbody id="tbody">
    {% for r in records %}
    <tr>
      <td>{{ r.get('code','—') }}</td>
      <td>{{ r.get('user_type','—') }}</td>
      <td>{{ r.get('device','—') }}</td>
      <td>{{ r.get('received_at','—') }}</td>
      <td class="{{ 'ok' if r.get('on_time') else 'bad' }}">
        {{ '✅ Вовремя' if r.get('on_time') else '❌ Опоздание' }}
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
<script>
const tbody  = document.getElementById('tbody');
const status = document.getElementById('status');

function connect() {
  const es = new EventSource('/events');

  es.onopen = () => { status.textContent = '🟢 Подключено — обновляется автоматически'; };

  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.event !== 'new_scan') return;
    const r = msg.record;
    const onTime = r.on_time;
    const tr = document.createElement('tr');
    tr.className = 'new-row';
    tr.innerHTML = `
      <td>${r.code || '—'}</td>
      <td>${r.user_type || '—'}</td>
      <td>${r.device || '—'}</td>
      <td>${r.received_at || '—'}</td>
      <td class="${onTime ? 'ok' : 'bad'}">${onTime ? '✅ Вовремя' : '❌ Опоздание'}</td>`;
    tbody.insertBefore(tr, tbody.firstChild);
  };

  es.onerror = () => {
    status.textContent = '🔴 Соединение потеряно, переподключаемся...';
    es.close();
    setTimeout(connect, 3000);
  };
}

connect();
</script>
</body>
</html>
"""

@app.route("/all_scans_view", methods=["GET"])
def all_scans_view():
    records = load_all_records()
    return render_template_string(ALL_SCANS_HTML, records=records)


# --- Запуск ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # threaded=True обязателен для SSE
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
