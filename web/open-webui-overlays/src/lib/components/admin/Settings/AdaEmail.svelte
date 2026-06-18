<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
import AdaSummarySkipRules from './AdaSummarySkipRules.svelte';
	import { user } from '$lib/stores';
	import {
		deleteAccount,
		getEmailSettings,
		getHeartbeatSettings,
		getOAuthReadiness,
		heartbeatTick,
		listAccounts,
		putEmailSettings,
		putHeartbeatSettings,
		putOAuthClient,
		startGmailOAuth,
		testAccount,
		type EmailAccount,
		type HeartbeatSettings,
	type OAuthReadiness,
	type SummarySkipRule,
	normalizeSummarySkipRule
	} from '$lib/apis/ada';

	const i18n = getContext('i18n');

	let ready = false;
	let refreshing = false;
	let actionBusy = false;
	let statusLine = '';
	let pollIntervalSec = 30;
	let attachmentMaxMb = '';
	let heartbeatIntervalSec = 60;
let emailServiceEnabled = true;
let emailGraphBatchSize = 5;
let summarySkipRules: SummarySkipRule[] = [];
	let accounts: EmailAccount[] = [];
	let heartbeat: HeartbeatSettings = { tasks: {} };
	let oauthReadiness: OAuthReadiness | null = null;
	let oauthClientId = '';
	let oauthClientSecret = '';
	let oauthSetupEl: HTMLDivElement | null = null;

	function focusOAuthSetup() {
		oauthSetupEl?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
	}

	function showSetupHint() {
		if (!oauthReadiness) {
			toast.info($i18n.t('Gmail OAuth setup required'));
			return;
		}
		if (!oauthReadiness.vault_unlocked) {
			toast.warning($i18n.t('Unlock vault first: ./scripts/ada.sh restart'));
			return;
		}
		if (!oauthReadiness.gmail_client) {
			toast.info($i18n.t('Enter Google OAuth client credentials in the form below.'));
			focusOAuthSetup();
			return;
		}
		toast.info(oauthReadiness.steps.join(' '));
	}

	async function saveOAuthClient() {
		if (!oauthClientId.trim() || !oauthClientSecret.trim()) {
			toast.error($i18n.t('Client ID and client secret are required.'));
			return;
		}
		actionBusy = true;
		try {
			const result = await putOAuthClient({
				client_id: oauthClientId.trim(),
				client_secret: oauthClientSecret.trim()
			});
			oauthClientSecret = '';
			statusLine = $i18n.t('OAuth client saved to vault.');
			toast.success($i18n.t('OAuth client saved to vault.'));
			await refresh();
			if (result.ready) {
				toast.success($i18n.t('You can now click Connect Gmail.'));
			}
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		} finally {
			actionBusy = false;
		}
	}

	async function refresh() {
		refreshing = true;
		statusLine = '';
		try {
			const [settings, hb, accts, oauth] = await Promise.all([
				getEmailSettings(),
				getHeartbeatSettings(),
				listAccounts(),
				getOAuthReadiness()
			]);
			pollIntervalSec = settings.inbox_poll_interval_sec ?? 30;
			attachmentMaxMb =
				settings.attachment_max_bytes == null
					? ''
					: String(Math.round(settings.attachment_max_bytes / 1024 / 1024));
			emailServiceEnabled = settings.email_service_enabled ?? true;
			emailGraphBatchSize = settings.email_graph_batch_size ?? 5;
			summarySkipRules = (settings.summary_skip_rules ?? []).map(normalizeSummarySkipRule);
			heartbeat = hb;
			heartbeatIntervalSec = hb.interval_sec ?? 60;
			accounts = accts.data ?? [];
			oauthReadiness = oauth;
			statusLine = $i18n.t('Refreshed');
			toast.success($i18n.t('Refreshed'));
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		} finally {
			ready = true;
			refreshing = false;
		}
	}

	async function saveEmailSettings() {
		const payload: Record<string, unknown> = {
			inbox_poll_interval_sec: Number(pollIntervalSec),
			email_service_enabled: Boolean(emailServiceEnabled),
			email_graph_batch_size: Number(emailGraphBatchSize)
		};
		if (attachmentMaxMb === '') {
			payload.attachment_max_bytes = null;
		} else {
			payload.attachment_max_bytes = Number(attachmentMaxMb) * 1024 * 1024;
		}
		try {
			await putEmailSettings(payload);
			statusLine = $i18n.t('Settings saved successfully!');
			toast.success($i18n.t('Settings saved successfully!'));
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		}
	}

	async function saveHeartbeatTasks() {
		try {
			heartbeat = await putHeartbeatSettings({
				tasks: heartbeat.tasks ?? {},
				interval_sec: Number(heartbeatIntervalSec)
			});
			statusLine = $i18n.t('Settings saved successfully!');
			toast.success($i18n.t('Settings saved successfully!'));
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		}
	}

	async function connectGmail() {
		if (oauthReadiness && !oauthReadiness.ready) {
			showSetupHint();
			return;
		}
		actionBusy = true;
		statusLine = '';
		try {
			const body = await startGmailOAuth();
			const opened = window.open(body.authorization_url, '_blank', 'noopener,noreferrer');
			if (!opened) {
				toast.error($i18n.t('Allow pop-ups for this site, then try Connect Gmail again.'));
				statusLine = body.authorization_url;
			} else {
				toast.success(`${$i18n.t('Connect Gmail')}: ${body.account_id}`);
				statusLine = `${$i18n.t('Connect Gmail')}: ${body.account_id}`;
			}
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		} finally {
			actionBusy = false;
		}
	}

	async function runTest(accountId: string) {
		actionBusy = true;
		try {
			const result = await testAccount(accountId);
			statusLine = `${$i18n.t('Test connection')}: ${result.email_address ?? accountId}`;
			toast.success(statusLine);
			await refresh();
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		} finally {
			actionBusy = false;
		}
	}

	async function disconnectAccount(accountId: string) {
		if (!confirm($i18n.t('Disconnect') + ` ${accountId}?`)) return;
		actionBusy = true;
		try {
			await deleteAccount(accountId);
			statusLine = $i18n.t('Disconnect');
			toast.success($i18n.t('Disconnect'));
			await refresh();
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		} finally {
			actionBusy = false;
		}
	}

	async function runHeartbeatNow() {
		actionBusy = true;
		try {
			await heartbeatTick();
			heartbeat = await getHeartbeatSettings();
			statusLine = $i18n.t('Run heartbeat now');
			toast.success($i18n.t('Run heartbeat now'));
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		} finally {
			actionBusy = false;
		}
	}

	async function saveSummarySkipRules() {
		try {
			await putEmailSettings({
				summary_skip_rules: summarySkipRules
			});
			statusLine = $i18n.t('Settings saved successfully!');
			toast.success($i18n.t('Settings saved successfully!'));
		} catch (err) {
			statusLine = String(err);
			toast.error(String(err));
		}
	}

	onMount(refresh);
</script>

{#if $user?.role === 'admin'}
	<form
		class="relative z-10 flex flex-col h-full justify-between space-y-3 text-sm"
		on:submit|preventDefault={saveEmailSettings}
	>
		<div class="space-y-3 overflow-y-auto scrollbar-hidden flex-1 min-h-0">
			<div>
				<div class="mb-3">
					<div class="text-lg font-medium">{$i18n.t('Ada Email')}</div>
					<div class="mt-2">
						<a
							href="/ada/email"
							class="inline-flex px-3 py-1.5 text-xs border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-850 transition"
						>
							{$i18n.t('Open email archive')}
						</a>
					</div>
				</div>

				<hr class="border-gray-50 dark:border-gray-850 my-2" />

				{#if oauthReadiness && !oauthReadiness.ready}
					<div class="mb-2.5 rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900 p-3 text-xs text-amber-900 dark:text-amber-100">
						<div class="font-medium mb-1">{$i18n.t('Gmail OAuth setup required')}</div>
						{#if oauthReadiness.steps?.length}
							<ul class="list-disc list-inside space-y-1 mb-2">
								{#each oauthReadiness.steps as step}
									<li>{step}</li>
								{/each}
							</ul>
						{/if}
						<ol class="list-decimal list-inside space-y-1">
							{#if !oauthReadiness.vault_file}
								<li><code class="text-[11px]">cd ada && make vault-init</code></li>
							{/if}
							{#if oauthReadiness.gmail_client_status === 'invalid'}
								<li>{$i18n.t('Replace invalid credentials using the form below.')}</li>
							{:else if !oauthReadiness.gmail_client}
								<li>{$i18n.t('Enter Google OAuth client credentials in the form below.')}</li>
							{/if}
							{#if !oauthReadiness.vault_unlocked}
								<li><code class="text-[11px]">./scripts/ada.sh restart</code> — {$i18n.t('enter vault password when prompted')}</li>
							{/if}
						</ol>
					</div>
				{/if}

				<div class="mb-2.5 text-xs text-gray-500">
					{$i18n.t('OAuth prerequisites')}
					<p class="mt-1">{$i18n.t('Ada agent must run on host port 8082. Register redirect URI http://127.0.0.1:8082/oauth/gmail/callback in Google Cloud Console.')}</p>
				</div>

				{#if oauthReadiness?.vault_unlocked && !oauthReadiness.gmail_client}
					<div
						id="ada-oauth-client-setup"
						bind:this={oauthSetupEl}
						class="mb-3 rounded-lg border border-gray-200 dark:border-gray-800 p-3 space-y-2"
					>
						<div class="text-xs font-medium">{$i18n.t('Google OAuth client (vault)')}</div>
						<p class="text-xs text-gray-500">
							{$i18n.t('From Google Cloud Console → APIs & Services → Credentials. Stored encrypted in vault only; not saved in the browser.')}
						</p>
						<div>
							<label class="text-xs text-gray-600" for="ada-oauth-client-id">Client ID</label>
							<input
								id="ada-oauth-client-id"
								class="w-full rounded-lg px-3 py-1.5 text-sm border dark:bg-gray-900 mt-0.5"
								type="text"
								autocomplete="off"
								bind:value={oauthClientId}
								placeholder="....apps.googleusercontent.com"
							/>
						</div>
						<div>
							<label class="text-xs text-gray-600" for="ada-oauth-client-secret">Client secret</label>
							<input
								id="ada-oauth-client-secret"
								class="w-full rounded-lg px-3 py-1.5 text-sm border dark:bg-gray-900 mt-0.5"
								type="password"
								autocomplete="new-password"
								bind:value={oauthClientSecret}
							/>
						</div>
						<button
							type="button"
							class="px-3 py-1.5 text-xs bg-gray-900 text-white dark:bg-white dark:text-black rounded-lg disabled:opacity-50"
							disabled={actionBusy}
							on:click={saveOAuthClient}
						>
							{$i18n.t('Save OAuth client to vault')}
						</button>
					</div>
				{/if}

				{#if statusLine}
					<p class="mb-2 text-xs {statusLine.toLowerCase().includes('error') || statusLine.includes('unreachable') || statusLine.includes('invalid') ? 'text-red-600' : 'text-gray-600'}">
						{statusLine}
					</p>
				{/if}
			</div>

			{#if ready}
				<div>
					<div class="mb-1 text-xs font-medium">{$i18n.t('Gmail accounts')}</div>
					<div class="flex flex-wrap gap-2 mb-2">
						<button
							type="button"
							class="px-3 py-1.5 text-xs rounded-lg transition {oauthReadiness?.ready
								? 'bg-gray-900 hover:bg-gray-850 text-white dark:bg-white dark:text-black'
								: 'border border-amber-300 bg-amber-50 text-amber-950 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100'}"
							disabled={actionBusy}
							on:click={connectGmail}
						>
							{oauthReadiness?.ready ? $i18n.t('Connect Gmail') : $i18n.t('Connect Gmail (setup required)')}
						</button>
						<button
							type="button"
							class="px-3 py-1.5 text-xs border rounded-lg disabled:opacity-50"
							disabled={refreshing || actionBusy}
							on:click={refresh}
						>
							{refreshing ? $i18n.t('Refreshing...') : $i18n.t('Refresh')}
						</button>
					</div>
					{#if accounts.length === 0}
						<p class="text-xs text-gray-500">—</p>
					{:else}
						{#each accounts as account}
							<div class="border rounded-lg p-2 mb-2 text-xs">
								<div class="font-medium">{account.email_address ?? account.id}</div>
								<div class="text-gray-500">{account.status ?? 'unknown'}</div>
								{#if account.last_error}
									<div class="text-red-600 mt-1">{account.last_error}</div>
								{/if}
								<div class="flex gap-2 mt-2">
									<button
										type="button"
										class="underline disabled:opacity-50"
										disabled={actionBusy}
										on:click={() => runTest(account.id)}
									>
										{$i18n.t('Test connection')}
									</button>
									<button
										type="button"
										class="underline disabled:opacity-50"
										disabled={actionBusy}
										on:click={() => disconnectAccount(account.id)}
									>
										{$i18n.t('Disconnect')}
									</button>
								</div>
							</div>
						{/each}
					{/if}
				</div>

				<hr class="border-gray-50 dark:border-gray-850 my-2" />

				<div class="mb-2.5">
					<div class="mb-1 text-xs font-medium">{$i18n.t('System')}</div>
					<div class="mb-1 text-xs text-gray-500">{$i18n.t('Heartbeat interval (sec)')}</div>
					<input
						class="w-full rounded-lg px-3 py-1.5 text-sm border dark:bg-gray-900"
						type="number"
						min="5"
						max="3600"
						bind:value={heartbeatIntervalSec}
					/>
				</div>

				<hr class="border-gray-50 dark:border-gray-850 my-2" />

				<div class="mb-2.5">
					<div class="mb-1 text-xs font-medium">{$i18n.t('Inbox UI poll interval (sec)')}</div>
					<p class="text-xs text-gray-500 mb-1">{$i18n.t('How often the chat Inbox panel polls for new summaries.')}</p>
					<input class="w-full rounded-lg px-3 py-1.5 text-sm border dark:bg-gray-900" type="number" min="5" bind:value={pollIntervalSec} />
				</div>
				<div class="mb-2.5">
					<div class="mb-1 text-xs font-medium">Email service enabled</div>
					<Switch state={emailServiceEnabled} on:change={(e) => (emailServiceEnabled = e.detail)} />
				</div>
				<div class="mb-2.5">
					<div class="mb-1 text-xs font-medium">Email graph batch size</div>
					<input class="w-full rounded-lg px-3 py-1.5 text-sm border dark:bg-gray-900" type="number" min="1" max="50" bind:value={emailGraphBatchSize} />
				</div>
				<div class="mb-2.5">
					<div class="mb-1 text-xs font-medium">{$i18n.t('Attachment max (MB)')} ({$i18n.t('empty = unlimited')})</div>
					<input class="w-full rounded-lg px-3 py-1.5 text-sm border dark:bg-gray-900" type="number" min="1" bind:value={attachmentMaxMb} />
				</div>

				<hr class="border-gray-50 dark:border-gray-850 my-2" />

				<div>
					<div class="mb-1 text-xs font-medium">{$i18n.t('Heartbeat tasks')}</div>
					<div class="text-xs text-gray-500 mb-2">
						{$i18n.t('Last run')}: {heartbeat.last_run_at ?? '—'}
					</div>
					<div class="text-xs text-gray-500 mb-2">
						{$i18n.t('Next run')}: {heartbeat.next_run_at ?? '—'}
					</div>
					{#each Object.entries(heartbeat.tasks ?? {}) as [taskId, enabled]}
						<div class="flex items-center justify-between py-1">
							<div class="text-xs">{taskId}</div>
							<Switch
								state={enabled}
								on:change={(e) => {
									if (!heartbeat.tasks) heartbeat.tasks = {};
									heartbeat.tasks[taskId] = e.detail;
									heartbeat.tasks = { ...heartbeat.tasks };
								}}
							/>
						</div>
					{/each}
					<div class="flex gap-2 mt-2">
						<button
							type="button"
							class="px-3 py-1.5 text-xs border rounded-lg disabled:opacity-50"
							disabled={actionBusy}
							on:click={saveHeartbeatTasks}
						>
							{$i18n.t('Save')}
						</button>
						<button
							type="button"
							class="px-3 py-1.5 text-xs border rounded-lg disabled:opacity-50"
							disabled={actionBusy}
							on:click={runHeartbeatNow}
						>
							{$i18n.t('Run heartbeat now')}
						</button>
					</div>
				</div>
				<hr class="border-gray-50 dark:border-gray-850 my-2" />
				<AdaSummarySkipRules bind:rules={summarySkipRules} disabled={actionBusy} on:save={saveSummarySkipRules} />
			{:else}
				<div class="flex justify-center py-8">
					<Spinner />
				</div>
			{/if}
		</div>

		<div class="flex justify-end text-sm font-medium">
			<button
				class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full disabled:opacity-50"
				type="submit"
				disabled={actionBusy}
			>
				{$i18n.t('Save')}
			</button>
		</div>
	</form>
{:else}
	<div class="text-sm text-gray-500 py-4">{$i18n.t('Access')}</div>
{/if}
