const GUIDANCE = {
  engine: {
    meaning: 'RUL is the estimated number of operating cycles remaining for the latest engine record.',
    caveat: 'This is a model estimate, not a maintenance interval. The model is based on NASA C-MAPSS data and is not validated for operational aircraft.',
  },
  battery: {
    meaning: 'SOH is estimated battery health as a percentage; RUL is estimated remaining discharge cycles.',
    caveat: 'These estimates come from laboratory battery data. RUL calibration is limited and is not a battery-life guarantee.',
  },
  hydraulic: {
    meaning: 'The four outputs estimate dataset-defined cooler, valve, pump-leakage, and accumulator states from the submitted sensor features.',
    caveat: 'These are UCI hydraulic test-bench labels, not a confirmed aircraft-system diagnosis. “Review required” means inspect the inputs and result before interpreting it.',
  },
  'landing-gear': {
    meaning: 'Fault class and RUL percentage are estimated from the submitted landing-event measurements.',
    caveat: 'The model was evaluated on synthetic digital-twin events; its output does not establish the condition of physical aircraft landing gear.',
  },
  'fuel-system': {
    meaning: 'An anomaly flag means readings depart from the model’s normal-data reference; the anomaly margin is a scaled difference, not a probability.',
    caveat: 'A flag does not prove a fault, and no alert does not prove the system is healthy. This detector remains experimental.',
  },
};

export function getResultGuidance(component) {
  return GUIDANCE[component] || null;
}
