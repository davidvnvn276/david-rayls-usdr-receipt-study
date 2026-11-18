#!/usr/bin/env python3
"""Separate, offline accounting audit of the preserved Explorer responses."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
CAPTURES = ROOT / "original/evidence/explorer"
USDR = "0x0000000000000000000000000000000000000400"
RLS = "0x07e17e17e17e17e17e17e17e17e17e17e17e17ea"
USDCE = "0x9001dbe4d68d36ab87923a2a9dfb0c745fd25001"
ZERO = "0x" + "00"*20
SCALE = 10**18
T = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
A = "8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
EXEC = "61ed099e74a97a1d7f8bb0952a88ca8b7b8ebd00c126ea04671f92a81213318a"
DVN = "07ea52d82345d6e838192107d8fd7123d9c2ec8e916cd0aad13fd2b60db24644"
PACKET = "1ab700d4ced0c005b164c0f789fd09fcbb0156d4c2041b8a3bfbcd961cd1567f"
CREDITS = "ce105e156370093e6600169f7c01277f740d45fbcf95435227ce6f43ad0c3abd"
MINT = "0f6798a560793a54c3bcfe86a93cde1e73087d944c0ea20544137d4121396885"
MINTED = "9d228d69b5fdb8d273a2336f8fb8612d039631024ea9bf09c424a9503aa078f0"
SWAP_ESCROW = "48644a6a821b386b0f8b970c2b71b8e0bb4b89677a1ebe83b2f16fffb96ccf84"
SWAP_COMPOSER = "a199edc830ae0ec22c21ba6e49d71cad061148d27fb04a74caef8aa316567bd1"
DELIVERED = "0036c98efcf9e6641dfbc9051f66f405253e8e0c2ab4a24dccda15595b7378c8"


def need(p, detail):
    if not p:
        raise ValueError(detail)


def load(name):
    need(Path(name).name == name, f"Unexpected capture path: {name}")
    return json.loads((CAPTURES / name).read_text(encoding="utf-8"))


def octets(value, width=None):
    need(isinstance(value, str) and re.fullmatch(r"0x(?:[a-fA-F0-9]{2})*", value),
         "Expected bytes in hexadecimal")
    b = bytes.fromhex(value[2:])
    need(width is None or len(b) == width, "Unexpected byte length")
    return b


def number(data):
    return int.from_bytes(data, "big")


def addr(s):
    return "0x" + octets(s, 20).hex()


def addr_word(b):
    need(len(b) == 32 and not any(b[:12]), "Invalid ABI address word")
    return "0x" + b[-20:].hex()


def split_words(b):
    need(len(b) % 32 == 0, "ABI data is not word aligned")
    return [b[i:i+32] for i in range(0, len(b), 32)]


def amount(s):
    return int(s)


def emit(log):
    return addr(log["address"]["hash"])


def is_event(log, topic):
    return octets(log["topics"][0], 32).hex() == topic


def only(logs, topic):
    picked = [x for x in logs if is_event(x, topic)]
    need(len(picked) == 1, f"Expected one event {topic}, received {len(picked)}")
    return picked[0]


def token_legs(logs, address):
    new = []
    for log in logs:
        if emit(log) == address and is_event(log, T):
            topic = [octets(t, 32) for t in log["topics"] if t is not None]
            need(len(topic) == 3, "Invalid Transfer topic count")
            new.append((int(log["index"]), addr_word(topic[1]), addr_word(topic[2]),
                        number(octets(log["data"], 32))))
    return sorted(new)


def net(legs, wallet):
    return sum(q for _, _, dst, q in legs if dst == wallet) - sum(
        q for _, src, _, q in legs if src == wallet)


def decimal_units(n):
    whole, frac = divmod(abs(n), SCALE)
    return ("-" if n < 0 else "") + str(whole) + (
        "." + f"{frac:018d}".rstrip("0") if frac else "")


def ratio(n, d, places=6):
    with localcontext() as ctx:
        ctx.prec = 64
        return f"{Decimal(n)/Decimal(d):.{places}f}"


def parse_packet(log):
    raw = octets(log["data"])
    head = split_words(raw[:96])
    need(len(head) == 3 and number(head[0]) == 96, "Invalid PacketSent tuple")

    def unpack_tail(start):
        need(start % 32 == 0 and start+32 <= len(raw), "Invalid packet dynamic offset")
        length = number(raw[start:start+32])
        end = start + 32 + ((length + 31)//32)*32
        need(end <= len(raw) and not any(raw[start+32+length:end]), "Invalid packet dynamic tail")
        return raw[start+32:start+32+length], end

    packet, end1 = unpack_tail(number(head[0]))
    need(end1 == number(head[1]), "Packet/options offset mismatch")
    _, end2 = unpack_tail(end1)
    need(end2 == len(raw) and len(packet) >= 113 and packet[0] == 1,
         "Unexpected LayerZero V1 packet")
    return {
        "packet_version": packet[0],
        "packet_nonce": number(packet[1:9]),
        "source_eid": number(packet[9:13]),
        "packet_sender": addr_word(packet[13:45]),
        "destination_eid": number(packet[45:49]),
        "packet_receiver_bytes32": "0x"+packet[49:81].hex(),
        "packet_guid": "0x"+packet[81:113].hex(),
        "packet_payload_bytes": len(packet)-113,
        "packet_send_library": addr_word(head[2]),
    }


def parse_fees(logs, library):
    e, d = only(logs, EXEC), only(logs, DVN)
    need(emit(e) == emit(d) == library, "Fee events do not come from the terminal address")
    a = split_words(octets(e["data"]))
    need(len(a) == 2, "Invalid ExecutorFeePaid payload")
    executor_addr = addr_word(a[0])
    b = split_words(octets(d["data"]))
    end, values = 3, []
    need(len(b) >= 6, "Invalid DVNFeePaid payload")
    for offset in b[:3]:
        need(number(offset) == 32*end and end < len(b), "Invalid DVNFeePaid offset")
        stop = end+1+number(b[end])
        need(stop <= len(b), "Invalid DVNFeePaid length")
        values.append(b[end+1:stop])
        end = stop
    need(end == len(b), "Unexpected trailing DVNFeePaid data")
    for word in values[0]+values[1]:
        addr_word(word)
    fees = [number(word) for word in values[2]]
    return executor_addr, number(a[1]), fees


def describe_route(tx, logs, usdr, gas, source_roles):
    sender, router = addr(tx["from"]["hash"]), addr(tx["to"]["hash"])
    val = amount(tx["value"])
    need(router == source_roles["Rayls CreditMessaging deployment"], "CreditMessaging address differs from the upstream deployment file")
    need(len(usdr) == 4 and val > 0, "Expected exactly four USDr legs")
    edges = {(a, b): q for _, a, b, q in usdr}
    need(len(edges) == 4 and edges.get((sender, router)) == val, "Top-level Value does not equal entry leg")
    hops = [(b, q) for (a, b), q in edges.items() if a == router]
    need(len(hops) == 1 and hops[0][1] == val, "Forwarder did not forward the full input")
    endpoint = hops[0][0]
    exits = [(b, q) for (a, b), q in edges.items() if a == endpoint and b != sender]
    need(len(exits) == 1 and (endpoint, sender) in edges, "Missing refund or terminal leg")
    library, fee = exits[0]
    refund = edges[endpoint, sender]
    need(len({sender, router, endpoint, library}) == 4 and refund > 0 and fee > 0
         and val == refund+fee, "Route does not conserve submitted value")
    need(net(usdr, sender) == -fee and net(usdr, router) == net(usdr, endpoint) == 0
         and net(usdr, library) == fee, "Wallet and route conservation")
    exact = val-refund+gas
    executor_addr, executor_fee, dvn_fees = parse_fees(logs, library)
    need(executor_fee+sum(dvn_fees) == fee, "Messaging event fees do not equal terminal leg")
    p = only(logs, PACKET)
    packet = parse_packet(p)
    c = only(logs, CREDITS)
    asset_roles={source_roles["Rayls StargateOFTUSDC deployment"]:"StargateOFTUSDC",
                 source_roles["Rayls StargateOFTETH deployment"]:"StargateOFTETH"}
    need(emit(p) == endpoint and emit(c) in asset_roles,
         "PacketSent emitter or Stargate credit emitter does not match an expected role")
    need(packet["packet_send_library"] == library and packet["packet_sender"] == router,
         "Packet roles disagree with four transfer legs")
    call = octets(tx["raw_input"])
    need(call[:4].hex() == "70485155", "Unexpected sendCredits selector")
    cw = list(map(number, split_words(octets(c["data"]))))
    need(len(cw) >= 3 and cw[1] == 64 and len(cw) == 3+2*cw[2] and cw[2] > 0,
         "Invalid CreditsSent array shape")
    need(all(x < (2**32 if i % 2 == 0 else 2**64) for i,x in enumerate(cw[3:])),
         "Invalid CreditsSent element width")
    need(number(call[4:36]) == cw[0] == packet["destination_eid"], "Destination EID disagrees across the three records")
    volume = sum(q for _, _, _, q in usdr)
    need(volume == 3*val, "Four-leg sum is not exactly three times Value")
    return {
        **packet, "payer": sender, "credit_messaging": router, "endpoint": endpoint,
        "send_library": library, "credit_emitter":emit(c),"credit_asset_contract":asset_roles[emit(c)],
        "gross_value_units": val, "refund_units": refund,
        "message_fee_units": fee, "executor_address": executor_addr,
        "executor_fee_units": executor_fee, "dvn_fee_units": sum(dvn_fees),
        "dvn_fee_entries": len(dvn_fees), "gas_units": gas, "net_debit_units": exact,
        "transfer_leg_sum_units": volume, "value_minus_floor_13_over_10_fee_units": val-13*fee//10,
        "leg_sum_to_net_debit": ratio(volume, exact),
    }


def read_specials(tx, cid, logs, usdr, val, gas):
    caller, target = addr(tx["from"]["hash"]), addr(tx["to"]["hash"])
    if cid == "case-25":
        need(tx["raw_input"] == "0x" and val > 0 and len(usdr) == 1
             and usdr[0][1:] == (caller,target,val), "Native send/log duplicate identity")
        return {"example":"native-send","wallet":target,"asset_movement_units":val,
                "wallet_usdr_delta_units":val, "wallet_fee_units":0}
    if cid in ("control-transfer","control-approve"):
        is_transfer=cid=="control-transfer"
        payload=octets(tx["raw_input"],68)
        need(val==0 and target==USDR and payload[:4].hex()==("a9059cbb" if is_transfer else "095ea7b3"),
             "Wrong calldata in wrapper control")
        recipient, q=addr_word(payload[4:36]),number(payload[36:])
        if is_transfer:
            need(len(usdr)==1 and usdr[0][1:]==(caller,recipient,q),"Wrapper transfer log differs from calldata")
        else:
            log=only(logs,A)
            need(not usdr and emit(log)==USDR and addr_word(octets(log["topics"][1],32))==caller
                 and addr_word(octets(log["topics"][2],32))==recipient
                 and number(octets(log["data"],32))==q, "Wrapper approval mismatch")
        return {"example":"wrapper-transfer" if is_transfer else "approval","wallet":caller,
                "asset_movement_units":-q if is_transfer else 0, "wallet_usdr_delta_units":(-q if is_transfer else 0)-gas,
                "wallet_fee_units":gas, "calldata_amount_units":q}
    if tx["method"]=="exactInputSingle":
        rl=token_legs(logs,RLS)
        need(val==0 and len(rl)==len(usdr)==1 and usdr[0][2]==rl[0][1]==caller
             and usdr[0][1]==rl[0][2], "Opposite swap-token movements disagree")
        return {"example":"swap","wallet":caller,"asset_movement_units":usdr[0][3],
                "wallet_usdr_delta_units":usdr[0][3]-gas,"wallet_fee_units":gas,"rls_out_units":rl[0][3]}
    if cid=="case-26":
        need(val==0 and len(usdr)==1 and usdr[0][1]==ZERO, "No unique USDr mint")
        _, _, receiver, q=usdr[0]
        mint,minted,esc,compose,delivered=[only(logs,t) for t in (MINT,MINTED,SWAP_ESCROW,SWAP_COMPOSER,DELIVERED)]
        ev_addr=lambda log,i:addr_word(octets(log["topics"][i],32))
        usdce=token_legs(logs,USDCE)
        need(emit(mint)==USDR and number(octets(mint["data"],32))==number(octets(minted["data"],32))==q
             and emit(esc)==ev_addr(minted,1)
             and ev_addr(esc,1)==emit(compose) and all(ev_addr(log,i)==receiver for log,i in ((mint,1),(minted,2),(esc,2),(compose,1))),
             "USDr mint and composition identities do not agree")
        in_units,out_units=map(number,split_words(octets(esc["data"],64)))
        need(octets(compose["data"],64)==octets(esc["data"],64)
             and len(usdce)==1 and usdce[0][1:]==(emit(compose),emit(esc),in_units)
             and in_units*10**12==out_units==q, "USDC.e input and USDr output do not reconcile")
        guid=octets(compose["topics"][2],32)
        _, dst, delivered_guid, _=split_words(octets(delivered["data"],128))
        need(addr_word(dst)==emit(compose) and delivered_guid==guid and receiver!=caller, "Wrong delivered GUID or wallet role")
        return {"example":"funding-mint","wallet":receiver,"asset_movement_units":q,
                "wallet_usdr_delta_units":q,"wallet_fee_units":0,"other_payer_gas_units":gas,
                "usdce_input_units":in_units,"compose_guid":"0x"+guid.hex()}
    return None


def assemble():
    meta=load("capture-index.json")
    annotations={r["file"]:r for r in meta["responses"]}
    all_files={p.name for p in CAPTURES.glob("*.json")}-{ "capture-index.json" }
    need(len(annotations)==len(meta["responses"])==132 and set(annotations)==all_files,
         "Capture index does not cover exactly the 132 saved responses")
    roles={r["role"]:r.get("published_address") for r in json.loads(
        (ROOT/"evidence/source-identities.json").read_text(encoding="utf-8"))["sources"]}
    pages=[load(f"mainnet-token-transfers-page{i}.json") for i in (1,2)]
    need(all(len(p["items"])==50 for p in pages), "Incomplete sampled page")
    q=parse_qs(urlsplit(annotations["mainnet-token-transfers-page2.json"]["url"]).query)
    need(q=={k:[str(v)] for k,v in pages[0]["next_page_params"].items()}, "Noncontiguous cursor")
    indexed=defaultdict(dict)
    unique=set()
    for page in pages:
        for r in page["items"]:
            h=r["transaction_hash"]
            i=int(r["log_index"])
            need((h,i) not in unique and addr(r["token"]["address_hash"])==USDR,
                 "Repeated or unrelated indexed row")
            unique.add((h,i))
            indexed[h][i]=(addr(r["from"]["hash"]),addr(r["to"]["hash"]),amount(r["total"]["value"]))
    credit_page={r["hash"]:r for r in load("mainnet-credit-contract-tx-page1.json")["items"]}
    control_page=load("mainnet-usdr-wrapper-tx-page1.json")["items"]
    crows={r["hash"]:r for r in control_page}
    need(len(indexed)==28 and set(indexed)=={c["hash"] for c in meta["case_records"]}, "Corpus grouping differs")
    chosen=[next(r["hash"] for r in control_page if r["status"]=="ok" and r["method"]==m
                 and addr(r["to"]["hash"])==USDR) for m in ("transfer","approve")]
    need(chosen==[c["hash"] for c in meta["control_cases"]] and not set(chosen)&set(indexed),
         "Separate control selection differs")
    cases, routes, specials, total_logs={},{},[],0
    for c in [*meta["case_records"],*meta["control_cases"]]:
        cid,h,b=c["id"],c["hash"],c["block"]
        prefix="bridge-01" if cid=="case-01" else cid
        lf=prefix+"-logs.json"
        url=urlsplit(annotations[lf]["url"])
        need(url.scheme=="https" and url.hostname=="explorer.rayls.com"
             and url.path==f"/api/v2/transactions/{h}/logs", "Wrong capture request for logs")
        response=load(lf)
        logs=response["items"]
        need(response["next_page_params"] is None and len({r["index"] for r in logs})==len(logs),
             "Incomplete/nonunique logs")
        total_logs+=len(logs)
        hashes={r["block_hash"] for r in logs}
        need(len(hashes)==1 and all(r["transaction_hash"]==h and r["block_number"]==b for r in logs),
             "Receipt linkage differs")
        tx=(credit_page[h] if c["method"]=="sendCredits" else crows[h] if h in crows and cid.startswith("control")
            else load(cid+"-transaction.json"))
        need(tx["hash"]==h and tx["timestamp"]==c["utc"] and tx["block_number"]==b and tx["method"]==c["method"],
             "Captured tx fields differ")
        val=amount(tx["value"])
        gas=amount(tx["gas_used"])*amount(tx["gas_price"])
        need(tx["status"]=="ok" and tx["fee"]["type"]=="actual" and gas==amount(tx["fee"]["value"]),
             "Fee or success status mismatch")
        usdr=token_legs(logs,USDR)
        if h in indexed:
            need({i:(a,z,q) for i,a,z,q in usdr}==indexed[h], "Indexed list differs from event bytes")
        else:
            ct=load(cid+"-token-transfers.json")
            need(ct["next_page_params"] is None and sorted(
                (int(r["log_index"]),addr(r["from"]["hash"]),addr(r["to"]["hash"]),amount(r["total"]["value"]))
                for r in ct["items"])==usdr, "Control transfer list differs from event bytes")
        cases[cid]={"case_id":cid,"hash":h,"height":b,"block_hash":next(iter(hashes)),"tx":tx,
                    "value":val,"gas":gas,"legs":usdr,"prefix":prefix}
        if c["method"]=="sendCredits":
            routes[cid]={"case_id":cid,"hash":h,"height":b,**describe_route(tx,logs,usdr,gas,roles)}
        else:
            extra=read_specials(tx,cid,logs,usdr,val,gas)
            if extra:
                specials.append({"case_id":cid,"hash":h,"height":b,"top_value_units":val,**extra})
    need(len(cases)==30 and total_logs==215 and len(routes)==23, "Capture totals differ")
    need(len({r["packet_guid"] for r in routes.values()})==23, "Repeated packet GUID")
    need(len({tuple(r[k] for k in ("payer","credit_messaging","endpoint","send_library")) for r in routes.values()})==1,
         "Route/payer coverage differs")
    need(all(r["value_minus_floor_13_over_10_fee_units"]==0 for r in routes.values()), "Observed 13/10 relation does not fit all 23 cases")

    balances, gas_rows=[],[]
    for cid in meta["balance_selection"]:
        c=cases[cid]
        block=load(c["prefix"]+"-block.json")
        author=addr(block["miner"]["hash"])
        gas_used=amount(c["tx"]["gas_used"])
        base=gas_used*amount(block["base_fee_per_gas"])
        tip=c["gas"]-base
        need(block["hash"]==c["block_hash"] and block["height"]==c["height"]
             and block["transactions_count"]==1 and block["withdrawals_count"]==0
             and gas_used==amount(block["gas_used"]) and tip>=0
             and tip==amount(block["priority_fee"]) and c["gas"]==amount(block["transaction_fees"]),
             "Block/fee split mismatch")
        gas_rows.append({"case_id":cid,"height":c["height"],"base_component_units":base,
                         "priority_component_units":tip,"network_fee_units":c["gas"]})
        caller,target=addr(c["tx"]["from"]["hash"]),addr(c["tx"]["to"]["hash"])
        parties={caller,target,*[a for i,s,d,u in c["legs"] for a in (s,d)]}-{ZERO}
        selected=[x for x in meta["balance_records"] if x["case_id"]==cid]
        need(parties=={addr(x["address"]) for x in selected} and len(parties)==len(selected) and author not in parties,
             "Balance coverage differs or contains the block's tip beneficiary")
        for x in selected:
            w=addr(x["address"])
            vals=[]
            for k,height in (("before",c["height"]-1),("after",c["height"])):
                f=x[k]
                u=urlsplit(annotations[f]["url"])
                qq=parse_qs(u.query)
                need(u.scheme=="https" and u.hostname=="explorer.rayls.com" and u.path=="/api"
                     and qq.get("module")==["account"] and qq.get("action")==["eth_get_balance"]
                     and qq.get("block")==[str(height)] and addr(qq["address"][0])==w, "Balance request binding differs")
                reply=load(f)
                need("error" not in reply and re.fullmatch(r"0x[0-9a-fA-F]+",reply.get("result","")),
                     "Historical balance unavailable")
                vals.append(int(reply["result"],16))
            expected=net(c["legs"],w)-(c["gas"] if w==caller else 0)
            balances.append({"case_id":cid,"address":w,"height":c["height"],"before_units":vals[0],
                             "after_units":vals[1],"log_net_less_gas_units":expected,
                             "explorer_delta_units":vals[1]-vals[0],"explorer_minus_expected_units":vals[1]-vals[0]-expected})
    matched=[r for r in balances if r["explorer_minus_expected_units"]==0]
    diff=[r for r in balances if r["explorer_minus_expected_units"]!=0]
    net_zero=sum(r["log_net_less_gas_units"]==0 for r in matched)
    need(len(balances)==37 and len(matched)==34 and net_zero==16
         and {r["case_id"] for r in diff}=={"case-25","case-26","control-transfer"} and len(diff)==3,
         "Historical comparison counts differ")
    route_bal=[r for r in balances if r["case_id"] in routes]
    need(len(route_bal)==16 and all(r["explorer_minus_expected_units"]==0 for r in route_bal), "Routing balance checks differ")

    hero=routes["case-01"]
    state=load("bridge-01-state-changes.json")
    actor=hero["payer"]
    indexed_row=next(r for r in balances if r["case_id"]=="case-01" and r["address"]==actor)
    coin_row=next(r for r in state["items"] if r["type"]=="coin" and addr(r["address"]["hash"])==actor)
    token_row=next(r for r in state["items"] if r["type"]=="token" and addr(r["address"]["hash"])==actor
                   and addr(r["token"]["address_hash"])==USDR)
    need(state["next_page_params"] is None, "Incomplete headline Explorer State response")
    for row in (coin_row,token_row):
        need(amount(row["balance_after"])-amount(row["balance_before"])==amount(row["change"]), "State row arithmetic")
    need(amount(coin_row["change"])==-(hero["gross_value_units"]+hero["gas_units"])
         and amount(token_row["change"])==-hero["message_fee_units"]
         and indexed_row["explorer_delta_units"]-amount(coin_row["change"])==hero["refund_units"],
         "State view comparison does not reproduce")
    need(amount(coin_row["balance_before"])==amount(token_row["balance_before"])==indexed_row["before_units"], "State view starting snapshot differs")

    mint=next(r for r in specials if r["example"]=="funding-mint")
    linked=next(r for r in diff if r["case_id"]=="case-25" and r["address"]==mint["wallet"])
    prior=next(r for r in diff if r["case_id"]=="case-26" and r["address"]==mint["wallet"])
    hresp=load("mint-to-transfer-coin-history.json")
    history=hresp["items"]
    need(history and [r["block_number"] for r in history]==sorted(
         {r["block_number"] for r in history},reverse=True), "Captured history page order")
    if hresp["next_page_params"] is not None:
        need(int(hresp["next_page_params"]["block_number"])<=history[-1]["block_number"], "History cursor out of range")
    selections=[]
    for item in (prior,linked):
        for label,h in (("before",item["height"]-1),("after",item["height"])):
            pick=next(x for x in history if x["value"] is not None and x["block_number"]<=h)
            need(amount(pick["value"])==item[label+"_units"], "Last recorded history row does not explain the lookup")
            selections.append({"case_id":item["case_id"],"lookup":label,"requested_height":h,
                               "selected_history_height":pick["block_number"],
                               "matches_at_or_before_model":True,"balance_units":amount(pick["value"])})
    combined=linked["after_units"]-prior["before_units"]
    need(combined==linked["log_net_less_gas_units"]+prior["log_net_less_gas_units"]
         and combined==amount(history[0]["delta"]) and history[0]["transaction_hash"]==cases["case-25"]["hash"],
         "Funding interval reconciliation differs")

    lookup={(r["case_id"],r["address"]):r for r in balances}
    for i in specials:
        m=lookup[(i["case_id"],i["wallet"])]
        i.update(explorer_delta_units=m["explorer_delta_units"],
                 explorer_delta_matches=m["explorer_minus_expected_units"]==0)

    all_routes=list(routes.values())
    stats={k:sum(r[k] for r in all_routes) for k in ("gross_value_units","refund_units","message_fee_units",
          "gas_units","net_debit_units","transfer_leg_sum_units")}
    rr=sorted(Fraction(r["transfer_leg_sum_units"],r["net_debit_units"]) for r in all_routes)
    need(stats["net_debit_units"]==stats["message_fee_units"]+stats["gas_units"],"Sample total debit")
    stats["aggregate_leg_sum_to_net_debit"]=ratio(stats["transfer_leg_sum_units"],stats["net_debit_units"])
    stats["ratio_min_median_max"]=[ratio(x.numerator,x.denominator) for x in (rr[0],rr[len(rr)//2],rr[-1])]
    core_blocks=[cases[c["id"]]["height"] for c in meta["case_records"]]
    summary={
        "scope":"Separate accounting calculations over one saved Explorer dataset; no node state attestation.",
        "counts":{"captured_json_responses":len(annotations),"sample_transfer_rows":len(unique),
                  "sample_transactions":len(indexed),"separate_controls":len(chosen),
                  "logs_including_other_events":total_logs,"credit_calls":len(routes),
                  "credit_payers":len({r["payer"] for r in all_routes}),
                  "packet_source_eids":sorted({r["source_eid"] for r in all_routes}),
                  "packet_destinations":sorted({r["destination_eid"] for r in all_routes}),
                  "credit_emitters":dict(sorted(Counter(r["credit_asset_contract"] for r in all_routes).items())),
                  "unique_packet_guids":len({r["packet_guid"] for r in all_routes}),
                  "isolated_blocks":len(gas_rows),"indexed_balance_pairs":len(balances),
                  "exact_pairs":len(matched),"exact_zero_change_pairs":net_zero,
                  "exact_nonzero_pairs":len(matched)-net_zero,"route_balance_pairs":len(route_bal)},
        "sample_block_range":[min(core_blocks),max(core_blocks)],"aggregate":stats,
        "hero":{**hero,**{k:v for k,v in gas_rows[0].items() if k.endswith("_component_units")},
                "indexed_wallet_delta_units":indexed_row["explorer_delta_units"],"state_tab_coin_delta_units":amount(coin_row["change"]),
                "state_tab_usdr_token_delta_units":amount(token_row["change"]),
                "state_tab_coin_minus_indexed_units":amount(coin_row["change"])-indexed_row["explorer_delta_units"]},
        "balance_exceptions":diff,"funding_window_combined_units":combined,"history_lookup_model":selections,
        "special_wallet_examples":specials,
    }
    return summary,all_routes,balances,gas_rows,selections


def write(dest, result):
    dest.mkdir(parents=True,exist_ok=False)
    summary,*rows=result
    (dest/"review-summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8",newline="\n")
    for name, table in zip(("route-audit","wallet-balances","network-fees","history-height-model"),rows):
        with (dest/(name+".csv")).open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(table[0]),lineterminator="\n")
            w.writeheader()
            w.writerows(table)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=assemble()
    write(a.out,result)
    c=result[0]["counts"]
    print(f"PASS: 30 captured transactions, {c['credit_calls']} routes, {c['unique_packet_guids']} packets, {len(c['packet_destinations'])} destination EIDs.")
    print("PASS: 23 exact 13/10 comparisons; four history lookups; one State-view cross-check.")
    print(f"OBSERVED: {c['exact_pairs']}/{c['indexed_balance_pairs']} indexed balance pairs; three point differences retained.")
