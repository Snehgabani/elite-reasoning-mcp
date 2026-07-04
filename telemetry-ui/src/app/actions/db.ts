'use server';

import Database from 'better-sqlite3';
import path from 'path';

const BRAIN_DIR = process.env.BRAIN_DIR || '/Users/snehgabani/.gemini/antigravity/brain/2126fc46-8eea-4684-8e0b-5ac8b7e69c4b/scratch';

type GraphNodeRow = {
  node_id: string;
  label: string;
  properties: string | null;
};

type GraphEdgeRow = {
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
  const db = new Database(path.join(BRAIN_DIR, 'elite.db'), { readonly: true });
  return db;
}

function getGraphDb() {
  const db = new Database(path.join(BRAIN_DIR, 'elite_graph.db'), { readonly: true });
  return db;
}

export async function getGraphData(): Promise<GraphData> {
  const db = getGraphDb();
  try {
    const nodes = db.prepare('SELECT node_id, label, properties, valid_from FROM nodes').all() as GraphNodeRow[];
    const edges = db.prepare('SELECT source_id, target_id, relation, properties, valid_from FROM edges').all() as GraphEdgeRow[];

    // Map to React Flow format
    const reactFlowNodes = nodes.map((n, i) => ({
      id: n.node_id,
      position: { x: (i % 5) * 250, y: Math.floor(i / 5) * 150 }, // simple layout
      data: { 
        label: `${n.label}\n${n.node_id}`,
        properties: parseProperties(n.properties)
      },
      type: graphNodeType(n.label),
    }));

    const reactFlowEdges = edges.map((e, i) => ({
      id: `e${i}-${e.source_id}-${e.target_id}`,
      source: e.source_id,
      target: e.target_id,
      label: e.relation,
      animated: true,
    }));

    return { nodes: reactFlowNodes, edges: reactFlowEdges };
  } catch (e) {
    console.error('Error fetching graph data', e);
    return { nodes: [], edges: [] };
  } finally {
    db.close();
  }
}

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  const db = getEliteDb();
  try {
    const mistakes = db.prepare('SELECT id, mistake, severity FROM anti_patterns ORDER BY created_at DESC LIMIT 5').all() as DashboardMetrics['mistakes'];
    const goals = db.prepare("SELECT id, objective, progress FROM goals WHERE status = 'active' ORDER BY created_at DESC LIMIT 5").all() as DashboardMetrics['goals'];
    const decisions = db.prepare('SELECT id, decision, rationale FROM decisions ORDER BY created_at DESC LIMIT 5').all() as DashboardMetrics['decisions'];
    
    return { mistakes, goals, decisions };
  } catch (e) {
    console.error('Error fetching metrics', e);
    return { mistakes: [], goals: [], decisions: [] };
  } finally {
    db.close();
  }
}
