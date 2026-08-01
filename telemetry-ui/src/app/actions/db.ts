'use server';

import Database from 'better-sqlite3';
import { homedir } from 'node:os';
import path from 'path';

function resolveBrainDir(): string {
  const configured = process.env.ELITE_BRAIN_DIR || process.env.BRAIN_DIR;
  if (!configured) {
    return path.join(homedir(), '.elite-reasoning', 'brain');
  }
  if (configured === '~') {
    return homedir();
  }
  if (configured.startsWith('~/')) {
    return path.join(homedir(), configured.slice(2));
  }
  return path.resolve(configured);
}

const BRAIN_DIR = resolveBrainDir();

type GraphNodeRow = {
  id: string;
  label: string;
  properties: string | null;
};

type GraphEdgeRow = {
  id: string;
  source_id: string;
  target_id: string;
  relation: string;
};

export type GraphData = {
  nodes: Array<{
    id: string;
    position: { x: number; y: number };
    data: { label: string; properties: Record<string, unknown> };
    type: 'input' | 'output' | 'default';
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    label: string;
    animated: boolean;
  }>;
  error?: string;
};

export type DashboardMetrics = {
  mistakes: Array<{
    id: number;
    mistake: string;
    severity: string | null;
  }>;
  goals: Array<{
    id: number;
    objective: string;
    progress: string | null;
  }>;
  decisions: Array<{
    id: number;
    decision: string;
    rationale: string | null;
  }>;
  error?: string;
};

function parseProperties(raw: string | null): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(raw || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function graphNodeType(label: string): 'input' | 'output' | 'default' {
  if (label === 'AntiPattern') {
    return 'input';
  }
  if (label === 'Hypothesis') {
    return 'output';
  }
  return 'default';
}

function getEliteDb() {
  return new Database(path.join(BRAIN_DIR, 'elite.db'), {
    readonly: true,
    fileMustExist: true,
  });
}

export async function getGraphData(): Promise<GraphData> {
  let db: ReturnType<typeof getEliteDb> | undefined;
  try {
    db = getEliteDb();
    const nodes = db.prepare('SELECT id, label, properties FROM graph_nodes ORDER BY created_at ASC').all() as GraphNodeRow[];
    const edges = db.prepare(
      `SELECT id, source_id, target_id, relation
       FROM graph_edges
       WHERE (valid_from IS NULL OR datetime(valid_from) <= datetime('now'))
         AND (valid_to IS NULL OR datetime(valid_to) > datetime('now'))
       ORDER BY valid_from ASC`,
    ).all() as GraphEdgeRow[];

    // Map to React Flow format
    const reactFlowNodes = nodes.map((n, i) => ({
      id: n.id,
      position: { x: (i % 5) * 250, y: Math.floor(i / 5) * 150 }, // simple layout
      data: {
        label: `${n.label}\n${n.id}`,
        properties: parseProperties(n.properties)
      },
      type: graphNodeType(n.label),
    }));

    const reactFlowEdges = edges.map((e) => ({
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      label: e.relation,
      animated: true,
    }));

    return { nodes: reactFlowNodes, edges: reactFlowEdges };
  } catch {
    console.error('Error fetching graph data');
    return { nodes: [], edges: [], error: 'Unable to read local graph data.' };
  } finally {
    db?.close();
  }
}

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  let db: ReturnType<typeof getEliteDb> | undefined;
  try {
    db = getEliteDb();
    const mistakes = db.prepare('SELECT id, mistake, severity FROM anti_patterns ORDER BY created_at DESC LIMIT 5').all() as DashboardMetrics['mistakes'];
    const goals = db.prepare("SELECT id, objective, progress FROM goals WHERE status = 'active' ORDER BY created_at DESC LIMIT 5").all() as DashboardMetrics['goals'];
    const decisions = db.prepare('SELECT id, decision, rationale FROM decisions ORDER BY created_at DESC LIMIT 5').all() as DashboardMetrics['decisions'];
    
    return { mistakes, goals, decisions };
  } catch {
    console.error('Error fetching metrics');
    return { mistakes: [], goals: [], decisions: [], error: 'Unable to read local metrics.' };
  } finally {
    db?.close();
  }
}
