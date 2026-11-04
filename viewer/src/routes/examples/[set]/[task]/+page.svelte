<script lang="ts">
	import { resolve } from '$app/paths';
	import ChevronLeftIcon from '@lucide/svelte/icons/chevron-left';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import MetricCard from '#lib/components/metric-card.svelte';
	import Notice from '#lib/components/notice.svelte';
	import OutcomeBadge from '#lib/components/outcome-badge.svelte';
	import PageHeader from '#lib/components/page-header.svelte';
	import ScoreBadge from '#lib/components/score-badge.svelte';
	import Timeline from '#lib/components/timeline.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { humanize, outcomeOf } from '#lib/format.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const task = $derived(data.task);

	function episodeHref(id: string) {
		return resolve('/examples/[set]/[task]', { set: data.set.name, task: id });
	}
</script>

{#snippet badgeList(label: string, items: string[])}
	<div class="flex flex-col gap-1.5">
		<p class="text-muted-foreground text-xs font-medium">{label}</p>
		{#if items.length > 0}
			<div class="flex flex-wrap gap-1">
				{#each items as item (item)}
					<Badge variant="outline" class="font-mono">{item}</Badge>
				{/each}
			</div>
		{:else}
			<p class="text-muted-foreground">None</p>
		{/if}
	</div>
{/snippet}

<PageHeader
	title={task.title}
	crumbs={[
		{ label: 'Examples', href: resolve('/examples') },
		{ label: data.set.name, href: resolve('/examples/[set]', { set: data.set.name }) }
	]}
>
	{#snippet meta()}
		<Badge variant="secondary" class="font-mono">{task.id}</Badge>
		<Badge variant="outline">v{task.version}</Badge>
		<Badge variant="outline">{humanize(task.family)}</Badge>
		<Badge variant="outline" class="capitalize">{task.difficulty}</Badge>
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
	<MetricCard label="Tool budget" value="{task.max_tool_calls} calls" />
	<MetricCard label="Horizon" value="{task.horizon_minutes} min" />
	<MetricCard
		label="Seed"
		value={task.seed === undefined ? '—' : String(task.seed)}
		detail="Drives the generated scenario"
	/>
	{#await data.scenario}
		<MetricCard label="Scheduled events" value="…" detail="Generating from the scenario code" />
	{:then scenario}
		<MetricCard
			label="Scheduled events"
			value={scenario.ok ? String(scenario.events.length) : '—'}
			detail={scenario.ok ? 'Generated from the scenario code' : "Couldn't generate events"}
		/>
	{/await}
</div>

<div class="grid gap-4 lg:grid-cols-3">
	<Card.Root class="lg:col-span-2">
		<Card.Header>
			<Card.Title>Prompt</Card.Title>
		</Card.Header>
		<Card.Content>
			<p class="leading-relaxed whitespace-pre-line">{task.prompt}</p>
		</Card.Content>
	</Card.Root>
	<Card.Root>
		<Card.Header>
			<Card.Title>Setup</Card.Title>
		</Card.Header>
		<Card.Content class="gap-4">
			{@render badgeList('Systems', task.systems)}
			{@render badgeList('Tags', task.tags)}
			{@render badgeList('Controlled plan actions', task.controlled_plan_actions)}
		</Card.Content>
	</Card.Root>
</div>

<Card.Root>
	<Card.Header>
		<Card.Title>Workflow</Card.Title>
		<Card.Description>Stages and required notifications from the scenario code</Card.Description>
	</Card.Header>
	<Card.Content class="gap-4">
		{#await data.scenario}
			<Skeleton class="h-4 w-2/3" />
			<Skeleton class="h-4 w-1/2" />
		{:then scenario}
			{#if !scenario.ok}
				<p class="text-muted-foreground">Unavailable because the scenario couldn't be generated.</p>
			{:else}
				{@const stages = scenario.task.workflow_stages ?? []}
				{#if stages.length === 0}
					<p class="text-muted-foreground">This episode has no workflow stages.</p>
				{:else}
					<ol class="flex flex-col gap-3">
						{#each stages as stage, index (stage.id)}
							<li class="flex gap-3">
								<span
									class="bg-muted text-muted-foreground flex size-6 shrink-0 items-center justify-center rounded-full text-xs tabular-nums"
								>
									{index + 1}
								</span>
								<div class="flex flex-col gap-0.5">
									<p class="font-mono text-xs font-medium">{stage.id}</p>
									<p>{stage.objective}</p>
									{#if stage.depends_on.length > 0}
										<p class="text-muted-foreground text-xs">After {stage.depends_on.join(', ')}</p>
									{/if}
								</div>
							</li>
						{/each}
					</ol>
				{/if}
				{@render badgeList(
					'Required notification roles',
					scenario.task.required_notification_roles ?? []
				)}
			{/if}
		{/await}
	</Card.Content>
</Card.Root>

<section class="flex flex-col gap-3">
	<div class="flex flex-col gap-1">
		<h2 class="text-lg font-semibold tracking-tight">Scheduled events</h2>
		<p class="text-muted-foreground max-w-3xl text-sm">
			Each event changes the simulated world at its minute. Agents only notice it through later tool
			calls. Tool calls can schedule more events, such as approval decisions, which run timelines
			also show.
		</p>
	</div>
	{#await data.scenario}
		<Skeleton class="h-20 w-full" />
		<Skeleton class="h-20 w-full" />
	{:then scenario}
		{#if !scenario.ok}
			<Notice tone="warning" title="Couldn't generate this episode's events">
				<p class="font-mono text-xs">{scenario.message}</p>
			</Notice>
		{:else if scenario.events.length === 0}
			<p class="text-muted-foreground text-sm">This episode has no scheduled events.</p>
		{:else}
			<Timeline entries={scenario.events.map((event) => ({ type: 'event' as const, event }))} />
		{/if}
	{/await}
</section>

<section class="flex flex-col gap-3">
	<h2 class="text-lg font-semibold tracking-tight">Saved runs</h2>
	{#if data.appearances.length === 0}
		<p class="text-muted-foreground text-sm">No saved run includes this episode version.</p>
	{:else}
		<div class="rounded-xl border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head class="pl-4">Run</Table.Head>
						<Table.Head class="text-right">Score</Table.Head>
						<Table.Head class="pr-4">Outcome</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.appearances as appearance (appearance.slug)}
						<Table.Row class="relative">
							<Table.Cell class="pl-4">
								<a
									href={resolve('/runs/[run]/[task]', { run: appearance.slug, task: task.id })}
									class="font-medium after:absolute after:inset-0 hover:underline"
								>
									{appearance.agent}
								</a>
								<p class="text-muted-foreground font-mono text-xs">{appearance.path}</p>
							</Table.Cell>
							<Table.Cell class="text-right"><ScoreBadge score={appearance.score} /></Table.Cell>
							<Table.Cell class="pr-4"><OutcomeBadge outcome={outcomeOf(appearance)} /></Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</section>
