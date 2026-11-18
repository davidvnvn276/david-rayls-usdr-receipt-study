#!/usr/bin/env python3
"""Reproduce the USDr study from saved public Explorer responses. No network."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "evidence" / "explorer"
EXPLORER = "https://explorer.rayls.com"
CHAIN_ID = 72957
USDR = "0x0000000000000000000000000000000000000400"
RLS = "0x07e17e17e17e17e17e17e17e17e17e17e17e17ea"
USDCE = "0x9001dbe4d68d36ab87923a2a9dfb0c745fd25001"
ZERO = "0x" + "0" * 40
Q = 10**18
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
APPROVAL = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
EXECUTOR_FEE = "0x61ed099e74a97a1d7f8bb0952a88ca8b7b8ebd00c126ea04671f92a81213318a"
DVN_FEE = "0x07ea52d82345d6e838192107d8fd7123d9c2ec8e916cd0aad13fd2b60db24644"
PACKET_SENT = "0x1ab700d4ced0c005b164c0f789fd09fcbb0156d4c2041b8a3bfbcd961cd1567f"
CREDITS_SENT = "0xce105e156370093e6600169f7c01277f740d45fbcf95435227ce6f43ad0c3abd"
MINT = "0x0f6798a560793a54c3bcfe86a93cde1e73087d944c0ea20544137d4121396885"
MINTED = "0x9d228d69b5fdb8d273a2336f8fb8612d039631024ea9bf09c424a9503aa078f0"
ESCROW_SWAP = "0x48644a6a821b386b0f8b970c2b71b8e0bb4b89677a1ebe83b2f16fffb96ccf84"
COMPOSER_SWAP = "0xa199edc830ae0ec22c21ba6e49d71cad061148d27fb04a74caef8aa316567bd1"
COMPOSE_DELIVERED = "0x0036c98efcf9e6641dfbc9051f66f405253e8e0c2ab4a24dccda15595b7378c8"


class EvidenceError(ValueError):
    pass


def require(test, why):
    if not test:
        raise EvidenceError(why)


def load(name):
    require(Path(name).name == name, f"Invalid capture name: {name!r}")
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def bytes32word(hex_string):
    require(isinstance(hex_string, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", hex_string),
            f"Invalid 32-byte value: {hex_string!r}")
    return int(hex_string, 16)


def address(s):
    require(isinstance(s, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", s),
            f"Invalid address: {s!r}")
    return s.lower()


def topic_address(topic):
    n = bytes32word(topic)
    require(n < 2**160, "Indexed address has nonzero high bytes")
    return "0x" + f"{n:040x}"


def topic0(log):
    return (log["topics"][0] or "").lower()


def uintwords(hex_data):
    require(isinstance(hex_data, str) and re.fullmatch(r"0x(?:[0-9a-fA-F]{64})*", hex_data),
            "Invalid ABI words")
    return [int(hex_data[i:i + 64], 16) for i in range(2, len(hex_data), 64)]


def transfer(log, token=USDR):
    """Return (log index, sender, recipient, amount), or ignore unrelated logs."""
    if address(log["address"]["hash"]) != token or topic0(log) != TRANSFER:
        return None
    require(all(t is None for t in log["topics"][3:]), "Unexpected extra ERC-20 Transfer topic")
    return (int(log["index"]), topic_address(log["topics"][1]), topic_address(log["topics"][2]),
            bytes32word(log["data"]))


def event_net(legs, account):
    return sum((int(dst == account) - int(src == account)) * q
               for _, src, dst, q in legs)


def native_fee(tx):
    require(tx["status"] == "ok" and tx["fee"]["type"] == "actual", f"No success/actual fee: {tx['hash']}")
    fee = int(tx["fee"]["value"])
    require(fee == int(tx["gas_used"]) * int(tx["gas_price"]), f"Gas fee equation failed: {tx['hash']}")
    return fee


def token_rows(items):
    rows = []
    for r in items:
        require(address(r["token"]["address_hash"]) == USDR and str(r["total"]["decimals"]) == "18",
                "Unexpected token address/decimals")
        rows.append((int(r["log_index"]), address(r["from"]["hash"]),
                     address(r["to"]["hash"]), int(r["total"]["value"])))
    return sorted(rows)


def chunk(logs, event_topic):
    matches = [l for l in logs if topic0(l) == event_topic]
    require(len(matches) == 1, f"Expected one log for {event_topic}, got {len(matches)}")
    return matches[0]


def decode_fee_events(logs, terminal):
    exec_event = chunk(logs, EXECUTOR_FEE)
    dvn_event = chunk(logs, DVN_FEE)
    require(address(exec_event["address"]["hash"]) == address(dvn_event["address"]["hash"]) == terminal,
            "Messaging fee events not emitted by terminal recipient")
    exec_words = uintwords(exec_event["data"])
    require(len(exec_words) == 2 and exec_words[0] < 2**160, "Unexpected executor ABI")
    dw = uintwords(dvn_event["data"])
    require(len(dw) >= 6, "Invalid DVN ABI")
    arrays = []
    end = 3
    for ix in range(3):
        require(dw[ix] == 32*end and end < len(dw), "Invalid DVN array offset")
        n = dw[end]
        require(end+1+n <= len(dw), "Truncated DVN array")
        arrays.append(dw[end+1:end+1+n])
        end += n+1
    require(end == len(dw) and all(a < 2**160 for a in arrays[0]+arrays[1]), "Invalid DVN tails")
    return exec_words[1], sum(arrays[2]), arrays[2]


def read_credit_flow(tx, logs, legs):
    """Match a directed flow by addresses and exact units, never by log order."""
    src, router = address(tx["from"]["hash"]), address(tx["to"]["hash"])
    require(len(legs) == 4 and tx["raw_input"].startswith("0x70485155"), "Not the sampled four-leg call")
    path = {(a, b): n for _, a, b, n in legs}
    require(len(path) == 4, "Duplicate directed leg")
    gross = int(tx["value"])
    require(path.get((src, router)) == gross, "Transaction value and entry leg differ")
    forwarded = [(b, v) for (a, b), v in path.items() if a == router]
    require(len(forwarded) == 1 and forwarded[0][1] == gross, "Cannot identify identical forwarding leg")
    endpoint = forwarded[0][0]
    refund = path.get((endpoint, src))
    final = [(b, v) for (a, b), v in path.items() if a == endpoint and b != src]
    require(refund is not None and len(final) == 1, "Cannot identify refund/terminal leg")
    terminal, retained = final[0]
    require(len({src, router, endpoint, terminal}) == 4, "Ambiguous flow roles")
    require(gross - refund == retained == -event_net(legs, src), "Credit flow imbalance")
    require(event_net(legs, router) == event_net(legs, endpoint) == 0, "Forwarders are not flat")
    gas = native_fee(tx)
    executor, dvn_total, dvn_parts = decode_fee_events(logs, terminal)
    require(executor + dvn_total == retained, "Fee events do not reconcile to the terminal leg")
    packet = chunk(logs, PACKET_SENT)
    packet_words = uintwords(packet["data"])
    require(len(packet_words) >= 3 and packet_words[2] < 2**160, "Invalid packet event")
    require(address(packet["address"]["hash"]) == endpoint
            and packet_words[2] == int(terminal, 16), "Packet event address mismatch")
    call_words = uintwords("0x"+tx["raw_input"][10:])
    credits = uintwords(chunk(logs, CREDITS_SENT)["data"])
    require(call_words[0] == credits[0] and 0 < credits[0] < 2**32, "Destination EID mismatch")
    return {
        "gross_value_units": gross, "forwarded_units": gross, "refund_units": refund,
        "message_fee_units": retained, "executor_event_units": executor,
        "dvn_event_sum_units": dvn_total, "dvn_event_entries": dvn_parts,
        "gas_units": gas, "caller_debit_units": retained + gas,
        "sum_transfer_rows_units": sum(path.values()), "dst_eid": credits[0],
        "payer": src, "credit_messaging": router, "endpoint": endpoint, "send_library": terminal,
    }


def read_mint_flow(tx, logs, legs):
    require(int(tx["value"])==0 and len(legs)==1 and legs[0][1]==ZERO and legs[0][3]>0, "Mint case mismatch")
    _,_,recipient,usdr=legs[0]
    mint,minted,escrow,composer,delivered=(chunk(logs,t) for t in
        (MINT,MINTED,ESCROW_SWAP,COMPOSER_SWAP,COMPOSE_DELIVERED))
    ac=address(composer["address"]["hash"])
    escrow_addr=address(escrow["address"]["hash"])
    for l,i in [(mint,1),(minted,2),(escrow,2),(composer,1)]:
        require(topic_address(l["topics"][i])==recipient, "Mint path disagrees on the recipient")
    require(address(mint["address"]["hash"])==USDR and topic_address(minted["topics"][1])==escrow_addr
            and topic_address(escrow["topics"][1])==ac, "Mint path emitter/caller mismatch")
    require(bytes32word(mint["data"])==bytes32word(minted["data"])==usdr,
            "Mint events disagree on amount")
    deposit,amount=uintwords(escrow["data"])
    require(uintwords(composer["data"])==[deposit,amount] and amount==usdr,
            "Escrow and composer amounts differ")
    contract_transfer=[t for l in logs if (t:=transfer(l,USDCE)) is not None]
    escrow_meta=[t["token"] for t in tx["token_transfers"] if address(t["token"]["address_hash"])==USDCE]
    require(len(contract_transfer)==1 and contract_transfer[0][1:]==(ac,escrow_addr,deposit)
            and len(escrow_meta)==1 and escrow_meta[0]["decimals"]=="6"
            and deposit*10**12==usdr, "USDC.e input and USDr output do not reconcile")
    guid=bytes32word(composer["topics"][2])
    deliver_words=uintwords(delivered["data"])
    require(len(deliver_words)==4 and deliver_words[1]==int(ac,16) and deliver_words[2]==guid and deliver_words[3]<2**16,
            "Local composition does not match the swap event")
    return {"usdr_mint_recipient":recipient,"usdr_mint_units":usdr,
            "usdce_input_units_6_decimals":deposit,"compose_guid":f"0x{guid:064x}"}


def capture_url_check(annotation, file, path=None):
    u = urlparse(annotation[file]["url"])
    require((u.scheme, u.netloc) == ("https", "explorer.rayls.com"), "Unexpected capture host")
    if path is not None:
        require(u.path == path, f"Unexpected request path for {file}")
    return u


def token_formatter(n):
    sign = "-" if n < 0 else ""
    units, frac = divmod(abs(n), Q)
    return sign + str(units) + (f".{frac:018d}".rstrip("0") if frac else "")


def ratio(a, b, places=4):
    with localcontext() as ctx:
        ctx.prec = 48
        return format(Decimal(a)/Decimal(b), f".{places}f")


def verify_manifest():
    seen = set()
    for line in (ROOT/"SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        file = ROOT / name
        require(file.is_file() and file.resolve().is_relative_to(ROOT), f"Missing/invalid file: {name}")
        require(re.fullmatch(r"[0-9a-f]{64}", digest) and name not in seen, f"Invalid manifest entry: {name}")
        seen.add(name)
        require(hashlib.sha256(file.read_bytes()).hexdigest() == digest, f"SHA-256 mismatch: {name}")
    require("verify.py" in seen and "evidence/explorer/capture-index.json" in seen,
            "Manifest lacks required inputs")
    return seen


def build_results():
    meta = load("capture-index.json")
    require(meta["chain_id_documented"] == CHAIN_ID and meta["transfer_token"] == USDR,
            "Unexpected network/token selection")
    annotations = {r["file"]: r for r in meta["responses"]}
    require(len(annotations) == len(meta["responses"]), "Duplicate capture filenames")
    present = {p.name for p in DATA.glob("*.json")} - {"capture-index.json"}
    require(set(annotations) == present, "Capture index disagrees with JSON files")
    for file in annotations:
        capture_url_check(annotations, file)
        load(file)
    token_meta = load("mainnet-usdr-token-metadata.json")
    require(address(token_meta["address_hash"]) == USDR and token_meta["decimals"] == "18"
            and token_meta["symbol"] == "USDr", "USDr metadata mismatch")

    page1 = load("mainnet-token-transfers-page1.json")
    page2 = load("mainnet-token-transfers-page2.json")
    token_path = f"/api/v2/tokens/{USDR}/transfers"
    p1 = capture_url_check(annotations, "mainnet-token-transfers-page1.json", token_path)
    p2 = capture_url_check(annotations, "mainnet-token-transfers-page2.json", token_path)
    require(not p1.query and parse_qs(p2.query) == {k:[str(v)] for k,v in page1["next_page_params"].items()},
            "Page 2 does not use page 1's captured cursor")
    corpus = page1["items"] + page2["items"]
    require(all((a["block_number"], a["log_index"]) > (b["block_number"], b["log_index"])
                for a,b in zip(corpus, corpus[1:])), "Snapshot is not strictly descending in block/log order")
    by_tx = defaultdict(list)
    for row in corpus:
        by_tx[row["transaction_hash"]].append(row)
    require(len(set((r["transaction_hash"], r["log_index"]) for r in corpus)) == len(corpus),
            "Duplicate transfer rows")
    control_page = load("mainnet-usdr-wrapper-tx-page1.json")["items"]
    chosen_controls = []
    for m in ("transfer", "approve"):
        t = next(t for t in control_page if t["method"] == m and t["status"] == "ok"
                 and address(t["to"]["hash"]) == USDR)
        chosen_controls.append(t["hash"])
    cases = meta["case_records"] + meta["control_cases"]
    require(list(by_tx) == [x["hash"] for x in meta["case_records"]], "Core case selection mismatch")
    require(chosen_controls == [x["hash"] for x in meta["control_cases"]], "Control selection mismatch")
    require(not set(by_tx).intersection(chosen_controls), "Controls overlap the corpus")
    tx_credit = {x["hash"]:x for x in load("mainnet-credit-contract-tx-page1.json")["items"]}
    tx_control = {t["hash"]:t for t in control_page}
    transactions, transfers, credit_rows = {}, {}, []
    all_decoded = []
    rows = []
    credit_by_day = defaultdict(list)

    for c in cases:
        cid, h, b, method = (c[k] for k in ("id","hash","block","method"))
        bytes32word(h)
        log_file = "bridge-01-logs.json" if cid == "case-01" else cid+"-logs.json"
        capture_url_check(annotations, log_file, "/api/v2/transactions/"+h+"/logs")
        lp = load(log_file)
        require(lp["next_page_params"] is None, f"Incomplete log set: {cid}")
        logs = lp["items"]
        require(len({l["index"] for l in logs}) == len(logs), f"Duplicate log indices: {cid}")
        block_hashes = {l["block_hash"].lower() for l in logs}
        require(len(block_hashes) == 1 and all(l["transaction_hash"] == h and l["block_number"] == b for l in logs),
                f"Log transaction linkage mismatch: {cid}")
        bh = next(iter(block_hashes))
        bytes32word(bh)
        if cid.startswith("control-"):
            tx = tx_control[h]
            tp = load(cid+"-token-transfers.json")
            require(tp["next_page_params"] is None, f"Incomplete control token rows: {cid}")
            indexed = tp["items"]
        else:
            tx = tx_credit[h] if method == "sendCredits" else load(cid+"-transaction.json")
            indexed = by_tx[h]
        require(tx["hash"] == h and tx["block_number"] == b and tx["timestamp"] == c["utc"]
                and tx["method"] == method, f"Transaction envelope mismatch: {cid}")
        require(all(r["block_hash"].lower() == bh and r["block_number"] == b and r["transaction_hash"] == h
                    for r in indexed), f"Index-to-log block linkage failed: {cid}")
        fee = native_fee(tx)
        src = address(tx["from"]["hash"])
        dst = address(tx["to"]["hash"])
        val = int(tx["value"])
        legs = sorted(t for l in logs if (t:=transfer(l)) is not None)
        require(legs == token_rows(indexed), f"Indexed USDr rows differ from raw logs: {cid}")
        transactions[cid], transfers[cid] = tx, legs
        all_decoded.extend({"case_id":cid, "hash":h, "log_index":i, "from":a, "to":z, "amount_units":q}
                           for i,a,z,q in legs)
        info = {"case_id":cid,"hash":h,"block":b,"block_hash":bh,"utc":c["utc"],
                "method":method or "native-value transfer","caller":src,"tx_to":dst,
                "top_level_value_units":val,"network_fee_units":fee,
                "caller_receipt_net_units":event_net(legs,src),
                "caller_expected_delta_units":event_net(legs,src)-fee,
                "usdr_transfer_log_count":len(legs),"all_log_count":len(logs)}
        if method == "sendCredits":
            f = read_credit_flow(tx,logs,legs)
            credit_rows.append({"case_id":cid,"hash":h,"block":b,"utc":c["utc"],**f})
            credit_by_day[c["utc"][:10]].append(cid)
        elif cid == "case-25":
            require(tx["raw_input"] == "0x" and legs == [(0,src,dst,val)] and val > 0,
                    "Native transfer's receipt does not mirror its top-level value")
        elif cid in ("control-transfer","control-approve"):
            selector = "0xa9059cbb" if method=="transfer" else "0x095ea7b3"
            require(val == 0 and dst == USDR and tx["raw_input"].startswith(selector),
                    "Wrong direct ERC-20 call")
            args = uintwords("0x"+tx["raw_input"][10:])
            require(len(args)==2 and args[0]<2**160, "Malformed direct ERC-20 input")
            amount = args[1]
            recipient = "0x"+f"{args[0]:040x}"
            if method=="transfer":
                require(legs == [(0,src,recipient,amount)] and amount>0 and len(logs)==1,
                        "ERC-20 calldata/receipt mismatch")
                info["erc20_transfer_amount_units"] = amount
            else:
                a = chunk(logs,APPROVAL)
                require(not legs and len(logs)==1 and address(a["address"]["hash"])==USDR,
                        "Approval has unexpected movement")
                require(topic_address(a["topics"][1]) == src and topic_address(a["topics"][2]) == recipient
                        and bytes32word(a["data"]) == amount, "Approval calldata/receipt mismatch")
                info["approved_amount_units"] = amount
        elif method == "exactInputSingle":
            rls_legs = [t for l in logs if (t:=transfer(l,RLS)) is not None]
            require(val==0 and len(legs)==len(rls_legs)==1 and logs[-1]["decoded"]["method_call"].startswith("Swap("),
                    "Not the sampled two-asset swap")
            require(legs[0][2]==src==rls_legs[0][1] and legs[0][1]==rls_legs[0][2],
                    "Swap legs do not connect the same pool and trader")
            info["rls_transfer_out_units"] = rls_legs[0][3]
        elif method == "compose302":
            info.update(read_mint_flow(tx,logs,legs))
        rows.append(info)

    expected_selection=[c for g in credit_by_day.values() for c in (g[0],g[-1])]
    expected_selection += [c["id"] for c in cases if c["method"] != "sendCredits"]
    require(meta["balance_selection"] == expected_selection, "Balance selection differs from declared rule")
    rowmap = {r["case_id"]:r for r in rows}
    not_beneficiary = {}
    for cid in expected_selection:
        r = rowmap[cid]
        f = "bridge-01-block.json" if cid=="case-01" else cid+"-block.json"
        block = load(f)
        capture_url_check(annotations, f, f"/api/v2/blocks/{r['block']}")
        require(block["height"] == r["block"] and block["hash"].lower()==r["block_hash"]
                and block["timestamp"] == r["utc"], f"Block binding failed: {cid}")
        require(block["transactions_count"]==1 and block["withdrawals_count"]==0
                and int(block["gas_used"])==int(transactions[cid]["gas_used"])
                and int(block["transaction_fees"])==r["network_fee_units"]
                and transactions[cid]["position"]==0, f"Not an isolated one-transaction block: {cid}")
        not_beneficiary[cid] = address(block["miner"]["hash"])

    observed = {(r["case_id"],address(r["address"])):r for r in meta["balance_records"]}
    desired = {(cid,a) for cid in expected_selection for a in [
        rowmap[cid]["caller"],rowmap[cid]["tx_to"],*(addr for _,u,v,_ in transfers[cid] for addr in (u,v))
    ] if a!=ZERO}
    require(set(observed)==desired and len(observed)==len(meta["balance_records"]),
            "Missing, duplicate, or extra sampled balance pairs")
    balances = []
    for (cid,a), pair in observed.items():
        r = rowmap[cid]
        require(a != not_beneficiary[cid], "Skip cases where the measured address receives block gas tips")
        got = []
        for label,effective_h in (("before",r["block"]-1),("after",r["block"])):
            file = pair[label]
            query = parse_qs(capture_url_check(annotations,file,"/api").query)
            require(query.get("module")==["account"] and query.get("action")==["eth_get_balance"]
                    and query.get("block")==[str(effective_h)]
                    and len(query.get("address",[]))==1 and address(query["address"][0])==a,
                    f"Block/account mismatch: {file}")
            reply = load(file)
            require(reply.get("jsonrpc")=="2.0" and re.fullmatch(r"0x[0-9a-fA-F]+",reply.get("result","")),
                    f"Invalid coin-balance response: {file}")
            got.append(int(reply["result"],16))
        explained=event_net(transfers[cid],a)-(r["network_fee_units"] if a==r["caller"] else 0)
        saw=got[1]-got[0]
        balances.append({"case_id":cid,"address":a,"before_units":got[0],"after_units":got[1],
                         "event_less_gas_units":explained,"observed_delta_units":saw,
                         "difference_units":saw-explained,"matched":saw==explained})
    mintrow, sendrow = rowmap["case-26"],rowmap["case-25"]
    linked = mintrow["usdr_mint_recipient"]
    require(linked == sendrow["caller"], "Funding and spend do not use the same account")
    a,b = (next(x for x in balances if x["case_id"] == cid and x["address"] == linked)
           for cid in ("case-26","case-25"))
    joined_delta = b["after_units"]-a["before_units"]
    expect_joined = a["event_less_gas_units"]+b["event_less_gas_units"]
    hist = [r for r in load("mint-to-transfer-coin-history.json")["items"]
            if mintrow["block"] <= r["block_number"] <= sendrow["block"]]
    sender_hist = [r for r in load("mint-to-transfer-address-transactions.json")["items"]
                   if mintrow["block"]<=r["block_number"]<=sendrow["block"]]
    require(joined_delta == expect_joined, "The observed two-transaction funding/spend window did not reconcile")
    require(len(hist)==len(sender_hist)==1 and hist[0]["block_number"] == sendrow["block"]
            and hist[0]["transaction_hash"]==sender_hist[0]["hash"]==sendrow["hash"]
            and int(hist[0]["delta"])==joined_delta and int(hist[0]["value"])==b["after_units"],
            "The captured address history does not confirm the later combined movement")
    joined={"address":linked,"first_block":mintrow["block"],"last_block":sendrow["block"],
            "mint_units":mintrow["usdr_mint_units"],"outgoing_value_units":sendrow["top_level_value_units"],
            "usdce_input_units_6_decimals":mintrow["usdce_input_units_6_decimals"],
            "compose_guid":mintrow["compose_guid"],
            "fee_units":sendrow["network_fee_units"],"observed_combined_delta_units":joined_delta,
            "expected_combined_delta_units":expect_joined}
    def aggregate(field):
        return sum(x[field] for x in credit_rows)
    stats={field:aggregate(field) for field in (
        "gross_value_units","refund_units","message_fee_units","gas_units",
        "caller_debit_units","sum_transfer_rows_units","executor_event_units","dvn_event_sum_units")}
    stats["log_sum_to_actual_debit_ratio"]=ratio(stats["sum_transfer_rows_units"],stats["caller_debit_units"])
    primary = dict(credit_rows[0])
    primary["log_sum_to_actual_debit_ratio"]=ratio(primary["sum_transfer_rows_units"],primary["caller_debit_units"])
    bridged = [r for r in balances if r["case_id"] in {x["case_id"] for x in credit_rows}]
    with_zero = sum(1 for b in balances if b["matched"] and b["observed_delta_units"]==0)
    summary={"chain_id_documented":CHAIN_ID,"usdr":USDR,"decimals":18,"indexed_transfer_rows":len(corpus),
             "corpus_transactions":len(by_tx),"additional_controls":len(chosen_controls),
             "core_methods":dict(Counter((c["method"] or "native-value transfer") for c in meta["case_records"])),
             "first_utc":corpus[-1]["timestamp"],"last_utc":corpus[0]["timestamp"],
             "captured_json_responses":len(annotations),
             "transactions_reconciled_to_raw_logs":len(rows),"total_raw_logs":sum(r["all_log_count"] for r in rows),
             "payment_routing_cases":len(credit_rows),"isolated_blocks":len(expected_selection),
             "balance_pairs":len(balances),"balance_pairs_exact":sum(b["matched"] for b in balances),
             "exact_zero_change_pairs":with_zero,
             "router_balance_pairs":len(bridged),"router_balance_pairs_exact":sum(b["matched"] for b in bridged),
             "balance_exceptions":[b for b in balances if not b["matched"]],
             "hero_case":primary,"routing_totals":stats,"linked_mint_send":joined}
    return summary,rows,all_decoded,credit_rows,balances


def write_outputs(dest, evidence):
    summary, *rows = evidence
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8",newline="\n")
    for name, table in zip(("transactions","transfers","credit_routes","balance_checks"),rows):
        fields=list(dict.fromkeys(k for r in table for k in r))
        with (dest/(name+".csv")).open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n")
            w.writeheader()
            w.writerows(table)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=ROOT/"rerun",help="write fresh CSV/JSON here (default: rerun/)")
    p.add_argument("--build",action="store_true",help=argparse.SUPPRESS)
    args=p.parse_args()
    try:
        manifest_paths=verify_manifest() if not args.build else None
        if manifest_paths is not None:
            required = {str(p.relative_to(ROOT).as_posix()) for p in DATA.iterdir() if p.is_file()}
            require(required.issubset(manifest_paths), "Capture file missing from SHA-256 manifest")
            require(args.out.resolve() != (ROOT/"results").resolve(), "Use a different output folder from results/")
        evidence=build_results()
        write_outputs(args.out,evidence)
        report=evidence[0]
        if not args.build:
            for name in ("summary.json","transactions.csv","transfers.csv","credit_routes.csv","balance_checks.csv"):
                require((args.out/name).read_bytes()==(ROOT/"results"/name).read_bytes(),
                        f"Rebuilt output differs: {name}")
        print(f"PASS: {report['indexed_transfer_rows']} indexed rows; {report['corpus_transactions']} corpus transactions; "
              f"{report['additional_controls']} separate controls.")
        print(f"PASS: {report['transactions_reconciled_to_raw_logs']} transactions linked to decoded event logs; "
              f"{report['payment_routing_cases']} four-leg routing and fee-event reconciliations.")
        print(f"OBSERVED: {report['balance_pairs_exact']}/{report['balance_pairs']} account/block pairs matched; "
              f"{report['router_balance_pairs_exact']}/{report['router_balance_pairs']} on the selected routing blocks.")
        print(f"PASS: mint + send window = {token_formatter(report['linked_mint_send']['observed_combined_delta_units'])} USDr.")
        print(f"{len(report['balance_exceptions'])} point-in-time differences retained in summary.json.")
        print(f"Outputs: {args.out}")
    except (EvidenceError, OSError, KeyError, StopIteration, ValueError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
