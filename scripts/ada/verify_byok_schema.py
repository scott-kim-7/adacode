#!/usr/bin/env python3
import json
import sys


def main() -> int:
	path = sys.argv[1]
	data = json.load(open(path))
	group = data[0] if data else {}
	bad = "configuration" in group and isinstance(group["configuration"], dict) and "models" in group["configuration"]
	good = isinstance(group.get("models"), list) and group.get("vendor") == "customendpoint"
	return 1 if bad or not good else 0


if __name__ == "__main__":
	raise SystemExit(main())
