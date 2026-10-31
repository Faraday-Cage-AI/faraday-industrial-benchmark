<script lang="ts">
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { formatScore, scoreTone, type ScoreTone } from '#lib/format.js';

	let { score }: { score: number } = $props();

	const TONES: Record<ScoreTone, string> = {
		good: 'border-emerald-600/20 bg-emerald-50 text-emerald-700',
		mixed: 'border-amber-600/25 bg-amber-50 text-amber-800',
		poor: 'border-red-600/20 bg-red-50 text-red-700'
	};
</script>

<Badge variant="outline" class="tabular-nums {TONES[scoreTone(score)]}">{formatScore(score)}</Badge>
