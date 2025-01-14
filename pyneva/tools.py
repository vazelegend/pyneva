import re
from re import Match
from time import sleep
from typing import Literal

import serial

from . import meters
from .types import IdentificationMsg, DataMsg, WrongBCC, ResponseError


def make_cmd_msg(obis: str = "", mode: Literal["P", "W", "R"] = "R", data: bytes = b"") -> bytes:
    """Return generated byte command message from OBIS code or password
    comparison message.
    """
    if type(obis) != str:
        raise TypeError(f"OBIS must be str, not {type(obis).__name__}")

    if type(data) != bytes:
        raise TypeError(f"data must be bytes, not {type(data).__name__}")

    if mode not in ("P", "W", "R"):
        raise ValueError(f"mode must be in ('P', 'W', 'R'), not {mode!r}")

    if mode in ("P", "W") and not data:
        raise ValueError("data cannot be empty if mode in ('P', 'W')")

    if not obis and mode in ("R", "W"):
        raise ValueError("if mode == 'W' OBIS code must be specified")

    if obis and mode == "P":
        raise ValueError("mode cannot be 'P' if OBIS code was specified")

    if obis:
        pattern = re.compile(r"({a})\.({a})\.({a})\*({a})".format(a="[A-F0-9]{2}"))
        obis = pattern.fullmatch(obis)
        if not obis:
            raise ValueError("OBIS code format is wrong")
        obis = obis[1] + obis[2] + obis[3] + obis[4]

    msg = b"\x01%s1\x02%s(%s)\x03" % (mode.encode(), obis.encode(), data)
    msg += calculate_bcc(msg[1:])
    return msg


def parse_id_msg(response: bytes) -> IdentificationMsg:
    if not isinstance(response, bytes):
        raise TypeError(f"response must be bytes, not {type(response).__name__}")
    pattern = b"^\\/(?P<vendor>[A-Z]{2}([A-Z]|[a-z]))(?P<baudrate>[0-5])(?P<identifier>" \
              b"[\x22-\x2E\x30-\x7E]{1,16})\r\n$"
    pattern = re.compile(pattern)
    id_msg = pattern.fullmatch(response)
    if not id_msg:
        check_err(response)
        raise ResponseError(f"invalid identification message format, msg: {response}")
    identifier = id_msg.group("identifier").decode("ascii")
    vendor = id_msg.group("vendor").decode("ascii")
    baudrate_num = int(id_msg.group("baudrate"))
    return IdentificationMsg(identifier=identifier, vendor=vendor, baudrate_num=baudrate_num)


def parse_password_msg(response: bytes) -> bytes:
    if not isinstance(response, bytes):
        raise TypeError(f"response must be bytes, not {type(response).__name__}")
    pattern = b"^\x01P0\x02\\((?P<data>.*)\\)\x03(?P<bcc>[\x00-\xff])$"
    pattern = re.compile(pattern)
    pass_msg = pattern.fullmatch(response)
    if not pass_msg:
        check_err(response)
        raise ResponseError(f"invalid password message format, msg: {response}")
    check_bcc(pass_msg)
    return pass_msg.group("data")


def parse_data_msg(response: bytes) -> DataMsg:
    if not isinstance(response, bytes):
        raise TypeError(f"response must be bytes, not {type(response).__name__}")
    pattern = b"^\x02(?P<addr>[0-9A-F]{8})\\((?P<data>.*)\\)\x03(?P<bcc>[\x00-\xff])$"
    pattern = re.compile(pattern)
    data_msg = pattern.fullmatch(response)
    if not data_msg:
        check_err(response)
        raise ResponseError(f"invalid data message format, msg: {response}")
    check_bcc(data_msg)
    data = tuple(val.decode("ascii") for val in data_msg["data"].split(b","))
    address = data_msg["addr"].decode("ascii")
    address = f"{address[:2]}.{address[2:4]}.{address[4:6]}*{address[6:]}"
    return DataMsg(data=data, address=address)


def parse_schedules(schedules: tuple[str, ...]) -> tuple[tuple[int, ...], ...]:
    schedules_parsed = []
    from textwrap import wrap
    for skd in schedules:
        if int(skd):
            schedules_parsed.append(tuple(int(skd_split) for skd_split in wrap(skd, 2)))
    return tuple(schedules_parsed)


def check_err(response: bytes):
    pattern = b"^\x02\\((?P<err>[0-9]+)\\)\x03[\x00-\xff]$"
    pattern = re.compile(pattern)
    response = pattern.fullmatch(response)
    if response:
        err = response['err'].decode('ascii')
        raise ResponseError(f"error message received, error code: {err}")


def check_bcc(msg: Match[bytes]):
    """Check that BCC from the response message is correct."""
    calc_bcc = calculate_bcc(msg[0][1:-1])
    if calc_bcc != msg["bcc"]:
        raise WrongBCC(f"BCC must be {calc_bcc}, but received {msg['bcc']}")


def calculate_bcc(data: bytes) -> bytes:
    """Return calculated BCC (block check character)."""
    if type(data) != bytes:
        raise TypeError(f"data must be bytes, not {type(data).__name__}")
    bcc = 0
    for byte in data:
        bcc ^= byte
    return chr(bcc).encode("ascii")


def start_without_model(interface: str, address: str = "", password: str = "",
                        initial_baudrate: int = 300, do_not_open: bool = False):
    session = serial.serial_for_url(url=interface, baudrate=initial_baudrate,
                                    bytesize=serial.SEVENBITS, parity=serial.PARITY_EVEN,
                                    stopbits=serial.STOPBITS_ONE, timeout=3)
    session.write(b"/?%s!\r\n" % address.encode("ascii"))
    ident = parse_id_msg(session.read(21)).identifier
    session.__del__()
    ident = ident[6:12]
    if ident == "324.11":
        klass = meters.NevaMT324AOS
    elif ident in ("324.23", "324.24", "324.25", "324.31"):
        klass = meters.NevaMT324R
    else:
        klass = meters.NevaMT3R
    if do_not_open:
        return klass
    sleep(.5)
    return klass(interface, address, password, initial_baudrate)


id_to_model = {
    "313.11": "MT313 AR E4S 5(10)A",
    "313.12": "MT313 AR E4S 5(60)A",
    "313.13": "MT313 AR E4S 5(100)A",
    "313.14": "MT313 AR E4S 57.7/100V 5(10)A",
    "314.31": "MT314 AR XXSR 5(10)A",
    "314.32": "MT314 AR XXSR 5(60)A",
    "314.33": "MT314 AR XXSR 5(100)A",
    "314.34": "MT314 AR XXSR 57.7/100V 5(10)",
    "315.41": "MT315 AR GSM(RF2)XBSPR 5(10)A",
    "315.42": "MT315 AR GSM(RF2)XBSCP 5(80)A",
    "315.51": "MT315 AR E4BSP 5(10)A",
    "315.52": "MT315 AR E4BSCP 5(80)A",
    "315.63": "MT315 AR GSMXBSCP 5(100)A",
    "323.21": "MT323 AR E4S 5(60)A",
    "323.22": "MT323 AR E4S 5(10)A",
    "324.11": "MT324 A OS 5(60)A",
    "324.23": "MT324 AR E4S 5(100)A",
    "324.24": "MT324 AR E4SC 5(80)A",
    "324.25": "MT324 AR E4S 5(60)A",
    "324.31": "MT324 AR RF2SC 5(80)A",
    "113.21": "MT113 AS OP (E4P) 5(100)A",
    "113.22": "MT113 AS OP (E4P) 5(60)A",
    "123.23": "MT123 AS OP (E4P) 5(60)A",
    "124.11": "MT124 AS OP 5(60)A",
    "124.21": "MT124 AS E4P 5(60)A",
    "124.31": "MT124 A2S E4PС 5(80)A",
    "124.41": "MT124 A2S RF2PС 5(80)A",
    "114.31": "MT114 AS XXPC 5(60)A  (XX - any other than E4)",
    "114.33": "MT114 AS XXPC 5(100)A  (XX - any other than E4)",
    "114.34": "MT114 AS XXP 5(100)A  (XX - any other than E4)",
    "114.35": "MT114 AS XXP 5(60)A  (XX - any other than E4)",
    "114.41": "MT114 A2S XXPC 5(60)A  (XX - any other than E4)",
    "114.42": "MT114 A2S XXPC 5(100)A  (XX - any other than E4)",
    "114.43": "MT114 ARST XXPC 5(60)A  (XX - any other than E4)",
    "114.44": "MT114 ARST XXPC 5(100)A  (XX - any other than E4)",
    "114.51": "MT114 AS E4PC (E4P)  5(60)A",
    "114.52": "MT114 AS E4PC (E4P)  5(100)A",
    "114.61": "MT114 AST  E4PC (E4P)  5(60)A",
    "114.63": "MT114 AST  E4PC (E4P)  5(100)A",
    "114.64": "MT114 ARST  E4PC (E4P)  5(60)A",
    "114.71": "MT114 AS XXPC (S) 5(60)A  (XX - any other than E4)",
    "114.73": "MT114 AS XXPC (S)  5(100)A  (XX - any other than E4)",
}
