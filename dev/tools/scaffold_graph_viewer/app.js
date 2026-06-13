const state = {
  payload: null,
  graph: null,
  layoutSeed: 1,
  selectedId: null,
  selectedKind: null,
  viewMode: "topology",
  topologyPhysics: false,
  layers: {
    scaffoldEdges: true,
    runEndpoints: true,
    families: true,
    traces: true,
    rails: true,
    ambiguities: true,
  },
};

const svg = document.getElementById("graphSvg");
const fileInput = document.getElementById("fileInput");
const demoButton = document.getElementById("demoButton");
const relayoutButton = document.getElementById("relayoutButton");
const unrollToggle = document.getElementById("unrollToggle");
const labelsToggle = document.getElementById("labelsToggle");
const topologyPhysicsToggle = document.getElementById("topologyPhysicsToggle");
const zoomRange = document.getElementById("zoomRange");
const viewModeInputs = document.querySelectorAll('input[name="viewMode"]');
const searchBox = document.getElementById("searchBox");
const searchResults = document.getElementById("searchResults");
const payloadMeta = document.getElementById("payloadMeta");
const summary = document.getElementById("summary");
const badges = document.getElementById("badges");
const dropHint = document.getElementById("dropHint");
const selectionTitle = document.getElementById("selectionTitle");
const selectionDetails = document.getElementById("selectionDetails");
const clearSelectionButton = document.getElementById("clearSelectionButton");

const COLORS = [
  "#61d6c7",
  "#8ab4ff",
  "#ffc85a",
  "#b69cff",
  "#7bd88f",
  "#ff9f7a",
  "#d5ec72",
  "#f58bd1",
  "#6bd0ff",
  "#ff746f",
];

function compactId(value) {
  if (!value) return "";
  const text = String(value);
  const parts = text.split(":");
  return parts.slice(-2).join(":");
}

function hashString(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function colorForId(id) {
  return COLORS[hashString(String(id)) % COLORS.length];
}

function normalizePayload(raw) {
  if (raw && raw.format === "scaffold_graph_viewer_payload_v1" && raw.inspection) {
    return {
      title: raw.source?.name || raw.source?.id || "Scaffold payload",
      source: raw.source || {},
      inspection: raw.inspection,
      wrapper: raw,
    };
  }
  return {
    title: raw?.source_mesh_id || raw?.surface_model?.id || "Inspection payload",
    source: {},
    inspection: raw,
    wrapper: null,
  };
}

function buildGraph(payload) {
  return state.viewMode === "topology" ? buildTopologyGraph(payload) : buildEvidenceGraph(payload);
}

function buildEvidenceGraph(payload) {
  const inspection = payload.inspection || {};
  const relations = inspection.relations || {};
  const nodes = new Map();
  const edges = [];
  const aliases = [];
  const rawItems = new Map();
  const nodeDegree = new Map();

  function addNode(id, item) {
    if (!id || nodes.has(id)) return;
    nodes.set(id, {
      id,
      canonicalId: id,
      label: item.label || compactId(id),
      kind: item.kind,
      subtype: item.subtype || "",
      raw: item.raw || {},
      x: 0,
      y: 0,
      alias: false,
      ambiguous: false,
    });
    rawItems.set(id, { kind: item.kind, raw: item.raw || {} });
  }

  for (const node of relations.scaffold_nodes || []) {
    const label = node.source_vertex_ids?.length ? `N ${node.source_vertex_ids.join(",")}` : compactId(node.id);
    addNode(node.id, { kind: "ScaffoldNode", subtype: "scaffold", label, raw: node });
  }

  for (const junction of relations.run_endpoint_junctions || []) {
    const label = junction.source_vertex_id ? `R ${junction.source_vertex_id}` : compactId(junction.id);
    addNode(junction.id, { kind: "RunEndpointJunction", subtype: "run", label, raw: junction });
  }

  function ensureNode(id, kind = "MissingNode") {
    if (!id) return;
    if (!nodes.has(id)) {
      addNode(id, { kind, subtype: "missing", label: compactId(id), raw: { id, missing_from_payload: true } });
    }
  }

  function addEdge(edge) {
    if (!edge.source || !edge.target) return;
    ensureNode(edge.source);
    ensureNode(edge.target);
    edges.push(edge);
    nodeDegree.set(edge.source, (nodeDegree.get(edge.source) || 0) + 1);
    nodeDegree.set(edge.target, (nodeDegree.get(edge.target) || 0) + 1);
    rawItems.set(edge.id, { kind: edge.kind, raw: edge.raw || edge });
  }

  for (const edge of relations.scaffold_edges || []) {
    addEdge({
      id: `edge:${edge.id}`,
      source: edge.start_scaffold_node_id,
      target: edge.end_scaffold_node_id,
      kind: "ScaffoldEdge",
      layer: "scaffoldEdges",
      label: edge.display_label || compactId(edge.patch_chain_id),
      color: "#42545b",
      raw: edge,
    });
  }

  const familyByMember = new Map();
  for (const family of relations.connected_direction_families || []) {
    for (const memberId of family.member_directional_evidence_ids || []) {
      familyByMember.set(memberId, family);
    }
  }

  const traceMemberByMember = new Map();
  for (const trace of relations.scaffold_traces || []) {
    for (const member of trace.members || []) {
      traceMemberByMember.set(member.directional_evidence_id, { trace, member });
    }
  }

  for (const family of relations.connected_direction_families || []) {
    for (const memberId of family.member_directional_evidence_ids || []) {
      const traceMember = traceMemberByMember.get(memberId);
      if (!traceMember) continue;
      const { member, trace } = traceMember;
      if (!member.start_trace_node_id || !member.end_trace_node_id) continue;
      addEdge({
        id: `family:${family.id}:${memberId}`,
        source: member.start_trace_node_id,
        target: member.end_trace_node_id,
        kind: "ConnectedDirectionFamilyMember",
        layer: "families",
        label: compactId(family.id),
        color: colorForId(family.id),
        familyId: family.id,
        traceId: trace.id,
        raw: { family, trace, member },
      });
    }
  }

  for (const trace of relations.scaffold_traces || []) {
    for (const member of trace.members || []) {
      if (!member.start_trace_node_id || !member.end_trace_node_id) continue;
      const family = familyByMember.get(member.directional_evidence_id);
      addEdge({
        id: `trace:${trace.id}:${member.directional_evidence_id}`,
        source: member.start_trace_node_id,
        target: member.end_trace_node_id,
        kind: "ScaffoldTraceMember",
        layer: "traces",
        label: compactId(trace.id),
        color: colorForId(trace.direction_family_id),
        familyId: trace.direction_family_id,
        traceId: trace.id,
        raw: { trace, member, family },
      });
    }
  }

  for (const rail of relations.scaffold_rails || []) {
    const trace = (relations.scaffold_traces || []).find((item) => item.id === rail.scaffold_trace_id);
    if (!trace) continue;
    const members = trace.members || [];
    const coincidentOpen = rail.first_trace_node_id && rail.first_trace_node_id === rail.last_trace_node_id;
    const useAlias = unrollToggle.checked && (rail.is_closed_loop || coincidentOpen);
    let aliasId = null;
    if (useAlias && rail.first_trace_node_id) {
      aliasId = `${rail.first_trace_node_id}#alias:${rail.id}`;
      const canonical = nodes.get(rail.first_trace_node_id);
      nodes.set(aliasId, {
        ...(canonical || {
          id: rail.first_trace_node_id,
          label: compactId(rail.first_trace_node_id),
          kind: "AliasNode",
          raw: {},
        }),
        id: aliasId,
        canonicalId: rail.first_trace_node_id,
        label: `${canonical?.label || compactId(rail.first_trace_node_id)}*`,
        kind: "AliasNode",
        subtype: "alias",
        alias: true,
        raw: { canonical_id: rail.first_trace_node_id, rail_id: rail.id, reason: "loop_or_coincident_endpoint_alias" },
      });
      aliases.push(aliasId);
      addEdge({
        id: `alias:${rail.id}`,
        source: rail.first_trace_node_id,
        target: aliasId,
        kind: "VisualAlias",
        layer: "ambiguities",
        label: "alias",
        color: "#6f817c",
        raw: { rail_id: rail.id, canonical_id: rail.first_trace_node_id, alias_id: aliasId },
      });
    }

    members.forEach((member, index) => {
      if (!member.start_trace_node_id || !member.end_trace_node_id) return;
      let target = member.end_trace_node_id;
      if (aliasId && index === members.length - 1 && target === rail.first_trace_node_id) {
        target = aliasId;
      }
      addEdge({
        id: `rail:${rail.id}:${member.directional_evidence_id}`,
        source: member.start_trace_node_id,
        target,
        kind: "ScaffoldRailMember",
        layer: "rails",
        label: rail.is_consumable_by_g5a ? "rail" : "rail?",
        color: colorForId(rail.id),
        familyId: rail.direction_family_id,
        railId: rail.id,
        raw: { rail, member, trace },
      });
    });

    if ((rail.branch_records && Object.keys(rail.branch_records).length) || (rail.loop_ambiguity_records && Object.keys(rail.loop_ambiguity_records).length) || (rail.diagnostics || []).length) {
      for (const nodeId of rail.ordered_trace_node_ids || []) {
        const node = nodes.get(nodeId);
        if (node) node.ambiguous = true;
      }
    }
  }

  for (const node of nodes.values()) {
    node.degree = nodeDegree.get(node.id) || 0;
  }

  return {
    nodes: Array.from(nodes.values()),
    edges,
    aliases,
    relations,
    inspection,
    source: payload.source,
    title: payload.title,
  };
}

function buildTopologyGraph(payload) {
  const inspection = payload.inspection || {};
  const relations = inspection.relations || {};
  const nodes = new Map();
  const edges = [];
  const rawItems = new Map();
  const scaffoldEdges = relations.scaffold_edges || [];
  const traces = relations.scaffold_traces || [];
  const loopGroupsByChain = new Map();
  const canonicalToLoopNode = new Map();

  function addNode(node) {
    if (!node.id || nodes.has(node.id)) return;
    nodes.set(node.id, {
      label: compactId(node.id),
      subtype: "",
      x: 0,
      y: 0,
      alias: false,
      ambiguous: false,
      ...node,
    });
    rawItems.set(node.id, { kind: node.kind, raw: node.raw || {} });
  }

  function addEdge(edge) {
    if (!edge.source || !edge.target) return;
    edges.push(edge);
    rawItems.set(edge.id, { kind: edge.kind, raw: edge.raw || edge });
  }

  for (const edge of scaffoldEdges) {
    if (edge.start_scaffold_node_id !== edge.end_scaffold_node_id) continue;
    const chainId = edge.chain_id || edge.patch_chain_id || edge.id;
    if (!loopGroupsByChain.has(chainId)) {
      loopGroupsByChain.set(chainId, {
        id: `loop-group:${chainId}`,
        chainId,
        selfEdges: [],
        patchChainIds: new Set(),
        patchIds: new Set(),
        anchorNodeIds: new Set(),
      });
    }
    const group = loopGroupsByChain.get(chainId);
    group.selfEdges.push(edge);
    if (edge.patch_chain_id) group.patchChainIds.add(edge.patch_chain_id);
    if (edge.patch_id) group.patchIds.add(edge.patch_id);
    if (edge.start_scaffold_node_id) group.anchorNodeIds.add(edge.start_scaffold_node_id);
    if (edge.end_scaffold_node_id) group.anchorNodeIds.add(edge.end_scaffold_node_id);
  }

  const loopGroups = Array.from(loopGroupsByChain.values()).sort((a, b) => a.chainId.localeCompare(b.chainId));

  function bestTraceForGroup(group) {
    const patchChainIds = group.patchChainIds;
    const candidates = [];
    for (const trace of traces) {
      const members = (trace.members || []).filter((member) => patchChainIds.has(member.patch_chain_id));
      if (members.length < 2) continue;
      candidates.push({ trace, members });
    }
    candidates.sort((a, b) => {
      if (b.members.length !== a.members.length) return b.members.length - a.members.length;
      return String(a.trace.id).localeCompare(String(b.trace.id));
    });
    return candidates[0] || null;
  }

  function recordLoopNode(canonicalId, visualId, loopId) {
    if (!canonicalId) return;
    if (!canonicalToLoopNode.has(canonicalId)) canonicalToLoopNode.set(canonicalId, []);
    canonicalToLoopNode.get(canonicalId).push({ visualId, loopId });
  }

  for (const [loopIndex, group] of loopGroups.entries()) {
    const best = bestTraceForGroup(group);
    const sequence = [];
    if (best) {
      for (const member of best.members) {
        if (!sequence.length && member.start_trace_node_id) sequence.push(member.start_trace_node_id);
        if (member.end_trace_node_id) sequence.push(member.end_trace_node_id);
      }
      if (sequence.length > 1 && sequence[0] === sequence[sequence.length - 1]) {
        sequence.pop();
      }
    }
    if (sequence.length < 2) {
      sequence.push(...Array.from(group.anchorNodeIds).sort());
    }
    if (sequence.length < 2) {
      sequence.push(`${group.id}:a`, `${group.id}:b`);
    }

    group.nodeIds = [];
    group.memberCount = best?.members.length || 0;
    group.patchUseCount = group.patchChainIds.size;
    group.patchIdsList = Array.from(group.patchIds).sort();
    group.patchChainIdsList = Array.from(group.patchChainIds).sort();
    group.traceId = best?.trace.id || null;

    sequence.forEach((canonicalId, index) => {
      const visualId = `${group.id}:node:${index}`;
      group.nodeIds.push(visualId);
      recordLoopNode(canonicalId, visualId, group.id);
      addNode({
        id: visualId,
        canonicalId,
        label: compactId(canonicalId),
        kind: canonicalId.startsWith("run_endpoint_junction:") ? "RunEndpointJunction" : "ScaffoldNode",
        subtype: "topology-loop",
        topologyLoopId: group.id,
        topologyLoopIndex: loopIndex,
        topologyOrder: index,
        topologyCount: sequence.length,
        raw: {
          display_identity: "topology_loop_vertex",
          canonical_id: canonicalId,
          chain_id: group.chainId,
          patch_ids: group.patchIdsList,
          patch_chain_ids: group.patchChainIdsList,
          trace_id: group.traceId,
        },
      });
    });

    for (let index = 0; index < group.nodeIds.length; index += 1) {
      const source = group.nodeIds[index];
      const target = group.nodeIds[(index + 1) % group.nodeIds.length];
      addEdge({
        id: `${group.id}:segment:${index}`,
        source,
        target,
        kind: "TopologyLoopSegment",
        layer: "scaffoldEdges",
        label: `${group.patchUseCount} uses`,
        color: colorForId(group.chainId),
        raw: {
          display_identity: "topology_loop_segment",
          chain_id: group.chainId,
          segment_index: index,
          patch_ids: group.patchIdsList,
          patch_chain_ids: group.patchChainIdsList,
          source_scaffold_edges: group.selfEdges.map((item) => item.id),
        },
      });
    }
  }

  const bridgeGroups = new Map();
  for (const edge of scaffoldEdges) {
    if (edge.start_scaffold_node_id === edge.end_scaffold_node_id) continue;
    const sourceHits = canonicalToLoopNode.get(edge.start_scaffold_node_id) || [];
    const targetHits = canonicalToLoopNode.get(edge.end_scaffold_node_id) || [];
    if (!sourceHits.length || !targetHits.length) {
      const source = `loose:${edge.start_scaffold_node_id}`;
      const target = `loose:${edge.end_scaffold_node_id}`;
      addNode({
        id: source,
        canonicalId: edge.start_scaffold_node_id,
        label: compactId(edge.start_scaffold_node_id),
        kind: "ScaffoldNode",
        subtype: "loose",
        raw: { display_identity: "loose_scaffold_node", canonical_id: edge.start_scaffold_node_id },
      });
      addNode({
        id: target,
        canonicalId: edge.end_scaffold_node_id,
        label: compactId(edge.end_scaffold_node_id),
        kind: "ScaffoldNode",
        subtype: "loose",
        raw: { display_identity: "loose_scaffold_node", canonical_id: edge.end_scaffold_node_id },
      });
      addEdge({
        id: `topology-edge:${edge.id}`,
        source,
        target,
        kind: "TopologyPatchChain",
        layer: "scaffoldEdges",
        label: compactId(edge.patch_chain_id),
        color: "#ffc85a",
        raw: edge,
      });
      continue;
    }
    const sourceHit = sourceHits[0];
    const targetHit = targetHits[0];
    const loopPair = [sourceHit.loopId, targetHit.loopId].sort().join("|");
    const key = `${loopPair}|${edge.chain_id || edge.patch_chain_id || edge.id}`;
    if (!bridgeGroups.has(key)) {
      bridgeGroups.set(key, { source: sourceHit.visualId, target: targetHit.visualId, edges: [] });
    }
    bridgeGroups.get(key).edges.push(edge);
  }

  for (const [key, group] of bridgeGroups.entries()) {
    const first = group.edges[0];
    addEdge({
      id: `topology-bridge:${key}`,
      source: group.source,
      target: group.target,
      kind: "TopologyBridge",
      layer: "scaffoldEdges",
      label: group.edges.length > 1 ? `bridge x${group.edges.length}` : "bridge",
      color: "#ffc85a",
      raw: {
        display_identity: "topology_bridge",
        chain_id: first.chain_id || null,
        patch_chain_ids: group.edges.map((item) => item.patch_chain_id),
        scaffold_edge_ids: group.edges.map((item) => item.id),
        source_scaffold_node_id: first.start_scaffold_node_id,
        target_scaffold_node_id: first.end_scaffold_node_id,
      },
    });
  }

  return {
    layout: "topology",
    nodes: Array.from(nodes.values()),
    edges,
    aliases: [],
    loopGroups,
    bridgeCount: bridgeGroups.size,
    relations,
    inspection,
    source: payload.source,
    title: payload.title,
  };
}

function visibleGraph(graph) {
  if (!graph) return { nodes: [], edges: [] };
  const visibleEdges = graph.edges.filter((edge) => {
    if (edge.layer === "families") return state.layers.families;
    return state.layers[edge.layer] !== false;
  });
  const usedNodeIds = new Set();
  for (const edge of visibleEdges) {
    usedNodeIds.add(edge.source);
    usedNodeIds.add(edge.target);
  }
  const visibleNodes = graph.nodes.filter((node) => {
    if (node.kind === "RunEndpointJunction" && !state.layers.runEndpoints) return false;
    if (node.alias && !state.layers.ambiguities) return false;
    if (node.kind === "TopologyLabel") return graph.layout === "topology";
    return usedNodeIds.has(node.id) || node.kind === "ScaffoldNode" || (state.layers.runEndpoints && node.kind === "RunEndpointJunction");
  });
  return { nodes: visibleNodes, edges: visibleEdges };
}

function layoutGraph(graph) {
  if (!graph) return;
  const { nodes, edges } = visibleGraph(graph);
  if (graph.layout === "topology") {
    layoutTopologyGraph(graph, nodes);
    return;
  }
  const width = svg.clientWidth || 900;
  const height = svg.clientHeight || 700;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.max(160, Math.min(width, height) * 0.34);

  nodes.forEach((node, index) => {
    const angle = ((index / Math.max(1, nodes.length)) * Math.PI * 2) + (hashString(node.id) % 100) / 100;
    const jitter = 0.74 + (hashString(`${node.id}:${state.layoutSeed}`) % 100) / 460;
    node.x = cx + Math.cos(angle) * radius * jitter;
    node.y = cy + Math.sin(angle) * radius * jitter;
  });

  const byId = new Map(nodes.map((node) => [node.id, node]));
  for (let step = 0; step < 320; step += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      let fx = 0;
      let fy = 0;
      for (let j = 0; j < nodes.length; j += 1) {
        if (i === j) continue;
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = Math.max(80, dx * dx + dy * dy);
        const f = 7800 / d2;
        fx += dx * f;
        fy += dy * f;
      }
      a.x += fx * 0.024;
      a.y += fy * 0.024;
    }

    for (const edge of edges) {
      const a = byId.get(edge.source);
      const b = byId.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const ideal = edge.kind === "VisualAlias" ? 104 : 205;
      const f = (dist - ideal) * (edge.kind === "ScaffoldRailMember" ? 0.024 : 0.016);
      const nx = (dx / dist) * f;
      const ny = (dy / dist) * f;
      if (!a.alias) {
        a.x += nx;
        a.y += ny;
      }
      if (!b.alias || edge.kind !== "VisualAlias") {
        b.x -= nx;
        b.y -= ny;
      }
    }

    for (const node of nodes) {
      node.x += (cx - node.x) * 0.003;
      node.y += (cy - node.y) * 0.003;
      node.x = Math.max(42, Math.min(width - 42, node.x));
      node.y = Math.max(64, Math.min(height - 42, node.y));
    }
  }
}

function layoutTopologyGraph(graph, visibleNodes) {
  const width = svg.clientWidth || 900;
  const height = svg.clientHeight || 700;
  const loopGroups = graph.loopGroups || [];
  const visibleById = new Map(visibleNodes.map((node) => [node.id, node]));
  const centers = topologyGroupCenters(graph, width, height);
  const count = Math.max(1, loopGroups.length);
  const radius = Math.max(86, Math.min(145, width / Math.max(5.8, count * 3.1), height * 0.24));

  loopGroups.forEach((group, index) => {
    const center = centers.get(group.id) || { x: width / 2, y: height / 2 };
    const centerX = center.x;
    const centerY = center.y;
    const nodeIds = group.nodeIds || [];
    const phase = index % 2 === 0 ? 0 : Math.PI;
    nodeIds.forEach((nodeId, order) => {
      const node = visibleById.get(nodeId);
      if (!node) return;
      const angle = phase + (order / Math.max(1, nodeIds.length)) * Math.PI * 2;
      node.x = centerX + Math.cos(angle) * radius;
      node.y = centerY + Math.sin(angle) * radius;
    });

    const labelId = `${group.id}:label`;
    if (!visibleById.has(labelId) && !graph.nodes.some((node) => node.id === labelId)) {
      graph.nodes.push({
        id: labelId,
        canonicalId: group.chainId,
        label: `loop ${index + 1}`,
        kind: "TopologyLabel",
        subtype: "topology-label",
        alias: false,
        ambiguous: false,
        x: centerX,
        y: centerY,
        raw: {
          display_identity: "topology_loop_label",
          chain_id: group.chainId,
          patch_ids: group.patchIdsList,
          patch_chain_ids: group.patchChainIdsList,
          trace_id: group.traceId,
          member_count: group.memberCount,
        },
      });
    }
    const label = graph.nodes.find((node) => node.id === labelId);
    if (label) {
      label.x = centerX;
      label.y = centerY;
    }
  });
}

function topologyGroupCenters(graph, width, height) {
  const loopGroups = graph.loopGroups || [];
  const count = Math.max(1, loopGroups.length);
  const centers = new Map();
  const radius = Math.max(86, Math.min(145, width / Math.max(5.8, count * 3.1), height * 0.24));
  const centerY = height / 2 + 18;
  const usable = Math.max(radius * 2.4, width - 260);
  const startX = width / 2 - usable / 2;
  const stepX = count === 1 ? 0 : usable / (count - 1);

  loopGroups.forEach((group, index) => {
    centers.set(group.id, {
      x: count === 1 ? width / 2 : startX + stepX * index,
      y: centerY,
    });
  });

  if (!state.topologyPhysics || count < 2) return centers;

  const nodeToGroup = new Map();
  for (const node of graph.nodes) {
    if (node.topologyLoopId) nodeToGroup.set(node.id, node.topologyLoopId);
  }
  const springs = [];
  for (const edge of graph.edges) {
    if (edge.kind !== "TopologyBridge") continue;
    const sourceGroup = nodeToGroup.get(edge.source);
    const targetGroup = nodeToGroup.get(edge.target);
    if (sourceGroup && targetGroup && sourceGroup !== targetGroup) {
      springs.push({ sourceGroup, targetGroup });
    }
  }

  const minX = radius + 56;
  const maxX = width - radius - 56;
  const minY = radius + 96;
  const maxY = height - radius - 56;
  const bridgeRest = Math.max(radius * 3.05, Math.min(520, width * 0.55));
  const repelStrength = Math.max(22000, radius * radius * 2.15);
  const groupIds = loopGroups.map((group) => group.id);

  for (let step = 0; step < 180; step += 1) {
    for (let i = 0; i < groupIds.length; i += 1) {
      for (let j = i + 1; j < groupIds.length; j += 1) {
        const a = centers.get(groupIds[i]);
        const b = centers.get(groupIds[j]);
        const dx = b.x - a.x || 0.01;
        const dy = b.y - a.y || 0.01;
        const dist2 = Math.max(80, dx * dx + dy * dy);
        const dist = Math.sqrt(dist2);
        const force = repelStrength / dist2;
        const nx = (dx / dist) * force;
        const ny = (dy / dist) * force;
        a.x -= nx;
        a.y -= ny;
        b.x += nx;
        b.y += ny;
      }
    }

    for (const spring of springs) {
      const a = centers.get(spring.sourceGroup);
      const b = centers.get(spring.targetGroup);
      if (!a || !b) continue;
      const dx = b.x - a.x || 0.01;
      const dy = b.y - a.y || 0.01;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (dist - bridgeRest) * 0.045;
      const nx = (dx / dist) * force;
      const ny = (dy / dist) * force;
      a.x += nx;
      a.y += ny;
      b.x -= nx;
      b.y -= ny;
    }

    for (const id of groupIds) {
      const center = centers.get(id);
      center.x += (width / 2 - center.x) * 0.0015;
      center.y += (height / 2 + 18 - center.y) * 0.0015;
      center.x = Math.max(minX, Math.min(maxX, center.x));
      center.y = Math.max(minY, Math.min(maxY, center.y));
    }
  }

  return centers;
}

function render() {
  if (!state.graph) {
    svg.innerHTML = "";
    dropHint.classList.remove("hidden");
    return;
  }
  dropHint.classList.add("hidden");
  layoutGraph(state.graph);
  const { nodes, edges } = visibleGraph(state.graph);
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const zoom = Number(zoomRange.value || 100) / 100;
  const labels = labelsToggle.checked;
  const nodeLabels = labels && state.graph.layout !== "topology";
  const width = svg.clientWidth || 900;
  const height = svg.clientHeight || 700;
  svg.setAttribute("viewBox", `${(width - width / zoom) / 2} ${(height - height / zoom) / 2} ${width / zoom} ${height / zoom}`);

  const edgeMarkup = edges.map((edge) => {
    const a = byId.get(edge.source);
    const b = byId.get(edge.target);
    if (!a || !b) return "";
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const classes = [
      "edge",
      edge.layer === "families" ? "family" : "",
      edge.layer === "rails" ? "rail" : "",
      edge.layer === "traces" ? "trace" : "",
      edge.kind === "TopologyLoopSegment" ? "topology-loop" : "",
      edge.kind === "TopologyBridge" ? "topology-bridge" : "",
      edge.kind === "VisualAlias" ? "alias-link" : "",
      edge.kind.includes("Ambigu") ? "ambiguity" : "",
    ].filter(Boolean).join(" ");
    const isSelected = state.selectedKind === "edge" && state.selectedId === edge.id;
    const selected = isSelected ? " selected" : "";
    return `
      <g>
        <line class="edge-hit${selected}" x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" data-kind="edge" data-id="${escapeAttr(edge.id)}"></line>
        <line class="${classes}${selected}" x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" style="stroke:${edge.color || "#42545b"}"></line>
        ${labels && isSelected ? `<text class="edge-label" x="${mx.toFixed(1)}" y="${(my - 5).toFixed(1)}">${escapeText(edge.label || "")}</text>` : ""}
      </g>`;
  }).join("");

  const nodeMarkup = nodes.map((node) => {
    if (node.kind === "TopologyLabel") {
      const raw = node.raw || {};
      return `
        <g class="topology-label" data-kind="node" data-id="${escapeAttr(node.id)}">
          <rect class="topology-label-hit" x="${(node.x - 76).toFixed(1)}" y="${(node.y - 30).toFixed(1)}" width="152" height="50"></rect>
          <text class="loop-title" x="${node.x.toFixed(1)}" y="${(node.y - 8).toFixed(1)}">${escapeText(node.label)}</text>
          <text class="loop-subtitle" x="${node.x.toFixed(1)}" y="${(node.y + 10).toFixed(1)}">${escapeText(`${(raw.patch_chain_ids || []).length} patch uses, ${raw.member_count || 0} members`)}</text>
        </g>`;
    }
    const isRun = node.kind === "RunEndpointJunction";
    const selected = state.selectedKind === "node" && state.selectedId === node.id ? " selected" : "";
    const cls = ["node", isRun ? "run" : "scaffold", node.subtype === "topology-loop" ? "topology" : "", node.alias ? "alias" : "", node.ambiguous ? "ambiguous" : "", selected.trim()].filter(Boolean).join(" ");
    const shape = isRun && !node.alias
      ? `<rect class="node-shape" x="${(node.x - 8).toFixed(1)}" y="${(node.y - 8).toFixed(1)}" width="16" height="16" transform="rotate(45 ${node.x.toFixed(1)} ${node.y.toFixed(1)})"></rect>`
      : `<circle class="node-shape" cx="${node.x.toFixed(1)}" cy="${node.y.toFixed(1)}" r="${node.alias ? 11 : 12}"></circle>`;
    return `
      <g class="${cls}" data-kind="node" data-id="${escapeAttr(node.id)}">
        ${shape}
        ${nodeLabels ? `<text class="label" x="${(node.x + 15).toFixed(1)}" y="${(node.y + 4).toFixed(1)}">${escapeText(node.label)}</text>` : ""}
      </g>`;
  }).join("");

  svg.innerHTML = `<g>${edgeMarkup}${nodeMarkup}</g>`;
  updateSummary();
}

function updateSummary() {
  if (!state.graph) return;
  const rel = state.graph.relations;
  if (state.graph.layout === "topology") {
    summary.textContent = `${state.graph.title}: topology view, ${state.graph.loopGroups.length} loop groups, ${state.graph.bridgeCount || 0} bridges. Canonical graph: ${rel.scaffold_node_count || (rel.scaffold_nodes || []).length} ScaffoldNodes, ${rel.scaffold_edge_count || (rel.scaffold_edges || []).length} ScaffoldEdges.`;
  } else {
    summary.textContent = `${state.graph.title}: ${state.graph.nodes.length} visual nodes, ${state.graph.edges.length} relations. Canonical graph: ${rel.scaffold_node_count || (rel.scaffold_nodes || []).length} ScaffoldNodes, ${rel.scaffold_edge_count || (rel.scaffold_edges || []).length} ScaffoldEdges.`;
  }
  const railCount = (rel.scaffold_rails || []).length;
  const loopCount = (rel.scaffold_rails || []).filter((rail) => rail.is_closed_loop).length;
  const consumable = (rel.scaffold_rails || []).filter((rail) => rail.is_consumable_by_g5a).length;
  badges.innerHTML = [
    badge(state.graph.layout === "topology" ? "topology" : "evidence"),
    state.graph.layout === "topology" && state.topologyPhysics ? badge("physics") : "",
    state.graph.layout === "topology" ? badge(`${state.graph.loopGroups.length} loop groups`) : "",
    state.graph.layout === "topology" ? badge(`${state.graph.bridgeCount || 0} bridges`) : "",
    badge(`${(rel.connected_direction_families || []).length} families`),
    badge(`${(rel.scaffold_traces || []).length} traces`),
    badge(`${railCount} rails`),
    badge(`${consumable} consumable`),
    badge(`${loopCount} loops`, loopCount ? "status-warn" : "status-ok"),
  ].join("");
  payloadMeta.textContent = state.graph.source?.name || state.graph.source?.id || state.graph.title || "Payload loaded.";
}

function badge(text, cls = "") {
  return `<span class="badge ${cls}">${escapeText(text)}</span>`;
}

function selectItem(kind, id) {
  state.selectedKind = kind;
  state.selectedId = id;
  updateInspector();
  render();
}

function updateInspector() {
  if (!state.graph || !state.selectedId) {
    selectionTitle.textContent = "Nothing selected";
    selectionDetails.textContent = "Select a node, edge, trace, rail or ambiguity marker.";
    return;
  }
  const item = state.selectedKind === "node"
    ? state.graph.nodes.find((node) => node.id === state.selectedId)
    : state.graph.edges.find((edge) => edge.id === state.selectedId);
  if (!item) return;

  const raw = item.raw || {};
  selectionTitle.textContent = `${item.kind || state.selectedKind}: ${item.id}`;
  selectionDetails.innerHTML = [
    kv("canonical", item.canonicalId || raw.canonical_id || item.id),
    kv("label", item.label || ""),
    kv("layer", item.layer || item.subtype || ""),
    kv("family", item.familyId || raw.family?.id || raw.rail?.direction_family_id || ""),
    kv("trace", item.traceId || raw.trace?.id || raw.rail?.scaffold_trace_id || ""),
    kv("rail", item.railId || raw.rail?.id || ""),
    `<pre class="json-block">${escapeText(JSON.stringify(raw, null, 2))}</pre>`,
  ].join("");
}

function kv(key, value) {
  if (value === undefined || value === null || value === "") return "";
  return `<div class="kv"><div class="key">${escapeText(key)}</div><div class="value">${escapeText(String(value))}</div></div>`;
}

function updateSearch() {
  if (!state.graph) {
    searchResults.innerHTML = "";
    return;
  }
  const query = searchBox.value.trim().toLowerCase();
  if (!query) {
    searchResults.innerHTML = "";
    return;
  }
  const matches = [
    ...state.graph.nodes.map((node) => ({ kind: "node", id: node.id, text: `${node.id} ${node.label} ${node.kind}` })),
    ...state.graph.edges.map((edge) => ({ kind: "edge", id: edge.id, text: `${edge.id} ${edge.label} ${edge.kind} ${edge.familyId || ""} ${edge.railId || ""}` })),
  ].filter((item) => item.text.toLowerCase().includes(query)).slice(0, 18);
  searchResults.innerHTML = matches.map((item) => (
    `<div class="result-item" data-kind="${item.kind}" data-id="${escapeAttr(item.id)}">${escapeText(item.kind)} · ${escapeText(compactId(item.id))}</div>`
  )).join("");
}

async function loadJsonFile(file) {
  const text = await file.text();
  loadPayload(JSON.parse(text), file.name);
}

function loadPayload(raw, title = "") {
  const payload = normalizePayload(raw);
  if (title) payload.title = title;
  state.payload = payload;
  state.graph = buildGraph(payload);
  state.selectedId = null;
  state.layoutSeed += 1;
  updateInspector();
  updateSearch();
  render();
}

function escapeText(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return escapeText(value).replaceAll('"', "&quot;");
}

function demoPayload() {
  return {
    format: "scaffold_graph_viewer_payload_v1",
    source: { id: "demo_topological_loop", name: "Demo: loop alias and rail ambiguity" },
    inspection: {
      relations: {
        scaffold_nodes: [
          { id: "scaffold_node:source:a", source_vertex_ids: ["a"], patch_ids: ["patch:seed:f0"] },
          { id: "scaffold_node:source:b", source_vertex_ids: ["b"], patch_ids: ["patch:seed:f0"] },
          { id: "scaffold_node:source:c", source_vertex_ids: ["c"], patch_ids: ["patch:seed:f0"] },
          { id: "scaffold_node:source:d", source_vertex_ids: ["d"], patch_ids: ["patch:seed:f0"] },
        ],
        run_endpoint_junctions: [
          { id: "run_endpoint_junction:source:x", source_vertex_id: "x", anchor_scaffold_node_id: null, incident_run_endpoint_occurrences: [] },
        ],
        scaffold_edges: [
          { id: "scaffold_edge:ab", start_scaffold_node_id: "scaffold_node:source:a", end_scaffold_node_id: "scaffold_node:source:b", patch_chain_id: "patch_chain:f0:0", patch_id: "patch:seed:f0" },
          { id: "scaffold_edge:bc", start_scaffold_node_id: "scaffold_node:source:b", end_scaffold_node_id: "scaffold_node:source:c", patch_chain_id: "patch_chain:f0:1", patch_id: "patch:seed:f0" },
          { id: "scaffold_edge:cd", start_scaffold_node_id: "scaffold_node:source:c", end_scaffold_node_id: "scaffold_node:source:d", patch_chain_id: "patch_chain:f0:2", patch_id: "patch:seed:f0" },
          { id: "scaffold_edge:da", start_scaffold_node_id: "scaffold_node:source:d", end_scaffold_node_id: "scaffold_node:source:a", patch_chain_id: "patch_chain:f0:3", patch_id: "patch:seed:f0" },
        ],
        connected_direction_families: [
          { id: "connected_direction_family:loop", member_directional_evidence_ids: ["m0", "m1", "m2", "m3"], patch_ids: ["patch:seed:f0"] },
        ],
        scaffold_traces: [
          {
            id: "scaffold_trace:loop",
            direction_family_id: "connected_direction_family:loop",
            ordered_member_directional_evidence_ids: ["m0", "m1", "m2", "m3"],
            trace_node_ids: ["scaffold_node:source:a", "scaffold_node:source:b", "scaffold_node:source:c", "scaffold_node:source:d"],
            members: [
              { directional_evidence_id: "m0", start_trace_node_id: "scaffold_node:source:a", end_trace_node_id: "scaffold_node:source:b" },
              { directional_evidence_id: "m1", start_trace_node_id: "scaffold_node:source:b", end_trace_node_id: "scaffold_node:source:c" },
              { directional_evidence_id: "m2", start_trace_node_id: "scaffold_node:source:c", end_trace_node_id: "scaffold_node:source:d" },
              { directional_evidence_id: "m3", start_trace_node_id: "scaffold_node:source:d", end_trace_node_id: "scaffold_node:source:a" },
            ],
          },
        ],
        scaffold_rails: [
          {
            id: "scaffold_rail:loop",
            scaffold_trace_id: "scaffold_trace:loop",
            direction_family_id: "connected_direction_family:loop",
            ordered_member_directional_evidence_ids: ["m0", "m1", "m2", "m3"],
            ordered_trace_node_ids: ["scaffold_node:source:a", "scaffold_node:source:b", "scaffold_node:source:c", "scaffold_node:source:d", "scaffold_node:source:a"],
            first_trace_node_id: "scaffold_node:source:a",
            last_trace_node_id: "scaffold_node:source:a",
            is_closed_loop: true,
            is_consumable_by_g5a: false,
            loop_ambiguity_records: { closed_loop: ["m0", "m1", "m2", "m3"] },
            branch_records: {},
            diagnostics: ["loop_not_opened_without_cut_context"],
          },
        ],
      },
    },
  };
}

fileInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (file) loadJsonFile(file).catch((error) => alert(`Failed to load JSON: ${error.message}`));
});

demoButton.addEventListener("click", () => loadPayload(demoPayload(), "demo"));
relayoutButton.addEventListener("click", () => {
  state.layoutSeed += 1;
  render();
});
unrollToggle.addEventListener("change", () => {
  if (state.payload) state.graph = buildGraph(state.payload);
  render();
});
labelsToggle.addEventListener("change", render);
topologyPhysicsToggle.addEventListener("change", () => {
  state.topologyPhysics = topologyPhysicsToggle.checked;
  render();
});
zoomRange.addEventListener("input", render);
searchBox.addEventListener("input", updateSearch);
clearSelectionButton.addEventListener("click", () => {
  state.selectedId = null;
  state.selectedKind = null;
  updateInspector();
  render();
});

viewModeInputs.forEach((input) => {
  input.addEventListener("change", () => {
    if (!input.checked) return;
    state.viewMode = input.value;
    if (state.payload) state.graph = buildGraph(state.payload);
    state.selectedId = null;
    state.selectedKind = null;
    updateInspector();
    updateSearch();
    render();
  });
});

document.querySelectorAll("[data-layer]").forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    state.layers[checkbox.dataset.layer] = checkbox.checked;
    render();
  });
});

svg.addEventListener("click", (event) => {
  const target = event.target.closest("[data-kind][data-id]");
  if (!target) return;
  selectItem(target.dataset.kind, target.dataset.id);
});

searchResults.addEventListener("click", (event) => {
  const target = event.target.closest("[data-kind][data-id]");
  if (!target) return;
  selectItem(target.dataset.kind, target.dataset.id);
});

for (const eventName of ["dragenter", "dragover"]) {
  window.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropHint.textContent = "Release to load JSON";
    dropHint.classList.remove("hidden");
  });
}

window.addEventListener("dragleave", () => {
  if (state.graph) dropHint.classList.add("hidden");
});

window.addEventListener("drop", (event) => {
  event.preventDefault();
  const file = event.dataTransfer?.files?.[0];
  if (file) loadJsonFile(file).catch((error) => alert(`Failed to load JSON: ${error.message}`));
});

window.addEventListener("resize", render);

loadPayload(demoPayload(), "demo");
