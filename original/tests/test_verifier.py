"""Check that plausible accounting mistakes do not pass on observed fixtures."""
import copy
import json
import unittest

from verify import (
    APPROVAL, DATA, EvidenceError, Q, USDR, build_results, event_net,
    read_credit_flow, token_formatter, transfer,
)


class EvidenceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tx = json.loads((DATA/"bridge-01-transaction.json").read_text())
        cls.logs = json.loads((DATA/"bridge-01-logs.json").read_text())["items"]
        cls.legs = [r for l in cls.logs if (r := transfer(l)) is not None]

    def test_labelling_gross_forwarding_as_total_cost_overstates_actual_debit(self):
        r = read_credit_flow(self.tx,self.logs,self.legs)
        self.assertEqual(token_formatter(r["caller_debit_units"]),"2.603705590440678034")
        self.assertEqual(r["sum_transfer_rows_units"],3*int(self.tx["value"]))
        self.assertNotEqual(r["sum_transfer_rows_units"],r["caller_debit_units"])
        self.assertEqual(-event_net(self.legs,r["payer"])+r["gas_units"],r["caller_debit_units"])

    def test_fee_split_mismatch_fails_even_if_transfer_legs_match(self):
        mutated = copy.deepcopy(self.logs)
        record = next(l for l in mutated if (l.get("decoded") or {}).get("method_call","").startswith("ExecutorFeePaid"))
        record["data"] = record["data"][:-64]+f"{int(record['data'][-64:],16)+1:064x}"
        with self.assertRaisesRegex(EvidenceError,"Fee events do not reconcile"):
            read_credit_flow(self.tx,mutated,self.legs)

    def test_neither_approval_nor_another_asset_counts_as_usdr_movement(self):
        original = json.loads((DATA/"control-approve-logs.json").read_text())["items"][0]
        self.assertEqual(original["topics"][0],APPROVAL)
        self.assertIsNone(transfer(original))
        fake_asset=copy.deepcopy(next(l for l in self.logs if l["address"]["hash"].lower()==USDR))
        fake_asset["address"]["hash"]="0x"+"a"*40
        self.assertIsNone(transfer(fake_asset))

    def test_known_unresolved_snapshots_are_visible(self):
        summary,*_=build_results()
        d={r["case_id"]:r["difference_units"] for r in summary["balance_exceptions"]}
        self.assertEqual(set(d),{"case-25","case-26","control-transfer"})
        self.assertEqual(d["case-25"],-d["case-26"])
        self.assertEqual(d["control-transfer"],-3*Q//100)
        self.assertEqual(summary["linked_mint_send"]["observed_combined_delta_units"],551_451_400_000_000_000)


if __name__=="__main__":
    unittest.main()
