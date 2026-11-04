import { mkdir, mkdtemp, readFile, rm, stat, utimes, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { execHelper } = vi.hoisted(() => ({ execHelper: vi.fn() }));
vi.mock('node:child_process', async () => {
	const { promisify } = await import('node:util');
	return { execFile: Object.assign(vi.fn(), { [promisify.custom]: execHelper }) };
});

import { loadScenario, replayEpisode } from './scenarios.js';

let root: string;
let packageRoot: string;
const task = { id: 'cache-test', version: '1' };

async function write(relative: string, contents: string) {
	const file = path.join(root, relative);
	await mkdir(path.dirname(file), { recursive: true });
	await writeFile(file, contents);
	return file;
}

beforeEach(async () => {
	vi.stubEnv('FARADAY_PYTHON', 'python3');
	execHelper.mockReset().mockResolvedValue({ stdout: JSON.stringify({ task, events: [] }) });
	root = await mkdtemp(path.join(tmpdir(), 'faraday-viewer-cache-'));
	packageRoot = 'src/faraday_industrial_benchmark';
	await write('tasks.json', '[]');
	await write('run.json', '{}');
	await write(`${packageRoot}/world.py`, '# stable');
	await write(`${packageRoot}/distributor/tools.py`, '# one');
	await write(`${packageRoot}/distributor/fixtures/case.json`, '{"value":1}');
});

afterEach(async () => {
	vi.unstubAllEnvs();
	await rm(root, { recursive: true, force: true });
});

describe('scenario cache dependencies', () => {
	it('shares unchanged requests and retains the cached result', async () => {
		const results = await Promise.all([
			loadScenario('tasks.json', task, root),
			loadScenario('tasks.json', task, root)
		]);
		expect(results[0].ok).toBe(true);
		expect(results[1]).toBe(results[0]);
		expect(await loadScenario('tasks.json', task, root)).toBe(results[0]);
		expect(execHelper).toHaveBeenCalledTimes(1);
	});

	it.each(['distributor/tools.py', 'distributor/fixtures/case.json'])(
		'invalidates same-size edits with preserved timestamps in nested %s',
		async (relative) => {
			await loadScenario('tasks.json', task, root);
			const file = path.join(root, packageRoot, relative);
			const original = await stat(file);
			const contents = await readFile(file, 'utf8');
			await writeFile(file, contents.replace('one', 'two').replace(':1', ':2'));
			await utimes(file, original.atime, original.mtime);
			await loadScenario('tasks.json', task, root);
			expect(execHelper).toHaveBeenCalledTimes(2);
		}
	);

	it.each(['nested/new.py', 'distributor/fixtures/new.json'])(
		'invalidates adding and removing %s even with old timestamps',
		async (relative) => {
			await loadScenario('tasks.json', task, root);
			const file = await write(`${packageRoot}/${relative}`, '{}');
			await utimes(file, new Date(0), new Date(0));
			await loadScenario('tasks.json', task, root);
			expect(execHelper).toHaveBeenCalledTimes(2);
			// Cache a distinct content state before deletion, so the original key
			// cannot mask whether removal changed the fingerprint.
			await write(`${packageRoot}/world.py`, '# changed');
			await loadScenario('tasks.json', task, root);
			await rm(file);
			await loadScenario('tasks.json', task, root);
			expect(execHelper).toHaveBeenCalledTimes(4);
		}
	);

	it('invalidates task and run inputs even when they are older than the helper', async () => {
		await replayEpisode('run.json', 'tasks.json', task, root);
		for (const input of ['tasks.json', 'run.json']) {
			const file = await write(input, '{"changed":true}');
			await utimes(file, new Date(0), new Date(0));
			await replayEpisode('run.json', 'tasks.json', task, root);
		}
		expect(execHelper).toHaveBeenCalledTimes(3);
	});
});
