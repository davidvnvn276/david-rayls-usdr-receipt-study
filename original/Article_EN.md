# How Do You Check What You Actually Spent in USDr on Rayls?

In one Rayls mainnet transaction, the explorer showed **3.356290 USDr** under Value. Four USDr transfer logs added up to **10.068869 USDr**. The sending wallet’s balance decreased by **2.603706 USDr**, including gas.

All three numbers describe the same transaction. Value is what went into the first call. The logs record what moved between addresses, including forwarding and a refund. The balance change tells you how much the caller ended up spending.

That distinction is useful the next time you read a Rayls swap, transfer or bridge receipt. Start with the wallet you care about. Work out what came in, what went out and who paid the network fee.

## Why USDr is visible in two places

USDr is the native gas coin on Rayls Public Chain. Rayls also exposes it through an ERC‑20 interface at **0x0000000000000000000000000000000000000400**. The published Axyl implementation reads the native account balance for `balanceOf`. It can also emit a USDr `Transfer` log when a call moves native value. A wallet or accounting system should therefore represent that balance once.

Here is a simple [native send](https://explorer.rayls.com/tx/0x4d39b36c5c4e12cdc79eccabffa3acd7e50213a3e651c39377d59de5e338ee80) that makes this concrete. The transaction’s input was empty and its Value was **4 USDr**. Its only log was a `Transfer` from the same sender to the same recipient for **4 USDr**, emitted at `0x0400`. The recipient’s indexed coin balance increased by **4 USDr**. The Value field and the event are two records of that same movement. Adding them would report an 8 USDr payment that never happened.

I also checked the reverse case: a [direct ERC‑20 transfer](https://explorer.rayls.com/tx/0x028c9c5af09b8500ed8f5dc781478b371049834ac463e978ce7904b133788f34) called `transfer(address,uint256)` at `0x0400` with **zero** top-level Value. The calldata and log agreed on **0.03 USDr**. The sender’s native balance decreased by **0.0336953293824 USDr**, exactly the transfer plus its network fee.

## Follow the refund before adding gas

The opening example was a [`sendCredits` call](https://explorer.rayls.com/tx/0x29a651bbd3d52b4a6a961358870275113d5757468b476a885b7618ba87d5c4d2) at block **14,723,934**. It is a Stargate credit message, used by bridge infrastructure. It is not a retail bridge quote.

The four USDr logs tell the story. The caller put **3.356289694836881444 USDr** into CreditMessaging, which forwarded the same amount to EndpointV2. EndpointV2 returned **0.774528391116203410 USDr** to the caller and sent the remainder, **2.581761303720678034 USDr**, to the send library. The two forwarding contracts had no net USDr change in the sampled balance reads.

The send library’s raw fee events give a second check inside the receipt. The executor amount was **1.532565805640508911 USDr**. The fee entries in `DVNFeePaid` summed to **1.049195498080169123 USDr**. Together they match the amount that reached the library, down to the smallest unit. They explain that transfer and should not be added to it again.

Then comes the separate Rayls network fee: **317,481 gas × 69.12 gwei = 0.021944286720 USDr**. Subtracting the refund from the initial value and adding that fee gives **2.603705590440678034 USDr**. The caller’s balance readings at blocks **14,723,933** and **14,723,934** show exactly that debit.

## Check the pattern across more than one receipt

I froze two consecutive pages of USDr transfers from Rayls Explorer. They contain **100 entries across 28 transactions**, covering **17–18 November 2026 UTC**. I matched the entries to the event emitter, indexed addresses and amount in the logs. Two separately selected ERC‑20 controls bring the total checked to **30 transactions**.

The same forwarding and refund pattern held across all **23** `sendCredits` calls in those pages. Summing the four USDr logs per call gave **174.114291 USDr** in aggregate leg volume. After refunds and gas, the calculated aggregate caller debit was **45.151340 USDr**. The log sum was about **3.86 times** that amount because it includes intermediate hops and refunds. Both numbers are useful when they describe the right thing. Neither is a network-wide average or a measure of customer payments.

For the earliest and latest `sendCredits` samples on each UTC date, I also checked every participant’s indexed native balance around the block. All **16** of those comparisons matched the event-based calculation. These four blocks each contained one transaction and no recorded withdrawals.

## Zero Value can mean a swap, an approval or a mint

Open the transfer logs before deciding what happened in a zero-Value transaction:

- A [swap at block 14,687,910](https://explorer.rayls.com/tx/0x578c41d7ad11dd2befb48f87e5df881e2827d2f4dc4a879196b1b82083cf6a31) credited the trader **41.677112904045526158 USDr** while transferring RLS out. After **0.012409056 USDr** in gas, the trader’s USDr balance rose by **41.664703848045526158 USDr**. The RLS outflow is separate.
- A [direct approval](https://explorer.rayls.com/tx/0xeb5f28a300049fa08349847ce3614cc84ae25a878ae13b42a4e2303a43cb1145) set a USDr allowance but emitted no USDr `Transfer` event. The sender’s balance fell by exactly the **0.0015360768 USDr** network fee.
- A [gas-funding composition](https://explorer.rayls.com/tx/0x253b1dbd4e53128070379ccb965fbe49679eaff90d0f2301cbeae50d3cd0d691) showed **4.552661 USDC.e** going into the Rayls-side escrow and a matching **4.552661 USDr** mint to the recipient. The mint and swap events agree on the amount and recipient, and the composer’s GUID matches the local delivery event. This checks the Rayls-side leg; it does not trace the original transfer on the source chain.

The balance data has a limit worth spelling out. **34 of 37** account/block comparisons matched, including 16 unchanged balances. The explorer history did not show the gas-funding credit at the exact mint block. Across the mint and the later 4 USDr send, it showed a net increase of **0.5514514 USDr**, exactly the mint minus the send and gas. The two individual comparisons still remain unmatched. The direct ERC‑20 transfer’s recipient was the third unmatched comparison. These are indexed balance reads from one explorer, so I have kept all three differences in the evidence rather than calling them node-level results.

## What to check in your own transaction

Open the transaction on **Rayls Mainnet** and check its status. Use **Transaction fee** for network gas. For the amount a wallet received or spent, check the **USDr events at `0x0400`**. Add amounts that reached the wallet, including refunds, then subtract amounts that left it. Subtract the network fee only for the account that paid it. If a native Value field describes the same movement, record it once. For a transaction outside the examined patterns, use a node state or trace check if the receipt alone cannot account for the movements. A history row may not exist for every event.

The companion evidence package preserves the 132 Explorer JSON responses, the sample selection and the code that rebuilds the checks. It also includes an optional read-only RPC script for comparing the captured logs and historical balance views. The measurements above use Rayls Public Chain mainnet records. They do not measure Enygma Public testnet payments or activity on private Sovereign chains.

## Sources

- [Rayls Public Chain reference](https://docs.rayls.com/docs/public-chain-reference) and [Get USDr](https://dapp.rayls.com/gas-token)
- [Axyl native balance read](https://github.com/raylsnetwork/axyl/blob/7ea68c68671dde1fe71ea0b15b4dae67f4677e37/crates/execution/evm/src/native_erc20/precompile.rs#L485-L497) and [native transfer event handling](https://github.com/raylsnetwork/axyl/blob/7ea68c68671dde1fe71ea0b15b4dae67f4677e37/crates/execution/evm/src/native_erc20/inspector.rs#L605-L625)
- [Stargate CreditMessaging source](https://github.com/stargate-protocol/stargate-v2/blob/348621c5430064e8d79445b8c1b8136fe3fbd967/packages/stg-evm-v2/src/messaging/CreditMessaging.sol#L17-L41)
- [Rayls Explorer API](https://explorer.rayls.com/api-docs), [Blockscout account API](https://docs.blockscout.com/devs/apis/rpc/account#return-balance-from-a-provided-block) and [ERC‑20 standard](https://eips.ethereum.org/EIPS/eip-20)
