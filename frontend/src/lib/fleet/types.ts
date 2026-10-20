export type Risk = "High" | "Medium" | "Low";
export type AircraftStatus = "Healthy" | "Warning" | "Critical";
export type ComponentType = "Engine" | "Landing Gear" | "Hydraulic" | "Electrical" | "Fuel";

export interface SensorDef {
  key: string;
  label: string;
  unit: string;
  range: [number, number];
}

export interface TrendPoint {
  cycle: number;
  value: number;
}

export interface Sensor extends SensorDef {
  value: number;
  trend: TrendPoint[];
}

export interface FleetComponent {
  type: ComponentType;
  slug: string;
  health: number;
  rul: number;
  risk: Risk;
  priority: Risk;
  recommendation: string;
  failureProbability: number;
  healthTrend: TrendPoint[];
  rulTrend: TrendPoint[];
  sensors: Sensor[];
}

export interface Aircraft {
  id: string;
  tail: string;
  model: string;
  status: AircraftStatus;
  overallHealth: number;
  flightHours: number;
  components: FleetComponent[];
}

export type Rng = () => number;
