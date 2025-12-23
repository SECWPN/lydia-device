from lydia_device.parse_process import parse_process_block


def test_parse_process_cur_pro() -> None:
    text = """power:100,fre:3000,duty:100,mode:0
head mode:1,fre:8,width:80
pulse tick on:150,off:150
gas tick early:200,delay:150
power tick rise:100,fall:50,early:0,delay:200
power on:0, power off:0
process index:0
msh >
"""
    parsed = parse_process_block(text)

    assert parsed["power"] == 100
    assert parsed["pwm_fre"] == 3000
    assert parsed["pwm_duty"] == 100
    assert parsed["mode"] == 0
    assert parsed["head_mode"] == 1
    assert parsed["head_fre"] == 8
    assert parsed["head_width"] == 80
    assert parsed["pulse_on"] == 150
    assert parsed["pulse_off"] == 150
    assert parsed["gas_early"] == 200
    assert parsed["gas_delay"] == 150
    assert parsed["pow_rise"] == 100
    assert parsed["pow_fall"] == 50
    assert parsed["pow_early"] == 0
    assert parsed["pow_delay"] == 200
    assert parsed["power_on"] == 0
    assert parsed["power_off"] == 0
    assert parsed["index"] == 0


def test_parse_process_feeder_pro() -> None:
    text = """feeder_mode:0,out_speed:10,len:13,in_speed:20,len:14
feeder_cycle:400, smoothness:40,out_delay:0,in_delay:400
msh >
"""
    parsed = parse_process_block(text)

    assert parsed["feeder_mode"] == 0
    assert parsed["feeder_out_speed"] == 10
    assert parsed["feeder_out_len"] == 13
    assert parsed["feeder_in_speed"] == 20
    assert parsed["feeder_in_len"] == 14
    assert parsed["feeder_cycle"] == 400
    assert parsed["feeder_smoothness"] == 40
    assert parsed["feeder_out_delay"] == 0
    assert parsed["feeder_in_delay"] == 400
