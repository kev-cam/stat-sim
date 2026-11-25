// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
//
// BMC with its default parameters, as Verilog in the directory given
package emit

import chisel3.stage.{ChiselGeneratorAnnotation, ChiselStage}
import baseband.{BMC, BasebandModemParams}

object Emit extends App {
  (new ChiselStage).execute(
    Array("--target-dir", args.headOption.getOrElse("out"), "-X", "verilog"),
    Seq(ChiselGeneratorAnnotation(() => new BMC(BasebandModemParams(), 4))))
}
