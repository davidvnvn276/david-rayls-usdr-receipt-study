#!/usr/bin/env python3
"""Optional recheck against a Rayls mainnet RPC. Only read methods are allowed."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from verify import CHAIN_ID, USDR, ROOT, EvidenceError, address, build_results, require, token_formatter, verify_manifest

METHODS = {"eth_chainId", "eth_getBlockByNumber", "eth_getTransactionByHash",
           "eth_getTransactionReceipt", "eth_getBalance", "eth_call"}
MAINNET_RPC = "https://mainnet-rpc.rayls.com/"


def quantity(s):
    require(isinstance(s,str) and re.fullmatch(r"0x[0-9a-fA-F]+",s), "Invalid RPC quantity")
    return int(s,16)


class Reader:
    def __init__(self, url, output):
        self.url, self.output, self.seq = url, output, 0
        self.host = urlparse(url).hostname
        require(urlparse(url).scheme == "https" and self.host, "Choose an HTTPS Rayls RPC endpoint")
        self.output.mkdir(parents=True,exist_ok=False)

    def get(self, method, params):
        require(method in METHODS, f"Read-only policy excludes {method}")
        self.seq += 1
        data = {"jsonrpc":"2.0","id":self.seq,"method":method,"params":params}
        payload = json.dumps(data).encode()
        base = self.output / f"{self.seq:03d}-{method}"
        base.with_suffix(".request.json").write_bytes(payload)
        try:
            req = Request(self.url,data=payload,headers={"Content-Type":"application/json","Accept":"application/json",
                                                        "User-Agent":"Rayls-USDr-read-only-reproduction/1.0"})
            with urlopen(req,timeout=20) as res:
                raw = res.read(5_000_001)
        except (HTTPError, URLError, OSError) as err:
            # Do not print the URL or request headers: a chosen provider URL may contain a key.
            raise EvidenceError(f"{method} request failed ({type(err).__name__}"
                                f"{' '+str(err.code) if isinstance(err,HTTPError) else ''})") from None
        require(len(raw)<=5_000_000, "RPC response exceeded the expected size")
        base.with_suffix(".response.json").write_bytes(raw)
        val = json.loads(raw)
        require(val.get("id")==self.seq, "RPC id mismatch")
        if "error" in val:
            raise EvidenceError(f"{method} returned JSON-RPC error code {val['error'].get('code','unknown')}")
        require(val.get("result") is not None, f"{method}: no data at the requested block")
        return val["result"]


def read_case(reader, cid, summary_data):
    _,case_rows,transfer_rows,_,pairs = summary_data
    r = next(x for x in case_rows if x["case_id"] == cid)
    selected = [p for p in pairs if p["case_id"] == cid]
    require(selected, f"No preselected account set for {cid}")
    b = r["block"]
    block = reader.get("eth_getBlockByNumber",[hex(b),False])
    parent = reader.get("eth_getBlockByNumber",[hex(b-1),False])
    require(block["hash"].lower()==r["block_hash"] and block["parentHash"].lower()==parent["hash"].lower()
            and quantity(block["number"])==b and quantity(parent["number"])==b-1,
            "RPC block or parent hash disagrees with the capture")
    require(block["transactions"]==[r["hash"]] and not block.get("withdrawals"),
            "RPC block is not the one-transaction comparison")
    tx = reader.get("eth_getTransactionByHash",[r["hash"]])
    receipt = reader.get("eth_getTransactionReceipt",[r["hash"]])
    require(tx["hash"]==r["hash"]==receipt["transactionHash"]
            and tx["blockHash"].lower()==r["block_hash"]==receipt["blockHash"].lower()
            and quantity(receipt["status"])==1 and quantity(tx["value"])==r["top_level_value_units"]
            and address(tx["from"])==r["caller"] and address(tx["to"])==r["tx_to"],
            "RPC envelope/receipt mismatch")
    require(quantity(receipt["gasUsed"])*quantity(receipt["effectiveGasPrice"])==r["network_fee_units"],
            "RPC network fee differs")
    from verify import TRANSFER, topic_address, bytes32word
    direct = sorted((quantity(l["logIndex"]),topic_address(l["topics"][1]),topic_address(l["topics"][2]),bytes32word(l["data"]))
                    for l in receipt["logs"] if address(l["address"])==USDR and l["topics"][0].lower()==TRANSFER)
    recorded = sorted((x["log_index"],x["from"],x["to"],x["amount_units"])
                      for x in transfer_rows if x["case_id"]==cid)
    require(direct==recorded,"RPC receipt USDr logs disagree with the explorer capture")

    observations = []
    for p in selected:
        acc = p["address"]
        tag_before,tag_after = hex(b-1),hex(b)
        direct_before = quantity(reader.get("eth_getBalance",[acc,tag_before]))
        direct_after = quantity(reader.get("eth_getBalance",[acc,tag_after]))
        calldata = "0x70a08231"+acc[2:].rjust(64,"0")
        read_call = {"to":USDR,"data":calldata}
        token_before = bytes32word(reader.get("eth_call",[read_call,tag_before]))
        token_after = bytes32word(reader.get("eth_call",[read_call,tag_after]))
        delta = direct_after-direct_before
        observations.append({
            "address":acc, "native_before_units":direct_before, "native_after_units":direct_after,
            "balance_of_before_units":token_before, "balance_of_after_units":token_after,
            "native_delta_units":delta, "event_less_gas_units":p["event_less_gas_units"],
            "explorer_before_units":p["before_units"],"explorer_after_units":p["after_units"],
            "alias_matches_at_both_blocks":(direct_before,direct_after)==(token_before,token_after),
            "rpc_delta_matches_event_less_gas":delta==p["event_less_gas_units"],
        })
    return {"case_id":cid,"block":b,"block_hash":block["hash"],
            "matches_capture_receipt_topics_and_gas":True,"account_checks":observations}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rpc",default=MAINNET_RPC,help="Public Rayls mainnet RPC with historical state (HTTPS)")
    p.add_argument("--case",action="append",help="Case ID from README, repeat for multiple cases; default case-01")
    p.add_argument("--out",type=Path,help="New output directory (must not exist)")
    args=p.parse_args()
    try:
        verify_manifest()
        dataset=build_results()
        ids=list(dict.fromkeys(args.case or ["case-01"]))
        valid={x["case_id"] for x in dataset[-1]}
        require(all(i in valid for i in ids), f"Choose only cases with balance pairs: {', '.join(sorted(valid))}")
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out=args.out or ROOT/"rpc_rechecks"/stamp
        rpc=Reader(args.rpc,out)
        require(quantity(rpc.get("eth_chainId",[]))==CHAIN_ID,"RPC is not Rayls mainnet (72957)")
        results=[read_case(rpc,i,dataset) for i in ids]
        report={"rpc_host":rpc.host,"chain_id":CHAIN_ID,"queried_utc":stamp,"cases":results}
        (out/"comparison.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        exact_all=True
        for case in results:
            for a in case["account_checks"]:
                ok=a["alias_matches_at_both_blocks"] and a["rpc_delta_matches_event_less_gas"]
                exact_all &= ok
                print(f"{case['case_id']} {a['address']} {token_formatter(a['native_delta_units'])} USDr "
                      f"alias={a['alias_matches_at_both_blocks']} event_delta={a['rpc_delta_matches_event_less_gas']}")
        print(f"Saved request/response pairs and comparison to {out}")
        return 0 if exact_all else 2
    except (EvidenceError, OSError, KeyError, ValueError, StopIteration) as e:
        print(f"INCOMPLETE: {e}. Keep any saved responses. Unavailable history is not a zero balance.",file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
