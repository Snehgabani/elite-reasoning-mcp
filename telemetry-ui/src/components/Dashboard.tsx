'use client';

import React, { useEffect, useState } from 'react';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import 'reactflow/dist/style.css';
import { getGraphData, getDashboardMetrics } from '../app/actions/db';

export default function Dashboard() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [metrics, setMetrics] = useState({ mistakes: [], goals: [], decisions: [] });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const gData = await getGraphData();
        const mData = await getDashboardMetrics();
        setGraph(gData as any);
        setMetrics(mData as any);
      } catch (err) {
        console.error(err);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 3000); // Auto-refresh every 3s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-8 flex flex-col gap-8 font-sans">
      <header className="flex justify-between items-center bg-slate-900/50 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent">
            Elite Reasoning Telemetry
          </h1>
          <p className="text-slate-400 mt-1">Live LangGraph & Temporal Knowledge Visualization</p>
        </div>
        <div className="flex gap-4">
          <div className="px-4 py-2 bg-emerald-500/10 text-emerald-400 rounded-full text-sm font-medium border border-emerald-500/20">
            ● System Active
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 h-[800px]">
        {/* Graph Visualizer */}
        <div className="lg:col-span-2 bg-slate-900/50 rounded-2xl border border-slate-800 backdrop-blur-md overflow-hidden relative shadow-xl shadow-black/50">
          <div className="absolute top-4 left-4 z-10 bg-slate-950/80 px-4 py-2 rounded-lg border border-slate-800">
            <h2 className="text-lg font-semibold text-slate-200">Temporal Knowledge Graph</h2>
          </div>
          <ReactFlow 
            nodes={graph.nodes} 
            edges={graph.edges} 
            fitView 
            defaultEdgeOptions={{ style: { stroke: '#6366f1', strokeWidth: 2 } }}
          >
            <Background color="#334155" gap={16} />
            <Controls className="bg-slate-800 border-slate-700 fill-slate-200" />
            <MiniMap style={{ backgroundColor: '#0f172a' }} nodeColor="#3b82f6" maskColor="rgba(15, 23, 42, 0.7)" />
          </ReactFlow>
        </div>

        {/* Metrics Panel */}
        <div className="flex flex-col gap-6 overflow-y-auto pr-2">
          {/* Recent Mistakes */}
          <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
            <h3 className="text-xl font-semibold mb-4 text-rose-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Recent Anti-Patterns
            </h3>
            <div className="flex flex-col gap-3">
              {metrics.mistakes.map((m: any) => (
                <div key={m.id} className="p-3 bg-slate-950 rounded-xl border border-rose-900/30">
                  <p className="text-sm font-medium text-slate-200">{m.mistake}</p>
                  <p className="text-xs text-slate-500 mt-2">Severity: <span className="text-rose-400">{m.severity.toUpperCase()}</span></p>
                </div>
              ))}
            </div>
          </div>

          {/* Active Goals */}
          <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
            <h3 className="text-xl font-semibold mb-4 text-blue-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              Active Goals
            </h3>
            <div className="flex flex-col gap-3">
              {metrics.goals.map((g: any) => {
                const progObj = JSON.parse(g.progress || '{}');
                const krs = Object.values(progObj) as number[];
                const avg = krs.length ? krs.reduce((a,b) => a+b, 0) / krs.length : 0;
                return (
                  <div key={g.id} className="p-3 bg-slate-950 rounded-xl border border-blue-900/30">
                    <p className="text-sm font-medium text-slate-200">{g.objective}</p>
                    <div className="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${avg}%` }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Decisions Log */}
          <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 backdrop-blur-md">
            <h3 className="text-xl font-semibold mb-4 text-purple-400 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-500"></span>
              Architectural Decisions
            </h3>
            <div className="flex flex-col gap-3">
              {metrics.decisions.map((d: any) => (
                <div key={d.id} className="p-3 bg-slate-950 rounded-xl border border-purple-900/30">
                  <p className="text-sm font-medium text-slate-200">{d.decision}</p>
                  <p className="text-xs text-slate-400 mt-1 truncate">{d.rationale}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
