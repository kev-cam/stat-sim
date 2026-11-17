-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-- SPDX-FileCopyrightText: 2026 D. Kevin Cameron
-- Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
-- spectral_accel_run_pkg, "on": the design's RF path can move out to the spectral accelerator (run nvc with --load=libspectral_accel.so).
package spectral_accel_run_pkg is
    constant SA_COMPILED_IN : boolean := true;
end package;
