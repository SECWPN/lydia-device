use anyhow::{anyhow, Result};
use lazy_static::lazy_static;
use regex::Regex;
use serde::Serialize;

/* ===================== Top-level typed messages ===================== */

/// Parsed, typed messages from the RT-Thread "msh" CLI.
#[derive(Debug, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ParsedMessage {
    Version(VersionInfo),
    Free(Free),
    Ps {
        columns: Vec<String>,
        rows: Vec<ThreadRow>,
    },
    WorkTime(WorkTime),
    Warning(FlagWord),
    Error(FlagWord),
    Lock(FlagWord),
    Mode {
        mode: String,
    },
    State {
        state: String,
    },
    Status(Status),
    SubStatus(SubStatus),
    IOState(Vec<KVLine>),
    IfConfig(IfConfig),
    Dns(Dns),
    Netstat(Netstat),
    ReadAll(Vec<PortLine>),

    /// NEW: current laser process parameters (from `cur_pro`)
    ProcessCur(ProcessParams),
    /// NEW: feeder process parameters (from `feeder_pro`)
    ProcessFeeder(ProcessParams),

    /// Fallback for unrecognized/unsupported commands (still useful for logging)
    Unknown {
        cmd: String,
        lines: Vec<String>,
    },
}

/* ===================== Common structs for variants ===================== */

#[derive(Debug, Serialize)]
pub struct VersionInfo {
    pub rtthread_version: String,
    pub build: String,
    pub copyright: String,
}

#[derive(Debug, Serialize)]
pub struct Free {
    pub total: i64,
    pub used: i64,
    pub maximum: i64,
}

#[derive(Debug, Serialize)]
pub struct ThreadRow {
    pub thread: String,
    pub pri: Option<i32>,
    pub status: String,
    pub sp: Option<String>,
    pub stack: Option<String>,
    pub size: Option<String>,
    pub max: Option<String>,
    pub used: Option<i32>,
    pub left: Option<i32>,
    pub tick: Option<i32>,
    pub error: Option<i32>,
}

#[derive(Debug, Serialize)]
pub struct WorkTime {
    #[serde(rename = "Start date")]
    pub start_date: Option<String>,
    #[serde(rename = "End date")]
    pub end_date: Option<String>,
    #[serde(rename = "Current date")]
    pub current_date: Option<String>,
    #[serde(rename = "Total startup time")]
    pub total_startup_time: Option<String>,
    #[serde(rename = "Current startup time")]
    pub current_startup_time: Option<String>,
    #[serde(rename = "onkey time")]
    pub onkey_time: Option<String>,
    #[serde(rename = "decodeTimes")]
    pub decode_times: Option<i64>,
    #[serde(rename = "Days available")]
    pub days_available: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct FlagWord {
    pub raw: String,    // e.g. "0x002000001"
    pub labels: String, // tail text, e.g. "INTERLOCK GND_LOCK"
}

#[derive(Debug, Serialize)]
pub struct Status {
    pub lines: Vec<KVLine>,
}

#[derive(Debug, Serialize)]
pub struct SubStatus {
    pub laser_sub_state: Option<i64>,
    pub feeder_state: Option<i64>,
    pub gas_state: Option<i64>,
    pub extras: Vec<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct KVLine {
    pub key: String,
    pub value: String,
}

#[derive(Debug, Serialize)]
pub struct IfConfig {
    pub iface: Option<String>,
    pub mtu: Option<i64>,
    pub mac: Option<String>,
    pub flags: Option<String>,
    pub ip_addr: Option<String>,
    pub gw_addr: Option<String>,
    pub netmask: Option<String>,
    pub dns0: Option<String>,
    pub dns1: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct Dns {
    pub iface: Option<String>,
    pub dns0: Option<String>,
    pub dns1: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct Netstat {
    pub listen_ports: Vec<i64>,
}

#[derive(Debug, Serialize)]
pub struct PortLine {
    pub port: String,   // PA..PG
    pub input: String,  // hex string
    pub output: String, // hex string (may have spaces)
}

/* ===================== NEW: Process parameters model ===================== */

/// Unified process parameter set parsed from `cur_pro` and `feeder_pro`.
/// We keep everything in one struct so upstream can render a single JSON doc.
#[derive(Debug, Serialize, Default, Clone)]
pub struct ProcessParams {
    // Main PWM/power controls
    pub power: Option<i64>,    // %
    pub pwm_fre: Option<i64>,  // Hz
    pub pwm_duty: Option<i64>, // %
    pub mode: Option<i64>,     // controller mode

    // Laser head params
    pub head_mode: Option<i64>,
    pub head_fre: Option<i64>,
    pub head_width: Option<i64>,

    // Pulse/Timing
    pub pulse_on: Option<i64>,  // us
    pub pulse_off: Option<i64>, // us

    // Gas timing
    pub gas_early: Option<i64>,
    pub gas_delay: Option<i64>,

    // Power timing ticks
    pub pow_rise: Option<i64>,
    pub pow_fall: Option<i64>,
    pub pow_early: Option<i64>,
    pub pow_delay: Option<i64>,

    // Other toggles
    pub power_on: Option<i64>,
    pub power_off: Option<i64>,

    // Process index / slot
    pub index: Option<i64>,

    // Feeder params (present only when reported)
    pub feeder_mode: Option<i64>,
    pub feeder_out_speed: Option<i64>,
    pub feeder_out_len: Option<i64>,
    pub feeder_in_speed: Option<i64>,
    pub feeder_in_len: Option<i64>,
    pub feeder_cycle: Option<i64>,
    pub feeder_smoothness: Option<i64>,
    pub feeder_out_delay: Option<i64>,
    pub feeder_in_delay: Option<i64>,

    /// Anything not recognized but looks like a key/value, for forensics.
    pub extras: Vec<KVLine>,
}

/* ===================== Entry point ===================== */

/// Entry point: tolerant parse of a reply for a given `cmd`.
pub fn parse(cmd: &str, lines: &[String]) -> ParsedMessage {
    let mut norm: Vec<String> = lines
        .iter()
        .map(|s| normalize_line(s))
        .filter(|s| !s.is_empty())
        .collect();

    // Strip banners/prompt echoes if present
    strip_prompt_noise(&mut norm);

    match cmd {
        "version" => parse_version(&norm).unwrap_or_else(|_| ParsedMessage::Unknown {
            cmd: cmd.into(),
            lines: norm,
        }),
        "free" => parse_free(&norm).unwrap_or_else(|_| ParsedMessage::Unknown {
            cmd: cmd.into(),
            lines: norm,
        }),
        "ps" => parse_ps(&norm),
        "worktime" => parse_worktime(&norm).unwrap_or_else(|_| ParsedMessage::Unknown {
            cmd: cmd.into(),
            lines: norm,
        }),
        "warning" => parse_flagword("WARNING", &norm).unwrap_or_else(|_| ParsedMessage::Unknown {
            cmd: cmd.into(),
            lines: norm,
        }),
        "error" => parse_flagword("ERROR", &norm).unwrap_or_else(|_| ParsedMessage::Unknown {
            cmd: cmd.into(),
            lines: norm,
        }),
        "lock" => parse_flagword("LOCK", &norm).unwrap_or_else(|_| ParsedMessage::Unknown {
            cmd: cmd.into(),
            lines: norm,
        }),
        "mode" => {
            let v = norm.first().cloned().unwrap_or_default();
            let mode = take_after_colon(&v).unwrap_or(v);
            ParsedMessage::Mode { mode }
        }
        "state" => {
            let v = norm.first().cloned().unwrap_or_default();
            let state = take_after_colon(&v).unwrap_or(v);
            ParsedMessage::State { state }
        }
        "status" => ParsedMessage::Status(Status {
            lines: norm.into_iter().filter_map(|l| split_kv(&l)).collect(),
        }),
        "substatus" => parse_substatus(&norm),
        "iostate" => ParsedMessage::IOState(parse_kv_lines(&norm)),
        "ifconfig" => parse_ifconfig(&norm),
        "dns" => parse_dns(&norm),
        "netstat" => parse_netstat(&norm),
        "readall" => parse_readall(&norm),

        // === NEW: process parsers ===
        "cur_pro" => ParsedMessage::ProcessCur(parse_process_like(&norm)),
        "feeder_pro" => ParsedMessage::ProcessFeeder(parse_process_like(&norm)),

        _ => ParsedMessage::Unknown {
            cmd: cmd.into(),
            lines: norm,
        },
    }
}

/* ===================== helpers and specific parsers ===================== */

fn normalize_line(s: &str) -> String {
    let mut t = s.replace('\r', "");
    // trim and collapse weird spacing tails
    t = t.trim_end().to_string();
    t
}

fn strip_prompt_noise(lines: &mut Vec<String>) {
    // Drop known banners / prompt echoes
    let _prefixes = [
        "RT-Thread shell commands:",
        " \\ | /",
        "- RT -",
        " / | \\",
        "msh >", // prompt
    ];
    // We keep actual content even if banners appear mid-stream; here we only drop a naked "msh >"
    lines.retain(|l| {
        if l == "msh >" {
            return false;
        }
        true
    });
}

fn take_after_colon(s: &str) -> Option<String> {
    s.split_once(':').map(|(_, right)| right.trim().to_string())
}

fn split_kv(line: &str) -> Option<KVLine> {
    let (k, v) = line.split_once(':')?;
    Some(KVLine {
        key: k.trim().to_string(),
        value: v.trim().to_string(),
    })
}

fn parse_kv_lines(lines: &[String]) -> Vec<KVLine> {
    lines.iter().filter_map(|l| split_kv(l)).collect()
}

/* --------- specific parsers already present ---------- */

fn parse_version(lines: &[String]) -> Result<ParsedMessage> {
    // Expected:
    // " \\ | /"
    // "- RT -     Thread Operating System"
    // " / | \\     4.1.0 build Apr 29 2025 17:44:53"
    // " 2022 - 2023 Copyright by Xinghan Laser"
    let _rt = lines
        .iter()
        .find(|l| l.contains("Thread Operating System"))
        .cloned()
        .unwrap_or_default();
    let build = lines
        .iter()
        .find(|l| l.contains("build"))
        .cloned()
        .unwrap_or_default();
    let cpr = lines
        .iter()
        .find(|l| l.contains("Copyright"))
        .cloned()
        .unwrap_or_default();

    let ver = build
        .split_whitespace()
        .collect::<Vec<_>>()
        .iter()
        .skip_while(|x| **x != "4.1.0" && **x != "3.1.5" && !x.contains('.'))
        .take(1)
        .cloned()
        .collect::<Vec<_>>()
        .join(" ");

    let info = VersionInfo {
        rtthread_version: if ver.is_empty() {
            "unknown".into()
        } else {
            ver
        },
        build,
        copyright: cpr,
    };
    Ok(ParsedMessage::Version(info))
}

fn parse_free(lines: &[String]) -> Result<ParsedMessage> {
    let mut total = None;
    let mut used = None;
    let mut maximum = None;
    for l in lines {
        if let Some(kv) = split_kv(l) {
            let v = kv.value.replace(' ', "");
            if kv.key.starts_with("total") {
                total = v.parse::<i64>().ok();
            } else if kv.key.starts_with("used") {
                used = v.parse::<i64>().ok();
            } else if kv.key.starts_with("maximum") {
                maximum = v.parse::<i64>().ok();
            }
        }
    }
    Ok(ParsedMessage::Free(Free {
        total: total.unwrap_or_default(),
        used: used.unwrap_or_default(),
        maximum: maximum.unwrap_or_default(),
    }))
}

fn parse_ps(lines: &[String]) -> ParsedMessage {
    // Skip header lines (2 lines)
    let mut rows = Vec::new();
    for l in lines.iter().skip_while(|x| !x.contains("status")).skip(2) {
        // Split by whitespace; thread name may contain spaces → squeeze columns from the right
        let toks: Vec<&str> = l.split_whitespace().collect();
        if toks.len() < 4 {
            continue;
        }
        // We expect columns: thread pri status sp stack size max used left tick error (<= 11)
        // We'll take from rightmost known slots and join the rest as thread.
        let mut cols = toks.clone();
        // rightmost ints may be missing; pad
        let error = pop_i32(&mut cols);
        let tick = pop_i32(&mut cols);
        let left = pop_i32(&mut cols);
        let used = pop_i32(&mut cols);
        let max = cols.pop().map(|s| s.to_string()); // can be hex
        let size = cols.pop().map(|s| s.to_string());
        let stack = cols.pop().map(|s| s.to_string());
        let sp = cols.pop().map(|s| s.to_string());
        let status = cols.pop().unwrap_or("").to_string();
        let pri = pop_i32(&mut cols);
        let thread = cols.join(" ");

        rows.push(ThreadRow {
            thread,
            pri,
            status,
            sp,
            stack,
            size,
            max,
            used,
            left,
            tick,
            error,
        });
    }
    let columns = vec![
        "thread", "pri", "status", "sp", "stack", "size", "max", "used", "left", "tick", "error",
    ]
    .into_iter()
    .map(|s| s.to_string())
    .collect();
    ParsedMessage::Ps { columns, rows }
}

fn pop_i32(v: &mut Vec<&str>) -> Option<i32> {
    v.pop().and_then(|s| s.parse::<i32>().ok())
}

fn parse_worktime(lines: &[String]) -> Result<ParsedMessage> {
    let mut wt = WorkTime {
        start_date: None,
        end_date: None,
        current_date: None,
        total_startup_time: None,
        current_startup_time: None,
        onkey_time: None,
        decode_times: None,
        days_available: None,
    };
    for l in lines {
        if let Some(kv) = split_kv(l) {
            match kv.key.as_str() {
                "Start date" => wt.start_date = Some(kv.value.to_string()),
                "End date" => wt.end_date = Some(kv.value.to_string()),
                "Current date" => wt.current_date = Some(kv.value.to_string()),
                "Total startup time" => wt.total_startup_time = Some(kv.value.to_string()),
                "Current startup time" => wt.current_startup_time = Some(kv.value.to_string()),
                "onkey time" => wt.onkey_time = Some(kv.value.to_string()),
                "decodeTimes" => wt.decode_times = kv.value.parse::<i64>().ok(),
                "Days available" => wt.days_available = kv.value.parse::<i64>().ok(),
                _ => {}
            }
        }
    }
    Ok(ParsedMessage::WorkTime(wt))
}

fn parse_flagword(_prefix: &str, lines: &[String]) -> Result<ParsedMessage> {
    // e.g. "ERROR(0x002000001) INTERLOCK GND_LOCK"
    let l = lines.first().ok_or_else(|| anyhow!("empty"))?.clone();
    let caps = FLAG_RE.captures(&l).ok_or_else(|| anyhow!("no match"))?;
    let raw = caps
        .name("hex")
        .map(|m| m.as_str().to_string())
        .unwrap_or_default();
    let labels = caps
        .name("labels")
        .map(|m| m.as_str().to_string())
        .unwrap_or_default();
    let fw = FlagWord { raw, labels };
    Ok(match _prefix {
        "WARNING" => ParsedMessage::Warning(fw),
        "ERROR" => ParsedMessage::Error(fw),
        "LOCK" => ParsedMessage::Lock(fw),
        _ => ParsedMessage::Unknown {
            cmd: _prefix.into(),
            lines: lines.to_vec(),
        },
    })
}

lazy_static! {
    static ref FLAG_RE: Regex =
        Regex::new(r#"(?i)^(WARNING|ERROR|LOCK)\((?P<hex>0x[0-9a-fA-F]+)\)\s*(?P<labels>.*)$"#)
            .unwrap();
}

fn parse_substatus(lines: &[String]) -> ParsedMessage {
    // "laser_sub_state(0)  feeder state(0) gas state(0)"
    // "laserhead_x(100),laserhead_x-127(-27)"
    let mut s = SubStatus {
        laser_sub_state: None,
        feeder_state: None,
        gas_state: None,
        extras: Vec::new(),
    };
    for l in lines {
        for token in l.split_whitespace() {
            if let Some(v) = capture_num(token, "laser_sub_state(") {
                s.laser_sub_state = Some(v);
            } else if let Some(v) = capture_num(token, "state(") {
                // ambiguous; we only set feeder/gas if unknown
                if s.feeder_state.is_none() {
                    s.feeder_state = Some(v);
                } else if s.gas_state.is_none() {
                    s.gas_state = Some(v);
                }
            } else {
                // keep interesting leftovers
                if token.contains('(') && token.contains(')') {
                    s.extras.push(token.to_string());
                }
            }
        }
    }
    ParsedMessage::SubStatus(s)
}

fn capture_num(tok: &str, key: &str) -> Option<i64> {
    if let Some(rest) = tok.strip_prefix(key) {
        return rest.trim_end_matches(')').parse::<i64>().ok();
    }
    None
}

fn parse_ifconfig(lines: &[String]) -> ParsedMessage {
    let mut r = IfConfig {
        iface: None,
        mtu: None,
        mac: None,
        flags: None,
        ip_addr: None,
        gw_addr: None,
        netmask: None,
        dns0: None,
        dns1: None,
    };
    for l in lines {
        if l.starts_with("network interface device:") {
            r.iface = take_after_colon(l);
        } else if l.starts_with("MTU:") {
            r.mtu = take_after_colon(l).and_then(|v| v.parse().ok());
        } else if l.starts_with("MAC:") {
            r.mac = take_after_colon(l);
        } else if l.starts_with("FLAGS:") {
            r.flags = take_after_colon(l);
        } else if l.starts_with("ip address:") {
            r.ip_addr = take_after_colon(l);
        } else if l.starts_with("gw address:") {
            r.gw_addr = take_after_colon(l);
        } else if l.starts_with("net mask") {
            r.netmask = take_after_colon(l);
        } else if l.starts_with("dns server #0") {
            r.dns0 = take_after_colon(l);
        } else if l.starts_with("dns server #1") {
            r.dns1 = take_after_colon(l);
        }
    }
    ParsedMessage::IfConfig(r)
}

fn parse_dns(lines: &[String]) -> ParsedMessage {
    let mut r = Dns {
        iface: None,
        dns0: None,
        dns1: None,
    };
    for l in lines {
        if l.starts_with("network interface device:") {
            r.iface = take_after_colon(l);
        } else if l.starts_with("dns server #0") {
            r.dns0 = take_after_colon(l);
        } else if l.starts_with("dns server #1") {
            r.dns1 = take_after_colon(l);
        }
    }
    ParsedMessage::Dns(r)
}

fn parse_netstat(lines: &[String]) -> ParsedMessage {
    let mut ports = Vec::new();
    for l in lines {
        if let Some((_left, right)) = l.split_once("local port") {
            let right = right.trim();
            if let Some((p, _state)) = right.split_once("state") {
                let p = p.trim();
                if let Ok(n) = p.parse::<i64>() {
                    ports.push(n);
                }
            }
        }
    }
    ParsedMessage::Netstat(Netstat {
        listen_ports: ports,
    })
}

fn parse_readall(lines: &[String]) -> ParsedMessage {
    let mut out = Vec::new();
    for l in lines {
        // "PA IN=0x3704, OUT=0x   0"
        if l.len() < 2 {
            continue;
        }
        let port = l[0..2].to_string();
        let input = l
            .split_once("IN=")
            .and_then(|(_, r)| r.split_once(','))
            .map(|(v, _)| v.trim().to_string())
            .unwrap_or_default();
        let output = l
            .split_once("OUT=")
            .map(|(_, r)| r.trim().to_string())
            .unwrap_or_default();
        out.push(PortLine {
            port,
            input,
            output,
        });
    }
    ParsedMessage::ReadAll(out)
}

/* -------- NEW: process parser shared by cur_pro / feeder_pro -------- */

fn parse_process_like(lines: &[String]) -> ProcessParams {
    let mut p = ProcessParams::default();

    // small helpers
    let mut set = |key: &str, v: &str| {
        if let Ok(n) = v.trim().parse::<i64>() {
            match key {
                "power" => p.power = Some(n),
                "pwm_fre" => p.pwm_fre = Some(n),
                "pwm_duty" => p.pwm_duty = Some(n),
                "mode" => p.mode = Some(n),

                "head_mode" => p.head_mode = Some(n),
                "head_fre" => p.head_fre = Some(n),
                "head_width" => p.head_width = Some(n),

                "pulse_on" => p.pulse_on = Some(n),
                "pulse_off" => p.pulse_off = Some(n),

                "gas_early" => p.gas_early = Some(n),
                "gas_delay" => p.gas_delay = Some(n),

                "pow_rise" => p.pow_rise = Some(n),
                "pow_fall" => p.pow_fall = Some(n),
                "pow_early" => p.pow_early = Some(n),
                "pow_delay" => p.pow_delay = Some(n),

                "power_on" => p.power_on = Some(n),
                "power_off" => p.power_off = Some(n),

                "index" => p.index = Some(n),

                "feeder_mode" => p.feeder_mode = Some(n),
                "feeder_out_speed" => p.feeder_out_speed = Some(n),
                "feeder_out_len" => p.feeder_out_len = Some(n),
                "feeder_in_speed" => p.feeder_in_speed = Some(n),
                "feeder_in_len" => p.feeder_in_len = Some(n),
                "feeder_cycle" => p.feeder_cycle = Some(n),
                "feeder_smoothness" => p.feeder_smoothness = Some(n),
                "feeder_out_delay" => p.feeder_out_delay = Some(n),
                "feeder_in_delay" => p.feeder_in_delay = Some(n),

                _ => {}
            }
        }
    };

    // Try to parse known line shapes.
    for raw in lines {
        let s = raw.trim();

        // "power:100,fre:3000,duty:100,mode:0"
        if s.starts_with("power:") && s.contains(',') {
            for part in s.split(',') {
                if let Some((k, v)) = part.split_once(':') {
                    match k.trim() {
                        "power" => set("power", v),
                        "fre" => set("pwm_fre", v),
                        "duty" => set("pwm_duty", v),
                        "mode" => set("mode", v),
                        _ => {}
                    }
                }
            }
            continue;
        }

        // "head mode:1,fre:8,width:80"
        if s.starts_with("head mode:") {
            let t = s.trim_start_matches("head mode:").trim();
            if let Some((m, rest)) = t.split_once(',') {
                set("head_mode", m);
                for part in rest.split(',') {
                    if let Some((k, v)) = part.split_once(':') {
                        match k.trim() {
                            "fre" => set("head_fre", v),
                            "width" => set("head_width", v),
                            _ => {}
                        }
                    }
                }
            } else {
                set("head_mode", t);
            }
            continue;
        }

        // "pulse tick on:150,off:150"
        if s.starts_with("pulse tick") {
            let t = s.trim_start_matches("pulse tick").trim();
            for part in t.split(',') {
                if let Some((k, v)) = part.split_once(':') {
                    match k.trim() {
                        "on" => set("pulse_on", v),
                        "off" => set("pulse_off", v),
                        _ => {}
                    }
                }
            }
            continue;
        }

        // "gas tick early:200,delay:150"
        if s.starts_with("gas tick") {
            let t = s.trim_start_matches("gas tick").trim();
            for part in t.split(',') {
                if let Some((k, v)) = part.split_once(':') {
                    match k.trim() {
                        "early" => set("gas_early", v),
                        "delay" => set("gas_delay", v),
                        _ => {}
                    }
                }
            }
            continue;
        }

        // "power tick rise:100,fall:50,early:0,delay:200"
        if s.starts_with("power tick") {
            let t = s.trim_start_matches("power tick").trim();
            for part in t.split(',') {
                if let Some((k, v)) = part.split_once(':') {
                    match k.trim() {
                        "rise" => set("pow_rise", v),
                        "fall" => set("pow_fall", v),
                        "early" => set("pow_early", v),
                        "delay" => set("pow_delay", v),
                        _ => {}
                    }
                }
            }
            continue;
        }

        // "power on:0, power off:0"
        if s.starts_with("power on:") || s.starts_with("power on") {
            for part in s.split(',') {
                if let Some((k, v)) = part.split_once(':') {
                    match k.trim() {
                        "power on" => set("power_on", v),
                        "power off" => set("power_off", v),
                        _ => {}
                    }
                }
            }
            continue;
        }

        // "process index:0"
        if s.starts_with("process index:") {
            if let Some((_, v)) = s.split_once(':') {
                set("index", v);
            }
            continue;
        }

        // "feeder_mode:0,out_speed:10,len:13,in_speed:20,len:14"
        if s.starts_with("feeder_mode:") {
            let mut expect_out_len = false;
            let mut expect_in_len = false;
            for part in s.split(',') {
                if let Some((k, v)) = part.split_once(':') {
                    match k.trim() {
                        "feeder_mode" => set("feeder_mode", v),
                        "out_speed" => {
                            set("feeder_out_speed", v);
                            expect_out_len = true;
                            expect_in_len = false;
                        }
                        "in_speed" => {
                            set("feeder_in_speed", v);
                            expect_in_len = true;
                            expect_out_len = false;
                        }
                        "len" => {
                            if expect_out_len {
                                set("feeder_out_len", v);
                                expect_out_len = false;
                            } else if expect_in_len {
                                set("feeder_in_len", v);
                                expect_in_len = false;
                            }
                        }
                        _ => {}
                    }
                }
            }
            continue;
        }

        // "feeder_cycle:400, smoothness:40,out_delay:0,in_delay:400"
        if s.starts_with("feeder_cycle:") || s.starts_with("smoothness:") {
            for part in s.split(',') {
                if let Some((k, v)) = part.split_once(':') {
                    match k.trim() {
                        "feeder_cycle" => set("feeder_cycle", v),
                        "smoothness" => set("feeder_smoothness", v),
                        "out_delay" => set("feeder_out_delay", v),
                        "in_delay" => set("feeder_in_delay", v),
                        "out_len" => set("feeder_out_len", v),
                        "in_len" => set("feeder_in_len", v),
                        _ => {}
                    }
                }
            }
            continue;
        }

        // If we got here, keep “KV-ish” leftovers as extras
        if let Some(kv) = split_kv(s) {
            p.extras.push(kv);
        }
    }

    p
}

/* -------- tests (incl. process) -------- */
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_free() {
        let lines = vec![
            "total   : 64424".into(),
            "used    : 60776".into(),
            "maximum : 60916".into(),
        ];
        match parse("free", &lines) {
            ParsedMessage::Free(f) => {
                assert_eq!(f.total, 64424);
                assert_eq!(f.used, 60776);
                assert_eq!(f.maximum, 60916);
            }
            _ => panic!("bad parse"),
        }
    }

    #[test]
    fn test_parse_cur_pro_and_feeder_pro() {
        let cur = vec![
            "power:100,fre:3000,duty:100,mode:0".to_string(),
            "head mode:1,fre:8,width:80".to_string(),
            "pulse tick on:150,off:150".to_string(),
            "gas tick early:200,delay:150".to_string(),
            "power tick rise:100,fall:50,early:0,delay:200".to_string(),
            "power on:0, power off:0".to_string(),
            "process index:0".to_string(),
        ];
        let feeder = vec![
            "feeder_mode:0,out_speed:10,len:13,in_speed:20,len:14".to_string(),
            "feeder_cycle:400, smoothness:40,out_delay:0,in_delay:400".to_string(),
        ];

        match parse("cur_pro", &cur) {
            ParsedMessage::ProcessCur(p) => {
                assert_eq!(p.index, Some(0));
                assert_eq!(p.power, Some(100));
                assert_eq!(p.pwm_fre, Some(3000));
                assert_eq!(p.pwm_duty, Some(100));
                assert_eq!(p.mode, Some(0));
                assert_eq!(p.head_mode, Some(1));
                assert_eq!(p.head_fre, Some(8));
                assert_eq!(p.head_width, Some(80));
                assert_eq!(p.pulse_on, Some(150));
                assert_eq!(p.pulse_off, Some(150));
                assert_eq!(p.gas_early, Some(200));
                assert_eq!(p.gas_delay, Some(150));
                assert_eq!(p.pow_rise, Some(100));
                assert_eq!(p.pow_fall, Some(50));
                assert_eq!(p.pow_early, Some(0));
                assert_eq!(p.pow_delay, Some(200));
                assert_eq!(p.power_on, Some(0));
                assert_eq!(p.power_off, Some(0));
            }
            other => panic!("unexpected parse result: {:?}", other),
        }

        match parse("feeder_pro", &feeder) {
            ParsedMessage::ProcessFeeder(p) => {
                assert_eq!(p.feeder_mode, Some(0));
                assert_eq!(p.feeder_out_speed, Some(10));
                assert_eq!(p.feeder_out_len, Some(13));
                assert_eq!(p.feeder_in_speed, Some(20));
                assert_eq!(p.feeder_in_len, Some(14));
                assert_eq!(p.feeder_cycle, Some(400));
                assert_eq!(p.feeder_smoothness, Some(40));
                assert_eq!(p.feeder_out_delay, Some(0));
                assert_eq!(p.feeder_in_delay, Some(400));
            }
            other => panic!("unexpected feeder parse result: {:?}", other),
        }
    }
}
