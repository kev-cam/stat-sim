# Wi-Fi (802.11 OFDM): a reference, and an outside modem under test

A start on doing for Wi-Fi what [`../cc2652r`](../cc2652r/README.md) does for Bluetooth LE: a
reference for the physical layer and the MAC frames, written from the standard, and somebody else's
modem run in nvc and judged against it.  The modem is Nuand's bladeRF-wiphy, an 802.11a/g modem in
VHDL for the bladeRF 2.0 micro.  It runs here whole (transmitter, receiver, acknowledgements,
channel access, host interface), and this page says how, what the bench checks and what it found.

What is not here yet is the air: the modem sits on a wire, at its converters' samples, with frames
from the reference put on the wire beside it.  There is no radio model around it, no arena, and no
tester that answers in real time (see [Limits](#limits)).

## The parts

| part | file | what it is |
|---|---|---|
| physical layer | `wifi_phy.py` | the 20 MHz OFDM PPDU, 6 to 54 Mb/s: `encode` a PSDU to samples, `decode` samples to a PSDU with rate, length, EVM, carrier offset |
| MAC frames | `wifi_mac.py` | the frames a test needs (data, ACK, RTS, beacon, probe, authentication, association), the FCS, the intervals of the OFDM PHY, a parser |
| build | `wiphy/wiphy_build.py` | compiles a bladeRF-wiphy checkout into nvc libraries, with the stand-ins below and a few changes made to copies of its files |
| vendor stand-ins | `wiphy/altera_mf_sim.vhd`, `lpm_sim.vhd`, `wlan_pll_sim.vhd` | what the design takes from the FPGA vendor: `scfifo`, `dcfifo`, `lpm_divide`, and the receiver's PLL |
| bench | `wiphy/wiphy_pair_tb.vhd` | one or two `wlan_top` on a wire, each with a host; injected frames; logs of the wire and of what the hosts are told |
| runner | `wiphy/wiphy_pair.py` | writes the scenarios, runs them, decodes the wire with `wifi_phy` and `wifi_mac`, prints a line per check |

`python3 wifi_phy.py check` and `python3 wifi_mac.py check` run the two references' own checks
(every rate through a channel with noise, carrier offset and echoes; the frame formats).

The modem is not part of this repository: <https://github.com/Nuand/bladeRF-wiphy> (GPL-2.0; the
runs below are of commit `8623814`, 2024-04-14).  Its host interface's types are in one file of
<https://github.com/Nuand/bladeRF>, `hdl/fpga/ip/nuand/synthesis/fifo_readwrite_p.vhd`.

## The set-up

      host 0 (sta0.script)                         host 1          reference frames
          |  packets, status                          |             wifi_phy.encode
      wlan_top                                    wlan_top              |
          |  DAC, ADC: 20 MS/s on 40 MHz              |                 |
          +---------------------- the wire -----------+-----------------+
                                     |
                                  air.log  ->  wifi_phy.decode, wifi_mac.Frame  ->  checks

- A **host** hands its modem frames at given times and logs what the modem hands back: received
  frames and transmit status.  It follows the packet mode of the bladeRF's `fifo_reader`, which is
  what feeds `wlan_top` on the board.
- The **wire** carries each station's DAC samples to the other's ADC with a gain, adds the injected
  samples and a little noise, and clips at 12 bits.  A path of it can be cut for a time.
- **Reference frames** are made beforehand, so the reference cannot react.  Where a test needs an
  answer at a time the modem decides (an acknowledgement of its own frame), the scenario is run
  twice: once to see when, once with the answer in place.  The simulation repeats exactly.
- With two stations the second is another copy of the modem.  Both then have the same address:
  the modem's is a constant in `wlan_rx.vhd` (`70:B3:D5:7D:80:01`).

## What it needs

- An nvc build (`--nvc-build` or `NB`) at 6843f9926 or later, where its regression tests
  `selfinst1` to `selfinst4` pass.  The design's FFT is an architecture that instantiates another
  architecture of its own entity, with expressions for actuals; nvc before that evaluated them
  against the wrong port and the transmitter's data symbols came out as zeros.
- A bladeRF-wiphy checkout (`--src` or `WIPHY_SRC`) and `fifo_readwrite_p.vhd` (`--host-pkg` or
  `WIPHY_HOST_PKG`).
- Python 3 with numpy.

## Running it

    wiphy_pair.py --work <dir> ack       reference frames to the modem: acknowledgements, timing, what its host gets
    wiphy_pair.py --work <dir> send      its host sends: broadcast, a frame nobody answers, one that is answered
    wiphy_pair.py --work <dir> defer     its host has frames while the wire is busy
    wiphy_pair.py --work <dir> pair      two modems, one sends to the other
    wiphy_pair.py --work <dir> levels    one frame at a row of input levels
    wiphy_pair.py --work <dir> all

    --keep       use the libraries already in <dir>
    -v           the timeline of each run: every frame on the wire and every packet to a host

The build takes a few seconds and a scenario half a minute to two (one nvc thread; `ack` is 4 ms of
simulated time in 50 s).  The exit status is 0 when no check fails.

## What the bench checks

A line per check: `PASS`, `FAIL`, or `NOTE` for something measured that is not a requirement.
Times are at the modem's samples; a frame ends where its last OFDM symbol does.

| scenario | check | what is done and looked for |
|---|---|---|
| `ack` | `ack 6` .. `ack 54` | a 100-octet data frame to the modem at each rate: its host gets it, and an ACK to the sender follows |
| | `other address`, `broadcast`, `bad FCS` | frames it must not acknowledge |
| | `probe request`, `long frame`, `shortest data` | a management frame, 1536 octets at 54 Mb/s, 28 octets |
| | `sifs` | the acknowledgements start 16 us after the frame, within 0.9 us |
| | `ack rate` | the rate of the acknowledgements |
| | `rts` | an RTS to it is answered by a CTS |
| `send` | `broadcast` | a broadcast from its host is sent once, FCS right |
| | `no answer` | an unanswered frame is sent again with the retry bit, and the host is told there was no acknowledgement |
| | `answered` | with an ACK 16 us after the frame it is sent once and the host is told it was acknowledged |
| | `retry limit` | how often it sends an unanswered frame |
| `defer` | `defer`, `own next` | a frame handed over while the wire is busy, and the one behind it, wait DIFS (34 us) at least |
| | `idle access` | how soon a frame goes out on an idle wire |
| | `backoff` | two frames handed over together, the first acknowledged: the wire turns busy again while the second waits, and it starts DIFS and 0 to 15 slots after (34 to 169 us) |
| `pair` | `pair` | one modem's frame reaches the other's host, is acknowledged, and its own host is told so |
| `levels` | `input level` | the ADC levels at which a 54 Mb/s frame is received |
| all | `whole frames` | every frame the modem sent has the OFDM symbols its SIGNAL field calls for |

## Results so far

bladeRF-wiphy `8623814`, built as described under [Changes](#changes-made-to-simulate-it).

    ack
    PASS  ack 6            ACK at 6 Mb/s, 3.18 us after the frame; host got the frame: yes
    PASS  ack 9            ACK at 6 Mb/s, 7.17 us after the frame; host got the frame: yes
    PASS  ack 12           ACK at 6 Mb/s, 3.48 us after the frame; host got the frame: yes
    PASS  ack 18           ACK at 6 Mb/s, 7.17 us after the frame; host got the frame: yes
    PASS  ack 24           ACK at 6 Mb/s, 7.47 us after the frame; host got the frame: yes
    PASS  ack 36           ACK at 6 Mb/s, 8.08 us after the frame; host got the frame: yes
    PASS  ack 48           ACK at 6 Mb/s, 7.47 us after the frame; host got the frame: yes
    PASS  ack 54           ACK at 6 Mb/s, 8.97 us after the frame; host got the frame: yes
    PASS  other address    nothing sent; host got the frame: yes
    PASS  broadcast        nothing sent; host got the frame: yes
    PASS  bad FCS          nothing sent; host got the frame: no
    PASS  probe request    ACK at 6 Mb/s, 3.18 us after the frame; host got the frame: yes
    PASS  long frame       ACK at 6 Mb/s, 9.47 us after the frame; host got the frame: yes
    PASS  shortest data    ACK at 6 Mb/s, 8.78 us after the frame; host got the frame: yes
    FAIL  sifs             acknowledgements start 3.18 to 9.47 us after the frame (16 us, +-0.9)
    NOTE  ack rate         always 6 Mb/s (with 6, 12 and 24 basic the standard asks for 6/12/24 by the frame's rate)
    FAIL  rts              an RTS to it gets no answer (a CTS is due)
    PASS  whole frames     11 frame(s) sent, all with the symbols their length calls for
    send
    PASS  broadcast        sent 1 time(s), at 12 Mb/s, FCS right, 10.57 us after its host gave it
    PASS  no answer        2 transmission(s): 24 Mb/s, then 18 Mb/s (retry bit); 125.3 us from the end of one to the start of the next; host told: no acknowledgement
    NOTE  retry limit      2 transmissions of an unanswered frame (the standard's default is 7 for a short frame)
    FAIL  whole frames     2 of 5 frame(s) a symbol short: 76 octets at 12 Mb/s, 88 octets at 18 Mb/s (16 + 8 x octets + 6 tail bits need one symbol more than 16 + 8 x octets)
    PASS  answered         acknowledged 16 us after its end: sent 1 time(s); host told: acknowledged
    defer
    FAIL  defer            frame handed over while the wire was busy starts 26.20 us after the busy frame ends (DIFS is 34 us, and a backoff of 0 to 15 slots of 9 us follows it)
    FAIL  own next         its next frame starts 19.62 us after its own (DIFS and a backoff: 34 us at least)
    NOTE  idle access      a frame handed over on an idle wire starts 10.58 us later
    FAIL  backoff          with a frame waiting, the wire turns busy again (the ACK of the frame before it): it starts 602.20, 602.20, 26.20, 26.20 us after that ACK (DIFS and 0 to 15 slots: 34 to 169 us)
    pair
    PASS  pair             sent 1 time(s); the other acknowledged 1 time(s), 7.10 us after the frame; the other's host got the frame: yes; sender's host told: acknowledged
    levels
    NOTE  input level      a 54 Mb/s frame is received at 450, 600, 800, 1000, 1200 rms and not at 150, 300, 1400, 1700, 2000 (a 12-bit converter's full scale is 2047)

What the bench found in the design:

- **The transmitter leaves out the last OFDM symbol of some frames.**  It sends as many data
  symbols as 16 + 8 x octets bits need, not counting the six tail bits; when those need a symbol of
  their own the frame is one symbol short of what its SIGNAL field says: every third length at
  6 Mb/s, every sixth at 12 Mb/s, two of every nine at 9 Mb/s, one in 27 at 54 Mb/s (the 100-octet
  frame of the design's own transmit bench is one of them at 6 and at 12 Mb/s).  The missing symbol
  holds only tail and padding, so a receiver that gets zeros there still has the frame; one that
  gets noise or the next transmission there decodes the frame's last bits, its FCS, without the
  code's termination.
- **Acknowledgements come early, and when the decoder is done.**  They start 7.2 to 9.5 us after
  the frame, and 3.2 to 3.5 us after it when its last symbol holds only tail and padding (the three
  such frames of the run); the standard has 16 us within 0.9 us.  The converters' and filters'
  delays on the board come on top of this and are not modelled here.
- **Channel access is not the standard's.**  It does defer to energy on the wire.  A frame waiting
  while the wire is busy goes out 26 us after the busy frame ends, and the next one 20 us after the
  modem's own frame, where DIFS is 34 us and a backoff of 0 to 15 slots of 9 us follows it.  The
  modem has no backoff until the wire turns busy again while a frame waits; its contention mask
  then widens from the top bit, and the wait is 26 us, or 576 us longer (128 units of 4.5 us), by
  a bit taken from the ADC's samples: 602, 602, 26 and 26 us in four tries.
- **The address of the acknowledgement is in a register that the receive framer's reset function
  does not mention**, and the framer resets between the frame and the acknowledgement.  A simulator
  makes the address undefined and the ACK goes out with dead address and FCS.  Hardware presumably
  keeps a register that its reset does not name (the board's acknowledgements would not arrive
  otherwise); the copy used here is changed to hold it, and everything above about acknowledgements
  rests on that.
- **A frame over about 1470 octets stops a simulator**: five bit counts in three files are
  declared to 12000.  Ranges like that are synthesised as 14 bits; the copies used here say so.
- **No CTS** to an RTS; **acknowledgements always at 6 Mb/s**; an unanswered frame is sent **twice**,
  the second time one rate lower; every frame with a right FCS is handed to the host, acknowledgements
  and other stations' frames included.
- **The receiver's input level has a floor and a ceiling.**  Its burst detector needs about 390 rms
  (in ADC counts; `wlan_agc.vhd` compares the smoothed power with 150000): a 54 Mb/s frame is
  received at 450 and not at 300.  At the top, with a converter that does not clip, frames are
  received at 1500 and not at 1600: the acquisition's correlator has overflowed its 32 bits by
  then and the FFT window lands 16 samples early, into the symbol before, which the low rates
  survive and the high ones do not.  The bench's 12-bit converter clips first: there the frame is
  received at 1200 and lost at 1400.  On the board the RFIC's gain control is to put the signal in
  between.  The design's own receive bench reads the files its transmit bench writes, which are at
  1845 rms.

And in the tools:

- **nvc** looked up the names in an actual of an instance in the instance's own scope first.
  When an architecture instantiates another architecture of its entity, or itself, the two scopes
  hold the same declarations, and the instance's port was connected to itself: for an expression
  actual, for a conversion on either side (one of them crashed).  Repaired in `src/lower.c`
  (6843f9926), with the tests `selfinst1` to `selfinst4`.  One corner is left, and not tested:
  where such an actual names a generic that the instance gives another value and the formal's type
  depends on that generic too, the type is evaluated with the outer value.
- **A vendor stand-in has to keep the vendor's latencies.**  The receiver finds its FFT window by
  counting samples out of a dual-clock FIFO from a mark that does not go through the FIFO.  The first
  stand-in passed words straight through; the vendor's takes two write clocks and a read clock
  (the FIFO user guide's table).  The stand-ins here keep those numbers, and the PLL stand-in puts
  its edges in the same delta cycle as the reference's, because the design also passes signals
  between the two clocks directly.

## Changes made to simulate it

`wiphy_build.py` makes them in copies, never in the checkout, and prints each one.

| file | change | why |
|---|---|---|
| `fft.vhd` | architecture `arch` moved before `mult` | `mult` instantiates it; nvc binds an instance when it analyses it |
| `wlan_tx_p.vhd` | one assignment dropped | it assigns 0 to a field of range 1 to 1366, then 1 |
| `wlan_bsd.vhd` | a range written out | a pure function sizes a variable by a port's range |
| `wlan_rx_p.vhd`, `wlan_rx_controller.vhd`, `wlan_depuncturer.vhd` | ranges to 12000 made 14 bits | see above |
| `wlan_rx_framer.vhd` | `ack_mac` holds through `NULL_STATE` | see above |

The files are analysed with `--relaxed` (a shared variable that is not of a protected type).

## Limits

- The 20 MHz OFDM rates only.  The design's DSSS receive path is built and idle.
- No radio: no frequency offset between the stations, no filters, no gain control (the gain
  requests are tied as the bladeRF's top level ties them), no delay on the wire.
- The reference is in Python and its frames are made before the run.  A tester inside the
  simulation, on the arena with the AD9361 model, is the next step; `wifi_phy.py` is what its VHDL
  would be checked against.
- One outside design so far.
