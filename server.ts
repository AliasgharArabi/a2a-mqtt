import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { randomUUID } from "crypto";
import { Aedes } from "aedes";
import { createServer, type Server as NetServer } from "net";
import mqtt from "mqtt";
import axios from "axios";

// --- Configuration ---
const PORT = Number(process.env.PORT) || 3000;
/** Must match the broker `client/test_client.py` and `mqtt_gateway.py` use (default 1883). */
const MQTT_PORT = Number(process.env.UI_MQTT_PORT) || 1883;
const MQTT_ORG = process.env.MQTT_ORG || "demo-org";
const SKIP_EMBEDDED_BROKER =
  process.env.EMBEDDED_MQTT === "0" || process.env.EMBEDDED_MQTT === "false";
/** Strands Python A2AServer (JSON-RPC POST /) */
const ORCHESTRATOR_A2A_URL = process.env.ORCHESTRATOR_A2A_URL || "http://127.0.0.1:9200/";

// --- Real Python orchestrator (A2A message/send) ---
function partsToText(parts: unknown[] | undefined): string {
  if (!parts?.length) return "";
  return (parts as { kind?: string; text?: string; root?: { text?: string } }[])
    .map((p) => {
      if (p.text && (p.kind === "text" || !p.kind)) return p.text as string;
      if (p.root?.text) return p.root.text;
      return "";
    })
    .filter(Boolean)
    .join("\n");
}

function a2aResultToOutput(result: Record<string, unknown>): string {
  if (result.kind === "message") {
    return partsToText(result.parts as unknown[]);
  }
  const history = result.history as { role?: string; parts?: unknown[] }[] | undefined;
  if (history?.length) {
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].role === "agent") return partsToText(history[i].parts);
    }
  }
  const artifacts = result.artifacts as { parts?: unknown[] }[] | undefined;
  if (artifacts?.length) {
    const chunks = artifacts.map((a) => partsToText(a.parts)).filter(Boolean);
    if (chunks.length) return chunks.join("\n");
  }
  const status = result.status as { message?: { parts?: unknown[] } } | undefined;
  if (status?.message?.parts) return partsToText(status.message.parts);
  return "";
}

async function callPythonOrchestrator(input: string): Promise<{
  ok: boolean;
  output: string;
  taskId?: string;
  error?: string;
  httpStatus: number;
}> {
  const rpcBody = {
    jsonrpc: "2.0" as const,
    id: randomUUID(),
    method: "message/send" as const,
    params: {
      message: {
        role: "user",
        kind: "message",
        messageId: randomUUID(),
        parts: [{ kind: "text", text: input }],
      },
    },
  };
  try {
    const response = await axios.post(ORCHESTRATOR_A2A_URL, rpcBody, {
      headers: { "Content-Type": "application/json" },
      timeout: 600_000,
      validateStatus: () => true,
    });
    const data = response.data as Record<string, unknown>;
    if (data.error) {
      const err = data.error as { message?: string };
      const msg = err?.message || JSON.stringify(data.error);
      return { ok: false, output: "", error: msg, httpStatus: 502 };
    }
    const result = data.result as Record<string, unknown>;
    const output = a2aResultToOutput(result);
    return {
      ok: true,
      output,
      taskId: result?.id as string | undefined,
      httpStatus: 200,
    };
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Request failed";
    return { ok: false, output: "", error: msg, httpStatus: 500 };
  }
}

async function startEmbeddedBroker(): Promise<NetServer | null> {
  if (SKIP_EMBEDDED_BROKER) {
    console.log("EMBEDDED_MQTT=0: not starting Aedes (connecting to existing broker only).");
    return null;
  }
  const broker = await Aedes.createBroker();
  const server = createServer(broker.handle);
  return await new Promise((resolve, reject) => {
    const onError = (err: NodeJS.ErrnoException) => {
      server.removeListener("listening", onListening);
      if (err.code === "EADDRINUSE") {
        console.warn(
          `[MQTT] Port ${MQTT_PORT} is already in use — using that broker as a client only ` +
            `(e.g. Mosquitto). Embedded Aedes not started.`
        );
        server.close();
        resolve(null);
        return;
      }
      reject(err);
    };
    const onListening = () => {
      server.removeListener("error", onError);
      console.log(`MQTT broker (Aedes) listening on port ${MQTT_PORT}`);
      resolve(server);
    };
    server.once("error", onError);
    server.listen(MQTT_PORT, onListening);
  });
}

async function startServer() {
  await startEmbeddedBroker();

  const app = express();
  app.use(express.json());

  const logs: { id: number; timestamp: string; agent: string; message: string; type: string }[] = [];
  let mqttClient: mqtt.MqttClient | null = null;

  const addLog = (agent: string, message: string, type: "info" | "success" | "error" = "info") => {
    const log = { id: Date.now(), timestamp: new Date().toISOString(), agent, message, type };
    logs.push(log);
    if (logs.length > 100) logs.shift();
    try {
      mqttClient?.publish("system/logs", JSON.stringify(log), { qos: 0 });
    } catch {
      /* ignore */
    }
  };

  mqttClient = mqtt.connect(`mqtt://127.0.0.1:${MQTT_PORT}`);

  mqttClient.on("connect", () => {
    console.log(`Node MQTT gateway connected to broker at 127.0.0.1:${MQTT_PORT}`);
    mqttClient!.subscribe(`${MQTT_ORG}/orchestrator/requests`);
    mqttClient!.publish(
      `discovery/${MQTT_ORG}/orchestrator`,
      JSON.stringify({
        agent_id: "orchestrator",
        name: "Research+Writer Orchestrator",
        endpoint: ORCHESTRATOR_A2A_URL,
      }),
      { retain: true }
    );
  });

  mqttClient.on("message", async (topic, message) => {
    if (topic !== `${MQTT_ORG}/orchestrator/requests`) return;
    const payload = JSON.parse(message.toString()) as { input?: string; task_id?: string };
    const { input, task_id: taskId } = payload;
    if (!input) {
      addLog("Gateway", "MQTT payload missing input", "error");
      return;
    }
    addLog("Gateway", `MQTT request: ${input.slice(0, 80)}${input.length > 80 ? "…" : ""}`);
    const r = await callPythonOrchestrator(input);
    if (!r.ok) {
      addLog("Gateway", r.error || "Orchestrator failed", "error");
      mqttClient!.publish(
        `${MQTT_ORG}/orchestrator/results`,
        JSON.stringify({
          task_id: taskId || "unknown",
          status: "error",
          output: "",
          error: r.error,
        }),
        { qos: 1 }
      );
      return;
    }
    mqttClient!.publish(
      `${MQTT_ORG}/orchestrator/results`,
      JSON.stringify({
        task_id: taskId || "unknown",
        status: "completed",
        output: r.output,
      }),
      { qos: 1 }
    );
    addLog("Gateway", `Published result to ${MQTT_ORG}/orchestrator/results`, "success");
  });

  app.get("/api/logs", (_req, res) => {
    res.json(logs);
  });

  /** In-process progress from Python orchestrator (HTTP; see transport/agent_progress.py). */
  app.get("/api/agent-progress", (_req, res) => {
    res.json({ ok: true, usage: "POST JSON { agent, message } to append a UI log line" });
  });
  app.post("/api/agent-progress", (req, res) => {
    const agent = req.body?.agent;
    const message = req.body?.message;
    if (typeof agent !== "string" || typeof message !== "string") {
      return res.status(400).json({ error: "JSON body must include string agent and message" });
    }
    addLog(agent, message, "info");
    return res.status(204).end();
  });

  app.post("/api/orchestrate", async (req, res) => {
    const input = req.body?.input;
    if (!input || typeof input !== "string") {
      return res.status(400).json({ error: "JSON body must include string input" });
    }
    addLog("Python-Orchestrator", `A2A message/send → ${ORCHESTRATOR_A2A_URL}`);
    const r = await callPythonOrchestrator(input);
    if (!r.ok) {
      addLog("Python-Orchestrator", r.error || "failed", "error");
      return res.status(r.httpStatus >= 400 ? r.httpStatus : 502).json({ error: r.error });
    }
    addLog("Python-Orchestrator", `Done (task ${r.taskId ?? "?"})`, "success");
    return res.json({ output: r.output, task_id: r.taskId });
  });

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`UI + API: http://localhost:${PORT}`);
    console.log(`Bedrock stack: Strands orchestrator at ${ORCHESTRATOR_A2A_URL}`);
  });
}

startServer().catch((err) => {
  console.error(err);
  process.exit(1);
});
