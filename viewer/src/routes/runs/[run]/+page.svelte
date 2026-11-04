<script lang="ts">
	import { snapshot } from '$app/navigation';
	import { resolve } from '$app/paths';
	import SearchIcon from '@lucide/svelte/icons/search';
	import Meter from '#lib/components/meter.svelte';
	import MetricCard from '#lib/components/metric-card.svelte';
	import OutcomeBadge from '#lib/components/outcome-badge.svelte';
	import PageHeader from '#lib/components/page-header.svelte';
	import ScoreBadge from '#lib/components/score-badge.svelte';
	import SortableHead from '#lib/components/sortable-head.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import {
		formatCount,
		formatDate,
		formatMoney,
		formatPercent,
		formatRate,
		formatScore,
		humanize,
		OUTCOME_LABELS,
		outcomeOf,
		scoreTone,
		TONE_TEXT,
		type Outcome
	} from '#lib/format.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	type SortKey = 'order' | 'id' | 'score' | 'tool_calls' | 'elapsed_minutes';

	interface View {
		tab: string;
		search: string;
		family: string;
		outcome: Outcome | '';
		sort: SortKey;
		descending: boolean;
	}

	const INITIAL_VIEW: View = {
		tab: 'episodes',
		search: '',
		family: '',
		outcome: '',
		sort: 'order',
		descending: false
	};

	let view = $state<View>({ ...INITIAL_VIEW });

	snapshot({
		capture: () => $state.snapshot(view),
		restore: (value) => {
			view = value;
		},
		reset: () => {
			view = { ...INITIAL_VIEW };
		}
	});

	const summary = $derived(data.listing.summary);
	const families = $derived([...new Set(data.episodes.map((episode) => episode.family))].sort());
	const filtering = $derived(view.search !== '' || view.family !== '' || view.outcome !== '');

	const visible = $derived.by(() => {
		const query = view.search.trim().toLowerCase();
		const rows = data.episodes.filter(
			(episode) =>
				(!query ||
					[episode.id, episode.title, episode.family].some((text) =>
						text.toLowerCase().includes(query)
					)) &&
				(!view.family || episode.family === view.family) &&
				(!view.outcome || outcomeOf(episode) === view.outcome)
		);
		if (view.sort === 'order') return rows;
		const key = view.sort;
		const sign = view.descending ? -1 : 1;
		return rows.sort((a, b) => {
			const left = a[key];
			const right = b[key];
			return (
				sign *
				(typeof left === 'number' && typeof right === 'number'
					? left - right
					: String(left).localeCompare(String(right)))
			);
		});
	});

	function sortBy(key: SortKey) {
		if (view.sort === key) {
			view.descending = !view.descending;
		} else {
			view.sort = key;
			view.descending = false;
		}
	}

	function direction(key: SortKey): 'asc' | 'desc' | null {
		if (view.sort !== key) return null;
		return view.descending ? 'desc' : 'asc';
	}

	function clearFilters() {
		view.search = '';
		view.family = '';
		view.outcome = '';
	}

	function showFamily(family: string) {
		clearFilters();
		view.family = family;
		view.tab = 'episodes';
	}
</script>

<PageHeader title={data.listing.agent} crumbs={[{ label: 'Runs', href: resolve('/') }]}>
	{#snippet meta()}
		<Badge variant="secondary" class="font-mono">{data.listing.path}</Badge>
		<Badge variant="outline">Benchmark v{data.listing.benchmark_version}</Badge>
		<Badge variant="outline">{data.listing.schema_version}</Badge>
		<span class="text-muted-foreground text-xs">Modified {formatDate(data.listing.modified)}</span>
	{/snippet}
</PageHeader>

<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
	<MetricCard
		label="Mean score"
		value={formatScore(summary.mean_score)}
		valueClass={TONE_TEXT[scoreTone(summary.mean_score)]}
		detail={summary.min_score !== undefined && summary.max_score !== undefined
			? `Range ${formatScore(summary.min_score)} to ${formatScore(summary.max_score)}`
			: undefined}
	/>
	<MetricCard
		label="Strict success"
		value={formatRate(summary.strict_successes, summary.tasks)}
		detail="{summary.strict_successes} of {summary.tasks} episodes"
	/>
	<MetricCard
		label="Critical failures"
		value={formatCount(summary.critical_failures)}
		valueClass={summary.critical_failures > 0 ? 'text-red-700' : undefined}
		detail="Episodes scored 0 for a critical violation"
	/>
	<MetricCard
		label="Tool calls"
		value={formatCount(summary.tool_calls)}
		detail={summary.tasks > 0
			? `${(summary.tool_calls / summary.tasks).toFixed(1)} per episode`
			: undefined}
	/>
	{#if summary.estimated_cost_avoided !== undefined}
		<MetricCard
			label="Estimated cost avoided"
			value={formatMoney(summary.estimated_cost_avoided)}
			detail={summary.unmitigated_cost !== undefined
				? `Of ${formatMoney(summary.unmitigated_cost)} at risk without action`
				: undefined}
		/>
	{/if}
</div>

<Tabs.Root bind:value={view.tab}>
	<Tabs.List>
		<Tabs.Trigger value="episodes">
			Episodes <span class="text-muted-foreground tabular-nums">{data.episodes.length}</span>
		</Tabs.Trigger>
		<Tabs.Trigger value="families">
			Families <span class="text-muted-foreground tabular-nums">{data.families.length}</span>
		</Tabs.Trigger>
		<Tabs.Trigger value="capabilities">
			Capabilities <span class="text-muted-foreground tabular-nums">{data.capabilities.length}</span>
		</Tabs.Trigger>
	</Tabs.List>

	<Tabs.Content value="episodes" class="flex flex-col gap-3 pt-2">
		<div class="flex flex-wrap items-center gap-2">
			<div class="relative w-full sm:w-72">
				<SearchIcon
					class="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2"
					aria-hidden="true"
				/>
				<Input
					type="search"
					bind:value={view.search}
					placeholder="Search by ID, title, or family"
					aria-label="Search episodes"
					class="pl-8"
				/>
			</div>
			<NativeSelect.Root bind:value={view.family} aria-label="Filter by family">
				<NativeSelect.Option value="">All families</NativeSelect.Option>
				{#each families as family (family)}
					<NativeSelect.Option value={family}>{humanize(family)}</NativeSelect.Option>
				{/each}
			</NativeSelect.Root>
			<NativeSelect.Root bind:value={view.outcome} aria-label="Filter by outcome">
				<NativeSelect.Option value="">All outcomes</NativeSelect.Option>
				{#each Object.entries(OUTCOME_LABELS) as [value, label] (value)}
					<NativeSelect.Option {value}>{label}</NativeSelect.Option>
				{/each}
			</NativeSelect.Root>
			{#if filtering}
				<Button variant="ghost" size="sm" onclick={clearFilters}>Clear filters</Button>
			{/if}
			<p class="text-muted-foreground ml-auto text-sm tabular-nums">
				{visible.length} of {data.episodes.length} episodes
			</p>
		</div>

		<div class="rounded-xl border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<SortableHead
							label="Episode"
							direction={direction('id')}
							onclick={() => sortBy('id')}
							class="pl-4"
						/>
						<Table.Head>Family</Table.Head>
						<Table.Head>Difficulty</Table.Head>
						<SortableHead
							label="Score"
							direction={direction('score')}
							onclick={() => sortBy('score')}
							class="text-right"
						/>
						<Table.Head>Outcome</Table.Head>
						<Table.Head class="text-right">Criteria</Table.Head>
						<SortableHead
							label="Tool calls"
							direction={direction('tool_calls')}
							onclick={() => sortBy('tool_calls')}
							class="text-right"
						/>
						<SortableHead
							label="Minutes"
							direction={direction('elapsed_minutes')}
							onclick={() => sortBy('elapsed_minutes')}
							class="text-right"
						/>
						<Table.Head class="pr-4 text-right">Violations</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each visible as episode (`${episode.id}@${episode.version}`)}
						<Table.Row class="relative">
							<Table.Cell class="max-w-sm pl-4 whitespace-normal">
								<a
									href={resolve('/runs/[run]/[task]', { run: data.listing.slug, task: episode.id })}
									class="font-medium after:absolute after:inset-0 hover:underline"
								>
									{episode.title}
								</a>
								<p class="text-muted-foreground font-mono text-xs">
									{episode.id} · v{episode.version}
								</p>
							</Table.Cell>
							<Table.Cell>{humanize(episode.family)}</Table.Cell>
							<Table.Cell class="capitalize">{episode.difficulty}</Table.Cell>
							<Table.Cell class="text-right"><ScoreBadge score={episode.score} /></Table.Cell>
							<Table.Cell><OutcomeBadge outcome={outcomeOf(episode)} /></Table.Cell>
							<Table.Cell class="text-right tabular-nums">
								{episode.criteria_passed}<span class="text-muted-foreground">/{episode.criteria_total}</span>
							</Table.Cell>
							<Table.Cell
								class={[
									'text-right tabular-nums',
									episode.tool_calls > episode.max_tool_calls && 'text-red-700'
								]}
							>
								{episode.tool_calls}<span class="text-muted-foreground">/{episode.max_tool_calls}</span>
							</Table.Cell>
							<Table.Cell class="text-right tabular-nums">
								{episode.elapsed_minutes}<span class="text-muted-foreground"
									>/{episode.horizon_minutes}</span
								>
							</Table.Cell>
							<Table.Cell
								class={[
									'pr-4 text-right tabular-nums',
									episode.violations > 0 ? 'text-amber-700' : 'text-muted-foreground'
								]}
							>
								{episode.violations}
							</Table.Cell>
						</Table.Row>
					{:else}
						<Table.Row>
							<Table.Cell colspan={9} class="text-muted-foreground py-10 text-center">
								No episodes match these filters.
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	</Tabs.Content>

	<Tabs.Content value="families" class="pt-2">
		<div class="rounded-xl border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head class="pl-4">Family</Table.Head>
						<Table.Head class="text-right">Episodes</Table.Head>
						<Table.Head>Mean score</Table.Head>
						<Table.Head class="text-right">Strict successes</Table.Head>
						<Table.Head class="text-right">Critical failures</Table.Head>
						<Table.Head class="pr-4 text-right">Tool calls</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.families as family (family.name)}
						<Table.Row>
							<Table.Cell class="pl-4">
								<button
									type="button"
									class="font-medium hover:underline"
									title="Show this family's episodes"
									onclick={() => showFamily(family.name)}
								>
									{humanize(family.name)}
								</button>
							</Table.Cell>
							<Table.Cell class="text-right tabular-nums">{family.tasks}</Table.Cell>
							<Table.Cell>
								<div class="flex items-center gap-3">
									<Meter
										value={family.mean_score / 100}
										tone={scoreTone(family.mean_score)}
										label="{humanize(family.name)} mean score"
										class="w-32"
									/>
									<span class="tabular-nums">{formatScore(family.mean_score)}</span>
								</div>
							</Table.Cell>
							<Table.Cell class="text-right tabular-nums">
								{family.strict_successes}<span class="text-muted-foreground">/{family.tasks}</span>
							</Table.Cell>
							<Table.Cell
								class={[
									'text-right tabular-nums',
									family.critical_failures > 0 ? 'text-red-700' : 'text-muted-foreground'
								]}
							>
								{family.critical_failures}
							</Table.Cell>
							<Table.Cell class="pr-4 text-right tabular-nums">{formatCount(family.tool_calls)}</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	</Tabs.Content>

	<Tabs.Content value="capabilities" class="flex flex-col gap-3 pt-2">
		<p class="text-muted-foreground text-sm">
			Attainment is the share of available points an agent earned for each capability, across the
			episodes that test it.
		</p>
		<div class="rounded-xl border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head class="pl-4">Capability</Table.Head>
						<Table.Head class="text-right">Episodes</Table.Head>
						<Table.Head class="text-right">Mean points</Table.Head>
						<Table.Head class="pr-4">Attainment</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each data.capabilities as capability (capability.name)}
						<Table.Row>
							<Table.Cell class="pl-4 font-medium">{humanize(capability.name)}</Table.Cell>
							<Table.Cell class="text-right tabular-nums">{capability.tasks}</Table.Cell>
							<Table.Cell class="text-right tabular-nums">
								{capability.mean_score.toFixed(1)}
								<span class="text-muted-foreground">of {capability.mean_max_score.toFixed(1)}</span>
							</Table.Cell>
							<Table.Cell class="pr-4">
								<div class="flex items-center gap-3">
									<Meter
										value={capability.attainment_rate}
										tone={scoreTone(capability.attainment_rate * 100)}
										label="{humanize(capability.name)} attainment"
										class="w-40"
									/>
									<span class="tabular-nums">{formatPercent(capability.attainment_rate)}</span>
								</div>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	</Tabs.Content>
</Tabs.Root>
