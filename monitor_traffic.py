import argparse
import datetime
import json

import redis

def start_monitoring(show_traffic_lights=True):
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe('traffic_channel')
    
    print("📡 ACTS TRAFFIC CONTROL CENTER")
    print("-" * 105)
    print(f"{'TIME':<10} | {'CLOCK':<6} | {'AGENT':<10} | EVENTO")
    print("-" * 105)

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                payload = json.loads(message['data'])
                
                agent = payload['agent_id']
                # Gestione Clock: se è 0 (come per i semafori), scriviamo SYS
                clock_val = payload.get('clock', 0)
                clock_str = f"L:{clock_val}" if clock_val > 0 else "SYS"
                
                evt = payload['event']
                data = payload['data']
                
                ts = datetime.datetime.now().strftime("%H:%M:%S")

                if evt == "DEPARTING":
                    print(f"{ts:<10} | {clock_str:<6} | Auto {agent:<5} | 💨 DRIVING {data['from']} -> {data['to']} ({data['duration']}s)")

                elif evt == "PLANNING_ASTAR":
                    print(f"{ts:<10} | {clock_str:<6} | Auto {agent:<5} | 🧭 A* target={data.get('dest')} steps={data.get('steps')}")

                elif evt == "TL_REQUEST":
                    print(f"{ts:<10} | {clock_str:<6} | Auto {agent:<5} | 📨 REQUEST TL_{data.get('target_intersection')} from {data.get('from_node')} to {data.get('to_node')}")

                elif evt == "TL_WAIT":
                    print(f"{ts:<10} | {clock_str:<6} | Auto {agent:<5} | ⛔ WAIT TL_{data.get('intersection')} from node {data.get('from_node')}")

                elif evt == "LOCK_WAIT":
                    print(f"{ts:<10} | {clock_str:<6} | Auto {agent:<5} | 🔒 WAIT LOCK node {data.get('node')} (I{data.get('intersection')})")
                
                elif evt == "ARRIVED_NODE":
                    # Opzionale: de-commenta se vuoi vedere ogni arrivo intermedio
                    # print(f"{ts:<10} | {clock_str:<6} | Auto {agent:<5} | 📍 ARRIVED Node {data['node']}")
                    pass

                elif evt == "PHASE_CHANGE":
                    if not show_traffic_lights:
                        continue
                    # --- FIX QUI: Usiamo .get() per sicurezza e cerchiamo 'allowed_from' ---
                    phase = data.get('new_phase', '?')
                    # Prende 'allowed_from', se non c'è prova 'allowed', se no mette '?'
                    allowed = data.get('allowed_from', data.get('allowed', '?'))
                    
                    print(f"{ts:<10} | {clock_str:<6} | {agent:<10} | 🚦 SWITCH PHASE {phase} -> Green for: {allowed}")

            except Exception as e:
                # Stampa l'errore completo per debug se succede ancora
                print(f"Error decoding msg: {e} | Payload: {payload}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACTS traffic monitor")
    parser.add_argument(
        "--hide-traffic-lights",
        action="store_true",
        help="Hide traffic light phase changes in the monitor",
    )
    args = parser.parse_args()

    start_monitoring(show_traffic_lights=not args.hide_traffic_lights)