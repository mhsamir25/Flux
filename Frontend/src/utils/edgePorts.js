// join is the only node type with two input ports; its handles are explicitly id="left"/
// id="right" (see FluxNode). Every other node's single target handle has no id, so
// targetHandle is null/undefined for those edges — exactly what the backend expects for
// target_port on a non-join edge. Shared by ReactFlowCanvas (building request payloads) and
// ConfigPanel (looking up which upstream node feeds a given COLUMN_SELECT field).
export const getTargetPort = (edge) =>
  edge.targetHandle === 'left' || edge.targetHandle === 'right' ? edge.targetHandle : null
