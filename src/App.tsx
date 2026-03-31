import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  Search, 
  PenTool, 
  Network, 
  Terminal, 
  Send, 
  CheckCircle2, 
  AlertCircle, 
  Activity,
  Cpu
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface Log {
  id: number;
  timestamp: string;
  agent: string;
  message: string;
  type: 'info' | 'success' | 'error';
}

export default function App() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [input, setInput] = useState('');
  const [result, setResult] = useState<string | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        setLogs(data);
      } catch (e) {
        console.error('Failed to fetch logs');
      }
    };

    const interval = setInterval(fetchLogs, 400);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    
    // Drive agent highlights from latest server log (names must match Agent Network nodes).
    if (logs.length > 0) {
      const lastLog = logs[logs.length - 1];
      if (lastLog.type === 'info') {
        setActiveAgent(mapLogAgentToNetworkNode(lastLog.agent));
      } else if (lastLog.type === 'success' || lastLog.type === 'error') {
        setActiveAgent(null);
      }
    }
  }, [logs]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    setIsProcessing(true);
    setResult(null);
    setResultError(null);
    try {
      const res = await fetch('/api/orchestrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: input.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setResultError(data.error || res.statusText || 'Request failed');
        return;
      }
      setResult(typeof data.output === 'string' ? data.output : JSON.stringify(data.output, null, 2));
      setInput('');
    } catch (error) {
      console.error(error);
      setResultError(error instanceof Error ? error.message : 'Request failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-300 font-sans selection:bg-orange-500/30">
      {/* Header */}
      <header className="border-b border-zinc-800/50 bg-black/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-orange-600 rounded-lg flex items-center justify-center">
              <Network className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-lg font-semibold tracking-tight text-white">Strands Orchestrator</h1>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-2 px-3 py-1 bg-zinc-900 rounded-full border border-zinc-800">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span>MQTT: 1883</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1 bg-zinc-900 rounded-full border border-zinc-800">
              <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              <span>Python A2A: 9200</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Flow Visualization */}
        <div className="lg:col-span-5 space-y-6">
          <section className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Cpu className="w-24 h-24" />
            </div>
            
            <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-500 mb-8">Agent Network</h2>
            
            <div className="space-y-12 relative">
              {/* Connection Lines */}
              <div className="absolute left-6 top-8 bottom-8 w-px bg-gradient-to-b from-orange-500/50 via-zinc-800 to-zinc-800" />

              <AgentNode 
                icon={<Bot className="w-5 h-5" />}
                name="Orchestrator"
                role="Manager"
                isActive={activeAgent === 'Orchestrator'}
                status={activeAgent === 'Orchestrator' ? 'Processing' : 'Idle'}
              />
              
              <AgentNode 
                icon={<Search className="w-5 h-5" />}
                name="Researcher"
                role="Worker"
                isActive={activeAgent === 'Researcher'}
                status={activeAgent === 'Researcher' ? 'Searching' : 'Idle'}
              />

              <AgentNode 
                icon={<PenTool className="w-5 h-5" />}
                name="Writer"
                role="Worker"
                isActive={activeAgent === 'Writer'}
                status={activeAgent === 'Writer' ? 'Writing' : 'Idle'}
              />
            </div>
          </section>

          {/* Input Form */}
          <section className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-500 mb-4">New Task</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Enter a topic for the agents to research and write about..."
                  className="w-full bg-black border border-zinc-800 rounded-xl p-4 text-sm focus:outline-none focus:border-orange-500/50 min-h-[120px] resize-none transition-colors"
                />
              </div>
              <button
                type="submit"
                disabled={isProcessing || !input.trim()}
                className="w-full bg-orange-600 hover:bg-orange-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
              >
                {isProcessing ? (
                  <Activity className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                {isProcessing ? 'Calling orchestrator...' : 'Run Python orchestrator'}
              </button>
            </form>
            <p className="mt-3 text-[11px] text-zinc-500 leading-relaxed">
              Sends <code className="text-zinc-400">message/send</code> to Strands on{' '}
              <code className="text-zinc-400">127.0.0.1:9200</code> (same contract as{' '}
              <code className="text-zinc-400">client/test_client.py</code> via MQTT gateway). Start the Python agents first.
            </p>
          </section>

          {(result || resultError) && (
            <section className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-6 flex flex-col min-h-[200px] max-h-[40vh]">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-zinc-500 mb-3">
                {resultError ? 'Error' : 'Orchestrator output'}
              </h2>
              <div
                ref={resultRef}
                className="flex-1 overflow-y-auto rounded-lg bg-black/50 border border-zinc-800/80 p-4 text-sm font-mono whitespace-pre-wrap text-zinc-300"
              >
                {resultError ? <span className="text-red-400">{resultError}</span> : result}
              </div>
            </section>
          )}
        </div>

        {/* Right Column: Terminal Logs */}
        <div className="lg:col-span-7 flex flex-col h-[calc(100vh-12rem)]">
          <div className="bg-black border border-zinc-800 rounded-2xl flex-1 flex flex-col overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/30">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-orange-500" />
                <span className="text-xs font-mono font-semibold uppercase tracking-wider">System Event Stream</span>
              </div>
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-zinc-800" />
                <div className="w-2.5 h-2.5 rounded-full bg-zinc-800" />
                <div className="w-2.5 h-2.5 rounded-full bg-zinc-800" />
              </div>
            </div>
            
            <div 
              ref={scrollRef}
              className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-2 scrollbar-thin scrollbar-thumb-zinc-800"
            >
              <AnimatePresence initial={false}>
                {logs.length === 0 && (
                  <div className="text-zinc-600 italic">Waiting for events...</div>
                )}
                {logs.map((log) => (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex gap-3 group"
                  >
                    <span className="text-zinc-600 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                    <span className={`font-bold shrink-0 w-24 ${getAgentColor(log.agent)}`}>{log.agent}:</span>
                    <span className={`flex-1 ${getMessageColor(log.type)}`}>
                      {log.type === 'success' && <CheckCircle2 className="w-3 h-3 inline mr-1.5 -mt-0.5" />}
                      {log.type === 'error' && <AlertCircle className="w-3 h-3 inline mr-1.5 -mt-0.5" />}
                      {log.message}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function AgentNode({ icon, name, role, isActive, status }: { 
  icon: React.ReactNode, 
  name: string, 
  role: string, 
  isActive: boolean,
  status: string 
}) {
  return (
    <div className="flex items-center gap-6 relative z-10">
      <div className={`
        w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-500
        ${isActive ? 'bg-orange-600 text-white shadow-[0_0_20px_rgba(234,88,12,0.4)] scale-110' : 'bg-zinc-800 text-zinc-500'}
      `}>
        {icon}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className={`font-semibold transition-colors ${isActive ? 'text-white' : 'text-zinc-400'}`}>{name}</h3>
          <span className="text-[10px] px-1.5 py-0.5 bg-zinc-800 rounded border border-zinc-700 text-zinc-500 uppercase font-bold tracking-tighter">
            {role}
          </span>
        </div>
        <p className="text-xs text-zinc-600 flex items-center gap-1.5 mt-0.5">
          {isActive && <div className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />}
          {status}
        </p>
      </div>
    </div>
  );
}

/** Map server log `agent` labels to Agent Network node names (Orchestrator / Researcher / Writer). */
function mapLogAgentToNetworkNode(agent: string): string | null {
  if (agent === 'Python-Orchestrator') return 'Orchestrator';
  if (agent === 'Orchestrator' || agent === 'Researcher' || agent === 'Writer') return agent;
  return null;
}

function getAgentColor(agent: string) {
  switch (agent) {
    case 'Orchestrator': return 'text-orange-500';
    case 'Researcher': return 'text-blue-400';
    case 'Writer': return 'text-emerald-400';
    case 'Gateway': return 'text-purple-400';
    case 'Python-Orchestrator': return 'text-amber-400';
    case 'UI': return 'text-zinc-400';
    default: return 'text-zinc-400';
  }
}

function getMessageColor(type: string) {
  switch (type) {
    case 'success': return 'text-emerald-500';
    case 'error': return 'text-red-500';
    default: return 'text-zinc-300';
  }
}
