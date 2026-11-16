export interface ToolFigure {
  name: string
  path?: string | null
  url?: string
}

export interface MetricEntry {
  label?: string
  task?: string
  accuracy?: number
  roc_auc?: number | null
  roc_auc_ovr?: number
  fpc?: number
  clusters?: number
  test_r2?: number
  test_rmse?: number
  test_mae?: number
  train_r2?: number
  metrics?: Record<string, unknown>
  tables?: Record<string, unknown>
  [key: string]: unknown
}

export interface ExperimentFailure {
  method: string
  label?: string
  error: string
}

export interface ExperimentResult {
  experiment_id?: string
  experiment_number?: number
  experiment_version?: number
  result_explanations?: Record<
    string,
    { text: string; model?: string; usage?: { total_tokens?: number } }
  >
  session?: string | null
  method?: string
  title?: string
  task?: string
  elapsed_ms?: number
  parameters?: Record<string, unknown>
  source?: string
  dataset?: string
  dataset_label?: string
  datasets?: Array<{ dataset?: string; label?: string; source?: string; methods: string[] }>
  data?: {
    label?: string
    dataset?: string
    records?: number
    rows?: number
    columns?: number
    column_names?: string[]
    features?: number | string[]
    classes?: string[]
    target?: string | null
    group?: string | null
    time?: string | null
  }
  split?: { kind?: string; train?: number; test?: number; validation?: number }
  methods?: Record<string, MetricEntry>
  metrics?: Record<string, unknown>
  tables?: Record<string, unknown>
  tree_count?: number
  figures?: ToolFigure[]
  warnings?: string[]
  notes?: string[]
  error?: string
  failures?: ExperimentFailure[]
  failures_note?: string | null
  results?: SearchEntry[]
  query?: string
  channels?: Record<string, number | string | null>
  context?: string
  reason?: string
}

export interface SearchEntry {
  id: string
  title: string
  capability?: string
  tasks?: string[]
  when?: string
  outputs?: string[]
  limits?: string[]
  score?: number
}

export interface ToolTrace {
  id?: string
  name: string
  reason?: string
  status: 'running' | 'complete' | 'error'
  result: ExperimentResult | null
  arguments?: Record<string, unknown>
  hidden?: boolean
}

export type LearningStatus = 'done' | 'todo' | 'locked' | 'tried'

export interface LearningNode {
  id: string
  key: string
  title: string
  capability?: string | null
  tasks?: string[]
  run_method?: string | null
  level?: number
  stage?: string
  requires?: string[]
  why?: string
  status?: LearningStatus
  manual?: boolean
  studying?: boolean
  x: number
  y: number
  note?: string
  number?: number
  session?: string | null
  method?: string | null
  step?: number
  turns?: number
  updated_at?: string
}

export interface LearningEdge {
  from: string
  to: string
}

export interface LearningMap {
  study_mode?: 'study_v2'
  unavailable_reason?: string
  mode: 'curriculum' | 'agent' | 'conversations'
  nodes: LearningNode[]
  edges: LearningEdge[]
  stages: Array<{ name: string; hint: string }>
  progress: Record<LearningStatus, number>
  total: number
  conversations?: number
  empty?: boolean
  next: string | null
  card?: { width: number; height: number }
}

export interface MethodMath {
  version: number
  variant: string
  formula: string
  meaning: string
  symbols: string
  steps: string
  conditions: string
  example: string
  implementation?: string
  sources: Array<{ title: string; url: string; section: string }>
}

export interface MethodCard {
  id: string
  label: string
  category: string
  category_name: string
  group: string
  kind: string
  tasks: string[]
  scenarios: string[]
  inputs: string[]
  outputs: string[]
  note: string
  math?: MethodMath | null
  when: string
  level: number
  needs: string | null
  missing: string[]
  before: string[]
  suggests: string[]
  after: string[]
  more: string[]
  similar: string[]
  similar_why: Record<string, string>
}

export interface CategoryTree {
  key: string
  name: string
  hint: string
  count: number
  scenarios: string[]
  groups: Array<{ name: string; kind: string; count: number; methods: string[] }>
}

export interface MethodLayer {
  level: number
  name: string
  hint: string
  count: number
  groups: string[]
  methods: string[]
}

export type RelationKind = 'prerequisite' | 'suggest' | 'alternative'

export interface RelationEdge {
  from: string
  to: string
  why?: string
}

export interface MethodGraph {
  cards: MethodCard[]
  tree: CategoryTree[]
  edges: Record<RelationKind, RelationEdge[]>
  layers: MethodLayer[]
  scenarios: Array<{ name: string; methods: string[] }>
  counts: {
    methods: number
    groups: number
    categories: number
    prerequisite: number
    suggest: number
    alternative: number
    levels: number
  }
  problems: string[]
}

export interface ToolOutcome {
  name: string
  reason?: string
  methods?: Record<string, MetricEntry>
  results?: SearchEntry[]
  split?: { kind?: string; train?: number; test?: number; validation?: number }
  figures?: string[]
  data?: {
    label?: string
    dataset?: string
    records?: number
    features?: number
    classes?: string[]
  }
  error?: string
}

export interface TurnImage {
  data_url: string
  name: string
  width: number
  height: number
  source_width?: number
  source_height?: number
  bytes?: number
}

export interface ChatAttachment {
  id: string
  session_id: string
  name: string
  size: number
  mime: string
  kind: 'image' | 'audio' | 'document' | 'table' | 'file'
  read_status: 'text' | 'image' | 'unreadable' | 'error'
  note: string
  truncated: boolean
}

export type TurnActivity =
  | { kind: 'message'; text: string; phase?: 'working' | 'final'; step?: number }
  | { kind: 'tool'; index: number }

export interface ChatTurn {
  event_id?: string
  model_phase?: 'connecting' | 'connected' | 'thinking' | 'generating' | 'tool_call'
  kind?: 'chat' | 'experiment'
  question: string
  answer: string
  activity?: TurnActivity[]
  tools?: ToolTrace[]
  tool_result?: ToolOutcome[] | null
  result?: ExperimentResult
  context?: Record<string, unknown> | null
  images?: TurnImage[] | null
  attachments?: ChatAttachment[]
  image?: TurnImage | null
  model?: string
  status: 'pending' | 'complete' | 'error' | 'stopped'
  detail_level?: DetailLevel
  elapsed_ms?: number
  steps?: number
  usage?: { total_tokens?: number }
  error?: string | null
  created_at?: string
}

export type DetailLevel = 'concise' | 'normal' | 'detailed'

export interface UploadedFile {
  id: string
  name: string
  dataset: string
  rows: number
  columns: number
  column_names: string[]
  dtypes: Record<string, string>
  target: string | null
  task: string
  head: unknown[][]
  saved_at: string
  error?: string
  kind?: 'upload'
  label?: string
  time?: string | null
  group?: string | null
  configured?: boolean
  suggested_target?: string | null
}

export interface DatasetChoice {
  id: string
  dataset: string
  label: string
  kind: 'builtin' | 'upload'
  task: string
  target?: string | null
  time?: string | null
  group?: string | null
  name?: string
  rows?: number
  columns?: number
  column_names?: string[]
  dtypes?: Record<string, string>
  head?: unknown[][]
  configured?: boolean
  suggested_target?: string | null
}

export interface ParameterSpec {
  key: string
  label: string
  type: 'boolean' | 'integer' | 'number' | 'enum' | 'text' | 'columns'
  default: unknown
  min?: number
  max?: number
  step?: number
  options?: unknown[]
  group?: string
  hidden_when?: Record<string, unknown>
  depends_on?: string
}

export interface ParameterGroup {
  name: string
  params: ParameterSpec[]
}

export interface MethodRequires {
  source_tasks?: string[]
  binary?: boolean
  features?: number
}

export interface MethodSpec {
  id: string
  title: string
  task: string
  engine: string
  extra?: boolean
  classic?: boolean
  params: ParameterSpec[]
  groups?: ParameterGroup[]
  group?: string | null
  kind?: string | null
  category?: string | null
  category_name?: string | null
  tasks?: string[]
  scenarios?: string[]
  inputs?: string[]
  outputs?: string[]
  note?: string
  when?: string
  level?: number | null
  needs?: string | null
  missing?: string[]
  runnable?: boolean
  requires?: MethodRequires
}

export interface SourceSpec {
  id: string
  label: string
  task: string
  features?: number
  classes?: number
  time?: string | null
  group?: string | null
  text?: string | null
  columns?: string[] | null
}

export interface Catalog {
  methods?: MethodSpec[]
  library: MethodSpec[]
  shared?: ParameterSpec[]
  sources: SourceSpec[]
  limits: { max_trees: number; max_run_seconds: number; max_rows: number | null; max_methods?: number }
  figures_dir?: string
}

export interface SessionSummary {
  title_source?: 'fallback' | 'branch' | 'ai' | 'manual'
  binding?: { session_id: string; method_id: string; card_id: string; card_missing?: boolean }
  id: string
  title: string
  created_at?: string
  updated_at?: string
  turns: number
  tools: number
  workspace?: string
}

export interface WorkspaceSummary {
  id: string
  label: string
  root: string
  sessions: number
}

export interface SessionEvent {
  v?: number
  seq?: number
  id?: string
  kind: string
  at?: string
  text?: string
  call?: string
  name?: string
  step?: number
  arguments?: Record<string, unknown>
  result?: ExperimentResult
  context?: Record<string, unknown> | null
  [key: string]: unknown
}

export interface SessionRecord {
  title_source?: SessionSummary['title_source']
  message_actions?: { revision: boolean; fork: boolean }
  experiment_sidebar?: ExperimentSidebar
  selected_dataset?: DatasetChoice | null
  run?: {
    running: boolean
    token?: string
    step?: number
    phase?: 'model' | 'tool'
    cancelled?: boolean
    model?: string
    answer?: string
  }
  id: string
  title: string
  view?: string
  turns?: ChatTurn[]
  events?: SessionEvent[]
  created_at?: string
  updated_at?: string
}

export interface ExperimentVersion {
  version: number
  created_at: string
  result: ExperimentResult
  explanations: Record<
    string,
    { text: string; model?: string; usage?: { total_tokens?: number }; fingerprint?: string }
  >
}

export interface SidebarExperiment {
  id: string
  number: number
  title: string
  source_key: string
  aliases?: string[]
  active_version: number
  deleted?: boolean
  versions: ExperimentVersion[]
}

export interface ExperimentSidebar {
  schema: number
  revision: number
  selected_id: string | null
  experiments: SidebarExperiment[]
}

export interface AgentEvent {
  type:
    | 'start'
    | 'user_message'
    | 'step'
    | 'model_status'
    | 'retry'
    | 'token'
    | 'message_reset'
    | 'message_end'
    | 'tool_call'
    | 'tool_result'
    | 'done'
    | 'error'
  event_id?: string
  session?: string
  model?: string
  tools?: boolean
  execution?: string
  step?: number
  phase?: string
  name?: string
  text?: string
  id?: string
  arguments?: Record<string, unknown>
  result?: ExperimentResult
  message?: string
  usage?: { total_tokens?: number }
  elapsed_ms?: number
  steps?: number
  tool_calls?: number
  attempt?: number
  delay_ms?: number
  code?: string
  status?: number
  request_id?: string
  attempts?: number
}

export interface MethodEmbeddings {
  model: string
  dims: number
  pooling: string
  ids: string[]
  vectors: number[][]
  documents: string[]
}
