# ha_ecobulles
An Home Assistant custom component to allow control and getting sensors data of an [Ecobulles](https://ecobulles.com) system installation

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
