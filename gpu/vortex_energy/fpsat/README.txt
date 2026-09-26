FP-SATURATION KERNELS FOR VORTEX 'mini' (2026-09-25)
=====================================================
Route 2 of the ordered fallbacks: purpose-written bare-metal rv32imf kernels,
assembled with stock Debian llvm-mc/llvm-objcopy 19.1.7 (no riscv-gcc on box, no
prebuilt FP-dense images found in rtlmeter tests/ or /home/claude/vortex).

FILES
  kernel_fma.S            FMA-saturation source (8 indep logistic-map chains/thread:
                          t=fnmsub.s(x,x,x); x=fmul.s(3.9,t); unroll 4; LOOPS via --defsym)
  kernel_div.S            DIVSQRT variant (fdiv.s by 1+2^-11 + fsqrt.s chains, unroll 2;
                          PASS gated on integer loop-trip-checksum markers @0x48000)
  oracle.c                independent x86 IEEE oracle (fmaf/div/sqrtf) -> post.bin
  ulpcheck.py             offline ulp-bounded check of div-variant FP outputs
  kernel_fma_L2048.bin    code blob as run (484 B), kernel_div_L768.bin (416 B)
  init_*.bin post_*.bin dcrs.bin   exact images of the two traced runs
                          (init md5 0041be6f.. / post 5a6a25e0.. match the run dir)

BUILD (exact commands)
  llvm-mc -triple=riscv32 -mattr=+m,+f -filetype=obj --defsym LOOPS=2048 kernel_fma.S -o k.o
  llvm-objcopy -O binary --only-section=.text k.o code.bin
  init.bin = struct.pack('<QQ',0x80000000,len(code))+code ; dcrs.bin = hello's
  post.bin: ./oracle fma 2048 post.bin   (div: ./oracle div 768 post.bin -> +.fpref)

RUN (one iteration, whole design, Verilator Vsim of work_qal_vortex_tr)
  cd <dir with init/dcrs/post.bin>
  Vsim +verilator+quiet +iterations=1            # smoke
  Vsim +verilator+quiet +trace +iterations=1     # traced, trace.vcd FIFO -> vcdact
  (same FIFO recipe as ../tracerun.sh)

RESULTS (MEASURED, full-run traces; TSVs in ../fpsat_fma.tsv ../fpsat_div.tsv,
         logs ../fpsat_*.sim.log ../fpsat_*.parse.log, table ../rep_fpsat.txt)
  fpsat_fma: TEST PASSED, 1,612,525 cycles, all 128 chain results bit-exact vs fmaf oracle.
    fpu_unit duty_D2 0.9781 (was .000/.032/.235 hello/saxpy/sgemm), alpha 0.0208 (5.2x sgemm)
    whole-GPU duty 0.9787; dcache/lsu/L2/L3 ~0 (clean FP isolation)
    FP-op acceptance ~0.33 instr/cyc (783 cyc per 264-instr loop epoch): limiter is the
    operands collector (~3 cyc/instr; operands scope duty 0.9932/alpha 0.128) + 1-wide issue.
    Duty target >0.8 exceeded, so no remediation needed for characterization.
  fpsat_div: TEST PASSED (marker gate), 1,385,576 cycles.
    i_fpnew_divsqrt_multi (4 lanes x 14,469 bits, dark in ALL prior kernels):
    duty 0.775-0.780, alpha ~0.125 per lane. fpu_unit duty 0.7806.
    Residual 22% idle = 16-cycle unpipelined ops + div/sqrt batch alternation (issue 0.33 =
    not the limiter; the divsqrt unit itself binds).

FINDING (RTL): fpnew divsqrt_multi is faithful-but-not-RNE-exact: 0..-11 ulp drift per 64
chained fdivs (negative bias ~0.05 ulp/op), -68..-158 ulp after 1536; fsqrt about half that.
FMA datapath (fnmsub/fmul) is bit-exact IEEE RNE (128/128 chains, chaotic map = error amplifier).

HARNESS TRAP found: tb.sv checks memory only #100 (10 cycles) after busy falls; the last
write-through stores were still in flight -> 11/128 words read back 0xbaadf00d. Fix in both
kernels: fence + 256-iteration spin before tmc(0).

NEXT (composition): feed fpsat_fma.tsv (and _div) through /home/claude/vortex_energy/
assemble.py + compose_energy.py to re-compose the map and make the FPU binding call.
