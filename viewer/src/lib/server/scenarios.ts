import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { access, readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { promisify } from 'node:util';
import type { ReplayResult, ScenarioResult, ScheduledEvent, Task } from '#lib/types.js';
import { REPO_ROOT, VIEWER_ROOT } from './repo.js';

const execFileAsync = promisify(execFile);
const HELPER = path.join(VIEWER_ROOT, 'scripts', 'scenario_events.py');
const TIMEOUT_MS = 60_000;
const cache = new Map<string, Promise<unknown>>();

type Failure = { ok: false; message: string };
type Success<Result> = Exclude<Result, Failure>;
type EpisodeRef = Pick<Task, 'id' | 'version'>;

/**
 * Generates one episode's public task fields and the events its scenario schedules up
 * front. Never rejects: failures come back as `{ ok: false }` for the page to show.
 */
export function loadScenario(
	taskFile: string,
	task: EpisodeRef,
	root = REPO_ROOT
): Promise<ScenarioResult> {
	const file = path.resolve(root, taskFile);
	return runHelper<Success<ScenarioResult>>([file, task.id, task.version], [file], root, (output) => {
		const parsed = output as { task: Task; events: ScheduledEvent[] };
		return { ok: true, task: parsed.task, events: parsed.events };
	});
}

/**
 * Replays a run episode's tool calls with the current benchmark code to find when each
 * event fired, including events the calls themselves scheduled. Never rejects.
 */
export function replayEpisode(
	runFile: string,
	taskFile: string,
	task: EpisodeRef,
	root = REPO_ROOT
): Promise<ReplayResult> {
	const run = path.resolve(root, runFile);
	const file = path.resolve(root, taskFile);
	return runHelper<Success<ReplayResult>>(
		[file, task.id, task.version, '--replay', run],
		[file, run],
		root,
		(output) => ({ ok: true, ...(output as Omit<Success<ReplayResult>, 'ok'>) })
	);
}

/** Cache against inputs, the helper, and all benchmark Python source and JSON fixtures. */
async function runHelper<Result>(
	args: string[],
	files: string[],
	root: string,
	toResult: (output: unknown) => Result
): Promise<Result | Failure> {
	let key: string;
	try {
		key = JSON.stringify([root, args, await sourceStamp(files, root)]);
	} catch (error) {
		return { ok: false, message: describe(error) };
	}
	let pending = cache.get(key) as Promise<Result | Failure> | undefined;
	if (!pending) {
		pending = execHelper(args, root)
			.then(toResult)
			.catch((error: unknown) => {
				cache.delete(key);
				return { ok: false as const, message: describe(error) };
			});
		cache.set(key, pending);
	}
	return pending;
}

async function sourceStamp(files: string[], root: string): Promise<string> {
	const sourceDirectory = path.join(root, 'src', 'faraday_industrial_benchmark');
	async function sourcesIn(directory: string): Promise<string[]> {
		const entries = await readdir(directory, { withFileTypes: true });
		const sources = await Promise.all(
			entries.map(async (entry) => {
				const file = path.join(directory, entry.name);
				if (entry.isDirectory()) return sourcesIn(file);
				return /\.(py|json)$/.test(entry.name) ? [file] : [];
			})
		);
		return sources.flat();
	}
	const sources = [...new Set([...files, HELPER, ...(await sourcesIn(sourceDirectory))])].sort();
	const contents = await Promise.all(sources.map((file) => readFile(file)));
	const hash = createHash('sha256');
	for (let index = 0; index < sources.length; index += 1) {
		// Lengths delimit both paths and bytes; additions, removals, and same-size
		// edits with preserved timestamps all produce a different fingerprint.
		hash.update(JSON.stringify([sources[index], contents[index].length]));
		hash.update(contents[index]);
	}
	return hash.digest('hex');
}

async function execHelper(args: string[], root: string): Promise<unknown> {
	const [command, ...prefix] = await pythonCommand();
	const { stdout } = await execFileAsync(command, [...prefix, HELPER, ...args], {
		cwd: root,
		env: { ...process.env, FARADAY_REPO: root },
		timeout: TIMEOUT_MS,
		maxBuffer: 64 * 1024 * 1024
	});
	return JSON.parse(stdout);
}

async function pythonCommand(): Promise<string[]> {
	const configured = process.env.FARADAY_PYTHON?.trim();
	if (configured) return configured.split(/\s+/);
	// The benchmark needs Python 3.11 or newer, which the system python3 may not be.
	if (await isOnPath('uv')) return ['uv', 'run', '--no-project', '--python', '>=3.11', 'python'];
	return ['python3'];
}

async function isOnPath(command: string): Promise<boolean> {
	for (const directory of (process.env.PATH ?? '').split(path.delimiter).filter(Boolean)) {
		try {
			await access(path.join(directory, command), constants.X_OK);
			return true;
		} catch {
			// Not in this directory.
		}
	}
	return false;
}

function describe(error: unknown): string {
	const stderr = (error as { stderr?: unknown }).stderr;
	const lastLine = typeof stderr === 'string' ? stderr.trim().split('\n').at(-1) : undefined;
	return lastLine || (error instanceof Error ? error.message : String(error));
}
