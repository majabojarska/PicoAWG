# PicoAWG

## About

> [!WARNING]
> This is an early work in progress. Expect lots of changes and experimentation.
> I provide no guarantees whatsoever regarding the development progress.
> If you need an arbitrary waveform generator right now, consider looking elsewhere.
> Also, I'm not an electrical engineer. This project might contain design flaws and (unintentionally) misleading information, use at your own risk.

### The What?

Arbitrary Waveform Generator (AWG) based on the Raspberry Pi Pico (RP2040).

| Parameter            | Value           |
| -------------------- | --------------- |
| Max Sampling Rate    | 125MSa/s        |
| Channels             | 2               |
| Vertical Resolution  | 11 bit          |
| Max Output Frequency | 5 MHz (unsure)  |
| Waveform length      | 2048pt/s        |

> It's not much, [but it's honest work](https://knowyourmeme.com/memes/but-its-honest-work).

In addition:

- Buffered outputs.
- Built-in waveform generators:
  - saw (positive, negative),
  - sine,
  - triangle,
  - sinc,
  - pulse (rectangular, adjustable duty cycle),
  - complex waves via combination of the above. Not sure what the UI/UX flow will be here, in standalone mode. We'll get there when we get there.
    - > [!NOTE]
      > This implies wavetable arithmetics.
- Phase shift (per-channel, independent).
- Configurable via:
  - standalone built-in user interface (LCD, buttons, rotary encoders),
  - host software.
    - Overrides standalone mode until disconnected from host.
    - Allows configuring an actual arbitrary wavetable (up to AWG storage limits).
- [Moonshot] Adjustable DC offset.

### The Why?

- There are some RP2040-based AWG projects on the web, but in my opinion they're somewhat lacking in various areas ([1](https://www.instructables.com/Arbitrary-Wave-Generator-With-the-Raspberry-Pi-Pic/), [2](https://github.com/BourneAgainMax/ArbitraryWaveFormGenerator_RaspPico/), [3](https://github.com/LifeWithDavid/Raspberry-Pi-Pico-PIO/blob/d244a4b7d0b5c187c08e7311026b45fdff7da13e/EP%2014%20AWG%20Files.txt)). Think: input configuration flexibility, code quality, toolchain, documentation, extensibility. These are some of the areas I'd like to (attempt to) improve by engineering my own solution.
- Pre-made signal generators can get quite pricey. Granted, they offer a wide set of features, high precision (14+ bits), large wavetable storage (16+ Ksps) and good performance. However, when it comes to electronics, I'm just a hobbyist. I can get by just fine with a far simpler AWG.
- Building an AWG from scratch is a great opportunity to learn both digital and analog electronics.
- This is a chance to contribute back to the open source community.

### The How?

- The RP2040 will output the waveform samples to PIO via DMA. Each PIO will output a logic signal corresponding to one target sample's bit, as a (DC-coupled) CMOS logic signal ($3.3V_{pp}$).
  - After the PIO reconfiguration are done and DMA transfer are done, the RP2040 core is free to do anything. This means input polling, UI refresh and UART comms can be done in a non-blocking fashion, without needing to take preemption issues into account, in the context of feeding wavetable samples.
- The 11-bit samples will be converted to the analog domain via a [R-2R resistor ladder network](https://en.wikipedia.org/wiki/Resistor_ladder) (DAC).
- The DAC output will be amplified and decoupled by an op-amp amplification stage.
  - The [AD8056](https://www.digikey.com/en/products/detail/analog-devices-inc/AD8056AN/11532438) seems like a good dual-channel candidate for this purpose, given the high-frequency signals.
- The op-amp will need both a negative and positive supply. This implies either:
  - a dual supply ($V_{-}$, $0V$, $V_{+}$).
  - a single supply used as a split supply with a virtual ground op-amp configuration. Leaning towards this approach, since it's fairly easy to get a $12V$-$24V$ single DC supply, making this project more accessible.
- In host mode (non-standalone), the host software will communicate with the AWG via UART.

### Risks

- GPIO count/capabilities. Is there a way to configure 22 PIO pins while keeping `UART0` and one `I2C bus` functional?

## Development

### Setting up the Debug Probe

This project leverages the [raspberrypi/debugprobe](https://github.com/raspberrypi/debugprobe) for development and debugging.

#### Linux

Copy [`99-pico-debug-probe.rules`](99-pico-debug-probe.rules) to `/etc/udev/rules.d/`

To make the rule effective immiediately, run:

```bash
udevadm control --reload-rules && udevadm trigger
```

#### Windows, Darwin

> womp womp

Sorry, no idea.

## Attributions

This project is based on the following resources:

- This Rust project was generated with the [rp-rs/rp2040-project-template](https://github.com/rp-rs/rp2040-project-template)
- [Arbitrary Wave Generator With the Raspberry Pi Pico](https://www.instructables.com/Arbitrary-Wave-Generator-With-the-Raspberry-Pi-Pic)
- [Raspberry Pi Pico PIO - Ep. 14 - Arbitrary Waveform Generator](https://www.youtube.com/watch?v=_lZ1Pw6WAqI)
