from __future__ import annotations

from html import escape

import tornado.web


class TrafficLightControlHandler(tornado.web.RequestHandler):
    def get(self):
        model = self.application.model
        overview = model.get_traffic_light_overview()
        self.write(_render_control_page(self.application.port, overview))

    def post(self):
        traffic_light_id = self.get_body_argument("traffic_light_id", default="")
        if traffic_light_id:
            self.application.model.toggle_traffic_light(traffic_light_id)
        self.redirect("/traffic-lights")


def _render_control_page(port: int, overview: list[dict]) -> str:
    rows = []
    for intersection in overview:
        light_rows = []
        for traffic_light in intersection["traffic_lights"]:
            working = bool(traffic_light["working"])
            status_label = "Working" if working else "OFF"
            button_label = "Turn off" if working else "Turn on"
            badge_class = "badge-working" if working else "badge-off"
            light_rows.append(
                f"""
                <div class="light-card">
                    <div class="light-header">
                        <div>
                            <div class="light-title">{escape(str(traffic_light['traffic_light_id']))}</div>
                            <div class="light-meta">Node {escape(str(traffic_light['node_id']))}</div>
                        </div>
                        <span class="badge {badge_class}">{status_label}</span>
                    </div>
                    <div class="light-status">Current state: {escape(str(traffic_light['status_summary']))}</div>
                    <form method="post" action="/traffic-lights">
                        <input type="hidden" name="traffic_light_id" value="{escape(str(traffic_light['traffic_light_id']))}">
                        <button type="submit" class="toggle-button">{button_label}</button>
                    </form>
                </div>
                """
            )

        rows.append(
            f"""
            <section class="intersection-card">
                <h2>Intersection {escape(str(intersection['intersection_id']))}</h2>
                <div class="lights-grid">
                    {''.join(light_rows) if light_rows else '<div class="empty-state">No traffic lights found.</div>'}
                </div>
            </section>
            """
        )

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta http-equiv="refresh" content="2">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>ACTS Traffic Light Control</title>
        <style>
            :root {{
                color-scheme: light;
                --bg: #f4f6f8;
                --panel: #ffffff;
                --text: #1f2933;
                --muted: #667085;
                --border: #d0d7de;
                --accent: #135dff;
                --accent-soft: #e8f0ff;
                --working: #1b7f3a;
                --working-soft: #e4f7ea;
                --off: #9aa4b2;
                --off-soft: #eef1f4;
            }}
            body {{
                margin: 0;
                font-family: Arial, Helvetica, sans-serif;
                background: var(--bg);
                color: var(--text);
            }}
            header {{
                position: sticky;
                top: 0;
                background: rgba(244, 246, 248, 0.95);
                backdrop-filter: blur(6px);
                border-bottom: 1px solid var(--border);
                padding: 20px 24px 16px;
                z-index: 1;
            }}
            h1 {{ margin: 0 0 8px; font-size: 24px; }}
            .subtitle {{ color: var(--muted); font-size: 14px; }}
            .actions {{ margin-top: 12px; }}
            .actions a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
            main {{ padding: 24px; display: grid; gap: 20px; }}
            .intersection-card {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 18px;
                box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
            }}
            .intersection-card h2 {{ margin: 0 0 16px; font-size: 18px; }}
            .lights-grid {{ display: grid; gap: 12px; }}
            .light-card {{
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 14px;
                background: #fbfcfe;
            }}
            .light-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 12px;
                margin-bottom: 10px;
            }}
            .light-title {{ font-weight: 700; }}
            .light-meta, .light-status {{ color: var(--muted); font-size: 13px; }}
            .badge {{
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
            }}
            .badge-working {{ background: var(--working-soft); color: var(--working); }}
            .badge-off {{ background: var(--off-soft); color: var(--off); }}
            .toggle-button {{
                margin-top: 12px;
                border: 0;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 700;
                color: #fff;
                background: var(--accent);
                cursor: pointer;
            }}
            .toggle-button:hover {{ filter: brightness(0.95); }}
            .empty-state {{ color: var(--muted); }}
            @media (max-width: 720px) {{
                header, main {{ padding-left: 14px; padding-right: 14px; }}
                .light-header {{ flex-direction: column; }}
            }}
        </style>
    </head>
    <body>
        <header>
            <h1>Traffic Light Control</h1>
            <div class="subtitle">Separate control window for the ACTS simulation running on port {port}. The page refreshes every 2 seconds.</div>
            <div class="actions"><a href="/">Back to visualization</a></div>
        </header>
        <main>
            {''.join(rows) if rows else '<div class="intersection-card">No intersections found.</div>'}
        </main>
    </body>
    </html>
    """
