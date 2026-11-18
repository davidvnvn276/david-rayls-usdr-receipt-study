# Sources and evidence provenance

| Source | Identifier | What it supports |
| --- | --- | --- |
| [Rayls Public Chain developer reference](https://docs.rayls.com/docs/public-chain-reference) | Public documentation, consulted 18 Nov 2026 | Network, RPC and USDr precompile identity |
| [Rayls Public Chain tokenomics](https://docs.rayls.com/docs/public-chain-tokenomics) | Public documentation, consulted 18 Nov 2026 | Described USDC.e to USDr design. Reserve and circulating-supply claims are outside this study. |
| [Rayls Get USDr](https://dapp.rayls.com/gas-token) | Official dApp route | Where a user can find the funding interface. No amount or route availability is promised. |
| [Axyl overview](https://github.com/raylsnetwork/axyl/blob/7ea68c68671dde1fe71ea0b15b4dae67f4677e37/doc/crates/execution/overview.md#L139-L173) | Commit `7ea68c68671dde1fe71ea0b15b4dae67f4677e37`; blob `acc3aca73ff04fac47944fdc94f1bb73298d3d2f` | Read-only and executed paths are described separately. The inspected source pin is not treated as the audited deployed binary. |
| [Axyl precompile implementation](https://github.com/raylsnetwork/axyl/blob/7ea68c68671dde1fe71ea0b15b4dae67f4677e37/crates/execution/evm/src/native_erc20/precompile.rs#L485-L497) | Same commit; blob `72a258bef50467411060db742ce13fbd970dd6d9` | `balanceOf` handler reads native balance |
| [Axyl execution inspector](https://github.com/raylsnetwork/axyl/blob/7ea68c68671dde1fe71ea0b15b4dae67f4677e37/crates/execution/evm/src/native_erc20/inspector.rs#L605-L625) | Same commit; blob `9a16eef4114c342fed81465b25bd4981ee50f74d` | Implementation path that emits matching successful native-value Transfer logs in the published source |
| [Stargate CreditMessaging](https://github.com/stargate-protocol/stargate-v2/blob/348621c5430064e8d79445b8c1b8136fe3fbd967/packages/stg-evm-v2/src/messaging/CreditMessaging.sol#L17-L41) | Commit `348621c5430064e8d79445b8c1b8136fe3fbd967`; blob `d5eeaa5d24e86598448b54a3a4b8f7ae8ba61e0a` | The source’s `sendCredits` forwards attached native value as messaging fee and supplies the caller as refund address. No compiled bytecode match was asserted. |
| [Rayls Explorer API](https://explorer.rayls.com/api-docs) | Explorer footer displayed Blockscout v11.2.2 on capture date | Recent token events, address transactions, per-transaction logs, block metadata and additional indexer observations |
| [Blockscout account API](https://docs.blockscout.com/devs/apis/rpc/account#return-balance-from-a-provided-block) | Legacy `account.eth_get_balance` with decimal `block` query | Semantics of the indexed historical balance lookup used in the study |
| [ERC-20](https://eips.ethereum.org/EIPS/eip-20) | EIP-20 standard | Transfer, Approval, balanceOf and zero sender convention for mint events |

The source pin identities were read directly from the upstream repositories. No upstream source files were copied into this evidence package. Event topics and addresses are decoded from the included Explorer captures. A numeric difference across views is an observation, not attribution of an implementation defect.

All claims using the saved dataset can be reproduced offline. Provider availability, historical state and a reader's fresh live results can change; the saved checks should be run before any optional live recheck.
