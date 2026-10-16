# System architecture

The prototype keeps each dataset and prediction task separate. The shared
application is an interface and API layer, not one model trained across all
systems.

<pre>
Raw subsystem data
       |
Validation and provenance checks
       |
Subsystem-specific preprocessing
       |
Grouped training and evaluation
       |
Versioned research model artifacts
       |
FastAPI prediction and evidence routes
       |
React model workspace
       |
Human review; not an automated maintenance decision
</pre>

## Data and model path

1. Raw records are validated against their component schema and dataset
   dictionary.
2. Features are derived by the matching subsystem pipeline; fitting-only
   transformations are not refit on an inference request.
3. Splits are grouped by engine, battery, operating condition, scenario, or
   mass regime as appropriate. The exact evaluation design varies by dataset.
4. Model bundles, source fingerprints, and evaluation reports are kept in
   versioned research releases.
5. FastAPI validates requests and returns predictions with task-specific
   uncertainty or review information when supported.
6. The React workspace calls those routes. Its separate aircraft-fleet visual
   mode is generated simulation and is labelled as such.

## Subsystems

Engine, battery, hydraulic, fuel, and landing-gear components each use their
own raw schema, labels, transforms, model, and metrics. Fuel is experimental;
an alert or lack of alert is not a readiness decision. See docs/API.md and the
data dictionaries for request contracts and field definitions.

## Trust boundary

All reported performance is tied to a named dataset and split. The datasets
are not live aircraft data, no component is certified, and an internal
development split is not independent field validation. Explanations and risk
bands are demonstration aids, not approved maintenance limits.
