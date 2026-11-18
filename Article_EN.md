# How to Check What You Actually Spent in USDr on Rayls

One Rayls transaction showed **3.356290 USDr** under Value. Its four USDr transfer logs added up to **10.068869 USDr**. The sending wallet spent **2.603706 USDr**, including gas. I checked that last number against the wallet’s balance on the mainnet RPC.

The difference comes from a refund and the way the logs record money moving through several contracts. I also checked two later calls on that route and four zero-Value calls from different senders. Together, they show how to read the receipt for the wallet you care about.

## Why do native USDr and the token view show the same funds?

On Rayls Public Chain, USDr pays for gas. It also has an ERC-20 interface at `0x0000000000000000000000000000000000000400`, usually shortened to `0x0400`. The [published Axyl implementation](https://github.com/raylsnetwork/axyl/blob/7ea68c68671dde1fe71ea0b15b4dae67f4677e37/crates/execution/evm/src/native_erc20/precompile.rs#L485-L497) reads the underlying native balance when you call `balanceOf`. Axyl can also [emit a USDr transfer event](https://github.com/raylsnetwork/axyl/blob/7ea68c68671dde1fe71ea0b15b4dae67f4677e37/crates/execution/evm/src/native_erc20/inspector.rs#L605-L625) for movement of native value.

A [4 USDr native send](https://explorer.rayls.com/tx/0x4d39b36c5c4e12cdc79eccabffa3acd7e50213a3e651c39377d59de5e338ee80) makes the distinction concrete. The transaction had empty input, Value of 4 USDr and one USDr transfer log for 4, from the same sender to the same recipient. The recipient’s indexed balance increased by **4 USDr**. Value and the event describe the same movement.

## How did 3.356290 USDr become a 2.603706 USDr debit?

The opening example is a [Stargate `sendCredits` transaction](https://explorer.rayls.com/tx/0x29a651bbd3d52b4a6a961358870275113d5757468b476a885b7618ba87d5c4d2) at Rayls block **14,723,934**. It is a bridge infrastructure call. The four USDr logs show this route:

| Leg | From → To | USDr |
| --- | --- | ---: |
| 1 | Caller → CreditMessaging | 3.356289694836881444 |
| 2 | CreditMessaging → EndpointV2 | 3.356289694836881444 |
| 3 | EndpointV2 → send library | 2.581761303720678034 |
| 4 | EndpointV2 → caller (refund) | 0.774528391116203410 |

The executor fee event recorded **1.532565805640508911 USDr**. The three fee entries in `DVNFeePaid` added up to **1.049195498080169123 USDr**. These add up to the library’s receipt exactly; they explain how the message fee is accounted for. Adding them again would count the fee twice.

The separate Rayls gas fee was **317,481 × 69,120,000,000 smallest units = 0.021944286720 USDr**. The wallet calculation is:

**3.356289694836881444 − 0.774528391116203410 + 0.021944286720 = 2.603705590440678034 USDr.**

The node returned that exact debit between blocks **14,723,933** and **14,723,934**. It also returned zero net change for both forwarding contracts and a credit matching the message fee for the send library. At both heights, native `eth_getBalance` and `balanceOf` agreed for all four addresses.

One useful cross-check: the Explorer’s saved **State** response showed a **3.378233981556881444 USDr** decrease in its coin row for the caller. That equals Value plus gas, and exceeds the node-verified debit by exactly the refund. Its USDr token row showed a **2.581761303720678034 USDr** decrease, equal to the message fee alone. These rows are views of the same transaction. For this example, the receipt’s refund and the before/after node balance tell you the net amount.

## What held across all 23 sampled calls?

I froze two consecutive Explorer pages: **100 USDr transfer entries, 28 transactions**, across **17–18 November 2026 UTC**. Two targeted controls bring the total to **30 transactions**. The 23 `sendCredits` calls came from one fee payer and used the same sending route, with nine LayerZero destination endpoint IDs. All 23 source receipts showed a distinct packet identifier. That establishes what was emitted on Rayls; this study did not check destination delivery.

Every sampled call reconciled to the smallest USDr unit. Adding all four legs on each receipt gave **174.114291 USDr** of recorded movement, versus a calculated **45.151340 USDr** of caller debits after refunds and gas. The first figure was **3.86×** the second because it counted forwarding and refunds.

I also found that in all 23 calls, the initial Value was the billed message fee multiplied by **13/10**, rounded down in the smallest unit. Refunds therefore returned about **23.08% of the initial Value**, before gas. This describes one payer’s observed funding pattern. It does not establish a Stargate pricing rule or a quote for a retail transfer.

In a separate scan at a fixed head block, I selected the latest two transactions with USDr transfer logs after the original sample, before reading their balances. The same payer spent **2.067085254607679666 USDr** at [block 14,728,392](https://explorer.rayls.com/tx/0xca4362cff32cb6517ff004c693484d6b98cd416f013c74d7a677cd1c054328bf) and **1.716349347288480000 USDr** at [block 14,729,950](https://explorer.rayls.com/tx/0x81d8c4d3dd5298dcadcf24873ea5327ee93d113b5dc6dea53d0111226c8b8a06). All eight before/after account comparisons matched the receipts. In both calls, using Value plus gas would overstate the debit by exactly the refund.

## What can move when the Value field is zero?

In one [new contract call at block 14,734,206](https://explorer.rayls.com/tx/0xc908fc4984fb3a337c6db440cd849f3b36bcc1b4e63876a9b91ef7954becdcee), Value was zero and the receipt had no USDr transfer log. The payer’s native balance went from **1** to **0.997187344 USDr**: an exact **0.002812656 USDr** gas debit. I observed that same relationship in **four calls from four distinct payers**, each in its own one-transaction block. This checks the payer’s USDr cost; other application outcomes need evidence of their own.

| Example | What the USDr evidence showed |
| --- | --- |
| [Direct ERC-20 transfer](https://explorer.rayls.com/tx/0x028c9c5af09b8500ed8f5dc781478b371049834ac463e978ce7904b133788f34) | The calldata and log showed 0.03 USDr sent. The sender’s indexed balance fell by 0.0336953293824 USDr, including gas. |
| [RLS swap](https://explorer.rayls.com/tx/0x578c41d7ad11dd2befb48f87e5df881e2827d2f4dc4a879196b1b82083cf6a31) | The trader received 41.677112904045526158 USDr and spent 0.012409056 USDr in gas. RLS moved out separately. |
| [Allowance approval](https://explorer.rayls.com/tx/0xeb5f28a300049fa08349847ce3614cc84ae25a878ae13b42a4e2303a43cb1145) | No USDr transfer log; the caller’s indexed debit was the 0.0015360768 USDr gas fee. |
| [Gas funding on Rayls](https://explorer.rayls.com/tx/0x253b1dbd4e53128070379ccb965fbe49679eaff90d0f2301cbeae50d3cd0d691) | Local events recorded 4.552661 USDC.e sent to escrow and 4.552661 USDr minted to the recipient. A different address paid the local gas. This does not trace the source chain. |

## Which balance evidence was available?

For the original sample, the mainnet RPC cross-check matched **30 transaction envelopes and 29 receipts**, including **214 raw logs**, to the saved Explorer data. The old transfer-control receipt returned null. Of **37** historical balance pairs, **4** were available and all matched; the other 33 were pruned. The follow-up added **12 exact balance comparisons in six separate transactions**. I keep those counts separate because the selection methods differ.

The original Explorer’s indexed balances matched **34 of 37** comparisons, including 16 unchanged balances. Two exceptions involve the funding mint and the later 4 USDr send by the same wallet. The combined indexed gain, **0.5514514 USDr**, reconciles exactly, but neither point reading settles the timing. The third exception is the old transfer recipient. The package retains all three and the underlying balance-history rows.

All direct state reads used the same Rayls RPC. I requested eight account proofs for the worked case and selected follow-ups; the node returned its historical proof-window error on all eight. The balances are fixed-height RPC observations. The study does not authenticate them against state roots, or check destination delivery for the bridge packets.

## How to check your own receipt

1. Open the transaction on Rayls Public Chain and check its status, payer and transaction fee.
2. For the wallet you are checking, add **USDr received** and subtract **USDr sent** using the events at `0x0400`. A refund is an inflow. If Value and a transfer log describe the same movement, count it once.
3. Subtract gas only from the wallet that paid it. If you need an exact balance check, compare native balance at the transaction’s block and its parent. Those readings include all changes in the block, so a busier block may require transaction-level tracing.

If you need to fund gas, [Rayls’ Get USDr page](https://dapp.rayls.com/gas-token) is a starting point. The receipt can tell you which assets moved on Rayls and how much the wallet paid there.

The evidence package includes the selection records, raw RPC requests and replies, exact calculations and an offline verifier. Run `python verify_review.py` from the extracted folder to check both datasets and the controls. The archived proof and pruning errors remain visible in the results.

## Sources

- [Rayls Public Chain reference](https://docs.rayls.com/docs/public-chain-reference)
- [Stargate CreditMessaging source and refund forwarding](https://github.com/stargate-protocol/stargate-v2/blob/348621c5430064e8d79445b8c1b8136fe3fbd967/packages/stg-evm-v2/src/messaging/CreditMessaging.sol#L17-L41)
- [LayerZero packet layout](https://github.com/LayerZero-Labs/LayerZero-v2/blob/9c741e7f9790639537b1710a203bcdfd73b0b9ac/packages/layerzero-v2/evm/protocol/contracts/messagelib/libs/PacketV1Codec.sol)
- [Blockscout reference for returning a balance by block](https://docs.blockscout.com/devs/apis/rpc/account#return-balance-from-a-provided-block) and [upstream indexed lookup implementation](https://github.com/blockscout/blockscout/blob/731015d88d7e73623f2a3c097e241bc82b04ea7a/apps/explorer/lib/explorer/etherscan/blocks.ex#L25-L35)
- [EIP-1186: account and storage proof RPC](https://eips.ethereum.org/EIPS/eip-1186)
