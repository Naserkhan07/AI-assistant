"""Headless CLI — `python -m nixi.cli` works on any OS without a display."""
from __future__ import annotations

import argparse
import sys


def cmd_chat(args) -> int:
    from nixi.config import get_config
    from nixi.core.llm_client import NixiLLMClient
    config = get_config()
    llm = NixiLLMClient(config=config)
    print(f"Nixi chat ({config.provider}/{config.model}) — type 'exit' to quit, Ctrl+C to interrupt.\n")
    while True:
        try:
            msg = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not msg or msg.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break
        print("Nixi: ", end="", flush=True)
        for chunk in llm.chat_stream([{"role": "user", "content": msg}]):
            print(chunk, end="", flush=True)
        print("\n")
    return 0


def cmd_doctor(args) -> int:
    from nixi.config import get_config
    from nixi.core.llm_client import NixiLLMClient
    from nixi.logging_utils import Diagnostics
    config = get_config()
    llm = None
    try:
        llm = NixiLLMClient(config=config)
    except Exception:
        pass
    print(Diagnostics(config, llm).format_text())
    return 0


def cmd_config(args) -> int:
    from nixi.config import get_config
    import json
    config = get_config()
    if args.show:
        print(json.dumps(config.as_dict(mask_secrets=not args.show_secrets), indent=2))
    if args.set:
        from nixi.config import save_env
        for item in args.set:
            if "=" not in item:
                print(f"skip invalid: {item} (use KEY=VALUE)")
                continue
            k, v = item.split("=", 1)
            k, v = k.strip(), v.strip()
            save_env({k: v})
            print(f"set {k}={v}")
        print("Run `nixi config --show` to verify.")
    return 0


def cmd_knowledge(args) -> int:
    from nixi.config import get_config
    from nixi.agent.knowledge import KnowledgeStore
    config = get_config()
    store = KnowledgeStore(config=config)
    if args.index:
        result = store.index_dirs()
        print(f"Indexed {result['files']} files, {result['chunks']} chunks")
        print(store.stats())
    elif args.search:
        results = store.search(args.search, limit=args.limit or 5)
        if not results:
            print("No results.")
        for r in results:
            print(f"[{r['path']}]\n{r['text'][:400]}\n")
    elif args.stats:
        import json
        print(json.dumps(store.stats(), indent=2))
    else:
        import json
        print(json.dumps(store.stats(), indent=2))
    return 0


def cmd_serve(args) -> int:
    from nixi.config import get_config
    from nixi.server import NixiServer
    from nixi.core.llm_client import NixiLLMClient
    config = get_config()
    if not config.api_enabled:
        print("API is disabled. Enable with: nixi config --set NIXI_API_ENABLED=true")
        print("Starting anyway for this session...")
        config.api_enabled = True
    server = NixiServer(config=config)
    server.llm = NixiLLMClient(config=config)
    server.chat_handler = lambda msg: server.llm.chat([{"role": "user", "content": msg}])
    print(server.start())
    print("Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nixi", description="Nixi AI Assistant")
    sub = p.add_subparsers(dest="command")

    c = sub.add_parser("chat", help="Interactive chat (headless)")
    c.set_defaults(func=cmd_chat)

    d = sub.add_parser("doctor", help="Run diagnostics")
    d.set_defaults(func=cmd_doctor)

    cfg = sub.add_parser("config", help="View or set config")
    cfg.add_argument("--show", action="store_true", help="Show current config")
    cfg.add_argument("--show-secrets", action="store_true", help="Include secrets")
    cfg.add_argument("--set", nargs="+", metavar="KEY=VALUE", help="Set config values")
    cfg.set_defaults(func=cmd_config)

    k = sub.add_parser("knowledge", help="Knowledge base")
    k.add_argument("--index", action="store_true", help="Index configured knowledge dirs")
    k.add_argument("--search", type=str, default=None, help="Search query")
    k.add_argument("--stats", action="store_true", help="Show stats")
    k.add_argument("--limit", type=int, default=5)
    k.set_defaults(func=cmd_knowledge)

    s = sub.add_parser("serve", help="Start local HTTP API")
    s.set_defaults(func=cmd_serve)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
