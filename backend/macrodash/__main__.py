"""
Command line:

  python -m macrodash run [--demo] [--skip-ingest]   fetch, compute, snapshot
  python -m macrodash serve [--port 8000]           start the API
  python -m macrodash scheduler [--now]             daily 05:30 UK refresh loop
  python -m macrodash sources [ID ...]              probe each instrument's sources
  python -m macrodash export [--out DIR]            write history CSVs + latest snapshot JSON
  python -m macrodash import [--dir DIR]            load exported history CSVs into the database
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import DATA_DIR
from .logging_setup import configure


def main(argv: list[str] | None = None) -> int:
    configure()
    p = argparse.ArgumentParser(prog="macrodash")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--demo", action="store_true", help="use the labelled synthetic dataset")
    r.add_argument("--skip-ingest", action="store_true", help="recompute from stored history only")
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sc = sub.add_parser("scheduler")
    sc.add_argument("--now", action="store_true")
    so = sub.add_parser("sources")
    so.add_argument("ids", nargs="*")
    ex = sub.add_parser("export")
    ex.add_argument("--out", default=str(DATA_DIR / "export"))
    im = sub.add_parser("import")
    im.add_argument("--dir", default=str(DATA_DIR / "export"))
    args = p.parse_args(argv)

    if args.cmd == "run":
        from .pipeline import run
        payload = run(demo=True if args.demo else None, skip_ingest=args.skip_ingest)
        print(json.dumps({"as_of": payload["meta"]["as_of"], "mode": payload["meta"]["mode"],
                          "regime": payload["regime"]["headline"], "failed": list(payload["meta"]["failed_sources"])}))
        return 0
    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("macrodash.api.app:app", host=args.host, port=args.port)
        return 0
    if args.cmd == "scheduler":
        from .scheduler import main as sched
        sched(run_now=args.now)
        return 0
    if args.cmd == "sources":
        from .clients import SourceRouter
        from .instruments import registry
        router = SourceRouter()
        ok = True
        for inst in registry().values():
            if args.ids and inst.id not in args.ids:
                continue
            for src in inst.sources:
                if src.provider == "derived":
                    continue
                try:
                    s = router._call(src.provider, src.code, inst.kind)
                    print(f"OK    {inst.id:12} {src.provider}:{src.code:40} {len(s):6d} rows, last {s.index[-1].date()} = {s.iloc[-1]:.4f}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    ok = False
                    print(f"FAIL  {inst.id:12} {src.provider}:{src.code:40} {str(exc)[:160]}", flush=True)
        if router.rdp is not None:
            router.rdp.release()
        return 0 if ok else 1
    if args.cmd == "export":
        from .exporter import export
        export(Path(args.out))
        return 0
    if args.cmd == "import":
        from .exporter import import_history
        n = import_history(Path(args.dir))
        print(f"imported {n} rows")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
