
const EDGE_STYLE = { stroke: 'var(--border-light)', strokeWidth: 2 }

export function buildOnboardingPipeline() {
  const csvData = [
    'Name,Subject,Grade',
    'Alice,Math,85',
    'Bob,Math,42',
    'Charlie,Science,90',
    'Diana,Science,35',
    'Eve,History,75',
    'Frank,Math,95',
    'Grace,Science,88',
    'Henry,History,60',
    'Ivy,History,40',
  ].join('\n')

 
  const nodes = [
    { id: 'n1', type: 'fluxNode', position: { x: 50, y: 150 }, data: { nodeType: 'read_csv', displayName: 'Read CSV', config: {} } },
    { id: 'n2', type: 'fluxNode', position: { x: 300, y: 150 }, data: { nodeType: 'filter', displayName: 'Filter Passing', config: { column: 'Grade', operator: '≥', value: '50' } } },
    { id: 'n3', type: 'fluxNode', position: { x: 550, y: 150 }, data: { nodeType: 'group_by_aggregate', displayName: 'Average by Subject', config: { group_column: 'Subject', aggregations: [{ column: 'Grade', function: 'AVERAGE' }] } } },
    { id: 'n4', type: 'fluxNode', position: { x: 800, y: 150 }, data: { nodeType: 'sort', displayName: 'Sort by Average', config: { column: 'Grade_average', direction: 'DESC' } } },
    { id: 'n5', type: 'fluxNode', position: { x: 1050, y: 150 }, data: { nodeType: 'bar_chart', displayName: 'Bar Chart', config: { x_column: 'Subject', y_column: 'Grade_average', title: 'Average Grade by Subject', color: '#7c3aed' } } },
  ]

  
  const edges = [
    { id: 'e1', source: 'n1', target: 'n2', animated: true, style: EDGE_STYLE },
    { id: 'e2', source: 'n2', target: 'n3', animated: true, style: EDGE_STYLE },
    { id: 'e3', source: 'n3', target: 'n4', animated: true, style: EDGE_STYLE },
    { id: 'e4', source: 'n4', target: 'n5', animated: true, style: EDGE_STYLE },
  ]

  return { nodes, edges, csvData }
}
