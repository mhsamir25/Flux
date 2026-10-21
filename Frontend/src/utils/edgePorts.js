
export const getTargetPort = (edge) =>
  edge.targetHandle === 'left' || edge.targetHandle === 'right' ? edge.targetHandle : null
