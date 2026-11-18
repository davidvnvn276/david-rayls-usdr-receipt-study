"""Controls for block identity and misleading same-value RPC views."""
import unittest
from unittest.mock import patch

import verify_followup as study


class FollowUpControls(unittest.TestCase):
    def test_two_real_balance_snapshots_cannot_swap_block_tags(self):
        def replaced(name,suffix):
            if (name,suffix)==("followup-01-inclusion","request"):
                return actual("followup-01-parent","request")
            return actual(name,suffix)
        actual=study.load
        with patch.object(study,"load",side_effect=replaced):
            with self.assertRaisesRegex(ValueError,"Request plan differs: followup-01-inclusion"):
                study.verify()

    def test_two_agreeing_balance_views_can_both_disagree_with_receipt(self):
        def replaced(name,suffix):
            result=actual(name,suffix)
            if (name,suffix)==("alternate-01-payer","response"):
                after={row["id"]:row for row in result}
                bumped=int(after[3]["result"],16)+1
                after[3]["result"]=hex(bumped)
                after[4]["result"]=f"0x{bumped:064x}"
            return result
        actual=study.load
        with patch.object(study,"load",side_effect=replaced):
            with self.assertRaisesRegex(ValueError,"Wallet delta does not match receipts"):
                study.verify()


if __name__=="__main__":
    unittest.main()
