# Editorial notes

The search question is “How do I check what I actually spent in USDr on Rayls?” The main audience is someone reading a public-chain receipt after a transfer, swap or bridge interaction.

The strongest finding is the same-unit reconciliation across three kinds of records. In 23 routed receipts, the gross entry, forward, refund and terminal charge balance exactly. The separate fee events equal the terminal charge. Four cases also match every compared account's pre/post indexed balance. This is a study of a consumer-facing accounting distinction, not a use/adoption, revenue, reserve or chain reliability study.

Use the cover as the cover only. Place the fee-flow figure after “Follow the refund before adding gas.” Place the zero-Value comparison after the examples in “Zero Value can mean a swap, an approval or a mint,” or omit that figure if the platform already shows the examples clearly. The figures round labeled quantities for readability and use the same underlying JSON as the article.

Before publishing, add the public evidence repo URL if you have uploaded it. This package was not posted, no repository was created, and no claim is made about a successful public GitHub Actions workflow.

If you want Rayls to confirm the three historical balance readings, the useful question is whether the Explorer’s block-number balance endpoint is backed by recorded snapshots in the affected cases, and which archive RPC supports exact balances at those heights. Share the hashes and the rows in `balance_checks.csv`. The article does not call the discrepancy a chain or payment fault.

| Claim | Strongest evidence | Limit |
| --- | --- | --- |
| USDr exposes the native balance through an ERC-20 interface | Official chain reference, pinned Axyl code, matching native send and direct wrapper receipts | Source review is not deployed binary attestation |
| Sampled sendCredits caller spent `Value − refund + gas` | All 23 exact message fee/log ties; four complete account-delta comparisons | Same route/caller family; not retail quotes or all bridge operations |
| A swap paid USDr at zero top-level Value | Two matched two-asset swaps and indexed deltas | Two examples, not execution-depth or price assessment |
| An allowance update did not transfer USDr | Calldata, Approval signature, zero Transfer logs and sender fee debit | One targeted control |
| Rayls-side gas-funding example minted 4.552661 USDr | USDC.e transfer, escrow and composition event amounts, mint events and matching recipient | Source-chain path not inspected; the exact mint-block balance is not resolved |
| 34/37 of the address/block comparisons match | 74 balance reads across 11 one-transaction blocks; 16 exact zero matches disclosed | One Explorer provider; does not replace a node archive read |
