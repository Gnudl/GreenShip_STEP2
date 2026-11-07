# STEP 2 scenario and data contract — v1

Decision date: 2026-10-24  
Status: model trial; parameters marked as assumptions are not operational vessel data.

| Item | Locked value | Unit / convention | Source or status |
|---|---:|---|---|
| Main case | Hai Phong → Cai Mep–Thi Vai | — | STEP 1 scenario |
| Departure | 2024-10-10T00:00:00Z | UTC | Selected inside downloaded coverage |
| Data bounding box | N 22, W 105, S 9, E 111 | decimal degrees | Download request and file audit |
| CRS | WGS84 / EPSG:4326 | Python `(lat, lon)`; GeoJSON `[lon, lat]` | STEP 2 data contract |
| Maximum sample spacing | 5 | nautical miles | STEP 2 conservative test setting |
| Mandatory weather | `u10`, `v10`, `swh` | m/s, m/s, m | ERA5 downloaded files |
| Optional currents | `uo`, `vo` at 0.494025 m | m/s, m/s | Copernicus Marine daily file |
| Wind coverage | 2024-10-10 00:00 → 2024-10-14 23:00 | UTC, hourly | File audit |
| Wave coverage | 2024-10-10 00:00 → 2024-10-14 23:00 | UTC, hourly | File audit |
| Current coverage | 2024-10-10 00:00 → 2024-10-14 00:00 | UTC, daily | File audit |
| Ship speed through water | 12 | kn | STEP 2 model assumption |
| Service power | 5,000 | kW | STEP 2 model assumption |
| SFOC | 190 | g/kWh | STEP 2 model assumption |
| Fuel / emission factor | HFO / 3.114 | tCO2/t-fuel | Provisional model assumption; cited CF table must be verified before reporting |

The main route endpoints in `config/scenario.yaml` are modeling approach points. They must pass the Natural Earth land-mask check before being accepted. The mini-case is an open-sea north–south segment used first to test geodesic distance, sampling, weather lookup, and repeatability.

Missing-value rule: keep missing cells as missing. `weather_at()` must return an invalid flag and diagnostic for missing variables, out-of-domain coordinates, or timestamps outside mandatory coverage. It must never replace missing weather values with zero.

The minimum fuel model holds power and SFOC constant. Results are estimated tank-to-wake CO2 for a toy model and cannot be presented as measurements from a real 40,000 DWT vessel.
