-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
--
-- ucb_bmc_radio_pkg: what a link layer has to know of ucb_bmc_radio (ucb_bmc_radio.vhd).
package ucb_bmc_radio_pkg is
    -- from a packet on tx to its first sample at the pin
    constant BMC_TX_DELAY : time := 3437 ns;
end package;
