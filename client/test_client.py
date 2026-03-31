import json
import uuid
import paho.mqtt.client as mqtt
import time

BROKER = "localhost"
ORG = "demo-org"
REQ_TOPIC = f"{ORG}/orchestrator/requests"
RES_TOPIC = f"{ORG}/orchestrator/results"

task_id = str(uuid.uuid4())

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode("utf-8"))
    if payload.get("task_id") == task_id:
        print("\n--- RECEIVED RESULT ---")
        print(payload["output"])
        print("-----------------------\n")
        client.disconnect()

def main():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(BROKER, 1883)
    client.subscribe(RES_TOPIC, qos=1)

    request = {
        "task_id": task_id,
        "input": "The future of renewable energy in urban environments."
    }
    
    print(f"Sending request: {request['input']}")
    client.publish(REQ_TOPIC, json.dumps(request), qos=1)
    client.loop_forever()

if __name__ == "__main__":
    main()
