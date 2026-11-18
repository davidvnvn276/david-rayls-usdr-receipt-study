"""Local controls for the new packet and node comparison paths."""
from pathlib import Path
import json
import shutil
from tempfile import TemporaryDirectory
import unittest

from audit_wallet import PACKET, ROOT, USDR, describe_route, only, octets, token_legs
from rpc_evidence import audit, case_data, plan


class ReviewControls(unittest.TestCase):
    def test_four_correct_transfer_legs_do_not_validate_wrong_packet_destination(self):
        cases, _ = case_data()
        route = cases["case-01"]
        tx, logs = route["tx"], route["logs"]
        pinned = json.loads((ROOT/"evidence/source-identities.json").read_text(encoding="utf-8"))
        roles = {row["role"]:row.get("published_address") for row in pinned["sources"]}
        packet = only(logs, PACKET)
        data = bytearray(octets(packet["data"]))
        start = int.from_bytes(data[:32],"big")+32
        data[start+48] ^= 1
        packet["data"] = "0x"+data.hex()
        with self.assertRaisesRegex(ValueError,"Destination EID disagrees"):
            describe_route(tx, logs, token_legs(logs, USDR), int(tx["fee"]["value"]), roles)

    def test_a_pruned_balance_must_not_become_a_zero_observation(self):
        rpc_dir = ROOT/"evidence/rpc"
        saved = audit(rpc_dir)
        unavailable = next(x for x in saved["state_rows"] if x["case_id"]=="case-26" and
                           x["native_before_units"] is None)
        self.assertIsNone(unavailable["native_after_units"])
        self.assertIsNone(unavailable["native_delta_units"])
        self.assertIsNone(unavailable["event_delta_matches_rpc"])
        _, _, _, states, _ = plan()
        wanted = states["case-26", unavailable["address"]][:2]
        with TemporaryDirectory() as d:
            temp = Path(d)/"rpc"
            shutil.copytree(rpc_dir,temp)
            found = []
            for path in temp.glob("*.response.json"):
                rows = json.loads(path.read_text(encoding="utf-8"))
                changed = False
                for i, row in enumerate(rows):
                    if row["id"] in wanted:
                        self.assertIn("pruned",row["error"]["message"].lower())
                        rows[i] = {"jsonrpc":"2.0","id":row["id"],"result":"0x0"}
                        found.append(row["id"])
                        changed = True
                if changed:
                    path.write_text(json.dumps(rows),encoding="utf-8")
            self.assertCountEqual(found,wanted)
            synthetic = audit(temp)
        altered = next(x for x in synthetic["state_rows"] if x["case_id"]=="case-26" and
                       x["address"]==unavailable["address"])
        self.assertEqual(altered["native_delta_units"],0)
        self.assertIs(altered["event_delta_matches_rpc"],False)


if __name__ == "__main__":
    unittest.main()
