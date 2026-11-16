-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- spectral_accel_pkg: nvc's side of the spectral accelerator (libspectral_accel.so, spectral_accel.h).
--
-- A --std=2040 spectral design's RF path -- the chips' transmit and receive paths, the antennas, the
-- arena -- can have its data and its processing moved out of the simulator to the accelerator, where
-- every frequency line of every net is a thread, and pulled back at any event boundary, to debug with
-- the simulator's own view of the nets or to suspend.  The model is the same VHDL either way:
--
--   sa_mode = SA_IN_NVC     the VHDL processes compute; the nets ('driver / 'other) carry the spectra
--   sa_mode = SA_ON_ACCEL   the chip processes only hand frames over at their data ports (sa_tx) and
--                           collect what their receivers deliver (sa_rx); the nets in nvc stand still
--   sa_mode = SA_RESTORING  one instant on the way back: the chips put the pulled-back spectra on
--                           their pins and take their state back; the receivers do not treat what
--                           arrives as a new event
--
-- Nothing here is called unless the run was compiled for the accelerator: package spectral_accel_run_pkg
-- says so with one constant, and comes in two files, spectral_accel_on.vhd and spectral_accel_off.vhd;
-- compile one of them first.  With "on", nvc must be run with --load=libspectral_accel.so.  The bridge
-- process that arena_resolver.py writes hands the accelerator the wiring, and drives sa_mode from
-- SPECTRAL_ACCEL_SCHEDULE in the environment ("0:out,2ms:in,5ms:out"; default "0:out").  A switch asked
-- for time t happens 1 fs after t: after everything at t has settled.
--
-- Every foreign subprogram takes reals and real_vectors only: that is passed the same way whatever
-- width the VHDL standard in force gives INTEGER.
use work.spectral_accel_run_pkg.all;

package spectral_accel_pkg is
    type sa_mode_t is (SA_IN_NVC, SA_ON_ACCEL, SA_RESTORING);
    signal sa_mode : sa_mode_t := SA_IN_NVC;         -- one driver: the bridge process

    -- "something new is at a data port": each chip process that hands the accelerator something
    -- counts on its own driver; the resolved sum changes with any of them
    function sa_sum(v : integer_vector) return integer;
    subtype sa_count is sa_sum integer;
    signal sa_kick : sa_count := 0;

    impure function sa_available return boolean;

    -- netlist
    impure function sa_chip_new(seed : real) return real;
    impure function sa_antenna_new(gain_dbi, pol_angle : real) return real;
    impure function sa_scatterer_new(rcs_m2 : real) return real;
    procedure sa_wire(chip, pin, antenna : in real);                 -- pin 0.0: TX1, 1.0: RX1
    procedure sa_arena_antenna(antenna : in real);
    procedure sa_antenna_platform(antenna, platform : in real);
    impure function sa_commit return real;                           -- 1.0: admitted
    -- parameters
    procedure sa_chip_params(chip : in real; p : in real_vector);    -- ad9361_pkg.ad9361_accel_params
    procedure sa_antenna_position(antenna, x, y, z : in real);
    procedure sa_scatterer_position(scatterer, x, y, z : in real);
    procedure sa_agc_init(chip, gain_db : in real);
    -- where the data and the processing are
    impure function sa_schedule_count return real;
    impure function sa_schedule_time(i : real) return real;          -- seconds
    impure function sa_schedule_mode(i : real) return real;          -- 1.0: out, 0.0: back
    procedure sa_set_mode(mode : in real);
    procedure sa_push_tx(chip : in real; state : in real_vector; lines : in real_vector);
    procedure sa_pull_tx(chip : in real; state : inout real_vector; lines : inout real_vector);
    procedure sa_push_rx(chip : in real; state : in real_vector);
    procedure sa_pull_rx(chip : in real; state : inout real_vector);
    -- events
    procedure sa_tx(chip, seq : in real; lines : in real_vector);
    procedure sa_touch;
    -- buf: 2 K reals of lines, the gain in use, then the frame's sequence number (0.0: no frame)
    procedure sa_rx(chip, now : in real; buf : inout real_vector);

    attribute foreign of sa_chip_new : function is "VHPIDIRECT sa_chip_new";
    attribute foreign of sa_antenna_new : function is "VHPIDIRECT sa_antenna_new";
    attribute foreign of sa_scatterer_new : function is "VHPIDIRECT sa_scatterer_new";
    attribute foreign of sa_wire : procedure is "VHPIDIRECT sa_wire";
    attribute foreign of sa_arena_antenna : procedure is "VHPIDIRECT sa_arena_antenna";
    attribute foreign of sa_antenna_platform : procedure is "VHPIDIRECT sa_antenna_platform";
    attribute foreign of sa_commit : function is "VHPIDIRECT sa_commit";
    attribute foreign of sa_chip_params : procedure is "VHPIDIRECT sa_chip_params";
    attribute foreign of sa_antenna_position : procedure is "VHPIDIRECT sa_antenna_position";
    attribute foreign of sa_scatterer_position : procedure is "VHPIDIRECT sa_scatterer_position";
    attribute foreign of sa_agc_init : procedure is "VHPIDIRECT sa_agc_init";
    attribute foreign of sa_schedule_count : function is "VHPIDIRECT sa_schedule_count";
    attribute foreign of sa_schedule_time : function is "VHPIDIRECT sa_schedule_time";
    attribute foreign of sa_schedule_mode : function is "VHPIDIRECT sa_schedule_mode";
    attribute foreign of sa_set_mode : procedure is "VHPIDIRECT sa_set_mode";
    attribute foreign of sa_push_tx : procedure is "VHPIDIRECT sa_push_tx";
    attribute foreign of sa_pull_tx : procedure is "VHPIDIRECT sa_pull_tx";
    attribute foreign of sa_push_rx : procedure is "VHPIDIRECT sa_push_rx";
    attribute foreign of sa_pull_rx : procedure is "VHPIDIRECT sa_pull_rx";
    attribute foreign of sa_tx : procedure is "VHPIDIRECT sa_tx";
    attribute foreign of sa_touch : procedure is "VHPIDIRECT sa_touch";
    attribute foreign of sa_rx : procedure is "VHPIDIRECT sa_rx_buf";
end package;

package body spectral_accel_pkg is
    function sa_sum(v : integer_vector) return integer is
        variable s : integer := 0;
    begin
        for i in v'range loop
            s := (s + v(i)) mod 1000000007;
        end loop;
        return s;
    end function;

    impure function sa_available return boolean is
    begin
        return SA_COMPILED_IN;
    end function;

    -- The bodies are never run: the attribute binds each name to the library.  Without the library
    -- loaded nvc stops at the first call ("foreign function ... not found").
    impure function sa_chip_new(seed : real) return real is
    begin
        return -1.0;
    end function;
    impure function sa_antenna_new(gain_dbi, pol_angle : real) return real is
    begin
        return -1.0;
    end function;
    impure function sa_scatterer_new(rcs_m2 : real) return real is
    begin
        return -1.0;
    end function;
    procedure sa_wire(chip, pin, antenna : in real) is
    begin
    end procedure;
    procedure sa_arena_antenna(antenna : in real) is
    begin
    end procedure;
    procedure sa_antenna_platform(antenna, platform : in real) is
    begin
    end procedure;
    impure function sa_commit return real is
    begin
        return 0.0;
    end function;
    procedure sa_chip_params(chip : in real; p : in real_vector) is
    begin
    end procedure;
    procedure sa_antenna_position(antenna, x, y, z : in real) is
    begin
    end procedure;
    procedure sa_scatterer_position(scatterer, x, y, z : in real) is
    begin
    end procedure;
    procedure sa_agc_init(chip, gain_db : in real) is
    begin
    end procedure;
    impure function sa_schedule_count return real is
    begin
        return 0.0;
    end function;
    impure function sa_schedule_time(i : real) return real is
    begin
        return 0.0;
    end function;
    impure function sa_schedule_mode(i : real) return real is
    begin
        return 0.0;
    end function;
    procedure sa_set_mode(mode : in real) is
    begin
    end procedure;
    procedure sa_push_tx(chip : in real; state : in real_vector; lines : in real_vector) is
    begin
    end procedure;
    procedure sa_pull_tx(chip : in real; state : inout real_vector; lines : inout real_vector) is
    begin
    end procedure;
    procedure sa_push_rx(chip : in real; state : in real_vector) is
    begin
    end procedure;
    procedure sa_pull_rx(chip : in real; state : inout real_vector) is
    begin
    end procedure;
    procedure sa_tx(chip, seq : in real; lines : in real_vector) is
    begin
    end procedure;
    procedure sa_touch is
    begin
    end procedure;
    procedure sa_rx(chip, now : in real; buf : inout real_vector) is
    begin
    end procedure;
end package body;
