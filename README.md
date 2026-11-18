# Verify the Rayls USDr receipt study

This guide lets you reproduce the article’s numbers from the saved evidence, trace a claim back to an actual request and response, and distinguish a verified calculation from a missing historical observation. The publication bundle preserves the original data, the reviewed RPC capture, the six follow-up transactions, and the tests from the V2 study. The article and figures use those same results.

The internal links in this guide are relative to the extracted ZIP. Open the `README.md` inside that folder to follow them.

**Worked result:** At Rayls mainnet block **14,723,934**, the [caller’s transaction](https://explorer.rayls.com/tx/0x29a651bbd3d52b4a6a961358870275113d5757468b476a885b7618ba87d5c4d2) carried **3.356289694836881444 USDr** in top-level Value. The four USDr transfer logs sum to **10.068869084510644332 USDr**. After the refund and network gas, the caller’s observed debit was **2.603705590440678034 USDr**. Each number answers a different question.

| If you want to… | Start here |
| --- | --- |
| Read the argument before checking data | [Article in HTML with figures](Article_EN.html) or [article in Markdown](Article_EN.md) |
| Run every archived check with one command | [1. Unpack and run offline](#1-unpack-and-run-offline) |
| Check the headline by hand | [3. Verify the worked transaction](#3-verify-the-worked-transaction) |
| Check cases, controls, or missing observations | [4. Separate the samples and exceptions](#4-separate-the-samples-and-exceptions) and [5. Test failures](#5-test-failures) |
| Go from one article sentence to its evidence | [Claim-by-claim evidence map](EVIDENCE_MAP.md) |

## 1. Unpack and run offline

**Requirements:** Python 3.10 or newer, using only its standard library. No package installation, API key, wallet, Docker, or network connection is required for the saved-data replay. The recorded clean-extraction run used Python 3.12.14 on Linux.

### Windows, from File Explorer

1. Download the full ZIP. Right-click it and choose **Extract All**. Wait for extraction to finish; do not run files from the compressed folder view.
2. Open the extracted `david-week3-usdr-final` folder. It should show **README.md**, **verify_review.py**, **SHA256SUMS**, and the `expected`, `evidence`, and `original` folders together. If you see another folder with the same name, open it.
3. In that folder’s address bar, type `powershell` and press **Enter**. In the window that opens, run:

```powershell
Get-Location
Get-Item .\verify_review.py
py -3 --version
py -3 verify_review.py
```

If `py` is not recognized but `python --version` shows Python 3.10 or later, use `python verify_review.py`. If both commands are unavailable, install [Python](https://www.python.org/downloads/) and reopen the terminal. A Python version number is sufficient; there is no `pip install` step for the verifier.

If you open PowerShell first, use `Set-Location "C:\path\to\david-week3-usdr-final"` with the folder you actually extracted. Quotes keep spaces in the path together.

### macOS or Linux

Extract the ZIP, open a terminal, and go to the extracted folder. Replace the example path with your own:

```bash
cd "/path/to/david-week3-usdr-final"
pwd
ls verify_review.py
python3 --version
python3 verify_review.py
```

### What success looks like

The verifier checks the reviewed SHA-256 manifest, runs the original capture’s checks, recalculates the route and balance results, replays archived RPC request/response pairs, and runs eight local controls. It compares all twelve regenerated artifacts with the bundled versions byte for byte. Look for these lines near the end:

```text
PASS: Five original and seven reviewed outputs reproduced byte for byte.
OBSERVED: Original Explorer 34/37 paired balances; original RPC 4/37 available, 4/4 exact.
OBSERVED: Follow-up six transactions; 12/12 direct balance comparisons exact.
OBSERVED: Original RPC 29/30 receipts; eight follow-up account-proof requests hit the proof window.
A pass checks saved data and calculations. It does not independently authenticate chain state.
```

A passing replay is compatible with missing historical results. The missing results are recorded inputs, so silently replacing them with zero or discarding the affected rows would break the audit.

## 2. Keep the files you rebuild

Without arguments, the verifier uses a temporary folder. To keep the rebuilt reports, use a **new** output directory. If `runs/review-01` already exists, choose `runs/review-02` instead.

```powershell
py -3 verify_review.py --out runs/review-01
Get-ChildItem .\runs\review-01\reviewed
```

```bash
python3 verify_review.py --out runs/review-01
ls runs/review-01/reviewed
```

The run writes five files under `runs/review-01/original/` and seven under `runs/review-01/reviewed/`. The reference outputs and captures remain unchanged. Use a text editor for CSV and JSON with large integers; spreadsheet defaults may round the last digits. USDr has **18 decimals**. The analysis uses integers in the smallest units, while figures use rounded display amounts.

| Saved output | What to look for |
| --- | --- |
| [expected/review-summary.json](expected/review-summary.json) | `hero` for the worked transaction, `counts` for the original sample, `balance_exceptions` for all three indexed differences |
| [expected/route-audit.csv](expected/route-audit.csv) | All 23 original credit calls: `net_debit_units`, `refund_units`, `transfer_leg_sum_units`, executor and DVN amounts, packet GUID, and destination EID |
| [expected/wallet-balances.csv](expected/wallet-balances.csv) | The 37 original indexed pairs, the amount expected from logs and gas, and `explorer_minus_expected_units` |
| [expected/network-fees.csv](expected/network-fees.csv) | Gas split into base and priority portions for the 11 sampled one-transaction blocks |
| [expected/history-height-model.csv](expected/history-height-model.csv) | The history row at or before each of the four requested mint/send heights used in the indexer explanation |
| [expected/rpc-summary.json](expected/rpc-summary.json) | Receipt, log, and balance comparison coverage; raw deltas and missing reads in `state_rows` |
| [expected/followup-summary.json](expected/followup-summary.json) | Two later bridge cases, four zero-Value cases, and eight historical account-proof errors |

The [original capture index](original/evidence/explorer/capture-index.json) records the selected transactions, 132 Explorer response files, their URLs, and collection times. [Source identities](evidence/source-identities.json) records the upstream revisions and deployment references used in the analysis. Those files document provenance; they do not add another operator for the RPC observations.

## 3. Verify the worked transaction

All amounts below refer to the Rayls source chain, **chain ID 72957**. Use the complete hash to identify the transaction, rather than its label or a rounded amount. The live Explorer is convenient for orientation, but the frozen files are the inputs to the replay.

### 3.1 Match the receipt and four USDr logs

1. Open the [worked transaction](https://explorer.rayls.com/tx/0x29a651bbd3d52b4a6a961358870275113d5757468b476a885b7618ba87d5c4d2) and identify its payer `0xe37f7c80ced04c4f243c0fd04a5510d663cb88b5`, top-level Value, successful receipt, and block **14,723,934**.
2. In the saved [request batch](evidence/rpc/01.request.json) and [response batch](evidence/rpc/01.response.json), match **ID 3** for the transaction envelope and **ID 4** for the receipt. Use the matching transaction and block identity before reading the amounts.
3. In the [eight saved Explorer logs](original/evidence/explorer/bridge-01-logs.json), the four USDr transfer events have indexes **4–7**, the emitter `0x0000000000000000000000000000000000000400`, and first topic `0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef`. The next two topics encode the sender and recipient. The hex `data` field is the integer amount.
4. Separate the legs by their parties. The caller sends Value to CreditMessaging; that contract forwards the same amount to EndpointV2. EndpointV2 sends the remaining fee to the send library and returns the refund to the original caller. The four legs are movements; the payer does not pay every leg again.

### 3.2 Rebuild the cost

| Measurement | Exact amount in USDr | Where to check it |
| --- | ---: | --- |
| Caller’s top-level Value | 3.356289694836881444 | `hero.gross_value_units` and the transaction’s `value` |
| Refund to the caller | 0.774528391116203410 | `hero.refund_units` and the EndpointV2 → caller log |
| Message fee after the refund | 2.581761303720678034 | `hero.message_fee_units` and the send-library leg |
| Network gas fee | 0.021944286720000000 | `317,481 × 69,120,000,000` smallest units |
| Caller net debit | 2.603705590440678034 | Value minus refund plus network gas |
| Gross sum of all four legs | 10.068869084510644332 | `hero.transfer_leg_sum_units`; includes forwarding and the refund |

The exact integer debit calculation is:

```text
3,356,289,694,836,881,444
- 774,528,391,116,203,410
+  21,944,286,720,000,000
=2,603,705,590,440,678,034 smallest units
```

In `route-audit.csv`, `executor_fee_units` and `dvn_fee_units` for this receipt sum to the message fee. They describe the component amounts of the observed fee leg, not a second amount to add to the payer’s debit. The separate network gas fee is computed from gas used and effective gas price.

### 3.3 Check the payer’s balance independently of the log sums

In the [balance requests](evidence/rpc/09.request.json) and their [replies](evidence/rpc/09.response.json), **IDs 104–105** are native balance reads for that payer at blocks **14,723,933** and **14,723,934**, in that order. **IDs 106–107** call `balanceOf` at the USDr precompile at the same address and heights. The request IDs connect each reply to its method, address, and block tag.

In `rpc-summary.json`, find the `state_rows` entry for `case-01` and the payer above:

| Payer balance | Before | After |
| --- | ---: | ---: |
| Native balance, smallest units | 358315996176546923848 | 355712290586106245814 |
| `balanceOf`, smallest units | 358315996176546923848 | 355712290586106245814 |

The signed change `after − before` equals **−2603705590440678034** smallest units. The debit is the magnitude of that change. The two balance interfaces agree for these reads; they do not make two wallets or two debits. [The archived Explorer State view](original/evidence/explorer/bridge-01-state-changes.json) lists different coin and token changes. In this worked example, its coin change is more negative than the indexed payer change by exactly the refund. Use the tied receipt and block-bound balance pair to answer the payer-debit question.

## 4. Separate the samples and exceptions

The sample groups have different selection methods. None is a count of all Rayls bridge traffic, independent routes, or users.

| Group | Selection and result | How to check |
| --- | --- | --- |
| Original transfer pages and controls | 100 indexed transfer entries correspond to 28 transactions. A direct transfer and an approval are two separate controls. The direct RPC returned 30 transaction envelopes and 29 receipts, with 214 matching raw logs. | Open `original/evidence/explorer/capture-index.json` and `expected/rpc-summary.json`. |
| Original credit calls | 23 calls, one payer and one sending route, nine distinct destination endpoint IDs. Values and receipts reconcile as reported. An endpoint ID is a messaging identifier and is not necessarily a chain ID. | In `expected/route-audit.csv`, check `payer`, `credit_messaging`, `destination_eid`, and the packet and fee fields. |
| Later bridge follow-up | The two latest observed USDr-log transactions above the original sample end in a fixed block scan were selected before reading their balances. Eight exact balance pairs across these two calls; the payer and route are still the same. | In `followup-summary.json`, open `scan` and `separate_recent_routes`. |
| Zero-Value follow-up | Four successful zero-Value calls from four different payers, with their own one-transaction blocks. No USDr transfer events in these receipts; the payer debit equals network gas in each. | In `followup-summary.json`, open `zero_value_cases` and inspect each payer’s `balance`. |

### 4.1 What the follow-up actually tests

For the two later bridge cases at blocks **14,728,392** and **14,729,950**, compare `value_plus_gas_units` with `net_debit_units`. The first exceeds the second by the exact refund in both. Then compare `transfer_leg_sum_units` with `net_debit_units` to see the effect of summing intermediary movements. The [follow-up captures](evidence/followup/) contain the receipt plus the parent and inclusion block reads for both cases.

For a second way to verify the method, open `alternate-01` at block **14,734,206** in the same summary. Its Value is zero. Its payer goes from **1** to **0.997187344 USDr**, an exact **0.002812656 USDr** debit. The archived [receipt requests](evidence/followup/alternate-01-receipt.request.json) and [responses](evidence/followup/alternate-01-receipt.response.json) and [payer reads](evidence/followup/alternate-01-payer.response.json) preserve the inputs. A receipt may contain events from other contracts, so check the USDr emitter before using a log as USDr movement.

### 4.2 How to read missing or differing results

- **Indexed balance comparisons:** 34/37 match, including 16 unchanged balances. Filter `wallet-balances.csv` for nonzero `explorer_minus_expected_units` to see the three exceptions. For the two observations on the funding-mint/later-send wallet, the combined **0.5514514 USDr** gain matches, while the two individual point comparisons remain unresolved. The separate older transfer recipient is the third exception. The history-height model is an explanation consistent with the saved rows, not a replacement of any observations.
- **Direct historical balances:** 4/37 original pairs were available; all four match. The other 33 pairs were pruned, giving 132 failed state reads across their before/after native and precompile queries. The old direct-transfer receipt returned `null`. Neither a pruned read nor a null receipt is a zero balance or evidence that a transaction did not occur.
- **Proof requests:** Eight saved historical `eth_getProof` queries returned error `-32602`, with the message `distance to target block exceeds maximum proof window`. They are under `unavailable_account_proofs`. The paired balance observations come from one official RPC and are not authenticated account proofs. The capture does not establish a separate operator or authenticate a header against a consensus anchor.

## 5. Test failures

The full offline command runs the tests below on **local copies of saved inputs**. These are controls for the stated claims, not additional observed network transactions.

| Local check | What it tests |
| --- | --- |
| Treat gross forwarding as the total cost | The intermediary movements and refund cannot stand in for the net debit |
| Change a fee component while keeping the legs | The executor and DVN amounts no longer reconcile with the message charge |
| Count an approval or another asset as a USDr transfer | The result has to use the specified USDr emitter and event |
| Hide the three unresolved indexed comparisons | The exception set is preserved and checked |
| Keep four valid transfer legs but change packet destination | Those legs alone do not validate the messaging destination |
| Turn pruned state into a zero observation | An explicit state gap cannot be counted as a measured zero |
| Retag the after-balance with the parent height | The block binding is checked along with the value |
| Edit both balance interfaces by the same smallest unit | Agreement between the interfaces is insufficient if their delta disagrees with the receipt |

The four earlier controls are in [original/tests](original/tests/); the four reviewed controls are in [tests](tests/). From the package root, the exact archived comparison can also be rerun in parts:

```powershell
py -3 rpc_evidence.py --from-saved evidence/rpc
py -3 verify_followup.py
py -3 -m unittest discover -s tests -v
```

On macOS or Linux, substitute `python3` for `py -3`. Use the full verifier when you also want the manifest, the original dataset’s tests, and byte-for-byte output comparisons in one run.

## 6. Optional fresh RPC read

This is separate from the offline checks. Choose a **new** path under `runs` so the archived responses remain frozen. The script makes 251 read-only requests for the original comparison. It never signs a transaction or submits one to the network.

```powershell
py -3 rpc_evidence.py --collect runs/rpc-fresh-01 --report runs/rpc-fresh-01.json
```

```bash
python3 rpc_evidence.py --collect runs/rpc-fresh-01 --report runs/rpc-fresh-01.json
```

The query set is fixed. It includes chain ID, transaction, receipt, block, and historical balance requests; its `eth_call` reads `balanceOf`. Request, response, and transport metadata are saved in the new folder. A later run may have different historical coverage or transport errors. Compare the exact block and method before comparing values. This command is not required for reproduction of the archived study.

If reviewing a repository run, the **Verify saved USDr receipt evidence** workflow uses the offline command. It pins **Python 3.12.14 on Ubuntu 24.04** and **Python 3.13.11 on Windows 2025**, with UTF-8 mode enabled on both. These exact versions have distributions for their selected runners. The earlier Windows setup requested Python 3.12.14, which has no Windows distribution in the setup-python version manifest; it failed before the evidence checks started. A configured workflow and an executed job are different records; verify the result against the repository revision you are reviewing.

## 7. Troubleshoot the offline run

| What you see | What to do |
| --- | --- |
| Python cannot open `verify_review.py` | Check `Get-Location` or `pwd`. Open the extracted folder that actually contains the script. |
| Command `py` or `python3` not found | Use the working Python command for your system and confirm the version is at least 3.10. |
| Output directory already exists | Use another new `runs/` directory. The archived inputs should not be overwritten. |
| Missing path, wrong hash, or an extra file in the manifest check | Extract a fresh copy. Keep the archived files unchanged and put your regenerated reports in `runs/` or outside the package. For editing or analysis, use separate copies. |
| RPC errors when running the optional fresh command | Inspect that run’s transport and message fields. Run the default offline command to check the archived evidence. |
| Spreadsheet values have lost digits | Reopen the raw CSV or JSON in a text editor, or import the smallest-unit columns as text. |

## 8. Article and figures

The [standalone HTML](Article_EN.html) includes the complete article and the four embedded PNGs. [Markdown](Article_EN.md) is the same text. The figure index [visuals/figures.json](visuals/figures.json) includes alt text and placement, and the PNGs have matching SVG sources.

| Figure | Size | What it shows |
| --- | --- | --- |
| [00-cover-usdr.png](visuals/00-cover-usdr.png) | 2500 × 1000, 5:2 | Value, sum of legs, and net debit in the worked transaction |
| [01-usdr-refund-route.png](visuals/01-usdr-refund-route.png) | 2400 × 1350 | Where the payer’s Value, refund, and gas enter the calculation |
| [02-usdr-value-examples.png](visuals/02-usdr-value-examples.png) | 2400 × 1440 | What can occur in a zero-Value transaction |
| [03-usdr-evidence-coverage.png](visuals/03-usdr-evidence-coverage.png) | 2400 × 1410 | The separate original and follow-up evidence coverage |

The study establishes how the inputs reconcile for the selected source-chain cases. It does not establish destination delivery, private Sovereign activity, a universal pricing formula, network-wide usage, or independently authenticated chain state. The unchanged original inputs and original manifest remain under `original/`.
