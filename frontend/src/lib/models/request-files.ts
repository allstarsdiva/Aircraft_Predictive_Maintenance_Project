import type { JsonObject } from "./types.ts";

type Row = Record<string, string>;

const normalized = (value: unknown) =>
  String(value ?? "")
    .trim()
    .replace(/^﻿/, "")
    .toLowerCase();

function parseTable(text: string): Row[] {
  if (typeof text !== "string" || !text.trim()) throw new Error("The CSV file is empty.");
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else quoted = !quoted;
    } else if (character === "," && !quoted) {
      row.push(cell.trim());
      cell = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell.trim());
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      cell = "";
    } else cell += character;
  }
  if (quoted) throw new Error("The CSV has an unclosed quoted value.");
  row.push(cell.trim());
  if (row.some((value) => value !== "")) rows.push(row);
  if (rows.length < 2) throw new Error("The CSV needs a header row and at least one data row.");

  const headers = rows[0].map(normalized);
  if (headers.some((header) => !header)) throw new Error("Every CSV column needs a header.");
  if (new Set(headers).size !== headers.length) throw new Error("The CSV contains duplicate column names.");
  return rows.slice(1).map((values, rowIndex) => {
    if (values.length !== headers.length) throw new Error(`CSV row ${rowIndex + 2} has ${values.length} values; expected ${headers.length}.`);
    return Object.fromEntries(headers.map((header, index) => [header, values[index]]));
  });
}

function requireHeaders(rows: Row[], expected: string[]): void {
  const actual = Object.keys(rows[0] || {});
  const wanted = expected.map(normalized);
  const missing = wanted.filter((header) => !actual.includes(header));
  const unexpected = actual.filter((header) => !wanted.includes(header));
  if (missing.length || unexpected.length) {
    const problems: string[] = [];
    if (missing.length) problems.push(`missing: ${missing.join(", ")}`);
    if (unexpected.length) problems.push(`unexpected: ${unexpected.join(", ")}`);
    throw new Error(`CSV columns do not match this system (${problems.join("; ")}). Download the selected system's CSV example for the required headers.`);
  }
}

function number(row: Row, key: string): number {
  const raw = row[normalized(key)];
  if (raw === undefined || raw === "") throw new Error(`CSV value for "${key}" is required.`);
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error(`CSV value for "${key}" must be a finite number.`);
  return value;
}

function csvBoolean(row: Row, key: string): boolean {
  const value = normalized(row[normalized(key)]);
  if (["true", "1"].includes(value)) return true;
  if (["false", "0"].includes(value)) return false;
  throw new Error(`CSV value for "${key}" must be true, false, 1, or 0.`);
}

export function csvToPayload(component: string, text: string, examplePayload: JsonObject): JsonObject {
  const rows = parseTable(text);
  let expected: string[];
  if (component === "engine") expected = Object.keys(examplePayload.records[0]);
  else if (component === "battery") expected = ["battery_id", "discharge_cycle", "ambient_temperature", ...Object.keys(examplePayload.samples[0])];
  else if (component === "hydraulic") expected = ["cycle_id", "operating_condition_stable", ...Object.keys(examplePayload.features)];
  else if (component === "landing-gear") expected = Object.keys(examplePayload);
  else if (component === "fuel-system") expected = Object.keys(examplePayload.samples[0]);
  else throw new Error("CSV import is not configured for this system.");
  requireHeaders(rows, expected);

  if (component === "engine") {
    return {
      subset: examplePayload.subset || "FD001",
      records: rows.map((row) => Object.fromEntries(expected.map((key) => [key, number(row, key)]))),
    };
  }
  if (component === "battery") {
    const batteryIds = new Set(rows.map((row) => row.battery_id));
    const cycles = new Set(rows.map((row) => row.discharge_cycle));
    const ambient = new Set(rows.map((row) => row.ambient_temperature));
    if (batteryIds.size !== 1 || cycles.size !== 1 || ambient.size !== 1) {
      throw new Error("Battery ID, discharge cycle, and ambient temperature must stay the same on every CSV row.");
    }
    return {
      battery_id: rows[0].battery_id,
      discharge_cycle: number(rows[0], "discharge_cycle"),
      ambient_temperature: number(rows[0], "ambient_temperature"),
      samples: rows.map((row) => Object.fromEntries(Object.keys(examplePayload.samples[0]).map((key) => [key, number(row, key)]))),
    };
  }
  if (component === "hydraulic") {
    if (rows.length !== 1) throw new Error("Hydraulic prediction expects exactly one cycle per CSV file.");
    return {
      cycle_id: number(rows[0], "cycle_id"),
      operating_condition_stable: csvBoolean(rows[0], "operating_condition_stable"),
      features: Object.fromEntries(Object.keys(examplePayload.features).map((key) => [key, number(rows[0], key)])),
    };
  }
  if (component === "landing-gear") {
    if (rows.length !== 1) throw new Error("Landing-gear prediction expects exactly one event per CSV file.");
    return Object.fromEntries(expected.map((key) => [key, number(rows[0], key)]));
  }
  return { samples: rows.map((row) => Object.fromEntries(expected.map((key) => [key, number(row, key)]))) };
}

function escapeCell(value: unknown): string {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function payloadToCsv(component: string, payload: JsonObject): string {
  let rows: JsonObject[];
  if (component === "engine") rows = payload.records;
  else if (component === "battery")
    rows = payload.samples.map((sample: JsonObject) => ({
      battery_id: payload.battery_id,
      discharge_cycle: payload.discharge_cycle,
      ambient_temperature: payload.ambient_temperature,
      ...sample,
    }));
  else if (component === "hydraulic") rows = [{ cycle_id: payload.cycle_id, operating_condition_stable: payload.operating_condition_stable, ...payload.features }];
  else if (component === "landing-gear") rows = [payload];
  else if (component === "fuel-system") rows = payload.samples;
  else throw new Error("CSV export is not configured for this system.");
  if (!rows?.length) throw new Error("There is no example data to export.");
  const headers = Object.keys(rows[0]);
  return [headers, ...rows.map((row) => headers.map((header) => row[header]))].map((values) => values.map(escapeCell).join(",")).join("\r\n");
}
