<script lang="ts">
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import ChevronsDownUpIcon from '@lucide/svelte/icons/chevrons-down-up';
	import ChevronsUpDownIcon from '@lucide/svelte/icons/chevrons-up-down';
	import { SvelteSet } from 'svelte/reactivity';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Collapsible from '#lib/components/ui/collapsible/index.js';
	import { toFields } from '#lib/payload.js';
	import type { EventStatus } from '#lib/timeline.js';
	import type { ScheduledEvent, ToolCall } from '#lib/types.js';
	import EventCard from './event-card.svelte';
	import JsonBlock from './json-block.svelte';
	import KeyValueList from './key-value-list.svelte';

	type Entry =
		| { type: 'call'; call: ToolCall }
		| { type: 'event'; event: ScheduledEvent; status?: EventStatus; scheduledBy?: ToolCall };

	let { entries }: { entries: Entry[] } = $props();

	const openResults = new SvelteSet<number>();
	const calls = $derived(entries.flatMap((entry) => (entry.type === 'call' ? [entry.call] : [])));

	function entryKey(entry: Entry): string {
		return entry.type === 'call' ? `call-${entry.call.index}` : `event-${entry.event.id}`;
	}

	function resultKeys(result: Record<string, unknown>): string {
		return Object.keys(result)
			.filter((key) => key !== 'ok' && key !== 'clock_minute')
			.join(', ');
	}

	function expandAll() {
		for (const call of calls) openResults.add(call.index);
	}
</script>

{#if calls.length > 0}
	<div class="flex items-center justify-end gap-1">
		<Button variant="ghost" size="sm" onclick={expandAll}>
			<ChevronsUpDownIcon aria-hidden="true" />
			Expand results
		</Button>
		<Button
			variant="ghost"
			size="sm"
			onclick={() => openResults.clear()}
			disabled={openResults.size === 0}
		>
			<ChevronsDownUpIcon aria-hidden="true" />
			Collapse all
		</Button>
	</div>
{/if}

<ol class="flex flex-col gap-2">
	{#each entries as entry (entryKey(entry))}
		<li class="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-3">
			<span
				class={[
					'pt-3 text-right font-mono text-xs whitespace-nowrap tabular-nums',
					entry.type === 'event' ? 'text-amber-700' : 'text-muted-foreground'
				]}
			>
				{entry.type === 'call' ? entry.call.minute : entry.event.at_minute} min
			</span>
			{#if entry.type === 'call'}
				{@render callCard(entry.call)}
			{:else}
				<EventCard event={entry.event} status={entry.status} scheduledBy={entry.scheduledBy} />
			{/if}
		</li>
	{/each}
</ol>

{#snippet callCard(call: ToolCall)}
	{@const failed = call.result.ok === false}
	{@const args = toFields(call.arguments ?? {})}
	<div class={['bg-card rounded-lg border p-3', failed && 'border-red-300']}>
		<div class="flex flex-wrap items-center gap-x-2 gap-y-1">
			<span class="text-muted-foreground font-mono text-xs tabular-nums">#{call.index + 1}</span>
			<span class="font-mono text-sm font-medium">{call.tool}</span>
			{#if failed}
				<Badge variant="destructive">Failed</Badge>
				{#if typeof call.result.error === 'string'}
					<span class="font-mono text-xs text-red-700">{call.result.error}</span>
				{/if}
			{/if}
		</div>
		{#if args.length > 0}
			<KeyValueList fields={args} class="mt-2" />
		{/if}
		<Collapsible.Root
			bind:open={
				() => openResults.has(call.index),
				(open) => {
					if (open) openResults.add(call.index);
					else openResults.delete(call.index);
				}
			}
			class="mt-2"
		>
			<Collapsible.Trigger
				class="group text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs font-medium"
			>
				<ChevronRightIcon
					class="size-3.5 transition-transform group-data-[state=open]:rotate-90"
					aria-hidden="true"
				/>
				Result
				<span class="font-normal">{resultKeys(call.result)}</span>
			</Collapsible.Trigger>
			<Collapsible.Content>
				<JsonBlock value={call.result} class="mt-2 max-h-96" />
			</Collapsible.Content>
		</Collapsible.Root>
	</div>
{/snippet}
