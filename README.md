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

## Sensors

### Water sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles Water Usage` | The value reported by Ecobulles for the current CO2 bottle cycle. This can drop when the bottle is changed. |
| `Ecobulles Water Usage Completed CO2 Bottles` | The sum of all *finished* bottle cycles that this integration has already observed. It only increases when a bottle change is detected. |
| `Ecobulles Water Usage Total` | The immutable lifetime total reconstructed by the integration: `completed bottle cycles + current bottle cycle`. This is the best water sensor to use for long-term statistics / dashboards because it never decreases. |

Example:

```text
Bottle A reaches 165894 L
New bottle starts at 165494 L

Ecobulles Water Usage                         = 165494 L
Ecobulles Water Usage Completed CO2 Bottles  = 165894 L
Ecobulles Water Usage Total                  = 331388 L
```

### CO2 sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles CO2 Usage` | A best-effort percentage estimate derived from the API CO2 value and the configured bottle weight. The exact meaning of the Ecobulles API value is not yet proven. |
| `Ecobulles Raw CO2 Value` | Optional diagnostic sensor, enabled by the `Ecobulles Raw CO2 Debug` switch, exposing the untouched CO2 value returned by the API so users can study its behavior over time. |

### Diagnostic sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles Install Date` | Installation date reported by the device. |
| `Ecobulles Last Date Receive` | Last timestamp at which the device reported data, passed through from the API. |
| `Ecobulles Activated` | Activation state reported by the device. |
| `Ecobulles Locked` | Lock state reported by the device. |
| `Ecobulles Suspended` | Suspension state reported by the device. |
