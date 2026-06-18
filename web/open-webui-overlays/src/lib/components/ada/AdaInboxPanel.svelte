<script lang="ts">
	import { getContext, onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		emailAttachmentUrl,
		emailRawUrl,
		getEmailMessage,
		getEmailSettings,
		markAllInboxRead,
		markInboxRead,
		pollInbox,
		type EmailMessageDetail,
		type InboxItem
	} from '$lib/apis/ada';

	const i18n = getContext('i18n');

	let pollIntervalSec = 30;
	let items: InboxItem[] = [];
	let sinceId = 0;
	let timer: ReturnType<typeof setInterval> | null = null;
	let agentError = '';
	let expandedId: number | null = null;
	let detailByMessageId: Record<string, EmailMessageDetail> = {};
	let loadingDetailId: number | null = null;
	let markingAll = false;

	async function loadSettings() {
		try {
			const body = await getEmailSettings();
			pollIntervalSec = body.inbox_poll_interval_sec ?? 30;
			agentError = '';
		} catch (err) {
			agentError = String(err);
		}
	}

	async function pollOnce() {
		try {
			const body = await pollInbox(sinceId);
			const incoming = body.data ?? [];
			if (incoming.length) {
				items = [...incoming, ...items].slice(0, 50);
				sinceId = body.next_since_id ?? sinceId;
			}
			agentError = '';
		} catch (err) {
			agentError = String(err);
		}
	}

	function restartTimer() {
		if (timer) clearInterval(timer);
		timer = setInterval(pollOnce, pollIntervalSec * 1000);
	}

	async function markAllRead() {
		markingAll = true;
		try {
			const body = await markAllInboxRead();
			const updated = body.updated ?? 0;
			items = [];
			expandedId = null;
			if (updated > 0) {
				toast.success($i18n.t('Marked {{count}} as read', { count: updated }));
			} else {
				toast.message($i18n.t('No unread summaries'));
			}
		} catch (err) {
			toast.error(String(err));
		} finally {
			markingAll = false;
		}
	}

	async function markRead(id: number) {
		try {
			await markInboxRead(id);
			items = items.filter((item) => item.id !== id);
			if (expandedId === id) expandedId = null;
		} catch (err) {
			toast.error(String(err));
		}
	}

	async function toggleOriginal(item: InboxItem) {
		if (expandedId === item.id) {
			expandedId = null;
			return;
		}
		expandedId = item.id;
		const messageId = item.message_id;
		if (!messageId || detailByMessageId[messageId]) return;
		loadingDetailId = item.id;
		try {
			detailByMessageId[messageId] = await getEmailMessage(messageId);
		} catch (err) {
			toast.error(String(err));
			expandedId = null;
		} finally {
			loadingDetailId = null;
		}
	}

	onMount(async () => {
		await loadSettings();
		await pollOnce();
		restartTimer();
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});

	function formatEmailDate(value: string | undefined): string {
		if (!value) return '';
		const parsed = new Date(value);
		if (Number.isNaN(parsed.getTime())) return value;
		return new Intl.DateTimeFormat(undefined, {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		}).format(parsed);
	}
</script>

<div class="flex flex-col h-full min-h-0 overflow-y-auto scrollbar-hidden p-1">
	<div class="flex items-center justify-between gap-2 mb-2 px-1">
		<h3 class="text-sm font-semibold">{$i18n.t('Ada Inbox')}</h3>
		<button
			type="button"
			class="text-xs underline disabled:opacity-50"
			disabled={markingAll || items.length === 0}
			on:click={markAllRead}
		>
			{markingAll ? $i18n.t('Loading...') : $i18n.t('Mark all as read')}
		</button>
	</div>
	{#if agentError}
		<p class="text-xs text-red-600 px-1">{$i18n.t('Agent unreachable')}: {agentError}</p>
	{:else if items.length === 0}
		<p class="text-xs text-gray-500 px-1">{$i18n.t('No new email summaries')}</p>
	{:else}
		<ul class="space-y-2 px-1">
			{#each items as item}
				<li class="rounded-lg border border-gray-100 dark:border-gray-800 p-2 text-xs">
					<div class="flex items-start justify-between gap-2">
						<div class="font-medium min-w-0">{item.subject ?? '(no subject)'}</div>
						{#if item.received_at}
							<time class="shrink-0 text-gray-400" datetime={item.received_at}>
								{formatEmailDate(item.received_at)}
							</time>
						{/if}
					</div>
					<div class="text-gray-500">{item.from_address}</div>
					{#if item.summary_status === 'pending'}
						<p class="text-gray-400 mt-1">{$i18n.t('Summarizing…')}</p>
					{:else}
						<div class="text-gray-400 mt-1 text-[10px] uppercase tracking-wide">{$i18n.t('Summary')}</div>
						<pre class="whitespace-pre-wrap mt-0.5 text-gray-700 dark:text-gray-300">{item.summary_text}</pre>
					{/if}
					{#if item.message_id}
						<button
							class="mt-2 underline"
							type="button"
							disabled={loadingDetailId === item.id}
							on:click={() => toggleOriginal(item)}
						>
							{expandedId === item.id ? $i18n.t('Hide original') : $i18n.t('View original')}
						</button>
					{/if}
					{#if expandedId === item.id && item.message_id}
						{@const detail = detailByMessageId[item.message_id]}
						<div class="mt-2 rounded border border-gray-100 dark:border-gray-800 p-2 space-y-2">
							<div class="text-[10px] uppercase tracking-wide text-gray-400">{$i18n.t('Original message')}</div>
							{#if loadingDetailId === item.id}
								<p class="text-gray-500">{$i18n.t('Loading message…')}</p>
							{:else if detail}
								<div class="text-gray-500">{detail.from_address}</div>
								<pre class="whitespace-pre-wrap text-gray-700 dark:text-gray-300 max-h-48 overflow-y-auto">{detail.body_text}</pre>
								<div class="flex gap-2 flex-wrap">
									<a class="underline" href={emailRawUrl(detail.message_id)}>{$i18n.t('Download .eml')}</a>
								</div>
								{#if detail.attachments?.length}
									<div class="text-[10px] uppercase tracking-wide text-gray-400">{$i18n.t('Attachments')}</div>
									<ul class="space-y-1">
										{#each detail.attachments as attachment}
											<li class="flex justify-between gap-2">
												<span class="truncate">{attachment.filename}</span>
												<a class="shrink-0 underline" href={emailAttachmentUrl(attachment.id)}>
													{$i18n.t('Download')}
												</a>
											</li>
										{/each}
									</ul>
								{/if}
							{:else}
								<p class="text-gray-500">{$i18n.t('No messages')}</p>
							{/if}
						</div>
					{/if}
					<button class="mt-2 underline block" type="button" on:click={() => markRead(item.id)}>
						{$i18n.t('Mark read')}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>
