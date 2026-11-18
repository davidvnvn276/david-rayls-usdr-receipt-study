# Reproduce the Rayls USDr receipt study

This package answers a narrow question: how much USDr actually left or reached a specified wallet when a Rayls transaction shows several amounts?

**Network:** Rayls Public Chain mainnet (documented chain ID `72957`).  
**USDr interface:** `0x0000000000000000000000000000000000000400`.  
**Capture time:** 18 November 2026, 09:00:39 to 09:10:53 UTC (16:00:39 to 16:10:53 UTC+7, rounded to seconds).  
**Inputs:** 132 saved public Rayls Explorer JSON responses. All work was read-only. No wallet, signed transaction, API key, real-funds transfer, or installation of any dependencies was required for the offline run.

## Run it on Windows, start to finish

1. Download the evidence ZIP. In File Explorer, right-click it, select **Extract All**, choose a folder, then select **Extract**. Do not run the script from inside the ZIP.
2. Open the extracted folder named `david-week3-usdr`. You should see `README.md`, `verify.py`, `recheck_rpc.py`, `SHA256SUMS`, `evidence` and `results`.
3. Click the folder’s address bar in File Explorer. Type **powershell** and press **Enter**. The terminal should open in that folder. Run `Get-ChildItem verify.py` if you want to check.
4. Check that Python is available. This uses Python **3.10 or newer**. There are no packages to install.

   ```powershell
   py -3 --version
   ```

   If `py` is unavailable but `python --version` works, replace `py -3` with `python` in the commands below. If both fail, install Python from [python.org](https://www.python.org/downloads/), reopen PowerShell and repeat step 4. On macOS or Linux use `python3` and open the extracted directory in Terminal.

5. Verify the files and rebuild the results **offline**:

   ```powershell
   py -3 verify.py
   ```

6. Run the four offline accounting controls:

   ```powershell
   py -3 -m unittest discover -s tests -v
   ```

7. Open `rerun/summary.json` in a text editor. The new files in `rerun/` must match the five result files under `results/` byte for byte. The `results/` directory is the original run; the command does not change it. `verify.py` will stop on a bad checksum, broken receipt/log link, partial page or changed result. If an output folder is unwritable, use `py -3 verify.py --out fresh-results`.

You should see:

```text
PASS: 100 indexed rows; 28 corpus transactions; 2 separate controls.
PASS: 30 transactions linked to decoded event logs; 23 four-leg routing and fee-event reconciliations.
OBSERVED: 34/37 account/block pairs matched; 16/16 on the selected routing blocks.
PASS: mint + send window = 0.5514514 USDr.
3 point-in-time differences retained in summary.json.
```

The three different balance readings are expected in this **saved** dataset. They are reported in `summary.json` and `balance_checks.csv`. The verifier checks that they are preserved; it does not make them pass by treating them as zero differences.

## Verify the headline transaction by hand

1. Open the [`sendCredits` transaction on Rayls Explorer](https://explorer.rayls.com/tx/0x29a651bbd3d52b4a6a961358870275113d5757468b476a885b7618ba87d5c4d2). On **Details**, check that it succeeded in block **14,723,934**, has Value **3.356289694836881444 USDr**, and used **317,481** gas at **69.12 gwei**. The interface may round long numbers; exact amounts are in the saved JSON.
2. Click **Token transfers** or **Logs**. Compare addresses and values; do not infer execution order from the transfer log numbers. The logs show a payment to CreditMessaging, forwarding to EndpointV2, a refund to the original sender, and a transfer to the SendUln302 library.
3. Open `evidence/explorer/bridge-01-logs.json`. In a USDr `Transfer` log, the emitter is `0x0400`, topic 0 is the ERC‑20 Transfer signature hash, topics 1 and 2 encode sender and recipient, and the 32-byte data word is the amount in smallest units. The first 12 bytes of each indexed address topic are padding. Divide a decoded USDr integer by `10^18` to display the token amount.
4. Open `results/credit_routes.csv` and find `case-01`. Verify the arithmetic with the integers below. Some spreadsheet programs truncate integers longer than 15 digits. Use a text editor, import these columns as **Text**, or use Python rather than pasting the numbers into ordinary numeric spreadsheet cells.

   ```text
   Top-level Value                    3,356,289,694,836,881,444
   Refund                             -774,528,391,116,203,410
   Net message fee                   2,581,761,303,720,678,034
   Network fee                         21,944,286,720,000,000
   Net wallet debit                  2,603,705,590,440,678,034
   ```

5. To check the fee twice, add the `ExecutorFeePaid.fee` word to the sum of the three `DVNFeePaid.fees[]` words. Both events come from the send-library address. Their sum equals the net message fee. They are metadata about that same amount, so do not charge them on top of the transfer. This study does not map each fee entry to an individual service provider.
6. Open the two files named `bridge-01-caller-coin-before.json` and `bridge-01-caller-coin-after.json`. Convert the two hexadecimal results to integers and subtract before from after. These are the captured legacy **Explorer** account balance responses, not raw node RPC. The difference is negative **2,603,705,590,440,678,034** smallest units. The block response is in `bridge-01-block.json`.

To see current Explorer responses for any saved query, open `evidence/explorer/capture-index.json`, find the filename and open its URL in a browser. Some lists paginate from the latest available record; the bundled first page and its cursor preserve the actual sample. Do not substitute newer pages and expect 100 identical rows.

## Optional: corroborate a case with a node RPC

This step requires a Rayls mainnet RPC endpoint that serves historical state. It is a separate read-only check. **It was not used to produce the recorded results.** The included script passes the offline syntax check. Its live result will depend on the node and the available history.

```powershell
py -3 recheck_rpc.py --case case-01
```

The script uses [Rayls’ documented public RPC](https://docs.rayls.com/docs/public-chain-reference). It checks the chain ID and saved block hash, fetches the transaction and receipt, and compares the USDr topics and data and effective gas bill. For each account it asks for native `eth_getBalance` and `balanceOf(address)` at the same two block numbers. It does not use the current balance in place of an unavailable historical balance. The responses and comparison are written in a new `rpc_rechecks/` folder. A missing archive response stops the run and is not evidence of a zero balance.

To investigate the three unmatched Explorer readings, run:

```powershell
py -3 recheck_rpc.py --case case-26 --case case-25 --case control-transfer
```

For provider comparison, supply a second known Rayls mainnet HTTPS RPC with `--rpc`. Saving replies from a second endpoint does not by itself prove it is independently operated. Record the provider and whether both endpoints returned the same anchored block and state. The script will not accept a different chain ID.

## How the dataset was selected

- The first two pages of the `0x0400` token-transfer listing returned 50 rows each. Page 2 uses the exact continuation cursor returned on page 1. The 100 rows span **17 Nov 12:20:42 to 18 Nov 08:40:05 UTC**, blocks **14,669,517–14,723,934**. The same transaction can appear on both pages with different log indices. The verifier groups by hash and checks the unique `(transaction hash, log index)` pairs.
- Every one of the 28 transactions was checked against its captured logs response. The breakdown is 23 `sendCredits` calls, two swaps, one native transfer, one composition mint and one `execute` call. These are the contents of the two pages, a token-event sample. They are not an activity census or an unbiased sample of wallets or dApps. All 23 credit calls came from the same sender in these pages.
- Two direct `0x0400` controls were chosen separately: the most recent successful `transfer` and `approve` to that address visible in its archived first page of transactions. The direct transfer dates to 25 October 2026; the approval is from 17 November. They are not included in the 100-row or 28-transaction counts.
- For the balance checks, take the first and last credit call on each UTC date and all five other transactions from the corpus, plus both controls. All 11 blocks had one recorded transaction and no withdrawals. For each, compare block B−1 with block B for all distinct nonzero addresses appearing as caller, target, or endpoint of a USDr transfer. The verifier also checks that none of those addresses is the sampled block’s gas-tip beneficiary.
- There are 37 account/block pairs (two reads per pair). Of 34 exact matches, 16 were zero changes and 18 were nonzero changes. Each of the four selected credit transactions contributes four account comparisons. This corroborates the 23 receipt-level calculations for **four**, rather than all 23, cases.
- Fee in smallest units is `gas_used × gas_price` using the actual transaction fee fields captured from Explorer. When reconstructing a compared account’s change, sum token movements signed by direction and subtract this fee only from the transaction caller. The method is tested for the recorded cases; other types of native balance changes may need tracing or state checks. Mint’s zero-address leg is recognized as issuance, not a funded account.

## Three balance differences, all retained

1. For `case-26`, the mint recipient’s indexed balance response stayed at **0.254455638976414746 USDr** on both requested heights, although the Transfer from the zero address, the Mint events and the swap/composition events agree on **4.552661 USDr**.
2. For the same address in `case-25`, the indexed balance change was **+0.5514514 USDr**. The outgoing transfer and network fee account for **−4.0012096 USDr** by themselves. The difference is exactly the earlier **4.552661 USDr** credit. The captured coin balance history has a single row in that interval, at the second block, with the combined change. The combined interval reconciles, while the two original point-in-time comparisons remain unmatched.
3. In `control-transfer`, calldata, log, and sender balance confirm its 0.03 USDr debit plus sender gas, but the recipient’s indexed point-in-time balance stayed unchanged. The exact recipient balance at that block is not authenticated by this capture.

These are observations about **what the captured Explorer queries returned**. The reason for each historical index result is not established. The dates, addresses and unaltered numeric values are available for follow-up. The State tab data for the main example is archived as additional context, but it is not substituted for the pre/post-block reads. Raw log bytes, transaction details and account snapshots come from different Explorer interfaces operated through the same service; this is cross-checking different records, not proving independence between providers. The study does not verify full source-chain delivery, production validator binaries, a state root, reserves, or private institutional transactions.

## Read the files

- `results/summary.json`: headline numbers, sample sizes, exact differences and the linked mint/send check.
- `results/transactions.csv`: every case, block hash, gas and method, with the amount expected for the caller.
- `results/transfers.csv`: decoded USDr logs with emitter filtering, direction and exact amounts.
- `results/credit_routes.csv`: the 23 routed calls, refunds, retained amounts and decoded LayerZero fee events.
- `results/balance_checks.csv`: observed and calculated deltas for every compared address.
- `evidence/explorer/capture-index.json`: query URLs, capture timestamps and the case-to-file mapping. The JSON bodies were archived from displayed live responses. Formatting in the first response comes from Swagger. They are not signed attestations.
- `evidence/sources.md`: official documentation and pinned code, with what each source supports.
- `Article_EN.md`: article draft. `visuals/`: publication figures and captions. `EDITOR_NOTES.md`: claim and placement notes for the author.
- `SHA256SUMS`: consistency check for the delivered files. A matching hash confirms matching bytes, not the truth of the source.

If you publish this folder on GitHub, keep the raw captures and `results/` together. Link directly to the repository’s README or a pinned commit so another reader can reproduce the version used in the article.
