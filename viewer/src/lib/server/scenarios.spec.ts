import { describe, expect, it } from 'vitest';
import { getRun } from './runs.js';
import { loadScenario, replayEpisode } from './scenarios.js';

// These run the real Python helper against the repository's own task and run files.
describe('loadScenario', () => {
	it('regenerates the scheduled events for a public episode', async () => {
		const scenario = await loadScenario('data/public/tasks.json', {
			id: 'faraday-quality-001',
			version: '0.2.3'
		});

		expect(scenario.ok).toBe(true);
		if (!scenario.ok) return;
		expect(scenario.task.id).toBe('faraday-quality-001');
		expect(scenario.events.map((event) => [event.at_minute, event.id])).toEqual([
			[5, 'EVT-LAB-CONFIRM'],
			[14, 'EVT-SHIPPING-CUTOFF']
		]);
	});

	it('reports a task that is not in the task file', async () => {
		const scenario = await loadScenario('data/public/tasks.json', {
			id: 'faraday-missing-001',
			version: '0.6.0'
		});

		expect(scenario).toEqual({
			ok: false,
			message: expect.stringContaining('not found')
		});
	});
});

describe('replayEpisode', () => {
	async function oracleEpisode(taskId: string) {
		const result = (await getRun('reports--oracle-run'))?.run.results.find(
			(item) => item.task.id === taskId
		);
		if (!result) throw new Error(`reports/oracle-run.json has no ${taskId}`);
		return result;
	}

	it('finds event timing and reports drift in the archived run', async () => {
		const result = await oracleEpisode('faraday-quality-001');
		const replay = await replayEpisode('reports/oracle-run.json', 'data/public/tasks.json', result.task);

		expect(replay.ok).toBe(true);
		if (!replay.ok) return;
		// This historical run predates get_incident's public scoring_contract.
		expect(replay.first_result_mismatch).toBe(0);
		expect(replay.first_record_mismatch).toBe(0);
		expect(replay.applied_events).toEqual(result.applied_events);
		expect(
			replay.events.map((item) => [item.event.id, item.fired_during, item.scheduled_by])
		).toEqual([
			['EVT-LAB-CONFIRM', 4, null],
			['EVT-SHIPPING-CUTOFF', 9, null]
		]);
	});

	it('includes events that tool calls scheduled', async () => {
		const result = await oracleEpisode('faraday-supply-001');
		const replay = await replayEpisode('reports/oracle-run.json', 'data/public/tasks.json', result.task);

		expect(replay.ok).toBe(true);
		if (!replay.ok) return;
		expect(replay.applied_events).toEqual(result.applied_events);
		const decision = replay.events.find((item) => item.event.kind === 'approval_decision');
		expect(decision?.scheduled_by).toEqual(expect.any(Number));
		expect(result.trace[decision?.scheduled_by ?? -1]?.tool).toBe('request_approval');
	});

	it('reports an episode that is not in the run file', async () => {
		const replay = await replayEpisode(
			'reports/coupled-hard-oracle.json',
			'data/public/tasks.json',
			{ id: 'faraday-quality-001', version: '0.2.3' }
		);

		expect(replay).toEqual({ ok: false, message: expect.stringContaining('has no episode') });
	});
});
