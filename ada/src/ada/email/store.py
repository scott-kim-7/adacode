from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EmailMessageRecord:
	message_id: str
	thread_id: str
	account_id: str
	subject: str
	body_text: str
	from_address: str
	to_addresses: str
	headers_json: str
	received_at: str


class EmailStore:
	def __init__(self, db_path: Path) -> None:
		self._db_path = db_path
		self._db_path.parent.mkdir(parents=True, exist_ok=True)
		self._init_schema()

	def _connect(self) -> sqlite3.Connection:
		conn = sqlite3.connect(str(self._db_path))
		conn.row_factory = sqlite3.Row
		return conn

	def _init_schema(self) -> None:
		with self._connect() as conn:
			conn.executescript(
				"""
				CREATE TABLE IF NOT EXISTS email_accounts (
					id TEXT PRIMARY KEY,
					email_address TEXT NOT NULL,
					token_meta_json TEXT NOT NULL DEFAULT '{}',
					status TEXT NOT NULL DEFAULT 'active',
					created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
					updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
				);

				CREATE TABLE IF NOT EXISTS email_threads (
					thread_id TEXT PRIMARY KEY,
					subject TEXT NOT NULL,
					participants_json TEXT NOT NULL DEFAULT '[]',
					last_message_at TEXT NOT NULL
				);

				CREATE TABLE IF NOT EXISTS email_messages (
					message_id TEXT PRIMARY KEY,
					thread_id TEXT NOT NULL,
					account_id TEXT NOT NULL,
					from_address TEXT NOT NULL,
					to_addresses TEXT NOT NULL DEFAULT '',
					subject TEXT NOT NULL,
					body_text TEXT NOT NULL,
					headers_json TEXT NOT NULL DEFAULT '{}',
					received_at TEXT NOT NULL,
					created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY(thread_id) REFERENCES email_threads(thread_id),
					FOREIGN KEY(account_id) REFERENCES email_accounts(id)
				);

				CREATE TABLE IF NOT EXISTS email_attachments (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					message_id TEXT NOT NULL,
					filename TEXT NOT NULL,
					mime_type TEXT NOT NULL,
					size_bytes INTEGER NOT NULL DEFAULT 0,
					storage_uri TEXT NOT NULL,
					created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY(message_id) REFERENCES email_messages(message_id)
				);

				CREATE TABLE IF NOT EXISTS email_actions (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					message_id TEXT NOT NULL,
					detected_mention INTEGER NOT NULL DEFAULT 0,
					detected_reply_intent INTEGER NOT NULL DEFAULT 0,
					draft_status TEXT NOT NULL DEFAULT 'not_requested',
					send_status TEXT NOT NULL DEFAULT 'not_sent',
					reason TEXT NOT NULL,
					created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
					updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY(message_id) REFERENCES email_messages(message_id)
				);

				CREATE TABLE IF NOT EXISTS email_audit_logs (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					action_id INTEGER,
					message_id TEXT NOT NULL,
					event_type TEXT NOT NULL,
					detail_json TEXT NOT NULL DEFAULT '{}',
					created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY(action_id) REFERENCES email_actions(id),
					FOREIGN KEY(message_id) REFERENCES email_messages(message_id)
				);

				CREATE INDEX IF NOT EXISTS idx_email_messages_thread ON email_messages(thread_id);
				CREATE INDEX IF NOT EXISTS idx_email_actions_status ON email_actions(send_status, draft_status);
				CREATE UNIQUE INDEX IF NOT EXISTS idx_email_actions_message_id
					ON email_actions(message_id);
				CREATE UNIQUE INDEX IF NOT EXISTS idx_email_attachments_message_filename
					ON email_attachments(message_id, filename);

				CREATE TABLE IF NOT EXISTS email_inbox_items (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					message_id TEXT NOT NULL UNIQUE,
					thread_id TEXT NOT NULL,
					summary_text TEXT,
					summary_status TEXT NOT NULL DEFAULT 'pending',
					delivered_at TEXT,
					read_at TEXT,
					created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY(message_id) REFERENCES email_messages(message_id)
				);

				CREATE TABLE IF NOT EXISTS email_settings (
					id INTEGER PRIMARY KEY CHECK (id = 1),
					value_json TEXT NOT NULL DEFAULT '{}',
					updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
				);

				INSERT OR IGNORE INTO email_settings (id, value_json) VALUES (1, '{}');

				CREATE TABLE IF NOT EXISTS system_settings (
					id INTEGER PRIMARY KEY CHECK (id = 1),
					value_json TEXT NOT NULL DEFAULT '{}',
					updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
				);

				INSERT OR IGNORE INTO system_settings (id, value_json) VALUES (1, '{"heartbeat_interval_sec": 60}');

				CREATE TABLE IF NOT EXISTS heartbeat_task_settings (
					task_id TEXT PRIMARY KEY,
					enabled INTEGER NOT NULL DEFAULT 1,
					updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
				);

				CREATE TABLE IF NOT EXISTS heartbeat_runs (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					started_at TEXT NOT NULL,
					finished_at TEXT,
					status TEXT NOT NULL,
					error TEXT
				);

				CREATE TABLE IF NOT EXISTS heartbeat_deferred_tasks (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					task_id TEXT NOT NULL,
					payload_json TEXT NOT NULL,
					created_at TEXT NOT NULL,
					processed_at TEXT
				);

				CREATE INDEX IF NOT EXISTS idx_deferred_pending
					ON heartbeat_deferred_tasks(task_id, processed_at);

				CREATE INDEX IF NOT EXISTS idx_inbox_visible
					ON email_inbox_items(summary_status, delivered_at, read_at);
				"""
			)
			self._migrate_columns(conn)

	def _migrate_columns(self, conn: sqlite3.Connection) -> None:
		cols = {row[1] for row in conn.execute("PRAGMA table_info(email_accounts)").fetchall()}
		if "gmail_history_id" not in cols:
			conn.execute("ALTER TABLE email_accounts ADD COLUMN gmail_history_id TEXT")
		if "last_error" not in cols:
			conn.execute("ALTER TABLE email_accounts ADD COLUMN last_error TEXT")
		msg_cols = {row[1] for row in conn.execute("PRAGMA table_info(email_messages)").fetchall()}
		if "eml_path" not in msg_cols:
			conn.execute("ALTER TABLE email_messages ADD COLUMN eml_path TEXT")

	def upsert_account(self, account_id: str, email_address: str) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO email_accounts (id, email_address)
				VALUES (?, ?)
				ON CONFLICT(id) DO UPDATE SET
					email_address = excluded.email_address,
					updated_at = CURRENT_TIMESTAMP
				""",
				(account_id, email_address),
			)

	def upsert_thread(self, thread_id: str, subject: str, participants_json: str, last_message_at: str) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO email_threads (thread_id, subject, participants_json, last_message_at)
				VALUES (?, ?, ?, ?)
				ON CONFLICT(thread_id) DO UPDATE SET
					subject = excluded.subject,
					participants_json = excluded.participants_json,
					last_message_at = excluded.last_message_at
				""",
				(thread_id, subject, participants_json, last_message_at),
			)

	def insert_message(self, record: EmailMessageRecord) -> bool:
		with self._connect() as conn:
			result = conn.execute(
				"""
				INSERT OR IGNORE INTO email_messages (
					message_id, thread_id, account_id, from_address, to_addresses,
					subject, body_text, headers_json, received_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					record.message_id,
					record.thread_id,
					record.account_id,
					record.from_address,
					record.to_addresses,
					record.subject,
					record.body_text,
					record.headers_json,
					record.received_at,
				),
			)
			return result.rowcount > 0

	def insert_attachment(
		self,
		*,
		message_id: str,
		filename: str,
		mime_type: str,
		size_bytes: int,
		storage_uri: str,
	) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				INSERT OR IGNORE INTO email_attachments (message_id, filename, mime_type, size_bytes, storage_uri)
				VALUES (?, ?, ?, ?, ?)
				""",
				(message_id, filename, mime_type, size_bytes, storage_uri),
			)

	def create_action(
		self,
		*,
		message_id: str,
		detected_mention: bool,
		detected_reply_intent: bool,
		reason: str,
		draft_status: str,
		send_status: str,
	) -> int:
		with self._connect() as conn:
			cur = conn.execute(
				"""
				INSERT INTO email_actions (
					message_id, detected_mention, detected_reply_intent, reason, draft_status, send_status
				) VALUES (?, ?, ?, ?, ?, ?)
				""",
				(
					message_id,
					1 if detected_mention else 0,
					1 if detected_reply_intent else 0,
					reason,
					draft_status,
					send_status,
				),
			)
			return int(cur.lastrowid)

	def append_audit_log(self, *, action_id: int | None, message_id: str, event_type: str, detail_json: str) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO email_audit_logs (action_id, message_id, event_type, detail_json)
				VALUES (?, ?, ?, ?)
				""",
				(action_id, message_id, event_type, detail_json),
			)

	def get_message(self, message_id: str) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"""
				SELECT message_id, thread_id, account_id, from_address, to_addresses,
				       subject, body_text, headers_json, received_at, eml_path
				FROM email_messages
				WHERE message_id = ?
				""",
				(message_id,),
			).fetchone()
		return dict(row) if row else None

	def list_pending_actions(self) -> list[dict[str, Any]]:
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT id, message_id, detected_mention, detected_reply_intent, draft_status, send_status, reason, created_at
				FROM email_actions
				WHERE send_status = 'pending_review'
				ORDER BY id DESC
				"""
			).fetchall()
		return [dict(row) for row in rows]

	def update_action_send_status(self, action_id: int, send_status: str, reason: str) -> bool:
		with self._connect() as conn:
			result = conn.execute(
				"""
				UPDATE email_actions
				SET send_status = ?, reason = ?, updated_at = CURRENT_TIMESTAMP
				WHERE id = ?
				""",
				(send_status, reason, action_id),
			)
			return result.rowcount > 0

	def get_action_by_message_id(self, message_id: str) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"""
				SELECT id, message_id, detected_mention, detected_reply_intent, draft_status, send_status, reason
				FROM email_actions
				WHERE message_id = ?
				""",
				(message_id,),
			).fetchone()
		return dict(row) if row else None

	def get_action(self, action_id: int) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"""
				SELECT id, message_id, detected_mention, detected_reply_intent, draft_status, send_status, reason
				FROM email_actions
				WHERE id = ?
				""",
				(action_id,),
			).fetchone()
		return dict(row) if row else None

	# --- accounts / oauth ---

	def list_accounts(self) -> list[dict[str, Any]]:
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT id, email_address, status, gmail_history_id, last_error, created_at, updated_at
				FROM email_accounts ORDER BY id
				"""
			).fetchall()
		return [dict(row) for row in rows]

	def get_account(self, account_id: str) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"""
				SELECT id, email_address, status, gmail_history_id, last_error
				FROM email_accounts WHERE id = ?
				""",
				(account_id,),
			).fetchone()
		return dict(row) if row else None

	def list_active_accounts(self) -> list[dict[str, Any]]:
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT id, email_address, status, gmail_history_id, last_error
				FROM email_accounts WHERE status = 'active'
				ORDER BY id
				"""
			).fetchall()
		return [dict(row) for row in rows]

	def set_account_status(self, account_id: str, status: str, *, last_error: str | None = None) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				UPDATE email_accounts
				SET status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
				WHERE id = ?
				""",
				(status, last_error, account_id),
			)

	def set_account_history_id(self, account_id: str, history_id: str | None) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				UPDATE email_accounts
				SET gmail_history_id = ?, updated_at = CURRENT_TIMESTAMP
				WHERE id = ?
				""",
				(history_id, account_id),
			)

	def delete_account(self, account_id: str) -> bool:
		with self._connect() as conn:
			result = conn.execute("DELETE FROM email_accounts WHERE id = ?", (account_id,))
			return result.rowcount > 0

	def update_message_eml_path(self, message_id: str, eml_path: str) -> None:
		with self._connect() as conn:
			conn.execute(
				"UPDATE email_messages SET eml_path = ? WHERE message_id = ?",
				(eml_path, message_id),
			)

	# --- inbox ---

	def insert_inbox_item(self, *, message_id: str, thread_id: str, summary_status: str = "pending") -> int:
		with self._connect() as conn:
			cur = conn.execute(
				"""
				INSERT OR IGNORE INTO email_inbox_items (message_id, thread_id, summary_status)
				VALUES (?, ?, ?)
				""",
				(message_id, thread_id, summary_status),
			)
			if cur.lastrowid:
				return int(cur.lastrowid)
			row = conn.execute(
				"SELECT id FROM email_inbox_items WHERE message_id = ?",
				(message_id,),
			).fetchone()
			return int(row["id"]) if row else 0

	def update_inbox_summary(
		self,
		message_id: str,
		*,
		summary_text: str,
		summary_status: str,
	) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				UPDATE email_inbox_items
				SET summary_text = ?, summary_status = ?
				WHERE message_id = ?
				""",
				(summary_text, summary_status, message_id),
			)

	def list_inbox_pending_summaries(self, *, limit: int | None = None) -> list[dict[str, Any]]:
		sql = """
				SELECT id, message_id, thread_id, summary_text, summary_status
				FROM email_inbox_items
				WHERE summary_status = 'pending'
				ORDER BY id ASC
		"""
		params: tuple[object, ...] = ()
		if limit is not None:
			sql += " LIMIT ?"
			params = (limit,)
		with self._connect() as conn:
			rows = conn.execute(sql, params).fetchall()
		return [dict(row) for row in rows]

	def list_inbox_for_delivery(self) -> list[dict[str, Any]]:
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT id, message_id, thread_id, summary_text, summary_status
				FROM email_inbox_items
				WHERE summary_status = 'ready' AND delivered_at IS NULL
				ORDER BY id ASC
				"""
			).fetchall()
		return [dict(row) for row in rows]

	def mark_inbox_delivered(self, inbox_id: int, delivered_at: str) -> None:
		with self._connect() as conn:
			conn.execute(
				"UPDATE email_inbox_items SET delivered_at = ? WHERE id = ?",
				(delivered_at, inbox_id),
			)

	def list_inbox_visible(self, *, since_id: int = 0) -> list[dict[str, Any]]:
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT i.id, i.message_id, i.thread_id, i.summary_text, i.summary_status,
				       i.delivered_at, i.read_at, m.subject, m.from_address, m.received_at
				FROM email_inbox_items i
				JOIN email_messages m ON m.message_id = i.message_id
				WHERE i.summary_status = 'ready'
				  AND i.delivered_at IS NOT NULL
				  AND i.read_at IS NULL
				  AND i.id > ?
				ORDER BY i.id ASC
				""",
				(since_id,),
			).fetchall()
		return [dict(row) for row in rows]

	def mark_inbox_read(self, inbox_id: int, read_at: str) -> bool:
		with self._connect() as conn:
			result = conn.execute(
				"UPDATE email_inbox_items SET read_at = ? WHERE id = ?",
				(read_at, inbox_id),
			)
			return result.rowcount > 0

	def mark_all_inbox_delivered_read(self, read_at: str) -> int:
		with self._connect() as conn:
			result = conn.execute(
				"""
				UPDATE email_inbox_items
				SET read_at = ?
				WHERE read_at IS NULL AND delivered_at IS NOT NULL
				""",
				(read_at,),
			)
			return int(result.rowcount)

	@staticmethod
	def _escape_like(value: str) -> str:
		return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

	def _build_search_where(self, filters: dict[str, Any]) -> tuple[str, list[Any]]:
		where: list[str] = []
		params: list[Any] = []
		q = str(filters.get("q") or "").strip()
		if q:
			safe = f"%{self._escape_like(q)}%"
			where.append(
				"""(
					m.subject LIKE ? ESCAPE '\\'
					OR m.from_address LIKE ? ESCAPE '\\'
					OR m.body_text LIKE ? ESCAPE '\\'
					OR COALESCE(i.summary_text,'') LIKE ? ESCAPE '\\'
					OR EXISTS (
						SELECT 1 FROM email_attachments a
						WHERE a.message_id = m.message_id
						  AND a.filename LIKE ? ESCAPE '\\'
					)
				)"""
			)
			params.extend([safe, safe, safe, safe, safe])
		account_id = str(filters.get("account_id") or "").strip()
		if account_id:
			where.append("m.account_id = ?")
			params.append(account_id)
		read_status = str(filters.get("read_status") or "all")
		if read_status == "read":
			where.append("i.read_at IS NOT NULL")
		elif read_status == "unread":
			where.append("(i.id IS NULL OR i.read_at IS NULL)")
		has_attachment = filters.get("has_attachment")
		if has_attachment is True:
			where.append("EXISTS (SELECT 1 FROM email_attachments a2 WHERE a2.message_id = m.message_id)")
		elif has_attachment is False:
			where.append("NOT EXISTS (SELECT 1 FROM email_attachments a2 WHERE a2.message_id = m.message_id)")
		summary_status = str(filters.get("summary_status") or "all")
		if summary_status in {"ready", "pending", "skipped"}:
			where.append("i.summary_status = ?")
			params.append(summary_status)
		date_from = str(filters.get("date_from") or "").strip()
		if date_from:
			where.append("m.received_at >= ?")
			params.append(date_from)
		date_to = str(filters.get("date_to") or "").strip()
		if date_to:
			where.append("m.received_at <= ?")
			params.append(date_to)
		return (" AND ".join(where) if where else "1=1"), params

	def search_messages(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
		sort_map = {
			"received_at": "m.received_at",
			"subject": "m.subject",
			"from_address": "m.from_address",
		}
		sort = sort_map.get(str(filters.get("sort") or "received_at"), "m.received_at")
		order = "ASC" if str(filters.get("order") or "desc").lower() == "asc" else "DESC"
		limit = max(1, min(100, int(filters.get("limit") or 50)))
		offset = max(0, int(filters.get("offset") or 0))
		where_sql, params = self._build_search_where(filters)
		with self._connect() as conn:
			rows = conn.execute(
				f"""
				SELECT m.message_id, m.thread_id, m.account_id, m.subject, m.from_address,
				       m.received_at, i.id AS inbox_id, i.summary_text, i.summary_status, i.read_at,
				       (SELECT COUNT(*) FROM email_attachments a WHERE a.message_id = m.message_id) AS attachment_count,
				       acc.email_address AS account_email
				FROM email_messages m
				LEFT JOIN email_inbox_items i ON i.message_id = m.message_id
				LEFT JOIN email_accounts acc ON acc.id = m.account_id
				WHERE {where_sql}
				ORDER BY {sort} {order}
				LIMIT ? OFFSET ?
				""",
				(*params, limit, offset),
			).fetchall()
		return [dict(row) for row in rows]

	def count_messages(self, filters: dict[str, Any]) -> int:
		where_sql, params = self._build_search_where(filters)
		with self._connect() as conn:
			row = conn.execute(
				f"""
				SELECT COUNT(*) AS n
				FROM email_messages m
				LEFT JOIN email_inbox_items i ON i.message_id = m.message_id
				WHERE {where_sql}
				""",
				params,
			).fetchone()
		return int(row["n"]) if row else 0

	def get_message_detail(self, message_id: str) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"""
				SELECT m.message_id, m.thread_id, m.account_id, m.subject, m.body_text, m.from_address,
				       m.to_addresses, m.headers_json, m.received_at, m.eml_path,
				       i.id AS inbox_id, i.summary_text, i.summary_status, i.read_at,
				       acc.email_address AS account_email
				FROM email_messages m
				LEFT JOIN email_inbox_items i ON i.message_id = m.message_id
				LEFT JOIN email_accounts acc ON acc.id = m.account_id
				WHERE m.message_id = ?
				""",
				(message_id,),
			).fetchone()
		if not row:
			return None
		item = dict(row)
		item["attachments"] = [
			{
				"id": int(a["id"]),
				"filename": a["filename"],
				"mime_type": a["mime_type"],
				"size_bytes": int(a["size_bytes"]),
			}
			for a in self.list_attachments(message_id)
		]
		return item

	def mark_inbox_read_bulk(
		self,
		*,
		inbox_ids: list[int] | None,
		filters: dict[str, Any] | None,
		read_at: str,
	) -> int:
		if (inbox_ids is None and filters is None) or (inbox_ids is not None and filters is not None):
			raise ValueError("Provide either inbox_ids or filters")
		with self._connect() as conn:
			if inbox_ids is not None:
				clean = [int(v) for v in inbox_ids if int(v) > 0]
				if not clean:
					raise ValueError("inbox_ids must not be empty")
				if len(clean) > 500:
					raise ValueError("too_many_ids")
				placeholders = ",".join("?" for _ in clean)
				res = conn.execute(
					f"UPDATE email_inbox_items SET read_at = ? WHERE id IN ({placeholders}) AND read_at IS NULL",
					(read_at, *clean),
				)
				return int(res.rowcount)
			assert filters is not None
			query_filters = dict(filters)
			query_filters["read_status"] = "unread"
			query_filters["limit"] = 501
			query_filters["offset"] = 0
			rows = self.search_messages(query_filters)
			ids = [int(r["inbox_id"]) for r in rows if r.get("inbox_id") is not None]
			if len(ids) > 500:
				raise ValueError("too_many_matches")
			if not ids:
				return 0
			placeholders = ",".join("?" for _ in ids)
			res = conn.execute(
				f"UPDATE email_inbox_items SET read_at = ? WHERE id IN ({placeholders}) AND read_at IS NULL",
				(read_at, *ids),
			)
			return int(res.rowcount)

	# --- email settings ---

	def get_email_settings(self) -> dict[str, Any]:
		with self._connect() as conn:
			row = conn.execute("SELECT value_json FROM email_settings WHERE id = 1").fetchone()
		if not row:
			return {}
		import json

		try:
			return json.loads(str(row["value_json"] or "{}"))
		except json.JSONDecodeError:
			return {}

	def set_email_settings(self, value: dict[str, Any]) -> None:
		import json

		with self._connect() as conn:
			conn.execute(
				"""
				UPDATE email_settings
				SET value_json = ?, updated_at = CURRENT_TIMESTAMP
				WHERE id = 1
				""",
				(json.dumps(value, ensure_ascii=True),),
			)

	# --- system settings ---

	DEFAULT_SYSTEM_SETTINGS: dict[str, Any] = {"heartbeat_interval_sec": 60}

	def get_system_settings(self) -> dict[str, Any]:
		with self._connect() as conn:
			row = conn.execute("SELECT value_json FROM system_settings WHERE id = 1").fetchone()
		if not row:
			return dict(self.DEFAULT_SYSTEM_SETTINGS)
		import json

		try:
			parsed = json.loads(str(row["value_json"] or "{}"))
		except json.JSONDecodeError:
			parsed = {}
		merged = dict(self.DEFAULT_SYSTEM_SETTINGS)
		merged.update(parsed if isinstance(parsed, dict) else {})
		return merged

	def set_system_settings(self, value: dict[str, Any]) -> None:
		import json

		current = self.get_system_settings()
		current.update(value)
		with self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO system_settings (id, value_json, updated_at)
				VALUES (1, ?, CURRENT_TIMESTAMP)
				ON CONFLICT(id) DO UPDATE SET
					value_json = excluded.value_json,
					updated_at = CURRENT_TIMESTAMP
				""",
				(json.dumps(current, ensure_ascii=True),),
			)

	# --- heartbeat ---

	DEFAULT_TASKS: tuple[str, ...] = (
		"email_graph_run",
		"gmail_sync",
		"gmail_backfill",
		"gmail_reply_review",
		"email_summary_to_chat",
		"gmail_token_refresh",
	)

	def ensure_default_tasks(self) -> None:
		with self._connect() as conn:
			for task_id in self.DEFAULT_TASKS:
				conn.execute(
					"""
					INSERT OR IGNORE INTO heartbeat_task_settings (task_id, enabled, updated_at)
					VALUES (?, 1, CURRENT_TIMESTAMP)
					""",
					(task_id,),
				)

	def get_task_enabled(self, task_id: str) -> bool:
		with self._connect() as conn:
			row = conn.execute(
				"SELECT enabled FROM heartbeat_task_settings WHERE task_id = ?",
				(task_id,),
			).fetchone()
		return bool(row and row["enabled"])

	def set_task_enabled(self, task_id: str, enabled: bool) -> None:
		with self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO heartbeat_task_settings (task_id, enabled, updated_at)
				VALUES (?, ?, CURRENT_TIMESTAMP)
				ON CONFLICT(task_id) DO UPDATE SET
					enabled = excluded.enabled,
					updated_at = CURRENT_TIMESTAMP
				""",
				(task_id, 1 if enabled else 0),
			)

	def list_task_settings(self) -> dict[str, bool]:
		self.ensure_default_tasks()
		with self._connect() as conn:
			rows = conn.execute(
				"SELECT task_id, enabled FROM heartbeat_task_settings ORDER BY task_id"
			).fetchall()
		return {str(row["task_id"]): bool(row["enabled"]) for row in rows}

	def record_heartbeat_run(self, *, started_at: str, finished_at: str, status: str, error: str | None) -> int:
		with self._connect() as conn:
			cur = conn.execute(
				"""
				INSERT INTO heartbeat_runs (started_at, finished_at, status, error)
				VALUES (?, ?, ?, ?)
				""",
				(started_at, finished_at, status, error),
			)
			return int(cur.lastrowid)

	def get_last_heartbeat_run(self) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"SELECT started_at, finished_at, status, error FROM heartbeat_runs ORDER BY id DESC LIMIT 1"
			).fetchone()
		return dict(row) if row else None

	def enqueue_deferred_task(self, task_id: str, payload_json: str, created_at: str) -> int:
		with self._connect() as conn:
			cur = conn.execute(
				"""
				INSERT INTO heartbeat_deferred_tasks (task_id, payload_json, created_at)
				VALUES (?, ?, ?)
				""",
				(task_id, payload_json, created_at),
			)
			return int(cur.lastrowid)

	def list_pending_deferred_tasks(self, task_id: str) -> list[dict[str, Any]]:
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT id, task_id, payload_json, created_at
				FROM heartbeat_deferred_tasks
				WHERE task_id = ? AND processed_at IS NULL
				ORDER BY id ASC
				""",
				(task_id,),
			).fetchall()
		return [dict(row) for row in rows]

	def mark_deferred_processed(self, deferred_id: int, processed_at: str) -> None:
		with self._connect() as conn:
			conn.execute(
				"UPDATE heartbeat_deferred_tasks SET processed_at = ? WHERE id = ?",
				(processed_at, deferred_id),
			)

	def get_attachment(self, attachment_id: int) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"""
				SELECT id, message_id, filename, mime_type, size_bytes, storage_uri
				FROM email_attachments WHERE id = ?
				""",
				(attachment_id,),
			).fetchone()
		return dict(row) if row else None

	def list_attachments(self, message_id: str) -> list[dict[str, Any]]:
		with self._connect() as conn:
			rows = conn.execute(
				"""
				SELECT id, message_id, filename, mime_type, size_bytes, storage_uri
				FROM email_attachments WHERE message_id = ?
				""",
				(message_id,),
			).fetchall()
		return [dict(row) for row in rows]
