# Interface

This document describes the websocket data contract exposed by `lydia-device`.
All examples are JSON-like; the actual wire format is CBOR.

## Transport

- WebSocket server at `WS_HOST:WS_PORT` (defaults `127.0.0.1:8787`)
- Messages are CBOR-encoded maps (use the `type` field to route)

## Client -> server

### Subscribe

Request:

```json
{ "type": "subscribe" }
```

Response:

```json
{ "type": "ack", "op": "subscribe" }
```

### Exec

Request:

```json
{ "type": "exec", "id": "req-1", "cmd": "status" }
```

Power setter example:

```json
{ "type": "exec", "id": "req-2", "cmd": "power 50" }
```

Dual-use commands (getter without params, setter with params): `power`, `wave`, `maxpower`,
`risetk`, `falltk`, `gaseatk`, `gaslatk`, `onwatk`, `offwatk`, `headfre`, `headwide`,
`feederoutspeed`

Power getter example:

```json
{ "type": "exec", "id": "req-3", "cmd": "power" }
```

Weld parameter setters:

```json
{ "type": "exec", "id": "req-4", "cmd": "headfre 800" }
{ "type": "exec", "id": "req-5", "cmd": "headwide 80" }
{ "type": "exec", "id": "req-6", "cmd": "feederoutspeed 10" }
```

Notes:

- `headfre` is in Hz (e.g., `headfre 800` -> 800 Hz).
- `headwide` uses device units (e.g., `headwide 80` -> 8.0 mm).
- `feederoutspeed` uses device units (commonly mm/s).

Response (success):

```json
{
  "type": "result",
  "id": "req-1",
  "ok": true,
  "stdout": "...",
  "parsed": { "...": "..." },
  "latency_ms": 12,
  "ts_ms": 1734800000000
}
```

Response (denied):

```json
{
  "type": "result",
  "id": "req-1",
  "ok": false,
  "error": "Command not allowed by policy",
  "reason": "Blocked verb: reboot",
  "ts_ms": 1734800000000
}
```

Response (failure):

```json
{
  "type": "result",
  "id": "req-2",
  "ok": false,
  "error": "Timed out waiting for msh prompt",
  "ts_ms": 1734800000000
}
```

Command lifecycle:

- Pending: once an `exec` is sent, treat it as pending until the `result` arrives (no explicit
  pending message is emitted).
- Success: `result.ok == true`.
- Failure: `result.ok == false` with `error` set.
- Denied: `result.ok == false` with `error == "Command not allowed by policy"` and a `reason`.

## Server -> client events

Event envelope:

```json
{
  "type": "event",
  "name": "status",
  "ts_ms": 1734800000000,
  "latency_ms": 8,
  "parsed": { "...": "..." }
}
```

Events:

- `heartbeat`: no `parsed`; emitted every status poll
- `status`: parsed status snapshot, emitted on change
- `status_error`: parsing or serial error; includes `error`
- `process_params`: parsed `cur_pro` and `feeder_pro`, emitted on change
- `process_error`: parsing or serial error; includes `error`
- `getall`: parsed `getall` snapshot, emitted on change (and on connect)
- `getall_error`: parsing or serial error; includes `error`

## Parsed payloads

### `status` parsed payload

All fields are optional and only present when parsed.

```json
{
  "power_on_time": "01:02:03",
  "rtc_time": "2024-01-01 00:00:00",
  "work_mode": "AUTO",
  "work_state": "IDLE",
  "laser_state": "OFF",
  "pulse_on": 150,
  "pulse_off": 150,
  "wave_state": 0,
  "io_flags": { "DOOR": 1, "COVER": 0 },
  "power_out": { "pct": 100.0, "w": 700, "dac": 255, "state": "ON" },
  "power_param": { "power": 100.0, "pwm_fre": 1000, "pwm_duty": 100 },
  "power_drive": { "v": 5.0, "a": 1.25 },
  "drive_volt": [10.0, 20.0],
  "drive_current": [1.0, 2.0, 3.0, 4.0],
  "energy": { "state": 1, "j": 10, "dac": 255 },
  "pilot": { "ma": 12.3, "adc": 123, "dac": 45, "onoff": "ON", "mode": 2 },
  "pd": { "mv": 23.4, "adc": 99 },
  "ntc": [{ "c": 22.4, "adc": 2162 }],
  "pressure": { "value": 1.23, "adc": 456 },
  "air_hr": { "value": 55.0, "adc": 789 },
  "air_t": { "value_c": 22.0, "adc": 111 },
  "env": { "temp_c": 22.52, "pres_kpa": 384.0, "dew": 0.0 },
  "warning": { "mask": "0x0001", "text": "OVERHEAT" },
  "error": { "mask": "0x0000", "text": "NONE" },
  "lock": { "mask": "0x0000", "text": "" },
  "tem": 12
}
```

Notes:

- `pulse_on`, `pulse_off`, and `wave_state` are the weld timing/mode fields surfaced from `status`.
- Units are reported by the firmware; treat integer timings as device ticks or ms depending on firmware.

### `process_params` parsed payload

Payload shape:

```json
{
  "cur_pro": { "...": "..." },
  "feeder_pro": { "...": "..." }
}
```

`cur_pro` and `feeder_pro` share the same schema; only the relevant fields appear.

```json
{
  "power": 100,
  "pwm_fre": 3000,
  "pwm_duty": 100,
  "mode": 0,
  "head_mode": 1,
  "head_fre": 8,
  "head_width": 80,
  "pulse_on": 150,
  "pulse_off": 150,
  "gas_early": 200,
  "gas_delay": 150,
  "pow_rise": 100,
  "pow_fall": 50,
  "pow_early": 0,
  "pow_delay": 200,
  "power_on": 0,
  "power_off": 0,
  "index": 0,
  "feeder_mode": 0,
  "feeder_out_speed": 10,
  "feeder_out_len": 13,
  "feeder_in_speed": 20,
  "feeder_in_len": 14,
  "feeder_cycle": 400,
  "feeder_smoothness": 40,
  "feeder_out_delay": 0,
  "feeder_in_delay": 400,
  "extras": [{ "key": "RAWKEY", "value": "RAWVALUE" }]
}
```

Notes:

- `head_fre` and `head_width` map to swing frequency and swing width.
- `feeder_out_speed` maps to wire feed speed (units per firmware, often mm/s).
- Timing fields (`pulse_on`, `pulse_off`, `gas_*`, `pow_*`) are integers in firmware units.

### `getall` parsed payload

The `getall` command parses into a key/value map where each entry contains:

```json
{
  "raw": "700 W",
  "value": 700,
  "unit": "W"
}
```

Notes:

- Keys are lowercased (e.g., `MAXPOWER` -> `maxpower`).
- `value` and `unit` are only present when a numeric value is detected.
- Emitted on connect and periodically as the `getall` event.
