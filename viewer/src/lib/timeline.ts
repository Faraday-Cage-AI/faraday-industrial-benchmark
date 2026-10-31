import type { ReplayedEvent, ScheduledEvent, ToolCall } from './types.js';

/** `fired`: the event fired during the call above it. `not_reached`: the run ended first. */
export type EventStatus = 'fired' | 'not_reached';

export type TimelineEntry =
	| { type: 'call'; call: ToolCall }
	| { type: 'event'; event: ScheduledEvent; status: EventStatus; scheduledBy?: ToolCall };

/**
 * Puts each replayed event right after the call during which it fired, keeping firing
 * order, and adds the events that never fired at the end.
 */
export function buildTimeline(trace: ToolCall[], events: ReplayedEvent[]): TimelineEntry[] {
	const byCall = new Map<number | null, TimelineEntry[]>();
	for (const item of events) {
		const group = byCall.get(item.fired_during) ?? [];
		group.push({
			type: 'event',
			event: item.event,
			status: item.fired_during === null ? 'not_reached' : 'fired',
			scheduledBy: item.scheduled_by === null ? undefined : trace[item.scheduled_by]
		});
		byCall.set(item.fired_during, group);
	}
	return [
		...trace.flatMap((call, position): TimelineEntry[] => [
			{ type: 'call', call },
			...(byCall.get(position) ?? [])
		]),
		...(byCall.get(null) ?? [])
	];
}
