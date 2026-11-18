# Verify the Rayls USDr receipt study

This package lets you check how much a wallet spent in USDr after a refund and gas. It preserves the original Explorer capture and adds a separate calculation and a saved mainnet RPC comparison. Start with the [article](Article_EN.md) for the result, or follow the steps below to reproduce it.

**Quick result:** The caller of the [worked transaction](https://explorer.rayls.com/tx/0x29a651bbd3d52b4a6a961358870275113d5757468b476a885b7618ba87d5c4d2) spent **2.603705590440678034 USDr**. Its top-level Value, summed transfer legs and actual wallet debit are three different measurements.

## 1. Open the package and check Python

On Windows, extract the ZIP in File Explorer, open the folder containing `verify_review.py`, and select **Open in Terminal**. On macOS or Linux, extract the ZIP and use Terminal to change into that folder. Use Python 3.10 or later; the reviewed run used Python 3.12.14 on Linux. The scripts use only the Python standard library. They need no API key, wallet, Docker or Node.js.

Windows (PowerShell):

```powershell
py -3 --version
py -3 verify_review.py
```

If the Python launcher is unavailable but `python --version` works, use `python` instead of `py -3`. On macOS or Linux:

```bash
python3 --version
python3 verify_review.py
```

The default command runs offline. It checks the package manifest, reruns the original and separate calculations, runs six accounting and evidence controls, and compares eleven regenerated files with their saved versions. It also checks that the RPC replies correspond to their saved JSON-RPC requests and block tags. The expected lines near the end are:

```text
PASS: Five original and six reviewed outputs reproduced byte for byte.
OBSERVED: Explorer 34/37 paired balances; direct RPC 4/37 available, 4/4 exact.
OBSERVED: RPC returned 29/30 receipts; 132 state reads were pruned.
```

A `PASS` here checks the saved evidence and calculations. It does not mean that all historical reads were available or that an independent party authenticated the chain.

## 2. Keep your regenerated results

Run the same verifier with an output folder that does not already exist:

```powershell
py -3 verify_review.py --out runs/check-01
```

```bash
python3 verify_review.py --out runs/check-01
```

Open the CSV files in a text editor for full precision. If you use a spreadsheet, set the large integer columns to text; several values are larger than typical spreadsheet numeric precision. USDr has 18 decimals. The underlying accounting is done in exact integer units; figures round display values.

| Open this file | What it shows |
| --- | --- |
| [expected/review-summary.json](expected/review-summary.json) | Main counts, exact worked-transaction values, balances that differed and zero-Value examples. |
| [expected/route-audit.csv](expected/route-audit.csv) | All 23 routes, receipt components, packet GUIDs, destination EIDs, and one integer funding comparison per route. |
| [expected/wallet-balances.csv](expected/wallet-balances.csv) | All 37 indexed account/block pairs and the difference compared with logs and gas. |
| [expected/network-fees.csv](expected/network-fees.csv) | Base and priority portions of the gas fee for the 11 sampled one-transaction blocks. |
| [expected/history-height-model.csv](expected/history-height-model.csv) | The most recent recorded history height at or before each of the four mint/send lookup heights. |
| [expected/rpc-summary.json](expected/rpc-summary.json) | What the direct mainnet RPC returned for each transaction and balance pair, including unavailable reads. |
| [original/evidence/explorer/capture-index.json](original/evidence/explorer/capture-index.json) | Original URLs, collection times, sample selection and filename for each of the 132 Explorer responses. |
| [evidence/source-identities.json](evidence/source-identities.json) | Upstream source revisions, Git blob identities and three published Stargate addresses used in the analysis. |

## 3. Verify the headline example by hand

1. Open the [mainnet transaction](https://explorer.rayls.com/tx/0x29a651bbd3d52b4a6a961358870275113d5757468b476a885b7618ba87d5c4d2) at block **14,723,934**. The original Explorer files are [transaction](original/evidence/explorer/bridge-01-transaction.json), [logs](original/evidence/explorer/bridge-01-logs.json) and [State](original/evidence/explorer/bridge-01-state-changes.json).
2. In the saved logs, four events are transfers from the USDr address ending in `0400`. The caller sent **3.356289694836881444**, and EndpointV2 refunded **0.774528391116203410** to that caller. The other two legs forward funds between contracts.
3. Multiply gas used **317,481** by effective gas price **69,120,000,000** in smallest units. The result corresponds to **0.021944286720 USDr**.
4. Subtract the refund from Value and add gas: **2.603705590440678034 USDr**. In [the RPC summary](expected/rpc-summary.json), look for `case-01` and the caller beginning with `0xe37f7c80`. Compare `native_before_units` and `native_after_units`; the difference is `-2603705590440678034`. Compare those fields with the corresponding `precompile_*` fields as well.
5. The **10.068869084510644332 USDr** sum of the four logs counts all contract movements. That answers a different question than the caller’s net debit. The executor and DVN amounts partition the fee sent to the library; adding them to that transfer again would double count it.

## 4. Check the sample and the exceptions

- The original pages contain **100 USDr transfer entries** covering 28 transactions on 17–18 November 2026 UTC. The direct USDr transfer and USDr approval are separate controls. The 23 credit-message calls came from one payer, used one sending route, and had nine destination endpoint IDs. EIDs are messaging identifiers; they are distinct from chain IDs.
- Across those 23 calls, the recorded transfer legs total **174.114291420410411853 USDr** and the calculated debits total **45.151339638677541506 USDr**. Every `value_minus_floor_13_over_10_fee_units` entry is zero. These observations do not establish a universal fee formula.
- In `wallet-balances.csv`, filter `explorer_minus_expected_units` for nonzero rows. The mint and following send fit the saved history’s at-or-before lookup; their combined window matches exactly. That leaves both individual point comparisons open. The direct transfer recipient is the third exception.
- In `rpc-summary.json`, a field with `null` due to missing/pruned state does not represent a zero balance. The direct RPC returned 30 envelopes and 29 receipts, with 214 matching raw logs. The 4 available historical balance pairs were all from the headline example. The truncated historical coverage means the node did not settle the three indexed exceptions.

See [Evidence map](EVIDENCE_MAP.md) for each article claim, where to find the supporting data and the limit of that evidence.

The [article preview](Article_EN.html) places the four figures alongside the corresponding evidence. The [figure index](visuals/figures.json) gives dimensions, alternative text and placement for each editable SVG and PNG.

## 5. Repeat the direct RPC comparison (optional)

The archived RPC capture is under [evidence/rpc](evidence/rpc). Each numbered batch contains its request, response and transport record. To rerun the comparison from those files, use:

```bash
python3 rpc_evidence.py --from-saved evidence/rpc
```

On Windows, use `py -3` in place of `python3`. To send the same fixed set of 251 **read-only** queries to the public Rayls RPC, choose a new directory:

```bash
python3 rpc_evidence.py --collect runs/rpc-fresh --report runs/rpc-fresh.json
```

Create or use the `runs` directory within the extracted package. The script queries chain ID, then saves batches of transaction, receipt, block and historical balance requests. The historical `eth_call` only calls USDr `balanceOf`; no transaction is signed or sent. Fresh coverage can differ. The endpoint can return pruned state, null receipts, or transport failures, which are reported separately. A new read does not overwrite the original Explorer or RPC collection. A provider with archive data is needed for an exact read at any unavailable height.

If you are reviewing the GitHub version, the **Verify saved USDr receipt evidence** workflow runs the same offline command. Its logs and status are visible under the repository’s Actions tab when a run is available.

## What this package establishes

The calculations tie transaction Value, transfer and messaging events, gas and wallet balances together for the specified samples. The same official network can be queried by a node and by an indexer; the study does not establish independent operation of those observation sources. Matching hashes and a passing checksum do not substitute for an authenticated state proof. No destination execution, private Sovereign activity, production pricing or network-wide adoption is inferred from this sample.

The unchanged original files are under `original/` with their original manifest. This reviewed package has its own `SHA256SUMS`.
