<script lang="ts">
	import { snapshot } from '$app/navigation';
	import { resolve } from '$app/paths';
	import SearchIcon from '@lucide/svelte/icons/search';
	import MetricCard from '#lib/components/metric-card.svelte';
	import PageHeader from '#lib/components/page-header.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import * as NativeSelect from '#lib/components/ui/native-select/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import { humanize } from '#lib/format.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	interface Filters {
		search: string;
		family: string;
		difficulty: string;
	}

	const NO_FILTERS: Filters = { search: '', family: '', difficulty: '' };

	let filters = $state<Filters>({ ...NO_FILTERS });

	snapshot({
		capture: () => $state.snapshot(filters),
		restore: (value) => {
			filters = value;
		},
		reset: () => {
			filters = { ...NO_FILTERS };
		}
	});

	const filtering = $derived(
		filters.search !== '' || filters.family !== '' || filters.difficulty !== ''
	);
	const inRuns = $derived(data.episodes.filter((episode) => episode.runs > 0).length);

	const visible = $derived.by(() => {
		const query = filters.search.trim().toLowerCase();
		return data.episodes.filter(
			(episode) =>
				(!query ||
					[episode.id, episode.title, episode.family, ...episode.tags].some((text) =>
						text.toLowerCase().includes(query)
					)) &&
				(!filters.family || episode.family === filters.family) &&
				(!filters.difficulty || episode.difficulty === filters.difficulty)
		);
	});
</script>

<PageHeader
	title={data.summary.name}
	crumbs={[{ label: 'Examples', href: resolve('/examples') }]}
>
	{#snippet meta()}
		<Badge variant="secondary" class="font-mono">{data.summary.path}</Badge>
	{/snippet}
</PageHeader>

<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
	<MetricCard label="Episodes" value={String(data.summary.tasks)} />
	<MetricCard label="Families" value={String(data.summary.families.length)} />
	<MetricCard
		label="Versions"
		value={String(data.summary.versions.length)}
		detail={data.summary.versions.join(', ')}
	/>
	<MetricCard
		label="In saved runs"
		value={String(inRuns)}
		detail="Episodes that at least one saved run includes"
	/>
</div>

<div class="flex flex-wrap items-center gap-2">
	<div class="relative w-full sm:w-72">
		<SearchIcon
			class="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2"
			aria-hidden="true"
		/>
		<Input
			type="search"
			bind:value={filters.search}
			placeholder="Search by ID, title, family, or tag"
			aria-label="Search episodes"
			class="pl-8"
		/>
	</div>
	<NativeSelect.Root bind:value={filters.family} aria-label="Filter by family">
		<NativeSelect.Option value="">All families</NativeSelect.Option>
		{#each data.summary.families as family (family)}
			<NativeSelect.Option value={family}>{humanize(family)}</NativeSelect.Option>
		{/each}
	</NativeSelect.Root>
	<NativeSelect.Root bind:value={filters.difficulty} aria-label="Filter by difficulty">
		<NativeSelect.Option value="">All difficulties</NativeSelect.Option>
		{#each data.summary.difficulties as difficulty (difficulty)}
			<NativeSelect.Option value={difficulty}>{humanize(difficulty)}</NativeSelect.Option>
		{/each}
	</NativeSelect.Root>
	{#if filtering}
		<Button variant="ghost" size="sm" onclick={() => (filters = { ...NO_FILTERS })}>
			Clear filters
		</Button>
	{/if}
	<p class="text-muted-foreground ml-auto text-sm tabular-nums">
		{visible.length} of {data.episodes.length} episodes
	</p>
</div>

<div class="rounded-xl border">
	<Table.Root>
		<Table.Header>
			<Table.Row>
				<Table.Head class="pl-4">Episode</Table.Head>
				<Table.Head>Family</Table.Head>
				<Table.Head>Difficulty</Table.Head>
				<Table.Head class="text-right">Tool budget</Table.Head>
				<Table.Head class="text-right">Horizon</Table.Head>
				<Table.Head class="text-right">Systems</Table.Head>
				<Table.Head class="pr-4 text-right">Runs</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each visible as episode (`${episode.id}@${episode.version}`)}
				<Table.Row class="relative">
					<Table.Cell class="max-w-md pl-4 whitespace-normal">
						<a
							href={resolve('/examples/[set]/[task]', { set: data.summary.name, task: episode.id })}
							class="font-medium after:absolute after:inset-0 hover:underline"
						>
							{episode.title}
						</a>
						<p class="text-muted-foreground font-mono text-xs">{episode.id} · v{episode.version}</p>
					</Table.Cell>
					<Table.Cell>{humanize(episode.family)}</Table.Cell>
					<Table.Cell class="capitalize">{episode.difficulty}</Table.Cell>
					<Table.Cell class="text-right tabular-nums">{episode.max_tool_calls} calls</Table.Cell>
					<Table.Cell class="text-right tabular-nums">{episode.horizon_minutes} min</Table.Cell>
					<Table.Cell class="text-right tabular-nums">{episode.systems}</Table.Cell>
					<Table.Cell
						class={[
							'pr-4 text-right tabular-nums',
							episode.runs === 0 && 'text-muted-foreground'
						]}
					>
						{episode.runs}
					</Table.Cell>
				</Table.Row>
			{:else}
				<Table.Row>
					<Table.Cell colspan={7} class="text-muted-foreground py-10 text-center">
						No episodes match these filters.
					</Table.Cell>
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
