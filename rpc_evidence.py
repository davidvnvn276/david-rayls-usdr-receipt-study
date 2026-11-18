#!/usr/bin/env python3
"""Collect or audit read-only mainnet evidence. Saved-data verification is offline."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from audit_wallet import ROOT, USDR, addr, amount, assemble, load, need, octets

RPC = "https://mainnet-rpc.rayls.com/"
METHODS = {"eth_chainId", "web3_clientVersion", "eth_getBlockByNumber",
           "eth_getTransactionByHash", "eth_getTransactionReceipt", "eth_getBalance", "eth_call"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def case_data():
    m=load("capture-index.json")
    credit={r["hash"]:r for r in load("mainnet-credit-contract-tx-page1.json")["items"]}
    control={r["hash"]:r for r in load("mainnet-usdr-wrapper-tx-page1.json")["items"]}
    data={}
    for c in [*m["case_records"],*m["control_cases"]]:
        cid,h=c["id"],c["hash"]
        prefix="bridge-01" if cid=="case-01" else cid
        logs=load(prefix+"-logs.json")["items"]
        tx=(credit[h] if c["method"]=="sendCredits" else control[h] if cid.startswith("control")
            else load(cid+"-transaction.json"))
        data[cid]={"hash":h,"height":c["block"],"block_hash":logs[0]["block_hash"].lower(),
                   "logs":logs,"tx":tx,"prefix":prefix}
    return data, m


def plan():
    cases,m=case_data()
    req,keys={},{}

    def add(method, params):
        need(method in METHODS,"Request is not an approved read")
        key=(method,json.dumps(params,sort_keys=True,separators=(",",":")))
        if key not in keys:
            i=len(req)+1
            keys[key]=i
            req[i]={"jsonrpc":"2.0","id":i,"method":method,"params":params}
        return keys[key]

    base={"chain_id":add("eth_chainId",[]),"client_version":add("web3_clientVersion",[])}
    block_set=set(m["balance_selection"])
    tx_map={}
    for cid,c in cases.items():
        b=c["height"]
        tx_map[cid]={"tx":add("eth_getTransactionByHash",[c["hash"]]),
                     "receipt":add("eth_getTransactionReceipt",[c["hash"]]),
                     "block":add("eth_getBlockByNumber",[hex(b),False])}
        if cid in block_set:
            tx_map[cid]["parent"]=add("eth_getBlockByNumber",[hex(b-1),False])
    state_map={}
    for r in m["balance_records"]:
        cid,w=r["case_id"],addr(r["address"])
        b=cases[cid]["height"]
        calldata={"to":USDR,"data":"0x70a08231"+w[2:].rjust(64,"0")}
        state_map[(cid,w)]=[add(method,[a,hex(h)]) for method,a in
                            (("eth_getBalance",w),("eth_call",calldata)) for h in (b-1,b)]
    return list(req.values()),base,tx_map,state_map,cases


def capture(out):
    req,*_=plan()
    out=out.resolve()
    for blocked in ("original","evidence","expected","visuals","assets"):
        need(not out.is_relative_to(ROOT/blocked),"Choose a new folder under runs/ or outside the package")
    out.mkdir(parents=True,exist_ok=False)
    chunks=[req[:2]]+[req[i:i+12] for i in range(2,len(req),12)]

    def send(item):
        n,body=item
        base=out/f"{n:02d}"
        payload=json.dumps(body,separators=(",",":")).encode()
        base.with_suffix(".request.json").write_bytes(payload)
        info={"batch":n,"requests":len(body),"started_utc":datetime.now(timezone.utc).isoformat()}
        try:
            q=Request(RPC,data=payload,headers={"Content-Type":"application/json","Accept":"application/json",
                                              "User-Agent":"Rayls-USDr-read-only-reproduction/1.0"})
            with urlopen(q,timeout=22) as res:
                raw=res.read(10_000_001)
                need(len(raw)<=10_000_000,"RPC reply exceeded maximum batch size")
                base.with_suffix(".response.json").write_bytes(raw)
                info["http_status"]=res.status
        except HTTPError as e:
            info.update(http_status=e.code,transport_error="HTTPError")
        except (URLError,OSError,ValueError) as e:
            info.update(transport_error=type(e).__name__)
        info["finished_utc"]=datetime.now(timezone.utc).isoformat()
        base.with_suffix(".transport.json").write_text(json.dumps(info,indent=2)+"\n",encoding="utf-8")
        return info

    first=send((0,chunks[0]))
    p=out/"00.response.json"
    if not p.is_file() or not any(r.get("id")==1 and r.get("result")=="0x11cfd" for r in read(p)):
        raise ValueError(f"Official RPC chain ID was not confirmed: {first}")
    with ThreadPoolExecutor(max_workers=3) as pool:
        for saved in pool.map(send,enumerate(chunks[1:],1)):
            print(f"Batch {saved['batch']:02}: {saved.get('http_status',saved.get('transport_error'))}",flush=True)
    (out/"capture.json").write_text(json.dumps({"endpoint":RPC,"chain_id_requested":72957,
        "scope":"Direct JSON-RPC query path; provider operation is not established as independent of Explorer.",
        "batches":len(chunks),"requests":len(req)},indent=2)+"\n",encoding="utf-8")
    return audit(out)


def q(n):
    need(isinstance(n,str) and n.startswith("0x"),"Invalid RPC quantity")
    return int(n,16)


def audit(directory):
    plan_rows,base,tx_map,state_map,cases=plan()
    saved_meta=read(directory/"capture.json")
    need(saved_meta["endpoint"]==RPC and saved_meta["requests"]==len(plan_rows),"Different RPC capture scope")
    requests,responses={},{}
    errs=[]
    files=sorted(directory.glob("*.request.json"))
    need(len(files)==saved_meta["batches"], "Incomplete saved request batches")
    for f in files:
        root=f.name.replace(".request.json","")
        batch=read(f)
        own={r["id"] for r in batch}
        need(len(own)==len(batch) and not own&requests.keys(),"Repeated RPC request IDs")
        requests.update({r["id"]:r for r in batch})
        response=directory/(root+".response.json")
        transport=read(directory/(root+".transport.json"))
        if response.is_file():
            need(transport.get("http_status")==200,"Unexpected saved response status")
            rows=read(response)
            if not isinstance(rows,list):
                for i in own:
                    errs.append({"id":i,"method":requests[i]["method"],"classification":"malformed-batch"})
                continue
            need({r["id"] for r in rows}==own and len(rows)==len(own),"RPC response IDs do not match their own batch")
            for r in rows:
                i=r["id"]
                need(r.get("jsonrpc")=="2.0","Wrong JSON-RPC version")
                if r.get("result") is not None and "error" not in r:
                    responses[i]=r["result"]
                else:
                    e=r.get("error") or {}
                    label="state-pruned" if "pruned" in str(e.get("message","")).lower() else "rpc-error" if e else "null-result"
                    errs.append({"id":i,"method":requests[i]["method"],"classification":label,
                                 "error_code":e.get("code"),"message":e.get("message")})
        else:
            need("transport_error" in transport,"Missing reply without transport record")
            for i in own:
                errs.append({"id":i,"method":requests[i]["method"],"classification":"transport-error",
                             "http_status":transport.get("http_status")})
    need(sorted(requests.values(),key=lambda e:e["id"])==plan_rows,"Request plan and saved requests disagree")
    need(q(responses[base["chain_id"]])==72957,"Wrong reported chain ID")
    err_by_id={r["id"]:r for r in errs}
    tx_rows={}
    for cid,ids in tx_map.items():
        c=cases[cid]
        result={k:responses.get(i) for k,i in ids.items()}
        h=c["hash"]
        tx,receipt,b=(result[k] for k in ("tx","receipt","block"))
        if tx is not None:
            t=c["tx"]
            need(tx["hash"].lower()==h and tx["blockHash"].lower()==c["block_hash"] and
                 q(tx["blockNumber"])==c["height"] and addr(tx["from"])==addr(t["from"]["hash"]) and
                 addr(tx["to"])==addr(t["to"]["hash"]) and q(tx["value"])==amount(t["value"]) and
                 octets(tx["input"])==octets(t["raw_input"]),"Direct RPC transaction envelope differs")
        if receipt is not None:
            need(receipt["transactionHash"].lower()==h and receipt["blockHash"].lower()==c["block_hash"] and
                 q(receipt["blockNumber"])==c["height"] and q(receipt["status"])==1 and
                 q(receipt["gasUsed"])==amount(c["tx"]["gas_used"]) and
                 q(receipt["effectiveGasPrice"])*q(receipt["gasUsed"])==amount(c["tx"]["fee"]["value"]),
                 "Direct RPC receipt fee or anchor differs")
            expected=sorted((int(x["index"]),addr(x["address"]["hash"]),
                             tuple(octets(t,32) for t in x["topics"] if t is not None),octets(x["data"])) for x in c["logs"])
            got=[]
            for x in receipt["logs"]:
                need(x["blockHash"].lower()==c["block_hash"] and x["transactionHash"].lower()==h and not x.get("removed",False),
                     "Direct log linkage differs")
                got.append((q(x["logIndex"]),addr(x["address"]),tuple(octets(t,32) for t in x["topics"]),octets(x["data"])))
            need(sorted(got)==expected,"Direct RPC logs and saved Explorer logs differ")
        if b is not None:
            need(q(b["number"])==c["height"] and b["hash"].lower()==c["block_hash"] and
                 h in [x.lower() for x in b["transactions"]],"Direct RPC block does not anchor the transaction")
        parent=result.get("parent")
        one_tx=False
        if b is not None and parent is not None:
            orig=load(c["prefix"]+"-block.json")
            need(q(parent["number"])==c["height"]-1 and b["parentHash"]==parent["hash"] and
                 b["parentHash"].lower()==orig["parent_hash"].lower() and
                 [s.lower() for s in b["transactions"]]==[h] and not b.get("withdrawals") and
                 q(b["gasUsed"])==amount(c["tx"]["gas_used"]) and
                 q(b["baseFeePerGas"])==amount(orig["base_fee_per_gas"]) and
                 addr(b["miner"])==addr(orig["miner"]["hash"]),
                 "Direct RPC parent, author or isolation differs")
            one_tx=True
        tx_rows[cid]={"case_id":cid,"transaction_hash":h,"height":c["height"],"block_hash":c["block_hash"],
                      "transaction_verified":tx is not None,"receipt_verified":receipt is not None,
                      "event_logs_verified":len(c["logs"]) if receipt is not None else 0,
                      "block_verified":b is not None,"isolated_parent_and_block_verified":one_tx,
                      "unavailable_reads":[err_by_id[i] for i in ids.values() if i in err_by_id]}
    indexed={(r["case_id"],r["address"]):r for r in assemble()[2]}
    state=[]
    for (cid,w),ids in state_map.items():
        r=indexed[cid,w]
        row={"case_id":cid,"address":w,"height":r["height"],
             "expected_delta_units":r["log_net_less_gas_units"],"explorer_delta_units":r["explorer_delta_units"]}
        keys=["native_before_units","native_after_units","precompile_before_units","precompile_after_units"]
        for key,i in zip(keys,ids):
            val=responses.get(i)
            row[key]=(q(val) if key.startswith("native") else int.from_bytes(octets(val,32),"big")) if val is not None else None
        row["unavailable_reads"]=[err_by_id[i] for i in ids if i in err_by_id]
        row["base_block_anchored"]=tx_rows[cid]["isolated_parent_and_block_verified"]
        nb,na,pb,pa=(row[k] for k in keys)
        row["alias_pair_verified"]=None if None in (nb,na,pb,pa) else (nb,na)==(pb,pa)
        row["native_delta_units"]=None if None in (nb,na) else na-nb
        row["event_delta_matches_rpc"]=None if row["native_delta_units"] is None or not row["base_block_anchored"] else na-nb==row["expected_delta_units"]
        state.append(row)
    error_counts=dict(sorted(Counter(r["classification"] for r in errs).items()))
    all_txs=list(tx_rows.values())
    return {"scope":"Direct official node replies, not cryptographic state proofs or an independently operated provider.",
            "rpc_endpoint":RPC,"chain_id":72957,"reported_client_version":responses.get(base["client_version"]),
            "requests":len(plan_rows),"results_received":len(responses),"nonresults_by_type":error_counts,
            "transaction_reads_verified":sum(r["transaction_verified"] for r in all_txs),
            "receipts_verified":sum(r["receipt_verified"] for r in all_txs),
            "event_logs_verified":sum(r["event_logs_verified"] for r in all_txs),
            "blocks_verified":sum(r["block_verified"] for r in all_txs),
            "isolated_blocks_verified":sum(r["isolated_parent_and_block_verified"] for r in all_txs),
            "account_block_pairs":len(state),
            "complete_native_balance_pairs":sum(r["native_delta_units"] is not None for r in state),
            "account_pairs_with_verified_alias":sum(r["alias_pair_verified"] is True for r in state),
            "account_pairs_with_rpc_event_match":sum(r["event_delta_matches_rpc"] is True for r in state),
            "account_pairs_with_rpc_event_mismatch":sum(r["event_delta_matches_rpc"] is False for r in state),
            "cases":all_txs,"state_rows":state}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    a=p.add_mutually_exclusive_group(required=True)
    a.add_argument("--collect",type=Path,help="Collect official RPC queries into a new folder")
    a.add_argument("--from-saved",type=Path,help="Read and audit an already saved query folder")
    p.add_argument("--report",type=Path,help="Write comparison JSON (must not exist)")
    o=p.parse_args()
    data=capture(o.collect) if o.collect is not None else audit(o.from_saved)
    if o.report:
        with o.report.open("x",encoding="utf-8",newline="\n") as f:
            f.write(json.dumps(data,indent=2)+"\n")
    print(json.dumps({k:v for k,v in data.items() if k not in ("cases","state_rows")},indent=2))
