# DIVSQRT variant: same skeleton as kernel_fma.S, inner op = fdiv.s + fsqrt.s chains.
# Per thread, 8 chains: x_c <- x_c / A (A = 1.00048828125 = 1+2^-11, slow geometric decay,
# stays normal), y_c = sqrt(x_c) (input changes every step -> sustained divsqrt activity).
# Chain step count = 2*LOOPS (unroll factor 2).
# FP results: 16 words/thread (8x x_c then 8x y_c) at 0x40000 + gtid*64 -- NOT gated
# byte-exact: the fpnew divsqrt_multi unit is faithful-but-not-RNE-exact (measured 0..-11
# ulp drift over 64 chained fdivs vs x86 IEEE). Offline ulp-bounded check instead.
# PASS gate (post.bin): integer markers at 0x48000 + gtid*8:
#   word0 = sum_{i=1..LOOPS} i (loop-trip checksum, accumulated inside the loop)
#   word1 = gtid + 1
.text
.globl _start
_start:
    li   a0, 4
    lui  a1, 0x80000
    addi a1, a1, 0x10
    .insn r 0x0B, 1, 0, x0, a0, a1      # wspawn(4, warp_entry)
warp_entry:
    li   a0, 15
    .insn r 0x0B, 0, 0, x0, a0, x0      # tmc(0b1111)
    csrr t2, mhartid
    lui  t5, 0x3F801                     # 0x3F801000 = 1.00048828125f
    addi t5, t5, 0
    # NOTE: 0x3F801000: lui gives 0x3F801000 exactly (low 12 bits zero)
    fmv.w.x fs2, t5
    lui  t5, 0x3B800                     # 2^-8
    fmv.w.x fs3, t5
    slli t4, t2, 3
.irp c,0,1,2,3,4,5,6,7
    addi t4, t4, 1
    fcvt.s.w ft\c, t4, rne
    fmul.s ft\c, ft\c, fs3, rne
.endr
    li   t3, LOOPS
    li   s1, 0
loop:
.rept 2
.irp c,0,1,2,3,4,5,6,7
    fdiv.s ft\c, ft\c, fs2, rne
.endr
.irp c,0,1,2,3,4,5,6,7
    fsqrt.s fa\c, ft\c, rne
.endr
.endr
    add  s1, s1, t3                      # loop-trip checksum: LOOPS*(LOOPS+1)/2
    addi t3, t3, -1
    bnez t3, loop
    lui  t5, 0x40
    slli t4, t2, 6                       # gtid*64
    add  t5, t5, t4
.irp c,0,1,2,3,4,5,6,7
    fsw  ft\c, (4*\c)(t5)
.endr
.irp c,0,1,2,3,4,5,6,7
    fsw  fa\c, (32+4*\c)(t5)
.endr
    # integer markers (the gated region)
    lui  t5, 0x48
    slli t4, t2, 3                       # gtid*8
    add  t5, t5, t4
    sw   s1, 0(t5)
    addi t4, t2, 1
    sw   t4, 4(t5)
    fence
    li   t3, 256
drain:
    addi t3, t3, -1
    bnez t3, drain
    .insn r 0x0B, 0, 0, x0, x0, x0      # tmc(0)
