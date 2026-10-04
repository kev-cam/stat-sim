#!/usr/bin/env python3
# ghash_ref.py
# ---------------------------------------------------------------------------
# PYTHON REFERENCE for GHASH (the authentication half of GCM-AES), with the
# CORRECT GCM BIT-REFLECTION, validated against pycryptodome's full AES-GCM
# tag on NIST SP 800-38D vectors.  NEVER self-asserted: the only thing this
# file trusts is pycryptodome (an independent GCM implementation) plus the two
# constants published in NIST SP 800-38D / the GCM spec.
#
# =========================================================================
# GCM BIT-REFLECTION  --  GHASH's #1 bug, documented EXPLICITLY
# =========================================================================
# GHASH works in GF(2^128) with reduction polynomial
#       P(x) = x^128 + x^7 + x^2 + x + 1          (the GCM polynomial)
# A 128-bit block is interpreted as a field element (a polynomial of degree
# < 128).  The GCM convention (SP 800-38D Sec. 6.3) is REFLECTED:
#
#     *** bit 0 of the block == the MSB of byte 0 == the coefficient of x^0 ***
#
# So, writing the block as a byte string b0 b1 ... b15 (b0 first on the wire),
# and loading it big-endian into a 128-bit integer  X  (so b0 is X's most
# significant byte, i.e. bits [127:120]):
#     GCM "bit i"  ==  integer bit (127 - i)
#     GCM bit 0    ==  integer bit 127 (the MSB)      ==  coefficient of x^0
#     GCM bit 127  ==  integer bit 0   (the LSB)      ==  coefficient of x^127
#
# The reduction constant used by the standard's shift-multiply is
#     R = 11100001 || 0^120   (GCM bit order)  ==  byte 0xE1 then 15 zero bytes
#       = 0xE1 << 120  as a big-endian integer.
# 0xE1 has GCM bits 0,1,2,7 set -> x^0 + x^1 + x^2 + x^7, which is exactly the
# low part of P(x): when a *x reaches x^128, reduce by x^128 = x^7+x^2+x+1.
#
# Multiply-by-x in this reflected convention is a RIGHT shift of the integer
# (GCM bit i, at integer position 127-i, moves to GCM bit i+1, integer
# position 126-i -- i.e. toward the LSB), with the bit that falls off the LSB
# (GCM bit 127) deciding whether to XOR R back in.  This is carry-LESS: pure
# shift / AND / XOR, no ripple adder anywhere.
# =========================================================================

import struct, sys
from Crypto.Cipher import AES

MASK128 = (1 << 128) - 1
R = 0xE1 << 120                      # reduction constant, big-endian integer

# ---------------------------------------------------------------------------
# Core GF(2^128) carry-less multiply, GCM convention.  This mirrors the RTL
# ghash_gfmul.v BIT-FOR-BIT: same bit indexing (a's GCM bit i = a>>(127-i)),
# same right-shift / conditional-XOR-R.  Unrolled, this is one combinational
# XOR/AND cone -- the "parallel" form used by the RTL.
# ---------------------------------------------------------------------------
def gf_mult(a, b):
    z = 0
    v = b
    for i in range(128):
        if (a >> (127 - i)) & 1:     # a's GCM bit i  (bit 0 = MSB)
            z ^= v
        if v & 1:                    # v's GCM bit 127 (LSB) about to shift off
            v = (v >> 1) ^ R
        else:
            v = v >> 1
    return z & MASK128

def ghash(H, blocks):
    """GHASH_H(blocks): Y_0 = 0 ; Y_i = (Y_{i-1} XOR C_i) . H ; return Y_n."""
    y = 0
    for c in blocks:
        y = gf_mult(y ^ c, H)
    return y

# ---------------------------------------------------------------------------
# helpers: bytes <-> 128-bit int (big-endian), and the GCM block assembly
# ---------------------------------------------------------------------------
def b2i(b):      return int.from_bytes(b, 'big')
def i2b(x):      return int(x & MASK128).to_bytes(16, 'big')

def pad16(data):
    """zero-pad a byte string up to a whole number of 16-byte blocks."""
    if len(data) % 16:
        data = data + b'\x00' * (16 - (len(data) % 16))
    return data

def to_blocks(data):
    data = pad16(data)
    return [b2i(data[i:i+16]) for i in range(0, len(data), 16)]

def ghash_blocks(aad, ct):
    """The exact sequence of 128-bit blocks GHASH absorbs for (aad, ct):
       padded AAD blocks, padded ciphertext blocks, then the length block
       [len(aad)*8]_64 || [len(ct)*8]_64."""
    lenblk = b2i(struct.pack('>Q', len(aad) * 8) + struct.pack('>Q', len(ct) * 8))
    return to_blocks(aad) + to_blocks(ct) + [lenblk]

def aes_ecb(key, block16):
    return AES.new(key, AES.MODE_ECB).encrypt(block16)

def gcm_tag(key, iv, aad, pt):
    """Full GCM: H = E_K(0); J0 = IV||0^31||1 (96-bit IV); C = GCTR_{J0+1}(P);
       S = GHASH_H(A,C); Tag = S XOR E_K(J0).  Returns (ct, tag, H, J0, S,
       ghblocks) computed WITHOUT pycryptodome's GCM (only its ECB engine)."""
    assert len(iv) == 12, "this reference handles the standard 96-bit IV case"
    H  = b2i(aes_ecb(key, b'\x00' * 16))
    J0 = b2i(iv + b'\x00\x00\x00\x01')
    # GCTR to produce the ciphertext (counter starts at J0+1)
    ct = bytearray()
    ctr = (J0 + 1) & MASK128
    for off in range(0, len(pt), 16):
        ks = aes_ecb(key, i2b(ctr))
        chunk = pt[off:off+16]
        ct += bytes(a ^ b for a, b in zip(chunk, ks[:len(chunk)]))
        ctr = (ctr + 1) & MASK128
    ct = bytes(ct)
    ghb = ghash_blocks(aad, ct)
    S   = ghash(H, ghb)
    tag = S ^ b2i(aes_ecb(key, i2b(J0)))
    return ct, i2b(tag), i2b(H), J0, i2b(S), ghb

# ---------------------------------------------------------------------------
# VALIDATION against pycryptodome + the published NIST / GCM-spec constants
# ---------------------------------------------------------------------------
def check(name, got, exp):
    ok = (got == exp)
    print("  %-46s %s" % (name, "PASS" if ok else "FAIL"))
    if not ok:
        print("      got = %s" % got.hex())
        print("      exp = %s" % exp.hex())
    return ok

def pyc_gcm(key, iv, aad, pt):
    """pycryptodome's INDEPENDENT full-GCM reference tag + ciphertext."""
    c = AES.new(key, AES.MODE_GCM, nonce=iv)
    if aad:
        c.update(aad)
    ct, tag = c.encrypt_and_digest(pt)
    return ct, tag

def main():
    allok = True
    print("GHASH python reference -- validation (NEVER self-asserted)")
    print("=" * 64)

    # --- (A) documented constants from NIST SP 800-38D / GCM spec ----------
    print("[A] published NIST SP 800-38D constants")
    key0 = b'\x00' * 16
    H0   = aes_ecb(key0, b'\x00' * 16)
    allok &= check("H = AES_0(0^128) == NIST",
                   H0, bytes.fromhex("66e94bd4ef8a2c3b884cfa59ca342b2e"))
    # empty message, key = iv = 0  -> tag 58e2fcce...  (SP 800-38D)
    _, tag_e, _, _, _, _ = gcm_tag(key0, b'\x00' * 12, b'', b'')
    allok &= check("empty-msg tag (key=iv=0) == NIST",
                   tag_e, bytes.fromhex("58e2fccefa7e3061367f1d57a4e7455a"))

    # --- (B) cross-check my GHASH-built tag vs pycryptodome, 3 vectors -----
    # These EXERCISE the gf_mult (non-trivial AAD and/or ciphertext).  If my
    # bit-reflection were wrong, the tags would not match pycryptodome.
    print("[B] my-GHASH full-GCM tag  ==  pycryptodome tag")
    vectors = [
        # GCM spec Test Case 3 (McGrew&Viega / SP 800-38D): 64-byte P, 96-bit IV
        dict(name="TC3 (64B ct, no aad)",
             key=bytes.fromhex("feffe9928665731c6d6a8f9467308308"),
             iv =bytes.fromhex("cafebabefacedbaddecaf888"),
             aad=b'',
             pt =bytes.fromhex("d9313225f88406e5a55909c5aff5269a"
                               "86a7a9531534f7da2e4c303d8a318a72"
                               "1c3c0c95956809532fcf0e2449a6b525"
                               "b16aedf5aa0de657ba637b391aafd255")),
        # GCM spec Test Case 4: 60-byte P (not block-aligned) + 20-byte AAD
        dict(name="TC4 (60B ct, 20B aad)",
             key=bytes.fromhex("feffe9928665731c6d6a8f9467308308"),
             iv =bytes.fromhex("cafebabefacedbaddecaf888"),
             aad=bytes.fromhex("feedfacedeadbeeffeedfacedeadbeefabaddad2"),
             pt =bytes.fromhex("d9313225f88406e5a55909c5aff5269a"
                               "86a7a9531534f7da2e4c303d8a318a72"
                               "1c3c0c95956809532fcf0e2449a6b525"
                               "b16aedf5aa0de657ba637b39")),
        # AAD-only (no ciphertext) -> GHASH over aad-pad + lenblock
        dict(name="AAD-only (0B ct, 20B aad)",
             key=bytes.fromhex("feffe9928665731c6d6a8f9467308308"),
             iv =bytes.fromhex("cafebabefacedbaddecaf888"),
             aad=bytes.fromhex("feedfacedeadbeeffeedfacedeadbeefabaddad2"),
             pt =b''),
    ]
    for v in vectors:
        ct_mine, tag_mine, H, J0, S, ghb = gcm_tag(v['key'], v['iv'], v['aad'], v['pt'])
        ct_pyc, tag_pyc = pyc_gcm(v['key'], v['iv'], v['aad'], v['pt'])
        ok = check("%-26s ct"  % v['name'], ct_mine,  ct_pyc)
        ok &= check("%-26s tag" % v['name'], tag_mine, tag_pyc)
        allok &= ok
    # known H for the TC3/TC4 key (GCM spec)
    allok &= check("H for feffe99.. key == GCM-spec",
                   aes_ecb(vectors[0]['key'], b'\x00'*16),
                   bytes.fromhex("b83b533708bf535d0aa6e52980d53b78"))

    # --- (C) emit the RTL test vector (validated intermediates) ------------
    # Use TC4 (AAD + unaligned ct -> several real gf_mult steps) as the RTL
    # vector.  Write H, nblocks, every absorbed block, and the final GHASH
    # output S, PLUS the running accumulator Y after each block, so the
    # Verilog testbench can check intermediates too.  All values here are now
    # validated (their derived tag matched pycryptodome above).
    print("[C] emit RTL test vector  ghash_tv.hex")
    v = vectors[1]                                     # TC4
    ct_mine, tag_mine, H, J0, S, ghb = gcm_tag(v['key'], v['iv'], v['aad'], v['pt'])
    # running accumulator trace
    ys, y = [], 0
    for c in ghb:
        y = gf_mult(y ^ c, b2i(H))
        ys.append(y)
    assert i2b(ys[-1]) == S, "internal trace != S"    # internal consistency
    with open("ghash_tv.hex", "w") as f:
        f.write("// GHASH RTL test vector (TC4), validated vs pycryptodome\n")
        f.write("// line 0: H ; line 1: nblocks ; then that many C_i blocks ;\n")
        f.write("// then that many running-Y values ; then final S.\n")
        f.write("%s\n" % H.hex())
        f.write("%032x\n" % len(ghb))
        for c in ghb:
            f.write("%032x\n" % c)
        for y in ys:
            f.write("%032x\n" % y)
        f.write("%s\n" % S.hex())
    print("      H        = %s" % H.hex())
    print("      nblocks  = %d" % len(ghb))
    print("      S (=Y_n) = %s" % S.hex())
    print("      tag      = %s  (== pycryptodome: see [B])" % tag_mine.hex())

    print("=" * 64)
    if allok:
        print("REFERENCE VALIDATED: python GHASH agrees with pycryptodome + NIST")
        return 0
    print("REFERENCE INVALID -- do NOT use for RTL check")
    return 1

if __name__ == "__main__":
    sys.exit(main())
