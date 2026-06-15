'use server';

import Database from 'better-sqlite3';
import path from 'path';

const BRAIN_DIR = process.env.BRAIN_DIR || '/Users/snehgabani/.gemini/antigravity/brain/2126fc46-8eea-4684-8e0b-5ac8b7e69c4b/scratch';

function getEliteDb() {
  const db = new Database(path.join(BRAIN_DIR, 'elite.db'), { readonly: true });
  return db;
}

function getGraphDb() {
  const db = new Database(path.join(BRAIN_DIR, 'elite_graph.db'), { readonly: true });
  return db;
}

export async function getGraphData() {
  const db = getGraphDb();
  try {
    const nodes = db.prepare('SELECT node_id, label, properties, valid_from FROM nodes').all();
    const edges = db.prepare('SELECT source_id, target_id, relation, properties, valid_from FROM edges').all();

    // Map to React Flow format
    const reactFlowNodes = nodes.map((n: any, i: number) => ({
      id: n.node_id,
      position: { x: (i % 5) * 250, y: Math.floor(i / 5) * 150 }, // simple layout
      data: { 
        label: `${n.label}\n${n.node_id}`,
        properties: JSON.parse(n.properties || '{}')
      },
      type: n.label === 'AntiPattern' ? 'input' : n.label === 'Hypothesis' ? 'output' : 'default',
    }));

    const reactFlowEdges = edges.map((e: any, i: number) => ({
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

export async function getDashboardMetrics() {
  const db = getEliteDb();
  try {
    const mistakes = db.prepare('SELECT * FROM anti_patterns ORDER BY created_at DESC LIMIT 5').all();
    const goals = db.prepare("SELECT * FROM goals WHERE status = 'active' ORDER BY created_at DESC LIMIT 5").all();
    const decisions = db.prepare('SELECT * FROM decisions ORDER BY created_at DESC LIMIT 5').all();
    
    return { mistakes, goals, decisions };
  } catch (e) {
    console.error('Error fetching metrics', e);
    return { mistakes: [], goals: [], decisions: [] };
  } finally {
    db.close();
  }
}
