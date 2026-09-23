---
name: gpgpu_older_node_target
description: "★ NORTH STAR: build an NVIDIA-grade GP-GPU on an OLDER node by dropping power to match 5nm silicon. GF FD-SOI (FDX) is the real target; SkyWater sky130 is the only PDK in hand"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4921ad0c-f17b-4b84-986a-5917c9ebd2a6
  modified: 2026-09-23T07:36:46.612Z
---

★ THE GOAL behind the async-power + GPU-sim work (user, 2026-09-23): **can we build an
NVIDIA-grade GP-GPU on an OLDER process node by reducing its power level to match what 5nm
silicon draws?** If an older/cheaper node can hit the power envelope, it can host a modern
GPGPU. **GF FD-SOI (FDX, e.g. 22FDX) is the ACTUAL target** (proprietary, not in hand);
**SkyWater sky130 is the only PDK we have** for the full open layout flow.

**How the pieces serve this:**
- [[vortex_test_vehicle]] — Vortex (open RISC-V GPGPU) is the GPGPU stand-in / device under test.
- Bundled-data async binding [[async_power_anchor]] — cuts the synchronous CLOCK-FLOOR power (the
  duty-dependent win, crossover α*≈0.51 for deep datapaths); the power lever for the envelope.
- [[statsim_gpu_prototype]] — verifies TIMING/RELIABILITY holds at whole-core scale on the node's
  Vt-mismatch (the reliability the power reduction must not break); the GPU makes it tractable.
- [[nulex_layout_tooling]] sky130 + OpenROAD = the open layout path we can actually run.
- [[phone_dev_environment_vision]] / [[scaling_direction_federation_fpga_asyncfsm]] — the endgame.

**PDK note:** transistor sims to date used **IHP SG13G2 (130nm)** for device-level power/delay
(PSP103); layout uses **sky130**. Neither is FDX — FD-SOI's back-gate bias + lower active power is
the real reason it's the target. Treat SG13G2/sky130 numbers as the OLDER-NODE proxy; the method
(async power reduction + GPU-verified reliability) is what transfers to FDX when a PDK is available.
