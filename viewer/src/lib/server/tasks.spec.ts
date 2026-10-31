import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { findTask, listTaskSets, summarizeTaskSet } from './tasks.js';

let root: string;

function task(id: string, extra: Record<string, unknown> = {}) {
	return { id, family: 'quality_drift', title: `Task ${id}`, prompt: 'Investigate.', seed: 1, ...extra };
}

async function writeTasks(set: string, payload: unknown) {
	await mkdir(path.join(root, 'data', set), { recursive: true });
	await writeFile(path.join(root, 'data', set, 'tasks.json'), JSON.stringify(payload));
}

beforeAll(async () => {
	root = await mkdtemp(path.join(tmpdir(), 'faraday-viewer-tasks-'));
	await writeTasks('public', [task('faraday-a-001'), task('faraday-b-001', { version: '0.2.0' })]);
	await writeTasks('close-chain', [task('faraday-c-001', { version: '1' })]);
	await writeTasks('close-chain-v2', [task('faraday-c-001', { version: '2' })]);
	await writeTasks('single', task('faraday-d-001', { difficulty: 'hard' }));
	await mkdir(path.join(root, 'data', 'no-task-file'), { recursive: true });
});

afterAll(async () => {
	await rm(root, { recursive: true, force: true });
});

describe('listTaskSets', () => {
	it('lists the public set first and reads single-task files', async () => {
		const sets = await listTaskSets(root);

		expect(sets.map((set) => set.name)).toEqual(['public', 'close-chain', 'close-chain-v2', 'single']);
		expect(sets[3].tasks.map((item) => item.id)).toEqual(['faraday-d-001']);
	});

	it('applies the same defaults as IncidentTask.from_dict', async () => {
		const [publicSet] = await listTaskSets(root);

		expect(publicSet.tasks[0]).toMatchObject({
			version: '0.6.0',
			difficulty: 'medium',
			max_tool_calls: 30,
			horizon_minutes: 60,
			systems: [],
			tags: []
		});
		expect(summarizeTaskSet(publicSet)).toMatchObject({
			tasks: 2,
			families: ['quality_drift'],
			versions: ['0.2.0', '0.6.0']
		});
	});
});

describe('findTask', () => {
	it('matches on ID and version because IDs repeat across versioned sets', async () => {
		expect((await findTask('faraday-c-001', '1', root))?.set.name).toBe('close-chain');
		expect((await findTask('faraday-c-001', '2', root))?.set.name).toBe('close-chain-v2');
		expect(await findTask('faraday-c-001', '3', root)).toBeUndefined();
	});
});
