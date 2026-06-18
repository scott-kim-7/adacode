<script lang="ts">
	import { getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { WEBUI_NAME, showSidebar, user, mobile } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';
	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';

	const i18n = getContext('i18n');
	let gateReady = false;
	let redirecting = false;

	$: if ($user === undefined) {
		gateReady = false;
	} else if ($user === null || $user.role !== 'admin') {
		if (!redirecting) {
			redirecting = true;
			goto('/');
		}
	} else {
		gateReady = true;
	}
</script>

<svelte:head>
	<title>{$i18n.t('Email Archive')} • {$WEBUI_NAME}</title>
</svelte:head>

{#if gateReady}
	<div
		class="flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-var(--sidebar-width))]'
			: ''} max-w-full"
	>
		<nav class="px-2 pt-1.5 backdrop-blur-xl w-full drag-region">
			<div class="flex items-center">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center">
						<Tooltip
							content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							interactive={true}
						>
							<button
								class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
								on:click={() => showSidebar.set(!$showSidebar)}
							>
								<div class="self-center p-1.5">
									<Sidebar />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div class="ml-2 py-0.5 self-center flex items-center justify-between w-full">
					<div class="flex items-center gap-3">
						<a class="text-sm underline" href="/">{$i18n.t('Back to chat')}</a>
						<span class="text-sm font-medium">{$i18n.t('Email Archive')}</span>
					</div>

					<div class="self-center flex items-center gap-1">
						{#if $user !== undefined && $user !== null}
							<UserMenu className="max-w-[240px]" role={$user?.role} help={true}>
								<button
									class="select-none flex rounded-xl p-1.5 w-full hover:bg-gray-50 dark:hover:bg-gray-850 transition"
									aria-label="User Menu"
								>
									<div class="self-center">
										<img
											src={`${WEBUI_API_BASE_URL}/users/${$user?.id}/profile/image`}
											class="size-6 object-cover rounded-full"
											alt="User profile"
											draggable="false"
										/>
									</div>
								</button>
							</UserMenu>
						{/if}
					</div>
				</div>
			</div>
		</nav>

		<div class="flex-1 max-h-full overflow-hidden">
			<slot />
		</div>
	</div>
{:else}
	<div class="flex items-center justify-center h-screen text-sm text-gray-500">{$i18n.t('Loading...')}</div>
{/if}
