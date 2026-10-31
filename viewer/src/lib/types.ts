export interface WorkflowStage {
	id: string;
	objective: string;
	depends_on: string[];
}

/** Task fields as `IncidentTask.public_dict()` publishes them, plus `seed` when read from a task file. */
export interface Task {
	id: string;
	version: string;
	family: string;
	title: string;
	prompt: string;
	difficulty: string;
	systems: string[];
	max_tool_calls: number;
	horizon_minutes: number;
	tags: string[];
	controlled_plan_actions: string[];
	workflow_stages?: WorkflowStage[];
	required_notification_roles?: string[];
	seed?: number;
}

export interface ScheduledEvent {
	id: string;
	at_minute: number;
	kind: string;
	payload: Record<string, unknown>;
}

export interface ToolCall {
	index: number;
	minute: number;
	tool: string;
	arguments: Record<string, unknown>;
	result: Record<string, unknown>;
	state_hash: string;
}

export interface Criterion {
	id: string;
	dimension: string;
	weight: number;
	passed: boolean;
	detail: string;
}

export interface Violation {
	minute?: number;
	code: string;
	message: string;
	severity: string;
}

export interface EpisodeScore {
	task_id: string;
	score: number;
	strict_success: boolean;
	critical_failure: boolean;
	estimated_cost: number;
	unmitigated_cost: number;
	best_known_cost: number;
	dimensions: Record<string, { score: number; max_score: number }>;
	criteria: Criterion[];
	violations: Violation[];
	tool_calls: number;
	elapsed_minutes: number;
}

export interface EpisodeResult {
	task: Task;
	agent: string;
	score: EpisodeScore;
	final_answer: { summary?: string; evidence?: string[]; [key: string]: unknown };
	trace: ToolCall[];
	initial_state_hash: string;
	final_state_hash: string;
	applied_events: string[];
}

export interface RunSummary {
	tasks: number;
	families: number;
	mean_score: number;
	min_score?: number;
	max_score?: number;
	strict_successes: number;
	strict_success_rate?: number;
	critical_failures: number;
	estimated_cost?: number;
	unmitigated_cost?: number;
	estimated_cost_avoided?: number;
	tool_calls: number;
}

export interface FamilySummary {
	tasks: number;
	mean_score: number;
	strict_successes: number;
	critical_failures: number;
	tool_calls: number;
}

export interface CapabilitySummary {
	tasks: number;
	mean_score: number;
	mean_max_score: number;
	attainment_rate: number;
}

/** A saved run file, as described by `schemas/run.schema.json`. */
export interface Run {
	schema_version: string;
	benchmark_version: string;
	agent: string;
	summary: RunSummary;
	family_summaries: Record<string, FamilySummary>;
	capability_summaries: Record<string, CapabilitySummary>;
	results: EpisodeResult[];
}

export interface RunListing {
	slug: string;
	/** Path relative to the repository root. */
	path: string;
	agent: string;
	benchmark_version: string;
	schema_version: string;
	modified: string;
	summary: RunSummary;
}

export interface TaskSetListing {
	name: string;
	/** Path relative to the repository root. */
	path: string;
	tasks: number;
	families: string[];
	versions: string[];
	difficulties: string[];
}

export interface TaskAppearance {
	slug: string;
	agent: string;
	path: string;
	score: number;
	strict_success: boolean;
	critical_failure: boolean;
}

export type ScenarioResult =
	| { ok: true; task: Task; events: ScheduledEvent[] }
	| { ok: false; message: string };

export interface ReplayedEvent {
	event: ScheduledEvent;
	/** Trace position of the call during which the event fired, or null if it never fired. */
	fired_during: number | null;
	/** Trace position of the call that scheduled the event, or null if the scenario did. */
	scheduled_by: number | null;
}

/** A run episode replayed with the current benchmark code. */
export type ReplayResult =
	| {
			ok: true;
			/** Fired events in firing order, then the events that never fired. */
			events: ReplayedEvent[];
			applied_events: string[];
			/** Trace position of the first call whose replayed result differs from the run's. */
			first_result_mismatch: number | null;
	  }
	| { ok: false; message: string };
