#!/usr/bin/env python3
"""Reproduce the reviewed evidence without any network access."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_wallet import ROOT, need


def check_manifest():
    manifest=ROOT/"SHA256SUMS"
    names=set()
    with manifest.open(encoding="utf-8") as lines:
        for line in lines:
            digest,name=line.rstrip("\n").split("  ",1)
            path=ROOT/name
            need(path.resolve().is_relative_to(ROOT) and path.is_file() and not path.is_symlink(),
                 f"Unsafe or missing manifest path: {name}")
            need(name not in names, f"Duplicate manifest path: {name}")
            names.add(name)
            need(hashlib.sha256(path.read_bytes()).hexdigest()==digest,
                 f"Wrong SHA-256 digest: {name}")
    tracked={p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()
             and not set(p.relative_to(ROOT).parts)&{".git","runs","__pycache__"}
             and p != manifest}
    need(names==tracked, f"Manifest coverage differs. Extra or missing: {sorted(names^tracked)}")
    print(f"PASS: {len(names)} listed files match the reviewed SHA-256 manifest.",flush=True)


def run(*args, cwd=ROOT):
    env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","PYTHONIOENCODING":"utf-8"}
    subprocess.run([sys.executable,*args],cwd=cwd,env=env,check=True)


def verify(out):
    original=ROOT/"original"
    run("verify.py","--out",str(out/"original"),cwd=original)
    run("-m","unittest","discover","-s","tests","-v",cwd=original)
    run("audit_wallet.py","--out",str(out/"reviewed"))
    run("rpc_evidence.py","--from-saved","evidence/rpc","--report",str(out/"reviewed"/"rpc-summary.json"))
    run("-m","unittest","discover","-s","tests","-v")
    for saved in sorted((ROOT/"expected").iterdir()):
        need(saved.read_bytes()==(out/"reviewed"/saved.name).read_bytes(),f"Rebuilt review file differs: {saved.name}")
    data=json.loads((out/"reviewed"/"rpc-summary.json").read_text(encoding="utf-8"))
    need(data["transaction_reads_verified"]==30 and data["receipts_verified"]==29 and data["event_logs_verified"]==214,
         "RPC transaction/receipt/log coverage changed")
    need(data["account_pairs_with_verified_alias"]==4 and data["account_pairs_with_rpc_event_match"]==4
         and data["account_pairs_with_rpc_event_mismatch"]==0 and data["account_block_pairs"]==37,
         "RPC balance coverage changed")
    print("PASS: Five original and six reviewed outputs reproduced byte for byte.")
    print("OBSERVED: Explorer 34/37 paired balances; direct RPC 4/37 available, 4/4 exact.")
    print("OBSERVED: RPC returned 29/30 receipts; 132 state reads were pruned.")
    print("A pass checks saved data and calculations. It does not independently authenticate chain state.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,help="Keep rebuilt results in a new folder below runs/ or outside the package")
    args=parser.parse_args()
    check_manifest()
    if args.out is None:
        with TemporaryDirectory(prefix="rayls-usdr-") as tmp:
            verify(Path(tmp))
    else:
        out=args.out.resolve()
        need(not out.is_relative_to(ROOT) or out.is_relative_to(ROOT/"runs"),"Use a new runs/ subfolder or an external folder")
        out.mkdir(parents=True,exist_ok=False)
        verify(out)
        print(f"Rebuilt files: {out}")
