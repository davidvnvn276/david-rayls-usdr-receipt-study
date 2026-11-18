#!/usr/bin/env python3
"""Offline audit of the fixed November 18 follow-up captures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_wallet import ROOT, USDR, T, addr, describe_route, need, octets, token_legs, net

EVIDENCE=ROOT/"evidence/followup"
RPC="https://mainnet-rpc.rayls.com/"
OTHER_RPC="https://explorer.rayls.com/api/v2/transactions?filter=validated"
BALANCE_OF="0x70a08231"
EXPECTED_PROOF_LIMIT="distance to target block exceeds maximum proof window"
MAIN=14723934
SWAP=14687910
NATIVE=14676417
HERO="0xe37f7c80ced04c4f243c0fd04a5510d663cb88b5"
SWAP_TX="0x578c41d7ad11dd2befb48f87e5df881e2827d2f4dc4a879196b1b82083cf6a31"
NATIVE_TX="0x4d39b36c5c4e12cdc79eccabffa3acd7e50213a3e651c39377d59de5e338ee80"


def load(name, suffix):
    return json.loads((EVIDENCE/f"{name}.{suffix}.json").read_text(encoding="utf-8"))


def batch(name, requests):
    plan=[{"jsonrpc":"2.0","id":i,"method":m,"params":p} for i,(m,p) in enumerate(requests,1)]
    need(load(name,"request")==plan, f"Request plan differs: {name}")
    meta=load(name,"metadata")
    need(meta["url"]==RPC and meta["transport_error"] is None, f"RPC transport not recorded: {name}")
    replies=load(name,"response")
    need(len(replies)==len(plan) and {r["id"] for r in replies}==set(range(1,len(plan)+1)),
         f"Missing or duplicate reply: {name}")
    need(all(r["jsonrpc"]=="2.0" and (("result" in r)!=("error" in r)) for r in replies), f"Bad reply: {name}")
    return sorted(replies,key=lambda r:r["id"])


def qty(s):
    need(isinstance(s,str) and s.startswith("0x"),"Nonquantity RPC field")
    return int(s,16)


def source_filter(a,b):
    return ("eth_getLogs",[{"fromBlock":hex(a),"toBlock":hex(b),"address":USDR,"topics":["0x"+T]}])


def scan():
    cid,h,head=batch("initial",[("eth_chainId",[]),("eth_blockNumber",[]),("eth_getBlockByNumber",["latest",False])])
    need(qty(cid["result"])==72957,"Wrong network")
    h=qty(h["result"])
    # Latest may move between the two calls; use only the fixed eth_blockNumber in filter selection.
    head=head["result"]
    groups=[
      ("recent-transfer-filter",[(h-127,h),(h-999,h-128)]),
      ("older-transfer-filter",[(h-3999,h-1000)]),
      ("next-tranche-filter",[(h-11999,h-4000),(h-19999,h-12000)]),
      ("cross-payer-search",[(h-29999,h-20000),(h-39999,h-30000),(h-49999,h-40000)]),
    ]
    direct={}
    seen=set()
    for group,bounds in groups:
        for response,(start,end) in zip(batch(group,[source_filter(a,b) for a,b in bounds]),bounds):
            for e in response["result"]:
                height=qty(e["blockNumber"])
                key=(height,e["transactionHash"])
                tag=(key,qty(e["logIndex"]))
                need(start<=height<=end and addr(e["address"])==USDR and e["topics"][0]=="0x"+T
                     and not e["removed"] and tag not in seen,"Log outside the captured filters or duplicate")
                seen.add(tag)
                direct.setdefault(key,[]).append(e)
    check,=batch("filter-positive-reference",[source_filter(MAIN,MAIN)])
    _,main_hash=next(k for k in direct if k[0]==MAIN)
    need(sorted(check["result"],key=lambda e:qty(e["logIndex"])) ==
         sorted(direct[MAIN,main_hash],key=lambda e:qty(e["logIndex"])) and len(check["result"])==4,
         "Exact-filter control differs from broader scan")
    choices=sorted((v for v in direct if v[0]>MAIN),reverse=True)
    need(len(choices)==2,"Different follow-up population")
    return ({"from_block":h-49999,"to_block":h,"head_response_height":qty(head["number"]),
             "logs":len(seen),"transactions_with_matching_logs":len(direct),
             "selection":"The two latest observed USDr-log transactions after the original capture. Chosen before reading balances."},
            direct, choices)


def inspect_case(name,h,txid):
    plans=[("eth_getTransactionByHash",[txid]),("eth_getTransactionReceipt",[txid]),
           *[("eth_getBlockByNumber",[hex(i),False]) for i in (h-1,h)]]
    t,r,p,b=(e["result"] for e in batch(f"{name}-receipt",plans))
    blockhash=b["hash"]
    need(qty(b["number"])==h and qty(p["number"])==h-1 and b["parentHash"]==p["hash"],
         f"Wrong parent or inclusion block: {name}")
    need(t["hash"]==r["transactionHash"]==txid and t["blockHash"]==r["blockHash"]==blockhash
         and qty(t["blockNumber"])==qty(r["blockNumber"])==h and b["transactions"]==[txid]
         and qty(t["transactionIndex"])==qty(r["transactionIndex"])==0 and not b.get("withdrawals")
         and qty(r["status"])==1, f"Receipt is not in an isolated successful block: {name}")
    need(qty(r["gasUsed"])==qty(r["cumulativeGasUsed"])==qty(b["gasUsed"]),f"Gas total differs: {name}")
    need(all(e["transactionHash"]==txid and e["blockHash"]==blockhash and qty(e["blockNumber"])==h
             and not e["removed"] for e in r["logs"]), f"Logs not linked to receipt: {name}")
    gas=qty(r["gasUsed"])*qty(r["effectiveGasPrice"])
    logs=[{"address":{"hash":e["address"]}, "topics":e["topics"],"data":e["data"],"index":qty(e["logIndex"])}
          for e in r["logs"]]
    return t,r,p,b,gas,logs,token_legs(logs,USDR)


def pair_requests(payers, height):
    return [q for a in payers for q in
            [("eth_getBalance",[a,hex(height)]),
             ("eth_call",[{"to":USDR,"data":BALANCE_OF+a[2:].rjust(64,"0")},hex(height)])]]


def compare_balance(address,before,after,expected):
    values=[]
    errors=[]
    for label,items in (("parent",before),("inclusion",after)):
        for i,r in enumerate(items):
            err=r.get("error")
            if err is not None:
                need(err["code"]==-32603 and "pruned" in err["message"],"Unexpected archived balance error")
                values.append(None)
                errors.append({"stage":label,"method":("eth_getBalance","eth_call")[i],**err})
            else:
                values.append(qty(r["result"]) if i==0 else int.from_bytes(octets(r["result"],32),"big"))
    b,x,a,y=values
    covered=None not in values
    if covered:
        need((b,a)==(x,y), f"Native and ERC-20 views differ: {address}")
        need(a-b==expected, f"Wallet delta does not match receipts: {address}")
    return {"address":address,"expected_delta_units":expected,
            "native_parent_units":b,"balanceOf_parent_units":x,
            "native_inclusion_units":a,"balanceOf_inclusion_units":y,
            "observed_delta_units":a-b if covered else None,"matches":True if covered else None,
            "errors":errors}


def inspect_balances(name,h,t,b,gas,legs):
    payer=addr(t["from"])
    parties={a for _,s,d,_ in legs for a in (s,d)}
    a_list=[addr(q["params"][0]) for q in load(name+"-parent","request") if q["method"]=="eth_getBalance"]
    need(set(a_list)==parties and len(set(a_list))==len(a_list)
         and addr(b["miner"]) not in parties and payer in parties,"The comparison has missing or extra parties")
    before=batch(name+"-parent",pair_requests(a_list,h-1))
    after=batch(name+"-inclusion",pair_requests(a_list,h))
    return [compare_balance(a,before[i*2:i*2+2],after[i*2:i*2+2],net(legs,a)-(gas if a==payer else 0))
            for i,a in enumerate(a_list)]


def shell(name,h,t,r,p,b,gas,legs):
    return {"case":name,"hash":t["hash"],"height":h,"parent_hash":p["hash"],"block_hash":b["hash"],
            "payer":addr(t["from"]),"block_author":addr(b["miner"]),"unix_seconds":qty(b["timestamp"]),
            "top_level_value_units":qty(t["value"]),"network_fee_units":gas,
            "raw_receipt_logs":len(r["logs"]),"usdr_transfer_logs":len(legs)}


def verify():
    filters,direct,new=scan()
    prior=json.loads((ROOT/"expected/review-summary.json").read_text(encoding="utf-8"))
    roles={r["role"]:r.get("published_address") for r in json.loads(
        (ROOT/"evidence/source-identities.json").read_text(encoding="utf-8"))["sources"]}
    outcomes=[]
    for i,(h,txid) in enumerate(new,1):
        name=f"followup-{i:02}"
        t,r,p,b,gas,logs,legs=inspect_case(name,h,txid)
        route=describe_route({"from":{"hash":t["from"]},"to":{"hash":t["to"]},
                              "raw_input":t["input"],"value":qty(t["value"])},logs,legs,gas,roles)
        need(all(route[k]==prior["hero"][k] for k in ["payer","credit_messaging","endpoint","send_library"]),
             "Follow-up does not use the same sending route and payer")
        usdr_only=[e for e in r["logs"] if e["address"]==USDR and e["topics"][0]=="0x"+T]
        need(usdr_only==direct[h,txid],"Receipt transfer logs differ from the USDr selection query")
        a=inspect_balances(name,h,t,b,gas,legs)
        need(len(a)==4 and all(x["matches"] is True for x in a),"Incomplete follow-up balance observations")
        payer=next(x for x in a if x["address"]==route["payer"])
        # Deliberately test two rival ways of reading the receipt against the saved wallet delta.
        wrong_value_and_gas=qty(t["value"])+gas
        wrong_sum_all_legs=route["transfer_leg_sum_units"]
        need(-payer["observed_delta_units"]==route["net_debit_units"]
             and wrong_value_and_gas-route["net_debit_units"]==route["refund_units"]
             and wrong_sum_all_legs!=route["net_debit_units"],"Wrong interpretation not distinguished")
        outcomes.append({**shell(name,h,t,r,p,b,gas,legs),
                         **{k:route[k] for k in ("refund_units","message_fee_units","net_debit_units",
                                                 "transfer_leg_sum_units","destination_eid","packet_guid",
                                                 "value_minus_floor_13_over_10_fee_units")},
                         "value_plus_gas_units":wrong_value_and_gas,"balances":a})
    altmeta=load("different-payer-selection","metadata")
    need(altmeta["url"]==OTHER_RPC,"Wrong alternative-payer selection source")
    seen=set()
    selected=[]
    for row in load("different-payer-selection","source")["items"]:
        if (row["hash"] not in seen and row["status"]=="ok" and row["value"]=="0" and row["block_number"] is not None
                and addr(row["from"]["hash"])!=HERO):
            seen.add(row["hash"])
            selected.append(row)
            if len(selected)==4:
                break
    need(len(selected)==4,"Different number of alternate-payer selections")
    alternatives=[]
    for i,row in enumerate(selected,1):
        name=f"alternate-{i:02}"
        h,txid=row["block_number"],row["hash"]
        t,r,p,b,gas,logs,legs=inspect_case(name,h,txid)
        payer=addr(t["from"])
        need(payer==addr(row["from"]["hash"])!=HERO and qty(t["value"])==0 and not legs
             and payer!=addr(b["miner"]) and gas>0, "Gas-only contrast does not meet scope")
        reads=batch(name+"-payer",pair_requests([payer],h-1)+pair_requests([payer],h))
        balance=compare_balance(payer,reads[:2],reads[2:],-gas)
        need(balance["matches"] and balance["observed_delta_units"]!=0, "Zero Value versus zero cost not distinguished")
        alternatives.append({**shell(name,h,t,r,p,b,gas,legs),"explorer_method_label":row["method"],
                             "balance":balance})
    unavailable=[]
    for name,h,txid in (("contrast-swap",SWAP,SWAP_TX),("archive-native",NATIVE,NATIVE_TX)):
        t,r,p,b,gas,logs,legs=inspect_case(name,h,txid)
        rows=inspect_balances(name,h,t,b,gas,legs)
        need(all(row["matches"] is None and len(row["errors"])==4 for row in rows),"Unexpected gap coverage")
        unavailable.append({**shell(name,h,t,r,p,b,gas,legs),"balances":rows})
    proof_checks=[]
    for name,b,payer in [("hero",MAIN,HERO),
                         *((e["case"],e["height"],e["payer"]) for e in outcomes),
                         (alternatives[0]["case"],alternatives[0]["height"],alternatives[0]["payer"])]:
        for height,result in zip((b-1,b),batch(name+"-state-proof",
                                   [("eth_getProof",[payer,[],hex(x)]) for x in (b-1,b)])):
            err=result.get("error")
            need(err and err["code"]==-32602 and err["message"]==EXPECTED_PROOF_LIMIT,
                 "Unexpected archived state proof response")
            proof_checks.append({"case":name,"height":height,"address":payer,**err})
    need(len({e["hash"] for e in outcomes+alternatives})==6,"Duplicate follow-up transactions")
    need(len({e["payer"] for e in alternatives})==4,"The alternate-payer sample is not four different senders")
    return {"scope":"RPC observations compared to transaction receipts; no authenticated state root or independent provider.",
            "chain_id":72957,"scan":filters,"separate_recent_routes":outcomes,"zero_value_cases":alternatives,
            "older_contrasts_repeated":unavailable,"unavailable_account_proofs":proof_checks,
            "six_new_cases_complete_native_comparisons":sum(len(e["balances"]) for e in outcomes)+len(alternatives)}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path)
    options=parser.parse_args()
    report=verify()
    if options.out is not None:
        with options.out.open("x",encoding="utf-8",newline="\n") as f:
            f.write(json.dumps(report,indent=2)+"\n")
    print("PASS: two newer routes, eight balance pairs, both rival debit readings rejected.")
    print("PASS: four different callers with zero Value and exact gas-only wallet changes.")
    print("OBSERVED: two older cases retain state gaps; eight historical proof requests returned the proof-window error.")
