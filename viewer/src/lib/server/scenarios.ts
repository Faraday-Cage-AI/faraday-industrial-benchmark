import { execFile } from 'node:child_process';
import { constants } from 'node:fs';
import { access, readdir, stat } from 'node:fs/promises';
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

/** Results are cached until one of `files`, the helper, or the benchmark's Python source changes. */
async function runHelper<Result>(
	args: string[],
	files: string[],
	root: string,
	toResult: (output: unknown) => Result
): Promise<Result | Failure> {
	let key: string;
	try {
		key = [...args, await sourceStamp(files, root)].join('|');
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

async function sourceStamp(files: string[], root: string): Promise<number> {
	const sourceDirectory = path.join(root, 'src', 'faraday_industrial_benchmark');
	const sources = (await readdir(sourceDirectory))
		.filter((name) => name.endsWith('.py'))
		.map((name) => path.join(sourceDirectory, name));
	const times = await Promise.all(
		[...files, HELPER, ...sources].map(async (file) => (await stat(file)).mtimeMs)
	);
	return Math.max(...times);
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
