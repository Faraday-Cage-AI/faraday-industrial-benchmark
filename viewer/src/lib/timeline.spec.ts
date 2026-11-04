import { describe, expect, it } from 'vitest';
import { buildTimeline, type TimelineEntry } from './timeline.js';
import type { ReplayedEvent, ToolCall } from './types.js';

function call(index: number, minute: number, tool = 'get_incident'): ToolCall {
	return {
		index,
		minute,
		tool,
		arguments: {},
		result: { ok: true },
		state_hash: '0'.repeat(64)
	};
}

function replayed(
	id: string,
	firedDuring: number | null,
	scheduledBy: number | null = null
): ReplayedEvent {
	return {
		event: { id, at_minute: 0, kind: 'message', payload: {} },
		fired_during: firedDuring,
		scheduled_by: scheduledBy
	};
}

function describeEntries(entries: TimelineEntry[]): string[] {
	return entries.map((entry) =>
		entry.type === 'call' ? `call:${entry.call.index}` : `event:${entry.event.id}:${entry.status}`
	);
}

describe('buildTimeline', () => {
	it('places each event after the call during which it fired, in firing order', () => {
		const trace = [call(0, 1), call(1, 2), call(2, 4), call(3, 7)];
		const entries = buildTimeline(trace, [
			replayed('EVT-A', 2),
			replayed('EVT-C', 3),
			replayed('EVT-B', 3)
		]);

		expect(describeEntries(entries)).toEqual([
			'call:0',
			'call:1',
			'call:2',
			'event:EVT-A:fired',
			'call:3',
			'event:EVT-C:fired',
			'event:EVT-B:fired'
		]);
	});

	it('lists events that never fired after the last call', () => {
		const entries = buildTimeline([call(0, 1), call(1, 2)], [replayed('EVT-LATE', null)]);

		expect(describeEntries(entries)).toEqual(['call:0', 'call:1', 'event:EVT-LATE:not_reached']);
	});

	it('links events to the call that scheduled them', () => {
		const trace = [call(0, 1), call(1, 3, 'request_approval')];
		const entries = buildTimeline(trace, [replayed('EVT-APR-001-DECISION', 1, 1), replayed('EVT-X', 0)]);

		expect(entries.filter((entry) => entry.type === 'event')).toMatchObject([
			{ event: { id: 'EVT-X' }, scheduledBy: undefined },
			{ event: { id: 'EVT-APR-001-DECISION' }, scheduledBy: { index: 1, tool: 'request_approval' } }
		]);
	});
});
