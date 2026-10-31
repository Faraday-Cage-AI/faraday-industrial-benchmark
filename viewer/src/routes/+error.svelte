<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '#lib/components/ui/button/index.js';
</script>

<svelte:head>
	<title>{page.status} · Faraday viewer</title>
</svelte:head>

<div class="mx-auto flex max-w-lg flex-col items-center gap-3 py-16 text-center">
	<p class="text-muted-foreground font-mono text-sm">{page.status}</p>
	<h1 class="text-2xl font-semibold tracking-tight text-balance">{page.error?.message}</h1>
	<div class="flex gap-2 pt-2">
		<Button href={resolve('/')} variant="outline">Runs</Button>
		<Button href={resolve('/examples')} variant="outline">Examples</Button>
	</div>
</div>
