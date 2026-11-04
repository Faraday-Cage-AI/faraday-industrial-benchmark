<script lang="ts">
	import { resolve } from '$app/paths';
	import Notice from '#lib/components/notice.svelte';
	import PageHeader from '#lib/components/page-header.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import * as Table from '#lib/components/ui/table/index.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const episodes = $derived(data.sets.reduce((sum, set) => sum + set.tasks, 0));
</script>

<PageHeader
	title="Examples"
	description="Benchmark episodes from every task set under data/. Opening an episode generates its scheduled events with the benchmark's scenario code."
>
	{#snippet meta()}
		<span class="text-muted-foreground text-sm">
			{data.sets.length} task sets · {episodes} episodes
		</span>
	{/snippet}
</PageHeader>

{#if data.sets.length === 0}
	<Notice title="No task sets found">
		<p>The viewer looks for <code class="font-mono">data/*/tasks.json</code> files.</p>
	</Notice>
{:else}
	<div class="rounded-xl border">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head class="pl-4">Task set</Table.Head>
					<Table.Head class="text-right">Episodes</Table.Head>
					<Table.Head class="text-right">Families</Table.Head>
					<Table.Head>Versions</Table.Head>
					<Table.Head class="pr-4">Difficulty</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each data.sets as set (set.name)}
					<Table.Row class="relative">
						<Table.Cell class="pl-4">
							<a
								href={resolve('/examples/[set]', { set: set.name })}
								class="font-medium after:absolute after:inset-0 hover:underline"
							>
								{set.name}
							</a>
							<p class="text-muted-foreground font-mono text-xs">{set.path}</p>
						</Table.Cell>
						<Table.Cell class="text-right tabular-nums">{set.tasks}</Table.Cell>
						<Table.Cell class="text-right tabular-nums">{set.families.length}</Table.Cell>
						<Table.Cell class="whitespace-normal">
							<div class="flex flex-wrap gap-1">
								{#each set.versions as version (version)}
									<Badge variant="outline" class="font-mono">{version}</Badge>
								{/each}
							</div>
						</Table.Cell>
						<Table.Cell class="pr-4 capitalize">{set.difficulties.join(', ')}</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
{/if}
