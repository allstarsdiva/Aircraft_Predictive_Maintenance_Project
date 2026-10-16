// Units are shown from the cited dataset documentation; unknown source units
// stay explicitly unknown rather than being guessed from numeric magnitudes.
export const INPUT_UNIT_GUIDANCE = {
  engine: [
    'unit_id: identifier only; cycle: operating-cycle count.',
    'operational_setting_1-3 and sensor_1-sensor_21: physical units are not provided for these anonymized C-MAPSS fields. Keep the original sensor names and values.',
  ],
  battery: [
    'voltage_measured, voltage_load: volts (V); current_measured, current_load: amperes (A). Preserve the source sign convention; discharge current can be negative.',
    'temperature_measured and ambient_temperature: degrees C; time: seconds (s); discharge_cycle: cycle count.',
  ],
  hydraulic: [
    'PS1-PS6 pressure: bar; EPS1 motor power: watts (W); FS1-FS2 volume flow: litres/minute (L/min).',
    'TS1-TS4 temperature: degrees C; VS1 vibration: mm/s; CE and SE efficiency: percent (%); CP cooling power: kilowatts (kW).',
    "The request contains per-cycle summary statistics. Each statistic retains its sensor's unit; slope is over normalized cycle time.",
  ],
  'landing-gear': [
    'max_deflection: metres (m); max_velocity: metres/second (m/s); settling_time: seconds (s); mass: kilograms (kg).',
    'The prediction request uses these four documented observable inputs only. Stiffness and damping are not accepted by the readiness endpoint.',
  ],
  'fuel-system': [
    'FTL and CTL tank levels: percent (%) as described in the source paper. The source data includes readings slightly above 100%; retain those readings and do not clip them.',
    'FTT and CRTT temperatures: degrees C. Units for FTF, FTV_S, CLF, and CLV_S are not published with the supplied CSVs.',
    'Samples are interpreted in the order supplied. The dataset does not provide a verified physical timestamp or sampling interval.',
  ],
};

export function getInputUnitGuidance(component) {
  return INPUT_UNIT_GUIDANCE[component] || [];
}
