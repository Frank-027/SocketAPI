# examen_dashboard.py
from flask import Flask, jsonify, render_template_string
import Examen_core as core
from datetime import datetime

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Heartbeat Monitor</title>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial; margin: 40px;">
    <h1>Studenten Live Monitor</h1>
    <p>Status wordt elke seconde bijgewerkt.</p>

    <table border="1" cellpadding="10">
        <thead>
            <tr>
                <th>Naam</th>
                <th>Laatste PONG tijd</th>
                <th>Inactiviteit (s)</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody id="students"></tbody>
    </table>

    <script>
        async function update() {
            const res = await fetch('/status');
            const data = await res.json();

            let html = "";
            for (const s of data.students) {
                html += `
                    <tr>
                        <td>${s.name}</td>
                        <td>${s.last_pong}</td>
                        <td>${s.inactive_seconds.toFixed(1)}</td>
                        <td style="color:${s.online ? 'green' : 'red'}; font-weight:bold;">
                            ${s.online ? 'ONLINE' : 'OFFLINE'}
                        </td>
                    </tr>
                `;
            }
            document.getElementById("students").innerHTML = html;
        }

        setInterval(update, 1000);
        update();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/status")
def status():
    now = datetime.now()
    students = []
    for conn, name in core.clients.items():
        last = core.last_pong[name]
        diff = (now - last).total_seconds()
        online = diff <= core.TIMEOUT_SECONDS
        students.append({
            "name": name,
            "last_pong": last.strftime("%H:%M:%S"),
            "inactive_seconds": diff,
            "online": online
        })
    return jsonify({"students": students})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
