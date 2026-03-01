<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { onMount } from 'svelte';
	import { authStore } from '$lib/stores/auth';

	let { children } = $props();

	onMount(() => {
		authStore.init();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Browser Agent Command Center</title>
</svelte:head>

{@render children()}
