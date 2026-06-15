"""
Memory Bridge — Cross-session knowledge persistence via mcp-server-memory.

Since MCP servers cannot directly call other MCP servers, this bridge
works by:
1. Generating structured payloads for mcp-server-memory tools
2. Providing sync tools that output what should be stored
3. The LLM/IDE routes these to the actual mcp-server-memory

Entity Types:
- DecisionRecord: Architectural/design decisions
- MistakeRecord: Past mistakes with root causes and fixes  
- PreventionRule: Automated prevention rules
- UserPreference: User thinking patterns and preferences
- QualityBaseline: Quality scores and trends
"""
import json
import time
import logging

logger = logging.getLogger(__name__)

# Entity type constants
ENTITY_TYPES = {
    'decision': 'DecisionRecord',
    'mistake': 'MistakeRecord', 
    'rule': 'PreventionRule',
    'preference': 'UserPreference',
    'quality': 'QualityBaseline',
}


def _build_entity(entity_type: str, name: str, observations: list[str]) -> dict:
    """Build an entity payload for mcp-server-memory create_entities."""
    return {
        'entityType': entity_type,
        'name': name,
        'observations': observations
    }


def _build_relation(from_name: str, to_name: str, relation_type: str) -> dict:
    """Build a relation payload for mcp-server-memory create_relations."""
    return {
        'from': from_name,
        'to': to_name,
        'relationType': relation_type
    }


def _timestamp() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())


def register(mcp, store):
    """Register memory bridge tools with the MCP server."""

    @mcp.tool()
    def memory_sync_decisions(limit: int = 10) -> str:
        """Generate mcp-server-memory payloads for recent decisions.
        Returns structured JSON that should be passed to mcp-server-memory's create_entities and create_relations tools.
        
        Args:
            limit: Max number of recent decisions to sync.
        """
        try:
            decisions = store.get_all_decisions(limit=limit)
            if not decisions:
                return "No decisions to sync."
            
            entities = []
            relations = []
            
            for d in decisions:
                name = f"Decision_{d['id']}_{d['created_at'][:10]}"
                obs = [
                    f"Decision: {d['decision']}",
                    f"Rationale: {d['rationale']}",
                    f"Recorded: {d['created_at']}",
                ]
                if d.get('alternatives_rejected'):
                    obs.append(f"Alternatives rejected: {d['alternatives_rejected']}")
                if d.get('context'):
                    obs.append(f"Context: {d['context']}")
                
                entities.append(_build_entity('DecisionRecord', name, obs))
            
            out = "## Memory Sync: Decisions\n\n"
            out += "**To persist these across sessions, call `mcp-server-memory.create_entities` with:**\n\n"
            out += f"```json\n{json.dumps({'entities': entities}, indent=2)}\n```\n\n"
            out += f"Synced {len(entities)} decisions.\n"
            
            if relations:
                out += f"\n**Then call `mcp-server-memory.create_relations` with:**\n\n"
                out += f"```json\n{json.dumps({'relations': relations}, indent=2)}\n```\n"
            
            return out
        except Exception as e:
            return f"❌ Failed to sync decisions: {e}"

    @mcp.tool()
    def memory_sync_mistakes(limit: int = 10) -> str:
        """Generate mcp-server-memory payloads for recent anti-patterns/mistakes.
        Returns structured JSON for cross-session persistence.
        
        Args:
            limit: Max number of recent mistakes to sync.
        """
        try:
            mistakes = store.get_all_anti_patterns(limit=limit)
            if not mistakes:
                return "No mistakes to sync."
            
            entities = []
            relations = []
            
            for m in mistakes:
                name = f"Mistake_{m['id']}_{m.get('created_at', 'unknown')[:10]}"
                obs = [
                    f"Mistake: {m['mistake']}",
                    f"Root cause: {m['root_cause']}",
                    f"Fix: {m['fix']}",
                    f"Severity: {m.get('severity', 'unknown')}",
                ]
                if m.get('tags'):
                    obs.append(f"Tags: {m['tags']}")
                
                entities.append(_build_entity('MistakeRecord', name, obs))
            
            out = "## Memory Sync: Mistakes\n\n"
            out += "**To persist these across sessions, call `mcp-server-memory.create_entities` with:**\n\n"
            out += f"```json\n{json.dumps({'entities': entities}, indent=2)}\n```\n\n"
            out += f"Synced {len(entities)} mistakes.\n"
            return out
        except Exception as e:
            return f"❌ Failed to sync mistakes: {e}"

    @mcp.tool()
    def memory_sync_rules(limit: int = 20) -> str:
        """Generate mcp-server-memory payloads for active prevention rules.
        Returns structured JSON for cross-session persistence.
        
        Args:
            limit: Max number of rules to sync.
        """
        try:
            rules = store.get_active_prevention_rules()
            if not rules:
                return "No prevention rules to sync."
            
            entities = []
            relations = []
            
            for r in rules[:limit]:
                name = f"Rule_{r['id']}_{r['rule_name']}"
                obs = [
                    f"Rule: {r['rule_name']}",
                    f"Trigger: {r['trigger_event']}",
                    f"Action: {r['action']}",
                    f"Times triggered: {r.get('times_triggered', 0)}",
                ]
                entities.append(_build_entity('PreventionRule', name, obs))
                
                # Link rule to what it prevents
                if r.get('source_mistake_id'):
                    relations.append(_build_relation(
                        name, 
                        f"Mistake_{r['source_mistake_id']}",
                        'PREVENTS'
                    ))
            
            out = "## Memory Sync: Prevention Rules\n\n"
            out += "**To persist these across sessions, call `mcp-server-memory.create_entities` with:**\n\n"
            out += f"```json\n{json.dumps({'entities': entities}, indent=2)}\n```\n\n"
            out += f"Synced {len(entities)} rules.\n"
            
            if relations:
                out += f"\n**Then call `mcp-server-memory.create_relations` with:**\n\n"
                out += f"```json\n{json.dumps({'relations': relations}, indent=2)}\n```\n"
            
            return out
        except Exception as e:
            return f"❌ Failed to sync rules: {e}"

    @mcp.tool()
    def memory_search_context(query: str) -> str:
        """Search mcp-server-memory for relevant context before a task.
        Returns instructions for calling mcp-server-memory search_nodes.
        
        Args:
            query: What to search for in cross-session memory.
        """
        out = "## Memory Search\n\n"
        out += "**To retrieve cross-session context, call `mcp-server-memory.search_nodes` with:**\n\n"
        out += f"```json\n{json.dumps({'query': query})}\n```\n\n"
        out += "Then also call `mcp-server-memory.read_graph` to see all stored knowledge.\n"
        out += "\n**Also checking local database...**\n\n"
        
        # Search local store as well
        try:
            decisions = store.search_decisions(query, limit=3)
            if decisions:
                out += "### Related Decisions (local):\n"
                for d in decisions:
                    out += f"- **{d['decision'][:100]}** (Rationale: {d['rationale'][:100]})\n"
            
            mistakes = store.check_anti_patterns(query, limit=3)
            if mistakes:
                out += "\n### Related Anti-Patterns (local):\n"
                for m in mistakes:
                    out += f"- ⚠️ {m['mistake'][:100]} → Fix: {m['fix'][:100]}\n"
        except Exception:
            pass
        
        return out

    logger.info("Memory bridge tools registered (memory_sync_decisions, memory_sync_mistakes, memory_sync_rules, memory_search_context)")
