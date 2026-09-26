# FP-SATURATION kernel for Vortex 'mini' (1 core / 4 warps / 4 threads), rv32imf bare-metal.
# Entry: warp0/thread0 at 0x80000000 (STARTUP_ADDR DCR).
# Per thread: 8 independent logistic-map chains x <- r*x*(1-x), r=3.9f (chaotic, never
# converges, stays in (0, 0.975]):
#   t_c = fnmsub.s(x_c, x_c, x_c) = -(x_c*x_c)+x_c = x_c*(1-x_c)   [fused, single rounding]
#   x_c = fmul.s(r, t_c)
# Seeds: x_c(0) = float32(gtid*8 + c + 1) * 2^-8   (gtid = wid*4+tid via mhartid, in [0,15])
# Chain step count = 4*LOOPS (unroll factor 4). Results: 8 words/thread at 0x40000 + gtid*32.
# Custom ops (verified against VX_decode.sv:483-497 of the rtlmeter tree):
#   .insn r 0x0B, 0, 0, x0, rs1, x0  = TMC(rs1)
#   .insn r 0x0B, 1, 0, x0, rs1, rs2 = WSPAWN(count=rs1, pc=rs2)
.text
.globl _start
_start:                                  # 0x80000000, warp0/thread0 only
    li   a0, 4
    lui  a1, 0x80000
    addi a1, a1, 0x10                    # warp_entry == 0x80000010 (4 insts * 4B)
    .insn r 0x0B, 1, 0, x0, a0, a1      # wspawn(4, warp_entry); fall through
warp_entry:
    li   a0, 15
    .insn r 0x0B, 0, 0, x0, a0, x0      # tmc(0b1111): enable all 4 threads
    csrr t2, mhartid                     # gtid = wid*4 + tid  (VX_csr_unit.sv:122,129)
    # constants
    lui  t5, 0x4079A
    addi t5, t5, -0x666                  # 0x4079999A = 3.9f
    fmv.w.x fs2, t5
    lui  t5, 0x3B800                     # 0x3B800000 = 2^-8
    fmv.w.x fs3, t5
    # seeds
    slli t4, t2, 3                       # gtid*8
.irp c,0,1,2,3,4,5,6,7
    addi t4, t4, 1
    fcvt.s.w ft\c, t4, rne               # exact: integer < 2^24
    fmul.s ft\c, ft\c, fs3, rne          # exact: *2^-8
.endr
    li   t3, LOOPS
loop:
.rept 4
.irp c,0,1,2,3,4,5,6,7
    fnmsub.s fa\c, ft\c, ft\c, ft\c, rne
.endr
.irp c,0,1,2,3,4,5,6,7
    fmul.s ft\c, fs2, fa\c, rne
.endr
.endr
    addi t3, t3, -1
    bnez t3, loop
    # store results: base 0x40000 + gtid*32
    lui  t5, 0x40
    slli t4, t2, 5
    add  t5, t5, t4
.irp c,0,1,2,3,4,5,6,7
    fsw  ft\c, (4*\c)(t5)
.endr
    fence                                # drain this warp's LSU
    li   t3, 256                         # spin: keep core busy while write-through
drain:                                   # traffic (L1->L2->L3->DPI) fully lands;
    addi t3, t3, -1                      # without this the tb's mem_check (busy low
    bnez t3, drain                       # +100ns) catches the last stores in flight
    .insn r 0x0B, 0, 0, x0, x0, x0      # tmc(0): halt this warp
