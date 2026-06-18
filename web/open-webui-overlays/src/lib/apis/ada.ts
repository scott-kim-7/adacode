import { WEBUI_API_BASE_URL } from '$lib/constants';

/** Browser → Open WebUI admin proxy → Agent (no local API key in browser). */
export function adaAgentBase(): string {
	return `${WEBUI_API_BASE_URL}/ada/agent`;
}

function adaHeaders(): Record<string, string> {
	return {
		'Content-Type': 'application/json'
	};
}

export async function adaFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
	const normalized = path.startsWith('/') ? path.slice(1) : path;
	const resp = await fetch(`${adaAgentBase()}/${normalized}`, {
		...init,
		credentials: 'include',
		headers: {
			...adaHeaders(),
			...(init?.headers ?? {})
		}
	});
	if (!resp.ok) {
		const detail = await resp.text().catch(() => '');
		try {
			const parsed = JSON.parse(detail) as { detail?: unknown };
			if (typeof parsed.detail === 'string' && parsed.detail) {
				throw new Error(parsed.detail);
			}
		} catch (err) {
			if (err instanceof Error && !(err instanceof SyntaxError)) {
				throw err;
			}
		}
		throw new Error(detail || `Ada API ${resp.status}`);
	}
	if (resp.status === 204) {
		return undefined as T;
	}
	return resp.json() as Promise<T>;
}

export type EmailSettings = {
	inbox_poll_interval_sec?: number;
	attachment_max_bytes?: number | null;
	email_service_enabled?: boolean;
	email_graph_batch_size?: number;
	summary_skip_rules?: SummarySkipRule[];
};

export type SummarySkipMatch =
	| 'sender_contains'
	| 'sender_domain'
	| 'subject_contains'
	| 'header_present'
	| 'from_noreply';

export type SummarySkipCondition = {
	match: SummarySkipMatch;
	pattern?: string;
	header?: string;
};

export type SummarySkipRuleLogic = 'all' | 'any';

export type SummarySkipRule = {
	id: string;
	name: string;
	enabled: boolean;
	logic: SummarySkipRuleLogic;
	conditions: SummarySkipCondition[];
};

/** @deprecated legacy single-match rules from older settings */
export type LegacySummarySkipRule = SummarySkipRule & {
	match?: SummarySkipMatch;
};

export function normalizeSummarySkipRule(
	rule: LegacySummarySkipRule
): SummarySkipRule {
	if (rule.conditions?.length) {
		return {
			id: rule.id,
			name: rule.name,
			enabled: rule.enabled,
			logic: rule.logic ?? 'any',
			conditions: rule.conditions.map((c) => ({ ...c }))
		};
	}
	if (rule.match) {
		const condition: SummarySkipCondition = { match: rule.match };
		if (rule.pattern) condition.pattern = rule.pattern;
		if (rule.header) condition.header = rule.header;
		return {
			id: rule.id,
			name: rule.name,
			enabled: rule.enabled,
			logic: 'any',
			conditions: [condition]
		};
	}
	return {
		id: rule.id,
		name: rule.name,
		enabled: rule.enabled,
		logic: 'any',
		conditions: [{ match: 'sender_contains', pattern: '' }]
	};
}

export type EmailAccount = {
	id: string;
	email_address?: string;
	status?: string;
	last_error?: string | null;
};

export type HeartbeatSettings = {
	interval_sec?: number;
	enabled?: boolean;
	tasks?: Record<string, boolean>;
	last_run_at?: string | null;
	next_run_at?: string | null;
};

export type InboxItem = {
	id: number;
	message_id?: string;
	thread_id?: string;
	subject?: string;
	from_address?: string;
	received_at?: string;
	summary_text?: string;
	summary_status?: string;
};

export async function getEmailSettings(): Promise<EmailSettings> {
	return adaFetch('/ops/email/settings');
}

export async function putEmailSettings(payload: EmailSettings): Promise<EmailSettings> {
	return adaFetch('/ops/email/settings', {
		method: 'PUT',
		body: JSON.stringify(payload)
	});
}

export async function listAccounts(): Promise<{ data: EmailAccount[] }> {
	return adaFetch('/ops/email/accounts');
}

export async function testAccount(accountId: string): Promise<Record<string, unknown>> {
	return adaFetch(`/ops/email/accounts/${encodeURIComponent(accountId)}/test`, { method: 'POST' });
}

export async function deleteAccount(accountId: string): Promise<Record<string, unknown>> {
	return adaFetch(`/ops/email/accounts/${encodeURIComponent(accountId)}`, { method: 'DELETE' });
}

export type OAuthReadiness = {
	ready: boolean;
	vault_file: boolean;
	vault_unlocked: boolean;
	gmail_client: boolean;
	gmail_client_status?: 'ok' | 'missing' | 'invalid';
	steps: string[];
};

export async function getOAuthReadiness(): Promise<OAuthReadiness> {
	return adaFetch('/ops/email/oauth-readiness');
}

export async function putOAuthClient(payload: {
	client_id: string;
	client_secret: string;
}): Promise<{ saved: boolean; ready: boolean; gmail_client_status?: string }> {
	return adaFetch('/ops/email/oauth-client', {
		method: 'PUT',
		body: JSON.stringify(payload)
	});
}

export async function startGmailOAuth(): Promise<{
	authorization_url: string;
	account_id: string;
}> {
	return adaFetch('/oauth/gmail/start');
}

export async function getHeartbeatSettings(): Promise<HeartbeatSettings> {
	return adaFetch('/ops/heartbeat/settings');
}

export async function putHeartbeatSettings(payload: {
	tasks: Record<string, boolean>;
	interval_sec?: number;
}): Promise<HeartbeatSettings> {
	return adaFetch('/ops/heartbeat/settings', {
		method: 'PUT',
		body: JSON.stringify(payload)
	});
}

export async function heartbeatTick(): Promise<Record<string, unknown>> {
	return adaFetch('/ops/heartbeat/tick', { method: 'POST' });
}

export async function pollInbox(sinceId: number): Promise<{
	data: InboxItem[];
	next_since_id: number;
}> {
	return adaFetch(`/email/inbox?visible=1&since_id=${sinceId}`);
}

export async function markInboxRead(inboxId: number): Promise<void> {
	await adaFetch(`/email/inbox/${inboxId}/read`, { method: 'POST' });
}

export async function markAllInboxRead(): Promise<{ updated: number }> {
	return adaFetch('/email/inbox/read-all', { method: 'POST' });
}

export type EmailMessageListItem = {
	message_id: string;
	thread_id?: string;
	account_id?: string;
	subject?: string;
	from_address?: string;
	received_at?: string;
	inbox_id?: number | null;
	summary_text?: string | null;
	summary_status?: string;
	read_at?: string | null;
	attachment_count?: number;
	account_email?: string;
};

export type EmailAttachment = {
	id: number;
	filename: string;
	mime_type: string;
	size_bytes: number;
};

export type EmailMessageDetail = EmailMessageListItem & {
	body_text?: string;
	to_addresses?: string;
	headers_json?: string;
	eml_path?: string | null;
	attachments?: EmailAttachment[];
};

export async function searchEmails(params: Record<string, string | number | boolean | undefined>): Promise<{
	data: EmailMessageListItem[];
	total: number;
	limit: number;
	offset: number;
}> {
	const q = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v === undefined || v === null || v === '') continue;
		q.set(k, String(v));
	}
	return adaFetch(`/email/messages?${q.toString()}`);
}

export async function getEmailMessage(messageId: string): Promise<EmailMessageDetail> {
	return adaFetch(`/email/messages/${encodeURIComponent(messageId)}`);
}

export async function markInboxReadBulk(payload: {
	inbox_ids?: number[];
	filter?: Record<string, unknown>;
}): Promise<{ updated: number }> {
	return adaFetch('/email/inbox/read-bulk', {
		method: 'POST',
		body: JSON.stringify(payload)
	});
}

export function emailRawUrl(messageId: string): string {
	return `${adaAgentBase()}/email/messages/${encodeURIComponent(messageId)}/raw`;
}

export function emailAttachmentUrl(attachmentId: number): string {
	return `${adaAgentBase()}/email/attachments/${attachmentId}`;
}
