import json
import uuid

import paho.mqtt.client as mqtt
import requests

from a2a.client.helpers import create_text_message_object
from a2a.types import (
    JSONRPCErrorResponse,
    Message,
    MessageSendParams,
    Role,
    SendMessageRequest,
    SendMessageResponse,
    Task,
    TextPart,
)

# Configuration
BROKER = "localhost"
ORG = "demo-org"
REQ_TOPIC = f"{ORG}/orchestrator/requests"
RES_TOPIC = f"{ORG}/orchestrator/results"
# Strands A2AServer speaks JSON-RPC at POST / (see a2a DEFAULT_RPC_URL), not /invoke
ORCH_A2A_URL = "http://localhost:9200/"


def _text_from_parts(parts) -> str:
    chunks = []
    for part in parts:
        root = part.root
        if isinstance(root, TextPart) and root.text:
            chunks.append(root.text)
    return "\n".join(chunks)


def _a2a_result_to_output(result: Message | Task) -> str:
    if isinstance(result, Message):
        return _text_from_parts(result.parts)
    if result.history:
        for message in reversed(result.history):
            if message.role == Role.agent:
                return _text_from_parts(message.parts)
    if result.artifacts:
        texts = []
        for art in result.artifacts:
            texts.append(_text_from_parts(art.parts))
        combined = "\n".join(t for t in texts if t)
        if combined:
            return combined
    if result.status and result.status.message:
        return _text_from_parts(result.status.message.parts)
    return ""


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        task_id = payload.get("task_id", str(uuid.uuid4()))
        user_input = payload.get("input")

        print(f"Received task {task_id}: {user_input}")

        # Bridge MQTT -> A2A Orchestrator (JSON-RPC message/send)
        message = create_text_message_object(content=user_input or "")
        rpc_body = SendMessageRequest(
            id=str(uuid.uuid4()),
            params=MessageSendParams(message=message),
        ).model_dump(mode="json", exclude_none=True)
        response = requests.post(ORCH_A2A_URL, json=rpc_body, timeout=300)
        response.raise_for_status()
        parsed = SendMessageResponse.model_validate(response.json())
        if isinstance(parsed.root, JSONRPCErrorResponse):
            raise RuntimeError(f"A2A error: {parsed.root.error}")
        output = _a2a_result_to_output(parsed.root.result)

        # Publish result back to MQTT
        result = {
            "task_id": task_id,
            "status": "completed",
            "output": output,
        }
        client.publish(RES_TOPIC, json.dumps(result), qos=1)
        print(f"Published result for {task_id}")

    except Exception as e:
        print(f"Error processing message: {e}")

def main():
    client = mqtt.Client()
    client.on_message = on_message
    
    print(f"Connecting to MQTT broker at {BROKER}...")
    client.connect(BROKER, 1883)
    
    # Discovery (Retained)
    discovery_card = {
        "agent_id": "orchestrator",
        "name": "Research Orchestrator",
        "endpoint": ORCH_A2A_URL
    }
    client.publish(f"discovery/{ORG}/orchestrator", json.dumps(discovery_card), qos=1, retain=True)
    
    client.subscribe(REQ_TOPIC, qos=1)
    print(f"Gateway listening on {REQ_TOPIC}")
    client.loop_forever()

if __name__ == "__main__":
    main()
