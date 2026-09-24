"""Dataset examples and honest evidence for the live model workspace."""
import json
from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.data.battery import load_battery_metadata, load_battery_measurement
from src.data.cmapss import load_test_with_rul, CMAPSS_COLUMNS
from src.data.fuel_system import load_fuel_scenario, FUEL_SENSOR_COLUMNS
from src.model_release import ROOT, active_release, metrics_root

router = APIRouter(prefix='/api/workspace', tags=['model-workspace'])
Component = Literal['engine', 'battery', 'hydraulic', 'landing-gear', 'fuel-system']


@lru_cache(maxsize=16)
def example(component, variant):
    endpoints = {'engine': '/api/v2/predict/engine', 'battery': '/api/v2/predict/battery',
                 'hydraulic': '/api/v2/predict/hydraulic', 'landing-gear': '/api/v2/predict/landing-gear',
                 'fuel-system': '/api/predict/fuel-system'}
    note = 'Dataset replay: these rows may have been used in fitting or tuning; this is a demonstration, not a new accuracy test.'
    source = ''
    if component == 'engine':
        table = load_test_with_rul('FD001')
        row_id = 1 if variant == 'normal' else 81
        rows = table.loc[table.unit_id == row_id]
        payload = {'subset': 'FD001', 'records': rows.loc[:, CMAPSS_COLUMNS].to_dict(orient='records')}
        actual = {'rul_cycles': int(rows.iloc[-1].rul)}
        source = f'NASA FD001 official test engine {row_id}'
        note = 'Official test replay; previously inspected during development. No new independent performance claim.'
    elif component == 'battery':
        cycles = pd.read_csv(ROOT / 'data/processed/battery/discharge_cycles.csv')
        rows = cycles.loc[cycles.rul_training_eligible & cycles.valid_capacity]
        row = rows.iloc[0 if variant == 'normal' else -1]
        measurement = load_battery_measurement(int(row.uid), load_battery_metadata())
        samples = measurement.samples.rename(columns={
            'Voltage_measured': 'voltage_measured', 'Current_measured': 'current_measured',
            'Temperature_measured': 'temperature_measured', 'Current_load': 'current_load',
            'Voltage_load': 'voltage_load', 'Time': 'time'})
        payload = {'battery_id': str(row.battery_id), 'discharge_cycle': int(row.discharge_cycle),
                   'ambient_temperature': float(row.ambient_temperature), 'samples': samples.to_dict(orient='records')}
        actual = {'soh_percent': float(row.soh_percent), 'rul_cycles': float(row.rul_cycles)}
        source = f'NASA battery {row.battery_id}, discharge {int(row.discharge_cycle)}'
    elif component == 'hydraulic':
        table = pd.read_csv(ROOT / 'data/processed/hydraulic/cycle_features.csv')
        stable = variant == 'normal'
        row = table.loc[table.stable_flag == (0 if stable else 1)].iloc[0]
        targets = ['cooler_condition_percent', 'valve_condition_percent', 'pump_leakage_severity', 'accumulator_pressure_bar']
        excluded = {'cycle_id', 'stable_flag', *targets}
        payload = {'cycle_id': int(row.cycle_id), 'operating_condition_stable': stable,
                   'features': {k: float(v) for k,v in row.items() if k not in excluded}}
        actual = {k: int(row[k]) for k in targets}
        source = f'UCI cycle {int(row.cycle_id)}, stable_flag={int(row.stable_flag)} (0=stable, 1=unstable)'
    elif component == 'landing-gear':
        table = pd.read_csv(ROOT / 'data/processed/landing_gear/validated_runs.csv')
        row = table.loc[table.fault_code == (0 if variant == 'normal' else 1)].iloc[0]
        payload = {k: float(row[k]) for k in ('max_deflection', 'max_velocity', 'settling_time', 'mass')}
        actual = {'fault_code': int(row.fault_code), 'rul_percent': float(row.rul_percent)}
        source = f'Synthetic landing event {int(row.run_id)}'
    else:
        scenario = 'normal' if variant == 'normal' else 'one'
        frame = load_fuel_scenario(scenario)
        payload = {'samples': frame.loc[:, FUEL_SENSOR_COLUMNS].to_dict(orient='records')}
        actual = {'scenario_is_abnormal': scenario != 'normal'}
        source = f'Fuel scenario {scenario}, full ordered trajectory'
    return {'endpoint': endpoints[component], 'payload': payload, 'actual': actual,
            'source': source, 'evaluation_note': note}


@router.get('/examples/{component}')
def get_example(component: Component, variant: Literal['normal', 'challenge'] = 'normal'):
    try:
        return example(component, variant)
    except (FileNotFoundError, ValueError, IndexError) as exc:
        raise HTTPException(503, detail='Dataset example unavailable; check local dataset installation.') from exc


@router.get('/evidence')
def evidence():
    root = metrics_root()
    audit = root / 'finalization_audit/audit.json'
    historical = root / 'readiness_v2_retraining.json'
    if not audit.is_file() or not historical.is_file():
        raise HTTPException(503, detail='Run the finalization audit before using the model workspace.')
    release = active_release()
    fuel_evaluation = root / 'fuel_nested/evaluation.json'
    return {'release_id': release[1]['release_id'] if release else 'working-artifacts',
            'release_status': 'research_candidate_only',
            'fuel_evaluation': json.loads(fuel_evaluation.read_text(encoding='utf-8')) if fuel_evaluation.is_file() else None,
            'historical_development_metrics': json.loads(historical.read_text(encoding='utf-8')),
            'audit': json.loads(audit.read_text(encoding='utf-8'))}
