# Captions and placement

01 – Cover, 2000 × 800. The value field, network fee and net caller debit of one Rayls mainnet USDr transaction. Each reads a different part of the receipt and balance history.

02 – After the fee-flow example, 1600 × 900. Four USDr movements explain a single routed payment. The forwarded value and refund must not be counted again when calculating the caller's debit. The two fee events give a second breakdown of the message fee.

03 – After the zero-Value examples, 1600 × 900. A direct ERC-20 transfer, a gas-only approval and a swap can all have zero top-level Value. Their observed caller deltas tell different stories. The full dataset records the unmatched receiver balance in the direct transfer.

Regenerate the figures using `python tools/make_visuals.py` with Pillow and DejaVu Sans fonts installed. This is optional: the evidence verifier only needs the Python standard library. Visual amounts are rounded to six decimal places. Exact amounts live in `results/`.
