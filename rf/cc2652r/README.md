# The Bluetooth LE test environment

This directory holds a simulated Bluetooth LE test bench: a reference radio, a tester that behaves
as a Bluetooth central, and a way to put somebody else's baseband design in the air beside them
and see whether it behaves as the specification says.  Everything runs in nvc (`--std=2040`,
spectral events).  This page says what the parts are, how to run them, how to attach a new design
and what has been found so far.  The detail of the models (where the numbers come from, how a GFSK
packet becomes spectral events, the nvc repairs made along the way) is in
[`../README.md`](../README.md), sections `cc2652r/` and `Federation`.

## The set-up

      tester (central + host)                       device under test (peripheral)
      ble_tester                                    ble_controller, NODE_PERIPHERAL
          |  cfg, tx, rx (packets)                      |  cfg, tx, rx (packets)
      radio  <- cc2652r, or an outside design       radio  <- cc2652r, or an outside design
          |  RF pin                                     |  RF pin
      antenna (0 m)  ~~~~~~~~~~ the arena ~~~~~~~~~~  antenna (10 m by default)

- A **radio** takes packets from its software and puts a 2.4 GHz signal on its RF pin, and the
  other way round.  The software above it never sees a sample.
- The **arena** is the air between the antennas: free-space loss and delay by distance.  It can sit
  inside one simulation or be shared by several (`--fed`), each side its own nvc process.
- The **device under test** is one radio of the pair.  By default it is the peripheral's; with
  `connect --central` it is the tester's, and the peripheral is the reference radio.

| part | file | what it is |
|---|---|---|
| reference radio | `cc2652r.vhd` (Python reference `cc2652r.py`) | TI CC2652R in its four LE modes, fitted to the data sheet |
| physical layer | `ble_phy_pkg.vhd` (`ble_phy.py`) | packets, whitening, CRC, coding, from the Core Specification |
| link layer | `ble_controller.vhd`, `ble_ll_pkg.vhd` | test transmitter and receiver, advertiser, scanner, peripheral |
| tester | `ble_tester.vhd` | a central and enough of a host to test a peripheral over the air |
| scenarios | `ble_link.vhd` | the devices, their antennas and where they stand |
| runner | `ble_nvc.py` | builds, runs, tabulates; the only thing to call |
| outside design 1 | `btle_phy_radio.vhd` | `btle_phy` of JiaoXianjun/BTLE (Verilog) behind an RF front end |
| outside design 2 | `ucb_bmc_radio.vhd`, `ucb_bmc/` | `BMC` of ucb-bar/baseband-modem (Chisel) behind a front end and a host |

The outside designs are not part of this repository.  Their Verilog is translated whole to VHDL by
sv2ghdl when a run asks for them.

## What it needs

- An nvc build with the arena support (`lib/sv2vhdl/libresolver.so`, `libarena.so`): `--nvc-build`
  or `NB`.
- For an outside design: an sv2ghdl checkout (`SV2GHDL`) and an iverilog with the VHDL back end
  (`IVERILOG`, or sv2ghdl's own choice).
  - BTLE: a checkout's `verilog` directory (`BTLE_SRC`).
  - Berkeley modem: `BMC.v` (`BMC_V`), which `ucb_bmc/emit.sh <directory>` makes with sbt and a
    JDK up to 17; give `--heap 2g`.
- For `--accel`: sv2ghdl's `yosys/gen_statemachine` built (`GEN_STATEMACHINE` if nvc does not find
  it).  The first run of a design compiles its model (13 minutes for the Berkeley modem); it is
  kept in `~/.cache/nvc/accel` after that.

## Running it

Global options go before the subcommand.

    ble_nvc.py selftest                         the radio's own bench, pin to pin with a CC2652R
    ble_nvc.py range [--compare]                packet error rate against distance (Direct Test Mode)
    ble_nvc.py scan                             a beacon, a neighbour and an active scanner
    ble_nvc.py connect                          the tester puts a peripheral through its tests
    ble_nvc.py connect --central                the device under test is the tester's radio instead

    --dut cc2652r | btle | btle-tail | bmc | bmc-txend     the radio under test (default cc2652r)
    --fed                                       also as two simulations sharing the arena
    --accel                                     the translated design as one compiled model
    --ppm A B, --power DBM, connect --dist M    crystal errors, transmit power, distance

A typical run of an outside design:

    NB=<nvc build> SV2GHDL=<sv2ghdl> BTLE_SRC=<BTLE>/verilog \
        ble_nvc.py --dut btle-tail --accel --fed connect --events 10 --time 0.25

`--events 10 --time 0.25` is the short form of the tester's pass, enough for every step; the
defaults (40 events, 2 s) are for the reference radio, which is fast.  The exit status is 0 when
the summary passes and a federated run gave the same lines.

In `scan` the device under test is the scanner.  In `range` it must be the CC2652R: the outside
designs send whitened LE 1M packets only, and have no test mode.

## What the tester checks

One pass, a line per step, `PASS` or `FAIL` with what was measured.

| step | what the tester does and checks |
|---|---|
| `adv`, `adv_chan` | hears four ADV_INDs on channel 37 (interval 20 ms or more, advDelay within 10 ms), then one on 38 and 39 |
| `scan` | three SCAN_REQs, each answered by a SCAN_RSP 150 us (+-2) later |
| `connect` | CONNECT_IND; the device answers within the first six connection events |
| `version`, `features` | LL_VERSION_IND and LL_FEATURE_REQ / LL_FEATURE_RSP exchanges |
| `mtu`, `services` | ATT Exchange MTU and GATT primary service discovery |
| `per` | connection events of empty packets: fewer than 30.8 % unanswered or with a bad CRC |
| `t_ifs` | the device's T_IFS over the connection, 150 us +-2, path delay taken out |
| `terminate` | LL_TERMINATE_IND is acknowledged; lists the data channels of unanswered events |

The peripheral reports its own side on one line: advertising events, connections, connection
events heard and missed, bad CRCs, whether the connection was terminated or lost.  With
`--central` that line is the evidence of what the device under test sent.

## Attaching another design

A design joins as a radio: an entity with the ports of `cc2652r` (`ant`, `cfg`, `tx`, `tx_busy`,
`rx`), so the link layer and the tester above it stay as they are.

1. Get the design as Verilog that sv2ghdl translates (it took both designs whole).
2. Write the wrapper: whatever the design lacks to be a radio.  For BTLE that was an RF front end
   and a clock; for the Berkeley modem also a host, a VCO model and its tables.  The two existing
   wrappers are the patterns.
3. Give its transmit latency in a small package (`..._radio_pkg.vhd`); the link layer hands
   packets over that much early where T_IFS counts.
4. Add an empty stand-in (`..._radio_none.vhd`) for runs that do not ask for it, a `dut` number in
   `ble_link.vhd` and a `--dut` name in `ble_nvc.py`.
5. Write a pin-to-pin bench against a CC2652R (`tb_..._radio.vhd`) and run `selftest` before the
   tester: it separates wrapper faults from design faults.

A device modelled elsewhere needs none of this: it can be its own simulation with an antenna on the
`ism2g4_td` band, joined to the tester's through the arena.

## Results so far

At 10 m, 0 dBm, `connect --events 10 --time 0.25`.  "As peripheral" is the default; "as central" is
`--central`.

| radio under test | as peripheral | as central | T_IFS |
|---|---|---|---|
| CC2652R (reference) | 11 of 11 | 11 of 11 | 150.00 us |
| BTLE as published (`btle`) | fails at `adv`: every advertisement has a bad CRC | `scan` and `connect` fail: the peripheral answers nothing | |
| BTLE, last symbol completed (`btle-tail`) | 11 of 11 | 11 of 11 | 149.75 us |
| Berkeley modem as published (`bmc`) | `adv` passes, `scan` and `connect` fail | `scan` and `connect` fail | |
| Berkeley modem, host ends transmissions (`bmc-txend`) | 11 of 11 | 11 of 11 | 149.91 to 149.94 us |

Defects the tester found in the published designs:

- **BTLE: the last symbol of every packet is not sent.**  The modulator's Gaussian filter delays
  the waveform by one symbol and the modulator stops on time, so the last bit of the CRC is cut
  off.  Its own receiver does not notice; another receiver gets that bit wrong for some packets.
- **BTLE: data channel 0 does not work.**  Channel number 0 is taken as "not set" and whitened as
  63, so the design neither sends nor receives on 2404 MHz.  A connection loses that event and
  carries on.
- **Berkeley modem: it is deaf after it transmits.**  The controller takes the end of a BLE
  transmission from the 802.15.4 modulator, which runs four times longer, so the design is still in
  its transmit state when the answer comes.  As a central it shows plainly: the peripheral accepts
  its CONNECT_IND and hears every connection event, and the design hears none of the answers.
- **Berkeley modem: channel index and frequency index.**  The design uses one index for whitening
  and for the VCO table; its documentation calls it the frequency's, which would whiten 37 of the
  40 channels wrongly.  The wrapper loads the table by BLE channel index.

Checks on the environment itself:

- Federated (`--fed`), every working combination reports the same lines as the one simulation.
- `--accel` gives the same report as the plain run for both designs, in `connect` and in `scan`.
- The translations are exact: BTLE's 1216 transmit samples match the Verilog in vvp; the Berkeley
  modem's pins match over 24 626 clocks but where the Verilog itself has unknown bits.
- The reference radio agrees with the data sheet (sensitivity within 0.2 dB on each PHY) and with
  its Python reference at range, as statistics.

Run times (one nvc thread; a model already compiled for `--accel`):

| run | plain | `--accel` |
|---|---|---|
| `connect`, CC2652R | 3.5 s | |
| `connect`, `btle-tail` as peripheral | 17.9 s | 3.4 s |
| `connect`, `btle-tail` as central | 18.2 s | 2.9 s |
| `connect`, `bmc-txend` as peripheral | 8 to 10 minutes | 28 s |
| `scan` (2 s simulated), `btle-tail` | 105.5 s | 20.6 s |
| `scan` (2 s simulated), `bmc-txend` | 3070 s | 202 s |

## Limits

- Connections are LE 1M, one packet each way in an event, with channel selection algorithm #1; no
  encryption, and no PHY, connection parameter or channel map updates.
- Legacy advertising only; no extended or directed advertising, filter policies or privacy.
- The tester's host does ATT Exchange MTU and primary service discovery, nothing more.
- The outside designs are tested as LE 1M radios under this repository's link layer.  Their own
  link layers, where they have one, and the Berkeley modem's 802.15.4 side are not exercised.
- A federation is fixed when it starts: a simulation cannot join an arena late, and a simulation
  has one arena.
- The Bluetooth federated runs were on one machine; across machines only the AD9361 link was run.
