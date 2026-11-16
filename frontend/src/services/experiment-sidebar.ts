import { ApiBase } from '@/utils/api-base'
import { readableError } from '@/services/agent'
import type { ExperimentSidebar } from '@/types'

export async function loadExperimentSidebar(
  session: string,
  signal?: AbortSignal,
): Promise<ExperimentSidebar> {
  const response = await ApiBase.request(
    '/api/experiments/sidebar?session=' + encodeURIComponent(session),
    { signal },
  )
  if (!response.ok) throw new Error(await readableError(response))
  return response.json() as Promise<ExperimentSidebar>
}

export async function changeExperiment(
  session: string,
  action: 'select' | 'delete' | 'version',
  experiment_id: string,
  version?: number,
  signal?: AbortSignal,
): Promise<ExperimentSidebar> {
  const response = await ApiBase.json(
    '/api/experiments/sidebar',
    {
      session,
      action,
      experiment_id,
      version,
    },
    signal,
  )
  if (!response.ok) throw new Error(await readableError(response))
  return response.json() as Promise<ExperimentSidebar>
}
