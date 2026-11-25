// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 D. Kevin Cameron
// Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
//
// Verilog of the Berkeley baseband-modem's BMC (baseband, modem, controller) without Chipyard:
// rocket-chip v1.6 and the EE290C DMA from source, the design's sources untouched.
val chiselVersion = "3.5.5"
// the directory with the checkouts: baseband-modem, sp21-dma, rocket-chip (emit.sh makes it)
val U = file(sys.env.getOrElse("UCB_SRC", sys.error("UCB_SRC is not set")))

lazy val commonSettings = Seq(
  scalaVersion := "2.12.15",
  scalacOptions ++= Seq("-deprecation", "-unchecked", "-Xsource:2.11", "-language:reflectiveCalls", "-nowarn"),
  libraryDependencies ++= Seq(
    "org.scala-lang" % "scala-reflect" % scalaVersion.value,
    "org.json4s" %% "json4s-jackson" % "3.6.1"),
  addCompilerPlugin("org.scalamacros" % "paradise" % "2.1.1" cross CrossVersion.full),
  Compile / doc / sources := Seq.empty
)

lazy val chiselSettings = Seq(
  libraryDependencies += "edu.berkeley.cs" %% "chisel3" % chiselVersion,
  addCompilerPlugin("edu.berkeley.cs" % "chisel3-plugin" % chiselVersion cross CrossVersion.full)
)

lazy val cde = (project in file("p/cde"))
  .settings(commonSettings)
  .settings(Compile / unmanagedSourceDirectories += U / "rocket-chip/api-config-chipsalliance/design/craft")

lazy val macros = (project in file("p/macros"))
  .settings(commonSettings)
  .settings(Compile / unmanagedSourceDirectories += U / "rocket-chip/macros/src/main/scala")

lazy val hardfloat = (project in file("p/hardfloat"))
  .settings(commonSettings, chiselSettings)
  .settings(Compile / unmanagedSourceDirectories += U / "rocket-chip/hardfloat/src/main/scala")

lazy val rocketchip = (project in file("p/rocketchip"))
  .settings(commonSettings, chiselSettings)
  .settings(
    Compile / unmanagedSourceDirectories += U / "rocket-chip/src/main/scala",
    Compile / unmanagedResourceDirectories += U / "rocket-chip/src/main/resources")
  .dependsOn(cde, macros, hardfloat)

lazy val bmc = (project in file("."))
  .settings(commonSettings, chiselSettings)
  .settings(
    Compile / unmanagedSourceDirectories ++= Seq(
      U / "baseband-modem/src/main/scala",
      U / "sp21-dma/src/main/scala"))
  .dependsOn(rocketchip)
