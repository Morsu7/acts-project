import argparse
import datetime
import json
import redis

def start_monitoring(show_traffic_lights=True, show_vehicles=True, show_failsafe=False, target_intersection=None):
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    pubsub = r.pubsub()
    
    # Se è specificato un incrocio, ascoltiamo SOLO il suo canale (i veicoli verranno ignorati in automatico)
    if target_intersection is not None:
        pubsub.psubscribe(f'channel_{target_intersection}')
        print(f"🚦 ACTS MONITOR - Modalità Focus Incrocio I_{target_intersection}")
    else:
        pubsub.psubscribe('traffic_channel', 'channel_*')
        print("🚦 ACTS TRAFFIC CONTROL CENTER - DISTRIBUTED MONITOR")

    print("-" * 135)
    print(f"{'TIME':<10} | {'CLOCK':<6} | {'INCROCIO':<8} | {'AGENT':<12} | EVENTO")
    print("-" * 135)

    for message in pubsub.listen():
        if message['type'] in ['message', 'pmessage']:
            try:
                payload = json.loads(message['data'])
                
                # Estraiamo il canale per capire a quale incrocio appartiene il messaggio
                channel = message['channel']
                if channel.startswith('channel_'):
                    incrocio = f"I_{channel.split('_')[1]}"
                else:
                    incrocio = "GLOBAL"
                
                agent = payload['agent_id']
                clock_val = payload.get('clock', 0)
                clock_str = f"L:{clock_val}" if clock_val > 0 else "SYS"
                
                evt = payload['event']
                data = payload['data']
                
                ts = datetime.datetime.now().strftime("%H:%M:%S")

                # ==========================================
                # EVENTI DEI VEICOLI (Canale Globale)
                # ==========================================
                if show_vehicles and incrocio == "GLOBAL":
                    if evt == "DEPARTING":
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | 💨 DRIVING {data['from']} -> {data['to']} ({data['duration']}s)")

                    elif evt == "PLANNING_ASTAR":
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | 🧭 A* target={data.get('dest')} steps={data.get('steps')}")

                # ==========================================
                # EVENTI DEL PROTOCOLLO DISTRIBUITO (SEMAFORI)
                # ==========================================
                if show_traffic_lights and incrocio != "GLOBAL":
                    # Negoziazione base
                    if evt == "REQUEST_GREEN":
                        score = float(data.get('queue_score', 0))
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | 🟡 REQ GREEN   | Dir: {data.get('direction_id')} | Score: {score:.1f} | ReqClock: {data.get('request_clock')}")

                    elif evt == "ALLOW_GREEN":
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | 🟢 ALLOW GREEN | To: {data.get('target_tl_id')} | Dir: {data.get('target_direction_id')} | ReqClock: {data.get('request_clock')}")

                    # Propagazione delle Onde di Traffico
                    elif evt == "TRAFFIC_SIGNAL":
                        cars = float(data.get('num_cars', 0))
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | 🌊 WAVE ALERT  | To: {data.get('target_tl_id')} | Cars: {cars:.1f}")

                    elif evt == "TRAFFIC_SIGNAL_FORWARD":
                        cars = float(data.get('num_cars', 0))
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | ⏩ WAVE FWD    | To: {data.get('target_tl_id')} | Cars: {cars:.1f} | ETA: {data.get('eta')}s")

                # ==========================================
                # EVENTI DI FAILSAFE E HEALTH CHECK
                # ==========================================
                if show_failsafe and incrocio != "GLOBAL":
                    if evt == "HEALTH_CHECK":
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | 🩺 HEALTH CHECK| Are you alive?")
                        
                    elif evt == "ALIVE_SIGNAL":
                        print(f"{ts:<10} | {clock_str:<6} | {incrocio:<8} | {agent:<12} | 💓 ALIVE       | To: {data.get('target_tl_id')}")

            except Exception as e:
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACTS traffic monitor")
    parser.add_argument("--hide-traffic-lights", action="store_true", help="Nasconde i messaggi di negoziazione semaforica")
    parser.add_argument("--hide-vehicles", action="store_true", help="Nasconde i log di movimento dei veicoli per concentrarsi sul protocollo")
    parser.add_argument("--show-failsafe", action="store_true", help="Mostra i messaggi di HEALTH_CHECK e ALIVE_SIGNAL")
    
    # NUOVO ARGOMENTO PER IL FOCUS INCROCIO
    parser.add_argument("-i", "--intersection", type=str, default=None, help="Mostra solo i log di uno specifico incrocio (es. 0, 1, 2)")
    
    args = parser.parse_args()

    start_monitoring(
        show_traffic_lights=not args.hide_traffic_lights,
        show_vehicles=not args.hide_vehicles,
        show_failsafe=args.show_failsafe,
        target_intersection=args.intersection
    )