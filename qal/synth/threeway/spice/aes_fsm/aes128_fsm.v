// aes128_fsm.v
// ---------------------------------------------------------------------------
// Self-timed AES-128 round FSM wrapper (one 128-bit block, encrypt).
//
//   128b cipher state + 128b running round key + a 4-bit round counter, all in
//   an edge-triggered DFF register (the dfrbp-class master-slave proven on the
//   4-bit accumulator and SHA-256). The deep next-state cone is aes_round (pure
//   static CMOS); the round key is advanced in-kind each round by aes_key_expand
//   (held state, like SHA's rolling message-schedule window). 10 rounds; round
//   10 is final (MixColumns omitted).
//
// Schedule (FIPS-197 Sec. 5.1, Cipher()):
//   reset     : state <- plaintext XOR roundkey[0]   (initial AddRoundKey;
//               roundkey[0] = cipher key, which is also loaded as the running key)
//   round 1..9: state <- aes_round(state, roundkey[r], final=0)
//   round 10  : state <- aes_round(state, roundkey[10], final=1)  -> ciphertext
//   each round r also advances the running key: roundkey[r] = KE(roundkey[r-1], r)
//
// SELF-TIMED CAPTURE MODEL (what the SPICE round-slice anchors; here a
// synchronous clk is used so the LOGIC can be proven against FIPS-197):
//   This wrapper is drawn as a conventional clocked FSM. The self-timed build is
//   BIT-IDENTICAL in function -- same aes_round / aes_key_expand next-state
//   cones, same edge-triggered DFF state register -- and differs ONLY in WHEN
//   the capture edge fires. Instead of a free-running clock, a per-round DONE
//   pulse fires once the round critical path has settled. That path is the
//   S-box substitution depth + the MixColumns GF XOR tree (AES has NO wide
//   ripple-carry, unlike SHA's 32-bit adders), reproduced by an IN-KIND REPLICA
//   delay line -- a dummy round cone and DFF identical to the real one, loaded to
//   the same point -- NOT a per-op analog comparator. The completion detector is
//   thus embedded/sparse and never re-dominates the duty crossover (the QAL
//   cliff). Because the combinational function and the state element are
//   identical, logic correctness proven on this synchronous wrapper transfers
//   verbatim to the done-pulsed self-timed wrapper; only capture TIMING (hence
//   energy-vs-duty) differs, and that is what the transistor round-slice measures.
//   The shallower AES round (no carry chain) makes the power-settle edge SHARPER
//   than SHA's, which is favourable for current-sense completion detection.
//
// AES idles between frames (MACsec / 802.1AE GCM-AES-128 is the Ethernet
// cipher) -> the low-duty regime where shedding the clock floor is the win.
// ---------------------------------------------------------------------------
module aes128_fsm(
  input          clk,
  input          rst,        // synchronous: load pt+key, do initial AddRoundKey
  input  [127:0] pt,         // plaintext block
  input  [127:0] key,        // cipher key = round key 0
  output reg [127:0] ct,     // ciphertext (valid when done)
  output reg         done
);
  reg  [127:0] state;        // working cipher state (held in DFF register)
  reg  [127:0] rkey;         // running round key    (held in DFF register)
  reg  [3:0]   round;        // 1..10

  // ---- this round's key (combinational advance of the held key) -----------
  wire [127:0] rkey_this;
  aes_key_expand KE(.rk_in(rkey), .round_idx(round), .rk_out(rkey_this));

  // ---- next cipher state (pure static combinational round cone) -----------
  wire         is_final = (round == 4'd10);
  wire [127:0] state_next;
  aes_round RND(.st(state), .rkey(rkey_this), .final_round(is_final),
                .nst(state_next));

  always @(posedge clk) begin
    if (rst) begin
      state <= pt ^ key;     // initial AddRoundKey with round key 0 (= key)
      rkey  <= key;          // running key starts at round key 0
      round <= 4'd1;
      done  <= 1'b0;
      ct    <= 128'd0;
    end else if (!done) begin
      state <= state_next;
      rkey  <= rkey_this;
      round <= round + 4'd1;
      if (round == 4'd10) begin
        ct   <= state_next;  // round 10 (final) output = ciphertext
        done <= 1'b1;
      end
    end
  end
endmodule
