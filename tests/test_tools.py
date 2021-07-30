import unittest
from pyneva.tools import make_request, parse_response, calculate_bcc, get_resp_data


class TestTools(unittest.TestCase):
    def test_make_request(self):
        first = (
            make_request("60.01.00*FF"),
            make_request(mode="P", data=b"00000000"),
        )
        second = (
            b"\x01R1\x02600100FF()\x03d",
            b"\x01P1\x02(00000000)\x03a",
        )
        self.assertEqual(first, second)

        self.assertRaises(TypeError, make_request, obis=b"60.01.00*FF")
        self.assertRaises(TypeError, make_request, obis=435)
        self.assertRaises(ValueError, make_request, obis="60.01.00*FF", mode="L")
        self.assertRaises(ValueError, make_request, mode="W")
        self.assertRaises(ValueError, make_request, mode="P")
        self.assertRaises(ValueError, make_request, mode="W")
        self.assertRaises(TypeError, make_request, mode="W", data=12231)
        self.assertRaises(ValueError, make_request, obis="", mode="W")
        self.assertRaises(ValueError, make_request, obis="60.01.00*FF", mode="P")
        self.assertRaises(ValueError, make_request, obis="600100FF")

    def test_get_resp_data(self):
        first = (
            get_resp_data(b"\x02600100FF(60089784)\x03\x09"),
            get_resp_data(b"\x024C0700FF(00134.2)\x03X"),
            get_resp_data(b"\x020F0680FF(04.8190,04.8457,02.5359,00.0000,00.0000)\x03R"),
            get_resp_data(
                b"\x020A0164FF(070001,230002,000000,000000,000000,000000,000000,000000)\x03Y"),
        )
        second = (
            "60089784",
            134.2,
            (4.819, 4.8457, 2.5359, 0.0, 0.0),
            ("070001", "230002", "000000", "000000", "000000", "000000", "000000", "000000"),
        )
        self.assertEqual(first, second)

        self.assertRaises(TypeError, get_resp_data, response=123)
        self.assertRaises(ValueError, get_resp_data, response=b"")
        self.assertRaises(ValueError, get_resp_data, response=b"\x024C0700FF00134.2\x03X")
        self.assertRaises(ValueError, get_resp_data, response=b"\x020F0880FF(016442.17,"
                                                              b"012865.25,003576.92,000000.00,"
                                                              b"000000.00)\x03S")  # Invalid BCC

    def test_calculate_bcc(self):
        first = (
            calculate_bcc(b"60010AFF(0000000000000000)\x03"),
            calculate_bcc(b"R1\x0260010AFF()\x03"),
        )
        second = (b"t", b"\x15",)
        self.assertEqual(first, second)

        self.assertRaises(TypeError, calculate_bcc, data=123)


if __name__ == '__main__':
    unittest.main()
