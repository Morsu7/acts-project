import redis
import json
import datetime

def start_monitoring():
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe('traffic_channel')
    
    print("📡 MONITOR DISTRIBUITO (Lamport Enabled)...")
    print("-" * 60)
    print(f"{'TIMESTAMP':<10} | {'LOGIC':<5} | {'AGENT':<6} | EVENTO")
    print("-" * 60)

    for message in pubsub.listen():
        if message['type'] == 'message':
            payload = json.loads(message['data'])
            
            agent = payload['agent_id']
            clock = payload.get('clock', 0) # Leggiamo il clock di Lamport
            evt = payload['event']
            data = payload['data']
            
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            
            if evt == "MOVED":
                details = f"{data['from']} -> {data['to']}"
                print(f"{ts:<10} | L:{clock:<3} | Auto {agent} | MOVED: {details}")
            elif evt == "ARRIVED":
                print(f"{ts:<10} | L:{clock:<3} | Auto {agent} | ✅ ARRIVED at {data['node']}")
            elif evt == "PLANNING":
                print(f"{ts:<10} | L:{clock:<3} | Auto {agent} | 🗺️  PLANNING ({data['steps']} steps)")

if __name__ == "__main__":
    start_monitoring()