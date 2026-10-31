<script lang="ts">
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import type { Snippet } from 'svelte';

	let {
		title,
		description,
		crumbs = [],
		meta,
		actions
	}: {
		title: string;
		description?: string;
		crumbs?: { label: string; href: string }[];
		meta?: Snippet;
		actions?: Snippet;
	} = $props();
</script>

<svelte:head>
	<title>{title} · Faraday viewer</title>
</svelte:head>

<header class="flex flex-col gap-3">
	{#if crumbs.length > 0}
		<nav aria-label="Breadcrumb">
			<ol class="text-muted-foreground flex flex-wrap items-center gap-1 text-sm">
				{#each crumbs as crumb (crumb.href)}
					<li class="flex items-center gap-1">
						<a href={crumb.href} class="hover:text-foreground transition-colors">{crumb.label}</a>
						<ChevronRightIcon class="size-3.5" aria-hidden="true" />
					</li>
				{/each}
			</ol>
		</nav>
	{/if}
	<div class="flex flex-wrap items-start justify-between gap-4">
		<div class="flex min-w-0 flex-col gap-2">
			<h1 class="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
			{#if description}
				<p class="text-muted-foreground max-w-3xl text-sm">{description}</p>
			{/if}
			{#if meta}
				<div class="flex flex-wrap items-center gap-1.5">{@render meta()}</div>
			{/if}
		</div>
		{#if actions}
			<div class="flex shrink-0 items-center gap-2">{@render actions()}</div>
		{/if}
	</div>
</header>
