//! vibefreak-lab: a scriptable measurement front end for the emulator.
//!
//! Reads one JSON object per line on stdin, answers with one JSON object per
//! line on stdout. Emulated time only moves when a command asks for it, so
//! every run is repeatable: there is no wall clock anywhere in here.
//!
//! The `render` command writes two recordings of the same stretch of time:
//!   * `raw_wav` is what the firmware wrote to the DAC (the digital oscillator,
//!     bit for bit what the real instrument computes), and
//!   * `wav` is that signal after the emulator's *model* of the analog filter
//!     and VCA.
//! It also reports the control voltages the firmware sent to the analog board
//! (filter cutoff, resonance, VCA level) so envelope and modulation shapes can
//! be read without guessing them from the audio.

use std::io::{BufRead, Write};
use std::path::{Path, PathBuf};

use serde_json::{json, Value};
use vibefreak_core::{SemFilterMode, VibeFreakEmulator, AUDIO_BLOCK_FRAMES, AUDIO_SAMPLE_RATE};

/// One audio block is 32 frames at 96 kHz.
const BLOCK_MS: f64 = (AUDIO_BLOCK_FRAMES as f64) * 1000.0 / (AUDIO_SAMPLE_RATE as f64);

const POTS: &[(&str, u16)] = &[
    ("cutoff", 0x0101),
    ("resonance", 0x0102),
    ("cyc_rise", 0x0201),
    ("cyc_fall", 0x0203),
    ("cyc_hold", 0x0204),
    ("cyc_amount", 0x0206),
    ("glide", 0x0300),
    ("attack", 0x0601),
    ("decay", 0x0602),
    ("sustain", 0x0603),
    ("filter_amount", 0x0605),
    ("volume", 0x0704),
];

fn find_firmware(arg: Option<PathBuf>) -> Result<PathBuf, String> {
    if let Some(p) = arg {
        return if p.is_file() { Ok(p) } else { Err(format!("firmware not found: {}", p.display())) };
    }
    if let Ok(p) = std::env::var("VIBEFREAK_MFF") {
        let p = PathBuf::from(p);
        if p.is_file() {
            return Ok(p);
        }
    }
    if let Ok(home) = std::env::var("HOME") {
        for rel in [".config/vibefreak/firmware.mff", ".vibefreak/firmware.mff"] {
            let p = Path::new(&home).join(rel);
            if p.is_file() {
                return Ok(p);
            }
        }
    }
    let p = PathBuf::from("firmware.mff");
    if p.is_file() {
        return Ok(p);
    }
    Err("no firmware: pass a .mff path, set VIBEFREAK_MFF, or put it at ~/.config/vibefreak/firmware.mff".into())
}

fn write_wav_mono(path: &str, samples: &[i16]) -> std::io::Result<()> {
    let data_len = (samples.len() * 2) as u32;
    let mut out = Vec::with_capacity(44 + samples.len() * 2);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVEfmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes()); // PCM
    out.extend_from_slice(&1u16.to_le_bytes()); // mono
    out.extend_from_slice(&AUDIO_SAMPLE_RATE.to_le_bytes());
    out.extend_from_slice(&(AUDIO_SAMPLE_RATE * 2).to_le_bytes());
    out.extend_from_slice(&2u16.to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for s in samples {
        out.extend_from_slice(&s.to_le_bytes());
    }
    std::fs::write(path, out)
}

fn push_left(block: &[u8], out: &mut Vec<i16>) -> bool {
    let mut differs = false;
    for frame in block.chunks_exact(4) {
        let l = i16::from_le_bytes([frame[0], frame[1]]);
        let r = i16::from_le_bytes([frame[2], frame[3]]);
        differs |= l != r;
        out.push(l);
    }
    differs
}

fn stats(samples: &[i16]) -> Value {
    let mut peak = 0i32;
    let mut sum = 0f64;
    for &s in samples {
        peak = peak.max((s as i32).abs());
        sum += (s as f64) * (s as f64);
    }
    let rms = if samples.is_empty() { 0.0 } else { (sum / samples.len() as f64).sqrt() };
    json!({ "peak": peak, "rms": (rms * 10.0).round() / 10.0 })
}

struct Lab {
    emu: VibeFreakEmulator,
    blocks: u64,
}

impl Lab {
    fn step_blocks(&mut self, n: usize) {
        for _ in 0..n {
            self.emu.step_audio_block_quantum();
        }
        self.blocks += n as u64;
    }

    fn ms_to_blocks(ms: f64) -> usize {
        (ms / BLOCK_MS).ceil().max(0.0) as usize
    }

    fn oled_rows(&self) -> Vec<String> {
        let fb = self.emu.coproc.get_framebuffer();
        (0..64)
            .map(|y| {
                let page = y / 8;
                let bit = 1u8 << (y % 8);
                (0..128)
                    .map(|x| if fb[page * 128 + x] & bit != 0 { '#' } else { '.' })
                    .collect()
            })
            .collect()
    }

    /// The control voltages the firmware is sending to the analog board right now.
    fn cv_now(&self) -> (u32, u32, f64, f64, f64) {
        let data = self.emu.uc.get_data();
        let tim3 = &data.mmio.timers.timers[2];
        let cutoff_16b = ((tim3.ccr4 & 0xFF) << 8) | (tim3.ccr3 & 0xFF);
        let res_dac = data.mmio.dac.dor1 & 0x0FFF;
        let tim14 = &data.mmio.timers.timers[13];
        let vca = if tim14.arr > 0 { tim14.ccr1 as f64 / tim14.arr as f64 } else { 0.0 };
        let hz = self.emu.audio_proc.filter.get_cutoff_hz() as f64;
        let q = self.emu.audio_proc.filter.get_resonance_q() as f64;
        (cutoff_16b, res_dac, vca, hz, q)
    }

    fn handle(&mut self, req: &Value) -> Result<Value, String> {
        let op = req.get("op").and_then(Value::as_str).ok_or("missing 'op'")?;
        let num = |k: &str| req.get(k).and_then(Value::as_f64);
        let text = |k: &str| req.get(k).and_then(Value::as_str);
        match op {
            "step" => {
                let n = Self::ms_to_blocks(num("ms").unwrap_or(BLOCK_MS));
                self.step_blocks(n);
                Ok(json!({ "blocks": n }))
            }
            "midi" => {
                let bytes: Vec<u8> = req
                    .get("bytes")
                    .and_then(Value::as_array)
                    .ok_or("midi needs 'bytes'")?
                    .iter()
                    .filter_map(|v| v.as_u64().map(|b| b as u8))
                    .collect();
                self.emu.enqueue_midi_bytes(&bytes);
                self.emu.service_usart3_rx();
                Ok(json!({ "sent": bytes.len() }))
            }
            "key" => {
                let key = num("key").ok_or("key needs 'key' 0..24")? as usize;
                let pressure = num("pressure").unwrap_or(200.0) as u8;
                if key > 24 {
                    return Err("key must be 0..24".into());
                }
                self.emu.set_key(key, pressure);
                Ok(json!({}))
            }
            "pot" => {
                let name = text("name").ok_or("pot needs 'name'")?;
                let value = num("value").ok_or("pot needs 'value' 0..4095")?.clamp(0.0, 4095.0) as u16;
                let cid = POTS
                    .iter()
                    .find(|(n, _)| *n == name)
                    .map(|(_, c)| *c)
                    .ok_or_else(|| format!("unknown pot '{name}'"))?;
                self.emu.set_potentiometer(cid, value);
                Ok(json!({}))
            }
            "enc" => {
                let name = text("name").ok_or("enc needs 'name'")?;
                let delta = num("delta").ok_or("enc needs 'delta'")? as i16;
                match name {
                    "preset" => self.emu.step_preset_encoder(delta),
                    "matrix" => self.emu.step_matrix_encoder(delta),
                    "type" => self.emu.step_type_encoder(delta),
                    "rate" => self.emu.step_rate_encoder(delta),
                    "lfo_rate" => self.emu.step_lfo_rate_encoder(delta),
                    "wave" => self.emu.step_wave_encoder(delta),
                    "timbre" => self.emu.step_timbre_encoder(delta),
                    "shape" => self.emu.step_shape_encoder(delta),
                    other => return Err(format!("unknown encoder '{other}'")),
                }
                Ok(json!({}))
            }
            "sw" => {
                let name = text("name").ok_or("sw needs 'name'")?;
                let pressed = req.get("pressed").and_then(Value::as_bool).ok_or("sw needs 'pressed'")?;
                self.emu.set_microswitch(name, pressed);
                Ok(json!({}))
            }
            "click" => {
                let name = text("name").ok_or("click needs 'name'")?;
                let hold = Self::ms_to_blocks(num("hold_ms").unwrap_or(60.0));
                let after = Self::ms_to_blocks(num("after_ms").unwrap_or(120.0));
                self.emu.set_microswitch(name, true);
                self.step_blocks(hold);
                self.emu.set_microswitch(name, false);
                self.step_blocks(after);
                Ok(json!({}))
            }
            "filter_mode" => {
                let mode = match text("mode").unwrap_or("lp") {
                    "lp" | "lowpass" => SemFilterMode::LowPass,
                    "bp" | "bandpass" => SemFilterMode::BandPass,
                    "hp" | "highpass" => SemFilterMode::HighPass,
                    other => return Err(format!("unknown filter mode '{other}'")),
                };
                self.emu.set_filter_mode_switch(mode);
                Ok(json!({}))
            }
            "touch" => {
                let value = num("value").unwrap_or(0.0).clamp(0.0, 4095.0) as u16;
                let touched = req.get("touched").and_then(Value::as_bool).unwrap_or(true);
                self.emu.set_touch_strip(value, touched);
                Ok(json!({}))
            }
            "render" => {
                let n = Self::ms_to_blocks(num("ms").ok_or("render needs 'ms'")?);
                let cv_every = num("cv_every").unwrap_or(0.0) as usize;
                let mut post = Vec::with_capacity(n * AUDIO_BLOCK_FRAMES);
                let mut raw = Vec::with_capacity(n * AUDIO_BLOCK_FRAMES);
                let mut stereo_differs = false;
                let (mut cv_cut, mut cv_res, mut cv_vca, mut cv_hz) = (vec![], vec![], vec![], vec![]);
                for i in 0..n {
                    let block = self.emu.step_audio_block_quantum();
                    stereo_differs |= push_left(&block, &mut post);
                    let raw_block = self.emu.audio_proc.last_raw_block;
                    push_left(&raw_block, &mut raw);
                    if cv_every > 0 && i % cv_every == 0 {
                        let (cut, res, vca, hz, _q) = self.cv_now();
                        cv_cut.push(cut);
                        cv_res.push(res);
                        cv_vca.push((vca * 10000.0).round() / 10000.0);
                        cv_hz.push((hz * 10.0).round() / 10.0);
                    }
                }
                self.blocks += n as u64;
                if let Some(path) = text("wav") {
                    write_wav_mono(path, &post).map_err(|e| format!("{path}: {e}"))?;
                }
                if let Some(path) = text("raw_wav") {
                    write_wav_mono(path, &raw).map_err(|e| format!("{path}: {e}"))?;
                }
                let mut out = json!({
                    "frames": post.len(),
                    "post": stats(&post),
                    "raw": stats(&raw),
                    "stereo_differs": stereo_differs,
                });
                if cv_every > 0 {
                    out["cv"] = json!({
                        "step_ms": BLOCK_MS * cv_every as f64,
                        "cutoff_16b": cv_cut,
                        "resonance_dac": cv_res,
                        "vca": cv_vca,
                        "model_cutoff_hz": cv_hz,
                    });
                }
                Ok(out)
            }
            "cv" => {
                let (cut, res, vca, hz, q) = self.cv_now();
                Ok(json!({ "cutoff_16b": cut, "resonance_dac": res, "vca": vca, "model_cutoff_hz": hz, "model_q": q }))
            }
            "codec" => {
                let codec = &self.emu.uc.get_data().mmio.i2c1.codec;
                Ok(json!({ "page0": codec.page0.to_vec(), "page1": codec.page1.to_vec() }))
            }
            "oled" => Ok(json!({ "rows": self.oled_rows() })),
            "leds" => Ok(json!({
                "matrix": self.emu.coproc.get_matrix_leds().to_vec(),
                "panel": self.emu.get_panel_leds().to_vec(),
                "icons": self.emu.get_icon_leds().to_vec(),
            })),
            "swd" => {
                let cmd = text("cmd").ok_or("swd needs 'cmd'")?;
                Ok(json!({ "out": self.emu.execute_swd_command(cmd) }))
            }
            "mem" => {
                let addr = num("addr").ok_or("mem needs 'addr'")? as u64;
                let len = (num("len").unwrap_or(64.0) as usize).min(1 << 20);
                let mut buf = vec![0u8; len];
                self.emu.uc.mem_read(addr, &mut buf).map_err(|e| format!("read {addr:#x}: {e:?}"))?;
                let hex: String = buf.iter().map(|b| format!("{b:02x}")).collect();
                Ok(json!({ "hex": hex }))
            }
            "save_qspi" => {
                let path = text("path").ok_or("save_qspi needs 'path'")?;
                self.emu.flush_qspi_to_disk(path).map_err(|e| e.to_string())?;
                Ok(json!({}))
            }
            "time" => Ok(json!({ "blocks": self.blocks, "ms": self.blocks as f64 * BLOCK_MS })),
            other => Err(format!("unknown op '{other}'")),
        }
    }
}

fn main() {
    let mut firmware: Option<PathBuf> = None;
    let mut qspi: Option<PathBuf> = None;
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--qspi" => qspi = args.next().map(PathBuf::from),
            "-h" | "--help" => {
                eprintln!("usage: vibefreak-lab [FIRMWARE.mff] [--qspi IMAGE.bin]\nJSON commands on stdin, one per line. See docs/LAB.md.");
                return;
            }
            _ => firmware = Some(PathBuf::from(a)),
        }
    }

    let stdout = std::io::stdout();
    let reply = |v: Value| {
        let mut out = stdout.lock();
        let _ = writeln!(out, "{v}");
        let _ = out.flush();
    };

    let path = match find_firmware(firmware) {
        Ok(p) => p,
        Err(e) => {
            reply(json!({ "ok": false, "error": e }));
            std::process::exit(2);
        }
    };
    let mut emu = match VibeFreakEmulator::from_mff_file(&path) {
        Ok(e) => e,
        Err(e) => {
            reply(json!({ "ok": false, "error": format!("{e}") }));
            std::process::exit(2);
        }
    };
    if let Some(q) = &qspi {
        if let Err(e) = emu.load_qspi_from_disk(q) {
            reply(json!({ "ok": false, "error": format!("{}: {e}", q.display()) }));
            std::process::exit(2);
        }
    }
    emu.boot(100_000_000);

    let mut lab = Lab { emu, blocks: 0 };
    // Run until the preset screen is up and the firmware has read every knob once.
    let mut screen_up = false;
    for _ in 0..6000 {
        lab.step_blocks(1);
        let lit = lab.emu.coproc.get_framebuffer().iter().filter(|&&b| b != 0).count();
        if lit > 200 && lab.emu.initial_pot_idx >= 12 {
            screen_up = true;
            break;
        }
    }
    lab.step_blocks(1500);
    reply(json!({
        "ok": true,
        "ready": screen_up,
        "firmware": path.display().to_string(),
        "block_ms": BLOCK_MS,
        "boot_ms": lab.blocks as f64 * BLOCK_MS,
    }));

    for line in std::io::stdin().lock().lines() {
        let Ok(line) = line else { break };
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let req: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(e) => {
                reply(json!({ "ok": false, "error": format!("bad JSON: {e}") }));
                continue;
            }
        };
        if req.get("op").and_then(Value::as_str) == Some("quit") {
            reply(json!({ "ok": true }));
            break;
        }
        match lab.handle(&req) {
            Ok(mut v) => {
                v["ok"] = json!(true);
                reply(v);
            }
            Err(e) => reply(json!({ "ok": false, "error": e })),
        }
    }
}
