# ha_ecobulles
An Home Assistant custom component to allow control and getting sensors data of an [Ecobulles](https://ecobulles.com) system installation

## Install

[![Open your Home Assistant instance and open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jul-fls&repository=ha_ecobulles&category=integration)

[![Open your Home Assistant instance and start setting up a new integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ecobulles)

1. Add the repository to HACS with the first button above.
2. Download the integration in HACS and restart Home Assistant.
3. Use the second button to start the Ecobulles setup flow.

## Local validation

Before pushing changes, run:

```powershell
python .\scripts\check_integration.py
```

This performs a syntax compilation pass for the integration and exercises the
water-accounting logic that keeps lifetime usage monotonic across CO2 bottle
changes.

## Raw CO2 diagnostics

If you want to study the API's undocumented CO2 value over time, enable the
`Ecobulles Raw CO2 Debug` switch in Home Assistant. When enabled, the integration
adds a diagnostic sensor named `Ecobulles Raw CO2 Value` so you can compare its
hourly / daily evolution against bottle changes and water usage.

## CI

The GitHub Actions pipeline intentionally avoids real Ecobulles credentials.
Instead it runs:

- the local regression command above;
- mocked Home Assistant integration tests;
- Hassfest validation;
- HACS repository validation.

That keeps CI deterministic while still checking that the integration loads,
creates the expected entities, and remains publishable as the project evolves.
