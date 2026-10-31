<script lang="ts">
	import { resolve } from '$app/paths';
	import Notice from '#lib/components/notice.svelte';
	import PageHeader from '#lib/components/page-header.svelte';
	import ScoreBadge from '#lib/components/score-badge.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { formatCount, formatDate, formatRate } from '#lib/format.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<PageHeader
	title="Runs"
	description="Saved benchmark runs from runs/ and reports/. Open a run to see its episodes, scores, and tool traces."
/>

{#if data.runs.length === 0}
	<Notice title="No run files yet">
		<p>Save a run under <code class="font-mono">runs/</code>, then reload this page:</p>
		<pre class="bg-background rounded-md border px-3 py-2 font-mono text-xs">faraday-bench run --agent oracle --output runs/oracle.json</pre>
		<p>The viewer reads files from <code class="font-mono">{data.repoRoot}</code>.</p>
	</Notice>
{:else}
	<div class="rounded-xl border">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head class="pl-4">Run</Table.Head>
					<Table.Head>Benchmark</Table.Head>
					<Table.Head class="text-right">Episodes</Table.Head>
					<Table.Head class="text-right">Mean score</Table.Head>
					<Table.Head class="text-right">Strict success</Table.Head>
					<Table.Head class="text-right">Critical failures</Table.Head>
					<Table.Head class="text-right">Tool calls</Table.Head>
					<Table.Head class="pr-4 text-right">Modified</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each data.runs as run (run.slug)}
					<Table.Row class="relative">
						<Table.Cell class="pl-4">
							<a
								href={resolve('/runs/[run]', { run: run.slug })}
								class="font-medium after:absolute after:inset-0 hover:underline"
							>
								{run.agent}
							</a>
							<p class="text-muted-foreground font-mono text-xs">{run.path}</p>
						</Table.Cell>
						<Table.Cell><Badge variant="outline">v{run.benchmark_version}</Badge></Table.Cell>
						<Table.Cell class="text-right tabular-nums">{formatCount(run.summary.tasks)}</Table.Cell>
						<Table.Cell class="text-right"><ScoreBadge score={run.summary.mean_score} /></Table.Cell>
						<Table.Cell class="text-right tabular-nums">
							{formatRate(run.summary.strict_successes, run.summary.tasks)}
							<span class="text-muted-foreground">({run.summary.strict_successes})</span>
						</Table.Cell>
						<Table.Cell
							class={[
								'text-right tabular-nums',
								run.summary.critical_failures > 0 && 'font-medium text-red-700'
							]}
						>
							{run.summary.critical_failures}
						</Table.Cell>
						<Table.Cell class="text-right tabular-nums">{formatCount(run.summary.tool_calls)}</Table.Cell>
						<Table.Cell class="text-muted-foreground pr-4 text-right">{formatDate(run.modified)}</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
{/if}
