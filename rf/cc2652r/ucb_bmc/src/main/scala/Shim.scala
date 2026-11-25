// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
//
// What the EE290C DMA takes from testchipip, so that it compiles outside Chipyard (the DMA's
// TileLink side is not in the Verilog made here: BMC has the DMA's request and data streams as ports).
package testchipip

import freechips.rocketchip.config.Parameters
import freechips.rocketchip.diplomacy.{IdRange, ValName}
import freechips.rocketchip.tilelink.{TLClientNode, TLMasterParameters, TLMasterPortParameters}

object TLHelper {
  def makeClientNode(name: String, sourceId: IdRange)(implicit valName: ValName): TLClientNode =
    TLClientNode(Seq(TLMasterPortParameters.v1(Seq(TLMasterParameters.v1(name = name, sourceId = sourceId)))))
}
