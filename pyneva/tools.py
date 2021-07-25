import re
from dataclasses import dataclass
from typing import Literal, Union


def make_request(obis: str = "", mode: Literal["P", "W", "R"] = "R", data: bytes = b"") -> bytes:
    if type(obis) != str:
        raise TypeError(f"OBIS must be str, not {type(obis).__name__}")

    if mode not in ("P", "W", "R"):
        raise ValueError(f"mode must be in ('P', 'W', 'R'), not '{mode}'")

    if mode in ("P", "W") and not data:
        raise ValueError("data cannot be empty if mode in ('P', 'W')")

    if obis and mode == "P":
        raise ValueError("mode cannot be 'P' if OBIS code was specified")

    if obis:
        pattern = re.compile(r"[A-F0-9]{2}\.[A-F0-9]{2}\.[A-F0-9]{2}\*FF")
        if not bool(pattern.fullmatch(obis)):
            raise ValueError("OBIS code format is wrong")
        obis = obis[:2] + obis[3:5] + obis[6:8] + obis[9:]

    obis = obis.encode()
    data = b"(%s)" % data

    request = b"\x01" + mode.encode() + b"1\x02" + obis + data + b"\x03"
    request += calculate_bcc(request[1:])

    return request


def parse_response(response: bytes) -> Union[str, float, tuple[Union[str, float], ...]]:
    try:
        response = response.split(b"(")[1].split(b")")[0]
    except (IndexError, ValueError):
        raise ValueError(f"invalid response format, response: {response}") from None

    response = response.split(b",")
    if b"." in response[0]:
        if len(response) != 1:
            return tuple(map(float, response))
        return float(response[0])
    if len(response) != 1:
        return tuple(map(lambda x: x.decode("ascii"), response))
    return response[0].decode("ascii")


def calculate_bcc(data: bytes) -> bytes:
    bcc = 0
    for byte in data:
        bcc ^= byte
    return bcc.to_bytes(1, "little")


@dataclass
class Commands:
    transfer_request = b"/?!\r\n"

    # <ACK>0<baudrate_num>1<CR><LF>
    ack = b"\x060%i1\r\n"

    # <SOH>B0<ETX><bcc>
    end_conn = b"\x01B0\x03q"

    total_energy = make_request("0F.08.80*FF")
    voltage_A = make_request("20.07.00*FF")
    voltage_B = make_request("34.07.00*FF")
    voltage_C = make_request("48.07.00*FF")
    active_power_A = make_request("24.07.00*FF")
    active_power_B = make_request("38.07.00*FF")
    active_power_C = make_request("4C.07.00*FF")
    active_power_sum = make_request("10.07.00*FF")
    serial_num = make_request("60.01.00*FF")
    status = make_request("60.05.00*FF")
    season_schedule = make_request("0D.00.00*FF")
    special_days = make_request("0B.00.00*FF")
    tariff_schedule_cmd = "0A.%s.64*FF"