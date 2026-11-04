<script lang="ts">
	import './layout.css';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import FactoryIcon from '@lucide/svelte/icons/factory';
	import favicon from '#lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const links = $derived([
		{
			label: 'Runs',
			href: resolve('/'),
			active: page.route.id === '/' || !!page.route.id?.startsWith('/runs')
		},
		{
			label: 'Examples',
			href: resolve('/examples'),
			active: !!page.route.id?.startsWith('/examples')
		}
	]);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="min-h-svh">
	<header class="bg-background/95 sticky top-0 z-20 border-b backdrop-blur">
		<div class="mx-auto flex h-14 max-w-7xl items-center gap-6 px-6">
			<a href={resolve('/')} class="flex items-center gap-2 text-sm font-semibold">
				<span
					class="bg-primary text-primary-foreground flex size-7 items-center justify-center rounded-md"
				>
					<FactoryIcon class="size-4" aria-hidden="true" />
				</span>
				Faraday benchmark viewer
			</a>
			<nav aria-label="Main" class="flex items-center gap-1">
				{#each links as link (link.label)}
					<a
						href={link.href}
						aria-current={link.active ? 'page' : undefined}
						class={[
							'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
							link.active ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'
						]}
					>
						{link.label}
					</a>
				{/each}
			</nav>
		</div>
	</header>
	<main class="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8">
		{@render children()}
	</main>
</div>
