from lydia_device.parse_getall import parse_getall_block


def test_parse_getall_block_numeric_and_raw() -> None:
    text = """.SN: 6832CEC4
.MAXPOWER: 700 W
.FEEDEROUTSPEED: 10 mm/S
.PRESMIN: 30.00 Kpa
.XTYPE: 0  X
.IPADDR: 192.168.16.200
msh >
"""
    parsed = parse_getall_block(text)

    assert parsed["sn"]["raw"] == "6832CEC4"
    assert parsed["maxpower"]["value"] == 700
    assert parsed["maxpower"]["unit"] == "W"
    assert parsed["feederoutspeed"]["value"] == 10
    assert parsed["feederoutspeed"]["unit"] == "mm/S"
    assert parsed["presmin"]["value"] == 30
    assert parsed["presmin"]["unit"] == "Kpa"
    assert parsed["xtype"]["value"] == 0
    assert parsed["xtype"]["unit"] == "X"
    assert "value" not in parsed["ipaddr"]
