<script lang="ts">
	import { resolve } from '$app/paths';
	import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import CircleXIcon from '@lucide/svelte/icons/circle-x';
	import JsonBlock from '#lib/components/json-block.svelte';
	import Meter from '#lib/components/meter.svelte';
	import MetricCard from '#lib/components/metric-card.svelte';
	import Notice from '#lib/components/notice.svelte';
	import OutcomeBadge from '#lib/components/outcome-badge.svelte';
	import PageHeader from '#lib/components/page-header.svelte';
	import Timeline from '#lib/components/timeline.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { formatMoney, formatScore, humanize, outcomeOf, scoreTone, TONE_TEXT } from '#lib/format.js';
	import { formatValue } from '#lib/payload.js';
	import { buildTimeline, type TimelineEntry } from '#lib/timeline.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const result = $derived(data.result);
	const task = $derived(result.task);
	const score = $derived(result.score);
	const passedCriteria = $derived(score.criteria.filter((criterion) => criterion.passed).length);
	// Failed criteria first. The sort is stable, so each group keeps the grader's order.
	const criteria = $derived(
		[...score.criteria].sort((a, b) => Number(a.passed) - Number(b.passed))
	);
	const summary = $derived(
		typeof result.final_answer.summary === 'string' ? result.final_answer.summary : ''
	);
	const evidence = $derived(
		Array.isArray(result.final_answer.evidence) ? result.final_answer.evidence.map(formatValue) : []
	);
	const otherAnswerFields = $derived(
		Object.fromEntries(
			Object.entries(result.final_answer).filter(([key]) => key !== 'summary' && key !== 'evidence')
		)
	);
	const overBudget = $derived(score.tool_calls > task.max_tool_calls);
	const callsOnly = $derived(buildTimeline(result.trace, []));

	let tab = $state('timeline');

	function episodeHref(id: string) {
		return resolve('/runs/[run]/[task]', { run: data.listing.slug, task: id });
	}

	function listIds(ids: string[]): string {
		return ids.length > 0 ? ids.join(', ') : 'no events';
	}

	function sameIds(a: string[], b: string[]): boolean {
		return a.length === b.length && a.every((id, position) => id === b[position]);
	}
</script>

{#snippet timelineList(entries: TimelineEntry[])}
	<!-- Keyed by episode so expanded results don't carry over to the next one. -->
	{#key `${data.listing.slug}/${task.id}`}
		<Timeline {entries} />
	{/key}
{/snippet}

<PageHeader
	title={task.title}
	crumbs={[
		{ label: 'Runs', href: resolve('/') },
		{ label: data.listing.agent, href: resolve('/runs/[run]', { run: data.listing.slug }) }
	]}
>
	{#snippet meta()}
		<Badge variant="secondary" class="font-mono">{task.id}</Badge>
		<Badge variant="outline">v{task.version}</Badge>
		<Badge variant="outline">{humanize(task.family)}</Badge>
		<Badge variant="outline" class="capitalize">{task.difficulty}</Badge>
		{#if data.taskSet}
			<a
				href={resolve('/examples/[set]/[task]', { set: data.taskSet, task: task.id })}
				class="text-muted-foreground hover:text-foreground ml-1 text-xs underline underline-offset-4"
			>
				View in {data.taskSet} examples
			</a>
		{/if}
	{/snippet}
	{#snippet actions()}
		<Button
			variant="outline"
			size="sm"
			href={data.previous ? episodeHref(data.previous) : undefined}
			disabled={!data.previous}
		>
			<ChevronLeftIcon aria-hidden="true" />
			Previous
		</Button>
		<Button
			variant="outline"
			size="sm"
			href={data.next ? episodeHref(data.next) : undefined}
			disabled={!data.next}
		>
			Next
			<ChevronRightIcon aria-hidden="true" />
		</Button>
	{/snippet}
</PageHeader>

<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
	<MetricCard
		label="Score"
		value={formatScore(score.score)}
		valueClass={TONE_TEXT[scoreTone(score.score)]}
	>
		<div class="flex flex-wrap items-center gap-2 pt-1">
			<OutcomeBadge outcome={outcomeOf(score)} />
			<span class="text-muted-foreground text-xs">
				{passedCriteria} of {score.criteria.length} criteria passed
			</span>
		</div>
	</MetricCard>
	<MetricCard
		label="Tool calls"
		value="{score.tool_calls} / {task.max_tool_calls}"
		valueClass={overBudget ? 'text-red-700' : undefined}
		detail={overBudget ? 'Over the tool budget' : 'Within the tool budget'}
	/>
	<MetricCard
		label="Elapsed"
		value="{score.elapsed_minutes} / {task.horizon_minutes} min"
		detail="Simulated minutes used of the horizon"
	/>
	<MetricCard
		label="Estimated cost"
		value={formatMoney(score.estimated_cost)}
		detail="Unmitigated {formatMoney(score.unmitigated_cost)} · best known {formatMoney(
			score.best_known_cost
		)}"
	/>
</div>

<div class="grid gap-4 lg:grid-cols-3">
	<div class="flex flex-col gap-4 lg:col-span-2">
		<Card.Root>
			<Card.Header>
				<Card.Title>Prompt</Card.Title>
			</Card.Header>
			<Card.Content>
				<p class="leading-relaxed whitespace-pre-line">{task.prompt}</p>
			</Card.Content>
		</Card.Root>
		<Card.Root>
			<Card.Header>
				<Card.Title>Final answer</Card.Title>
			</Card.Header>
			<Card.Content>
				{#if summary}
					<p class="leading-relaxed whitespace-pre-line">{summary}</p>
				{:else}
					<p class="text-muted-foreground">The agent didn't submit a summary.</p>
				{/if}
				{#if evidence.length > 0}
					<div class="flex flex-wrap items-center gap-1.5">
						<span class="text-muted-foreground text-xs">Evidence</span>
						<!-- The agent's own list, which can repeat entries. -->
						{#each evidence as item, index (index)}
							<Badge variant="secondary" class="font-mono">{item}</Badge>
						{/each}
					</div>
				{/if}
				{#if Object.keys(otherAnswerFields).length > 0}
					<JsonBlock value={otherAnswerFields} />
				{/if}
			</Card.Content>
		</Card.Root>
	</div>
	<Card.Root>
		<Card.Header>
			<Card.Title>Dimensions</Card.Title>
			<Card.Description>Points earned of the points available</Card.Description>
		</Card.Header>
		<Card.Content class="gap-3">
			{#each Object.entries(score.dimensions) as [name, dimension] (name)}
				{@const ratio = dimension.max_score > 0 ? dimension.score / dimension.max_score : 1}
				<div class="flex flex-col gap-1">
					<div class="flex items-baseline justify-between gap-2">
						<span>{humanize(name)}</span>
						<span class="text-muted-foreground text-xs tabular-nums">
							{dimension.score.toFixed(1)} / {dimension.max_score.toFixed(1)}
						</span>
					</div>
					<Meter value={ratio} tone={scoreTone(ratio * 100)} label="{humanize(name)} points" />
				</div>
			{/each}
		</Card.Content>
	</Card.Root>
</div>

<Tabs.Root bind:value={tab}>
	<Tabs.List>
		<Tabs.Trigger value="timeline">
			Timeline <span class="text-muted-foreground tabular-nums">{result.trace.length}</span>
		</Tabs.Trigger>
		<Tabs.Trigger value="criteria">
			Criteria
			<span class="text-muted-foreground tabular-nums">{passedCriteria}/{score.criteria.length}</span>
		</Tabs.Trigger>
		<Tabs.Trigger value="violations">
			Violations <span class="text-muted-foreground tabular-nums">{score.violations.length}</span>
		</Tabs.Trigger>
	</Tabs.List>

	<Tabs.Content value="timeline" class="flex flex-col gap-3 pt-2">
		<p class="text-muted-foreground max-w-3xl text-sm">
			Each call shows the simulated minute after it ran. Events appear after the call during which
			they fired. Some, such as approval decisions, are scheduled by the agent's own calls.
		</p>
		{#await data.replay}
			<div class="flex items-center gap-3 rounded-lg border border-dashed p-3">
				<Skeleton class="size-4 rounded-full" />
				<span class="text-muted-foreground text-sm">Replaying the run to place its events…</span>
			</div>
			{@render timelineList(callsOnly)}
		{:then replay}
			{#if !replay.ok}
				<Notice tone="warning" title="Couldn't replay this run">
					<p class="font-mono text-xs">{replay.message}</p>
					<p>
						The timeline shows tool calls only. The run recorded {listIds(result.applied_events)}.
					</p>
				</Notice>
				{@render timelineList(callsOnly)}
			{:else}
				{@const eventsDiffer = !sameIds(replay.applied_events, result.applied_events)}
				{#if replay.first_result_mismatch !== null || eventsDiffer}
					<Notice tone="warning" title="The current benchmark code doesn't reproduce this run exactly">
						{#if replay.first_result_mismatch !== null}
							<p>Call #{replay.first_result_mismatch + 1} returns a different result when replayed.</p>
						{/if}
						{#if eventsDiffer}
							<p>
								The run recorded {listIds(result.applied_events)}. The replay fired
								{listIds(replay.applied_events)}.
							</p>
						{/if}
						<p>
							Events are shown where the current code fires them, so they may not match what the
							agent saw. This run used benchmark v{data.listing.benchmark_version}.
						</p>
					</Notice>
				{/if}
				{@render timelineList(buildTimeline(result.trace, replay.events))}
			{/if}
		{/await}
	</Tabs.Content>

	<Tabs.Content value="criteria" class="pt-2">
		<div class="rounded-xl border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head class="w-10 pl-4"><span class="sr-only">Result</span></Table.Head>
						<Table.Head>Criterion</Table.Head>
						<Table.Head>Dimension</Table.Head>
						<Table.Head class="text-right">Weight</Table.Head>
						<Table.Head class="pr-4">Detail</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each criteria as criterion (criterion.id)}
						<Table.Row>
							<Table.Cell class="pl-4">
								{#if criterion.passed}
									<CircleCheckIcon class="size-4 text-emerald-600" aria-hidden="true" />
									<span class="sr-only">Passed</span>
								{:else}
									<CircleXIcon class="size-4 text-red-600" aria-hidden="true" />
									<span class="sr-only">Failed</span>
								{/if}
							</Table.Cell>
							<Table.Cell class="font-mono text-xs">{criterion.id}</Table.Cell>
							<Table.Cell>{humanize(criterion.dimension)}</Table.Cell>
							<Table.Cell class="text-right tabular-nums">{criterion.weight}</Table.Cell>
							<Table.Cell class="text-muted-foreground pr-4 whitespace-normal">
								{criterion.detail}
							</Table.Cell>
						</Table.Row>
					{:else}
						<Table.Row>
							<Table.Cell colspan={5} class="text-muted-foreground py-10 text-center">
								This episode has no criteria.
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	</Tabs.Content>

	<Tabs.Content value="violations" class="pt-2">
		{#if score.violations.length === 0}
			<p class="text-muted-foreground rounded-xl border px-4 py-10 text-center text-sm">
				No violations.
			</p>
		{:else}
			<div class="rounded-xl border">
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head class="pl-4 text-right">Minute</Table.Head>
							<Table.Head>Severity</Table.Head>
							<Table.Head>Code</Table.Head>
							<Table.Head class="pr-4">Message</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						<!-- Identical violations can repeat, so rows are keyed by position. -->
						{#each score.violations as violation, index (index)}
							<Table.Row>
								<Table.Cell class="pl-4 text-right tabular-nums">{violation.minute ?? '—'}</Table.Cell>
								<Table.Cell>
									<Badge
										variant={violation.severity === 'critical' ? 'destructive' : 'outline'}
										class={[
											'capitalize',
											violation.severity === 'warning' && 'border-amber-600/25 bg-amber-50 text-amber-800'
										]}
									>
										{violation.severity}
									</Badge>
								</Table.Cell>
								<Table.Cell class="font-mono text-xs">{violation.code}</Table.Cell>
								<Table.Cell class="pr-4 whitespace-normal">{violation.message}</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</div>
		{/if}
	</Tabs.Content>
</Tabs.Root>
