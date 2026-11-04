<script lang="ts">
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import ZapIcon from '@lucide/svelte/icons/zap';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import * as Collapsible from '#lib/components/ui/collapsible/index.js';
	import { humanize } from '#lib/format.js';
	import { describePayload } from '#lib/payload.js';
	import type { EventStatus } from '#lib/timeline.js';
	import type { ScheduledEvent, ToolCall } from '#lib/types.js';
	import JsonBlock from './json-block.svelte';
	import KeyValueList from './key-value-list.svelte';

	let {
		event,
		status,
		scheduledBy
	}: { event: ScheduledEvent; status?: EventStatus; scheduledBy?: ToolCall } = $props();

	const STATUS: Record<EventStatus, { label: string; class: string; title: string }> = {
		fired: {
			label: 'Fired',
			class: 'border-emerald-600/20 bg-emerald-50 text-emerald-700',
			title: 'The event fired during the call above it.'
		},
		not_reached: {
			label: 'Not reached',
			class: 'bg-background text-muted-foreground',
			title: 'The run ended before this event fired.'
		}
	};

	const view = $derived(describePayload(event.payload));
</script>

<article class="rounded-lg border border-amber-300/70 bg-amber-50/60 p-3">
	<header class="flex flex-wrap items-center gap-x-2 gap-y-1">
		<ZapIcon class="size-4 text-amber-600" aria-hidden="true" />
		<h3 class="text-sm font-medium">{humanize(event.kind)}</h3>
		<code class="text-muted-foreground font-mono text-xs">{event.id}</code>
		{#if view.sender}
			<span class="text-muted-foreground text-xs">from {view.sender}</span>
		{/if}
		{#if status}
			<Badge variant="outline" class="ml-auto {STATUS[status].class}" title={STATUS[status].title}>
				{STATUS[status].label}
			</Badge>
		{/if}
	</header>
	{#if scheduledBy}
		<p class="text-muted-foreground mt-1 text-xs">
			Scheduled by call #{scheduledBy.index + 1}, <span class="font-mono">{scheduledBy.tool}</span>
		</p>
	{/if}

	{#if view.prose.length > 0}
		<div class="mt-2 flex flex-col gap-1 text-sm">
			{#each view.prose as field (field.key)}
				{#if field.key === 'subject'}
					<p class="font-medium">{field.value}</p>
				{:else if field.key === 'body'}
					<p class="whitespace-pre-line">{field.value}</p>
				{:else}
					<p class="whitespace-pre-line">
						<span class="text-muted-foreground font-mono text-xs">{field.key}</span>
						{field.value}
					</p>
				{/if}
			{/each}
		</div>
	{/if}

	{#if view.fields.length > 0}
		<KeyValueList fields={view.fields} class="mt-2" />
	{/if}

	{#each view.groups as group (group.key)}
		<div class="mt-2 flex flex-col gap-1">
			<p class="text-muted-foreground font-mono text-xs">{group.key}</p>
			<KeyValueList fields={group.fields} class="border-l border-amber-300/70 pl-3" />
		</div>
	{/each}

	{#each view.nested as item (item.key)}
		<Collapsible.Root class="mt-2">
			<Collapsible.Trigger
				class="group text-muted-foreground hover:text-foreground inline-flex items-center gap-1 font-mono text-xs"
			>
				<ChevronRightIcon
					class="size-3.5 transition-transform group-data-[state=open]:rotate-90"
					aria-hidden="true"
				/>
				{item.key}
			</Collapsible.Trigger>
			<Collapsible.Content>
				<JsonBlock value={item.value} class="bg-background mt-1 max-h-80" />
			</Collapsible.Content>
		</Collapsible.Root>
	{/each}
</article>
