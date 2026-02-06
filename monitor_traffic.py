import redis
import json
import datetime

def start_monitoring():
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
                
                elif evt == "ARRIVED_NODE":
                    # Opzionale: de-commenta se vuoi vedere ogni arrivo intermedio
                    # print(f"{ts:<10} | {clock_str:<6} | Auto {agent:<5} | 📍 ARRIVED Node {data['node']}")
                    pass

                elif evt == "PHASE_CHANGE":
                    # --- FIX QUI: Usiamo .get() per sicurezza e cerchiamo 'allowed_from' ---
                    phase = data.get('new_phase', '?')
                    # Prende 'allowed_from', se non c'è prova 'allowed', se no mette '?'
                    allowed = data.get('allowed_from', data.get('allowed', '?'))
                    
                    print(f"{ts:<10} | {clock_str:<6} | {agent:<10} | 🚦 SWITCH PHASE {phase} -> Green for: {allowed}")

            except Exception as e:
                # Stampa l'errore completo per debug se succede ancora
                print(f"Error decoding msg: {e} | Payload: {payload}")

if __name__ == "__main__":
    start_monitoring()