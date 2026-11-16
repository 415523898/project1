import type { ToolTrace } from '@/types'

function sameAttempt(left: ToolTrace, right: ToolTrace): boolean {
  if (left.name !== right.name) return false
  const leftMethods = left.arguments?.methods
  const rightMethods = right.arguments?.methods
  if (Array.isArray(leftMethods) && Array.isArray(rightMethods)) {
    const a = leftMethods.map(String).sort().join(',')
    const b = rightMethods.map(String).sort().join(',')
    if (a !== b) return false
  }
  const leftDataset = left.arguments?.dataset
  const rightDataset = right.arguments?.dataset
  if (typeof leftDataset === 'string' && typeof rightDataset === 'string') {
    if (leftDataset !== rightDataset) return false
  }
  return true
}

export function hideRetriedFailures(tools: ToolTrace[] | undefined, succeeded: ToolTrace): void {
  if (!tools || succeeded.status === 'error') return
  for (const tool of tools) {
    if (tool === succeeded) break
    if (tool.status === 'error' && !tool.hidden && sameAttempt(tool, succeeded)) tool.hidden = true
  }
}

export function visibleTools(tools?: ToolTrace[]): ToolTrace[] {
  return (tools ?? []).filter((tool) => !tool.hidden)
}
