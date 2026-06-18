from __future__ import annotations

import argparse
import os
import sys

from ada.registry import get_profile, load_registry
from ada.tri_chat import TriChatSession
from ada.vault import Vault, VaultError, VaultSession, prompt_password, secure_zero
from ada.vault_secrets import ensure_secret_in_vault, read_tty_secret_bytes, store_secret_in_vault


def cmd_profiles(args: argparse.Namespace) -> int:
	reg = load_registry()
	if args.name:
		p = get_profile(reg, args.name)
		print(f"{p.name} ({p.label})")
		print(f"  provider:   {p.provider}")
		print(f"  base_url:   {p.base_url}")
		print(f"  models:     GET {p.base_url.rstrip('/')}/models")
		print(f"  api_key:    {p.api_key or '(vault: ' + str(p.api_key_vault) + ')'}")
		print(f"  notes:      {p.notes}")
	else:
		for name, p in sorted(reg.profiles.items()):
			print(f"  {name}: {p.label} — {p.base_url}")
	return 0


def cmd_vault_init(_args: argparse.Namespace) -> int:
	if Vault().exists():
		print("Vault already exists.", file=sys.stderr)
		return 1
	password = prompt_password("VAULT_INIT")
	password2 = prompt_password("VAULT_INIT_CONFIRM")
	if password != password2:
		print("Passwords do not match.", file=sys.stderr)
		return 1
	Vault().init(password)
	print("Vault initialized.")
	return 0


def cmd_vault_set(args: argparse.Namespace) -> int:
	vault = Vault()
	if not vault.exists():
		print("Vault not found. Run: make vault-init", file=sys.stderr)
		return 1
	if args.auto:
		return _cmd_vault_set_auto(args)
	value = read_tty_secret_bytes(f"Value for {args.key} (stored encrypted in vault only): ")
	try:
		store_secret_in_vault(args.key, value, unlock_action="VAULT_SET")
	except VaultError as exc:
		print(f"Vault error: {exc}", file=sys.stderr)
		return 1
	print(f"Set {args.key}")
	return 0


def _cmd_vault_set_auto(args: argparse.Namespace) -> int:
	try:
		value, created = ensure_secret_in_vault(
			args.key,
			nbytes=args.bytes,
			force=args.force,
			unlock_action="VAULT_SET_AUTO",
		)
	except VaultError as exc:
		print(f"Vault error: {exc}", file=sys.stderr)
		return 1
	if created:
		print(f"Auto-generated and stored: {args.key}")
		if args.show:
			print(value)
		else:
			print("(use --show to display the value once on create)", file=sys.stderr)
	else:
		print(f"{args.key} already exists (unchanged; use --force to regenerate)")
	return 0


def cmd_vault_ensure(args: argparse.Namespace) -> int:
	args.auto = True
	return _cmd_vault_set_auto(args)


def cmd_vault_migrate_local_key(_args: argparse.Namespace) -> int:
	"""One-time: copy ada/.local/ada_local_api_key into vault as ada.local.api_key."""
	from pathlib import Path

	from ada.paths import ada_root
	from ada.vault import VaultSession, secure_zero
	from ada.vault_unlock import LOCAL_API_KEY_VAULT_KEY

	key_file = Path(os.environ.get("ADA_LOCAL_KEY_FILE", ada_root() / ".local" / "ada_local_api_key"))
	vault = Vault()
	if not vault.exists():
		print("Vault not found. Run: make vault-init", file=sys.stderr)
		return 1
	if not key_file.is_file():
		print(f"No legacy key file at {key_file}", file=sys.stderr)
		return 1
	legacy_bytes = bytearray(key_file.read_text().strip().encode("utf-8"))
	if not legacy_bytes:
		print("Legacy key file is empty.", file=sys.stderr)
		return 1
	password = prompt_password("VAULT_MIGRATE_LOCAL_KEY")
	session = VaultSession.unlock_from_password(vault, password)
	if session.get(LOCAL_API_KEY_VAULT_KEY):
		print(f"Vault already has {LOCAL_API_KEY_VAULT_KEY}. Remove it first to overwrite.", file=sys.stderr)
		secure_zero(legacy_bytes)
		return 1
	try:
		session.set(LOCAL_API_KEY_VAULT_KEY, legacy_bytes.decode("utf-8"))
		session.save()
	finally:
		secure_zero(legacy_bytes)
	print(f"Migrated legacy key to vault:{LOCAL_API_KEY_VAULT_KEY}")
	try:
		key_file.unlink()
		print(f"Deleted legacy plaintext file {key_file}")
	except OSError as exc:
		print(f"Warning: could not delete {key_file}: {exc}", file=sys.stderr)
	return 0


def cmd_vault_list(_args: argparse.Namespace) -> int:
	vault = Vault()
	if not vault.exists():
		print("Vault not found.", file=sys.stderr)
		return 1
	password = prompt_password("VAULT_LIST")
	for key in vault.list_keys(password):
		print(f"  {key}")
	return 0


def cmd_ada_agent(args: argparse.Namespace) -> int:
	from ada.agent.graph import run_user_turn
	from ada.agent.llm import load_profile_from_env, make_llm_callable
	from ada.vault_unlock import bootstrap_vault_session

	profile_name = args.profile or None
	if profile_name:
		import os

		os.environ["ADA_AGENT_PROFILE"] = profile_name

	profile = load_profile_from_env()
	vault_session = bootstrap_vault_session()
	llm_callable = make_llm_callable(profile, vault_session=vault_session)
	history = []

	def run_once(user_text: str) -> str:
		nonlocal history
		assistant_text, history = run_user_turn(user_text, history, llm_callable)
		return assistant_text

	try:
		if args.once:
			print(run_once(args.once))
			return 0

		print(f"Ada Agent — profile: {profile.name} ({profile.label})")
		print("Commands: /quit  /history")
		while True:
			try:
				line = input("\nYou> ").strip()
			except (EOFError, KeyboardInterrupt):
				print()
				break
			if not line:
				continue
			if line in ("/quit", "/exit"):
				break
			if line == "/history":
				for idx, msg in enumerate(history, start=1):
					content = getattr(msg, "content", "")
					print(f"  {idx}. {type(msg).__name__}: {content!s}"[:160])
				continue
			print(f"\n[assistant]\n{run_once(line)}\n")
	finally:
		return 0


def cmd_tri_chat(args: argparse.Namespace) -> int:
	from ada.vault_unlock import bootstrap_vault_session

	reg = load_registry()
	vault_session = bootstrap_vault_session()
	session = TriChatSession.from_registry(reg, vault_session=vault_session)

	def print_turn(turn_msgs):
		for m in turn_msgs:
			print(f"\n[{m.speaker}]\n{m.content}\n")

	try:
		if args.once:
			print_turn(session.run_turn(args.once))
			return 0

		print("Tri-Chat MVP — Local (MLX) + External API + You")
		print("Commands: /quit  /history")
		while True:
			try:
				line = input("\nYou> ").strip()
			except (EOFError, KeyboardInterrupt):
				print()
				break
			if not line:
				continue
			if line in ("/quit", "/exit"):
				break
			if line == "/history":
				for m in session.history:
					print(f"  [{m.speaker}] {m.content[:120]}...")
				continue
			print_turn(session.run_turn(line))
	finally:
		session.close()
	return 0


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(prog="ada", description="Ada orchestration CLI")
	sub = parser.add_subparsers(dest="command")

	p_profiles = sub.add_parser("profiles", help="List or show Model Registry profiles")
	p_profiles.add_argument("name", nargs="?", help="Profile name (e.g. chat_profile)")
	p_profiles.set_defaults(func=cmd_profiles)

	p_vault = sub.add_parser("vault", help="Encrypted secrets vault")
	vault_sub = p_vault.add_subparsers(dest="vault_cmd")
	v_init = vault_sub.add_parser("init", help="Create empty vault")
	v_init.set_defaults(func=cmd_vault_init)
	v_set = vault_sub.add_parser("set", help="Set a vault key (interactive or --auto)")
	v_set.add_argument("key", help="e.g. external.openai.api_key")
	v_set.add_argument(
		"--auto",
		action="store_true",
		help="Generate a cryptographically strong secret and store under KEY",
	)
	v_set.add_argument(
		"--force",
		action="store_true",
		help="With --auto: overwrite an existing key",
	)
	v_set.add_argument(
		"--show",
		action="store_true",
		help="With --auto: print the generated value once (create only)",
	)
	v_set.add_argument(
		"--bytes",
		type=int,
		default=32,
		metavar="N",
		help="With --auto: random bytes before encoding (default: 32)",
	)
	v_set.set_defaults(func=cmd_vault_set)
	v_ensure = vault_sub.add_parser(
		"ensure",
		help="Idempotent auto-generate: create KEY only if missing",
	)
	v_ensure.add_argument("key", help="e.g. webhook.shared_secret")
	v_ensure.add_argument("--force", action="store_true", help="Overwrite an existing key")
	v_ensure.add_argument("--show", action="store_true", help="Print generated value once on create")
	v_ensure.add_argument("--bytes", type=int, default=32, metavar="N", help="Random bytes (default: 32)")
	v_ensure.set_defaults(func=cmd_vault_ensure)
	v_list = vault_sub.add_parser("list", help="List vault keys (not values)")
	v_list.set_defaults(func=cmd_vault_list)
	v_migrate = vault_sub.add_parser(
		"migrate-local-key",
		help="Copy legacy ada/.local/ada_local_api_key into vault",
	)
	v_migrate.set_defaults(func=cmd_vault_migrate_local_key)

	p_tri = sub.add_parser("tri-chat", help="Tri-Chat MVP CLI")
	p_tri.add_argument("--once", metavar="MSG", help="Run one user turn and exit")
	p_tri.set_defaults(func=cmd_tri_chat)

	p_agent = sub.add_parser("ada-agent", help="Ada Agent (LangGraph MainGraph CLI)")
	p_agent.add_argument("--once", metavar="MSG", help="Run one user turn and exit")
	p_agent.add_argument("--profile", help="Model registry profile (default: chat_profile)")
	p_agent.set_defaults(func=cmd_ada_agent)

	return parser


def main(argv: list[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)
	if not args.command:
		parser.print_help()
		return 0
	if args.command == "vault" and not getattr(args, "vault_cmd", None):
		parser.parse_args(["vault", "-h"])
		return 0
	try:
		return args.func(args)
	except VaultError as exc:
		print(f"Vault error: {exc}", file=sys.stderr)
		return 1
	except Exception as exc:
		print(f"Error: {exc}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	raise SystemExit(main())
