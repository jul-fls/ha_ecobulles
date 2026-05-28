# ha_ecobulles

Home Assistant custom integration for an [Ecobulles](https://ecobulles.com) installation.

[English](#english) · [Français](#français)

## English

### Install

[![Open your Home Assistant instance and open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jul-fls&repository=ha_ecobulles&category=integration)

[![Open your Home Assistant instance and start setting up a new integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ecobulles)

1. Add the repository to HACS with the first button above.
2. Download the integration in HACS and restart Home Assistant.
3. Use the second button to start the Ecobulles setup flow.

### Local validation

Before pushing changes, run:

```powershell
python .\scripts\check_integration.py
```

To compare the live Ecobulles API value with the official app, create a local
`.env` file with `ECOBULLES_EMAIL=...` and `ECOBULLES_PASSWORD=...`, then run:

```powershell
python .\scripts\check_live_usage.py
```

This performs a syntax compilation pass for the integration and exercises the
water-accounting logic that keeps lifetime usage monotonic across CO2 bottle
changes.

### Raw CO2 diagnostics

If you want to study the API's undocumented CO2 value over time, enable the
`Ecobulles Raw CO2 Debug` switch in Home Assistant. When enabled, the integration
adds a diagnostic sensor named `Ecobulles Raw CO2 Value` so you can compare its
hourly / daily evolution against bottle changes and water usage.

### CO2 estimation settings

The integration stores the configured CO2 bottle mass, micrometric screw setting,
and CO2 pressure. For the bottle estimate, it maps the micrometric screw range
`2 → 9` linearly onto an estimated middle dose range of `85 → 150 mg/L`,
derived from Ecobulles indications that a 10 kg CO2 bottle treats about
`60 → 120 m³` or `80 → 120 m³` of water depending on the page.

With the observed/default `1500 ms/L` CO2 pulse, the integration estimates:

```text
estimated dose mg/L = 85 + ((screw - 2) / 7) × 65
estimated active flow g/min = estimated dose mg/L ÷ pulse ms/L × 60
CO2 used ≈ injection open time × estimated active flow
```

Advanced settings also include the polling interval in seconds. The default is
`120` seconds.

### CI

The GitHub Actions pipeline intentionally avoids real Ecobulles credentials.
Instead it runs:

- the local regression command above;
- mocked Home Assistant integration tests;
- Hassfest validation;
- HACS repository validation.

That keeps CI deterministic while still checking that the integration loads,
creates the expected entities, and remains publishable as the project evolves.

### Sensors

#### Water sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles Water Usage` | The value reported by Ecobulles for the current CO2 bottle cycle. It resets to `0` when the bottle is changed, although by the next refresh it may already be a small value such as `2 L` or `10 L`. |
| `Ecobulles Water Usage Before Current CO2 Bottle` | The sum of all *finished* bottle cycles that this integration has already observed. It only increases when a bottle change is detected. |
| `Ecobulles Water Usage Total` | The immutable lifetime total reconstructed by the integration: `completed bottle cycles + current bottle cycle`. This is the best water sensor to use for long-term statistics / dashboards because it never decreases. |

The integration polls Ecobulles every minute and asks the cloud API for data up
to the current minute. This avoids delaying each update until the next closed
hour, which would make Home Assistant assign water used between `00:00` and
`01:00` to the `01:00`-`02:00` Energy dashboard bucket. If the Ecobulles cloud
itself only publishes a value after the hour has closed, Home Assistant will
still record the increase when it first becomes visible.

Example:

```text
Bottle A reaches 165894 L
Bottle B starts at 7 L before the next refresh

Ecobulles Water Usage                            = 7 L
Ecobulles Water Usage Before Current CO2 Bottle = 165894 L
Ecobulles Water Usage Total                     = 165901 L
```

#### CO2 sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles CO2 Injection Time` | Cumulative CO2 electrovalve open time, derived from the API `total_gas` value. The API value appears to be milliseconds; the sensor displays seconds. |
| `Ecobulles Estimated CO2 Bottle Usage` | Experimental estimate of bottle usage, derived from the configured bottle CO2 mass, micrometric screw setting, the inferred 85-150 mg/L middle dose range, and the observed/default 1500 ms/L pulse. |
| `Ecobulles Raw CO2 Value` | Optional diagnostic sensor, enabled by the `Ecobulles Raw CO2 Debug` switch, exposing the untouched CO2 value returned by the API so users can study its behavior over time. |

#### Diagnostic sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles Install Date` | Installation timestamp reported by the device. |
| `Ecobulles Last Date Receive` | Last timestamp at which the device reported data. |
| `Ecobulles Active Alerts` | Number of currently active Ecobulles alerts. Alert payloads are exposed as attributes for debugging / diagnosis. |
| `Ecobulles Activated` | Activation state reported by the device. |
| `Ecobulles Locked` | Lock state reported by the device. |
| `Ecobulles Suspended` | Suspension state reported by the device. |

Entity names are translated from Home Assistant's backend language when the
entities are first created. Entity IDs and unique IDs stay stable; changing the
backend language later does not automatically rename already-created entities.

The Ecobulles API does not currently expose an explicit model/gamme field. The
integration therefore infers the device model from the serial number prefix when
possible: `X...` is treated as `Ecobulles Expert`, `E...` as `Ecobulles Équilibre`,
and unknown prefixes remain simply `Ecobulles`.

## Français

### Installation

[![Ouvrir votre instance Home Assistant et ouvrir ce dépôt dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jul-fls&repository=ha_ecobulles&category=integration)

[![Ouvrir votre instance Home Assistant et démarrer la configuration d'une nouvelle intégration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ecobulles)

1. Ajoutez le dépôt à HACS avec le premier bouton ci-dessus.
2. Téléchargez l'intégration dans HACS puis redémarrez Home Assistant.
3. Utilisez le second bouton pour démarrer la configuration d'Ecobulles.

### Validation locale

Avant de pousser des changements, lancez :

```powershell
python .\scripts\check_integration.py
```

Pour comparer la valeur live de l'API Ecobulles avec l'application officielle,
cree un fichier local `.env` avec `ECOBULLES_EMAIL=...` et
`ECOBULLES_PASSWORD=...`, puis lance :

```powershell
python .\scripts\check_live_usage.py
```

Cette commande compile l'intégration et vérifie la logique de comptage de l'eau
qui conserve une consommation totale monotone malgré les changements de bouteille
de CO2.

Pour analyser directement l'historique Ecobulles depuis l'API, sans passer par
l'historique Home Assistant :

```powershell
$env:ECOBULLES_EMAIL="vous@example.com"
$env:ECOBULLES_PASSWORD="mot-de-passe"
python .\scripts\analyze_co2_api_history.py --start "2026-05-17 00:00:00" --stop "2026-05-18 00:00:00" --bucket-minutes 5
```

Le script interroge des fenêtres précises et cherche notamment les périodes où
`+1 L` d'eau correspond à `+1500` unités CO2 brutes.

### Diagnostic CO2 brut

Pour étudier dans le temps la valeur CO2 non documentée de l'API, activez
l'interrupteur `Debug CO2 brut` dans Home Assistant. Lorsqu'il est activé,
l'intégration ajoute le capteur de diagnostic `Valeur CO2 brute`, afin de comparer
son évolution horaire / journalière avec les changements de bouteille et la
consommation d'eau.

### Réglages pour l'estimation CO2

L'intégration conserve la masse de CO2 de la bouteille, le réglage de la vis
micrométrique et la pression CO2. Pour l'estimation de bouteille, elle projette
linéairement la plage de réglage de vis `2 → 9` sur une plage médiane estimée
`85 → 150 mg/L`, déduite des indications Ecobulles selon lesquelles une bouteille
de 10 kg de CO2 traite environ `60 → 120 m³` ou `80 → 120 m³` d'eau selon la page.

Avec l'impulsion CO2 observée/par défaut de `1500 ms/L`, l'intégration estime :

```text
dose estimée mg/L = 85 + ((vis - 2) / 7) × 65
débit actif estimé g/min = dose estimée mg/L ÷ impulsion ms/L × 60
CO2 utilisé ≈ temps d'ouverture d'injection × débit actif estimé
```

Les réglages avancés contiennent aussi l'intervalle de rafraîchissement en
secondes. La valeur par défaut est `120` secondes.

### CI

Le pipeline GitHub Actions évite volontairement d'utiliser de vrais identifiants
Ecobulles. Il exécute :

- la commande de régression locale ci-dessus ;
- des tests d'intégration Home Assistant avec API simulée ;
- la validation Hassfest ;
- la validation HACS du dépôt.

Cela garde la CI déterministe tout en vérifiant que l'intégration se charge,
crée les bonnes entités et reste publiable au fil de son évolution.

### Capteurs

#### Capteurs d'eau

| Capteur | Signification |
| --- | --- |
| `Consommation d'eau` | La valeur reportée par Ecobulles pour le cycle de la bouteille de CO2 actuelle. Elle revient à `0` lors d'un changement de bouteille, même si au prochain rafraîchissement elle peut déjà valoir quelques litres, par exemple `2 L` ou `10 L`. |
| `Consommation d'eau avant la bouteille de CO2 actuelle` | La somme de tous les cycles de bouteilles *terminés* déjà observés par l'intégration. Elle n'augmente que lorsqu'un changement de bouteille est détecté. |
| `Consommation d'eau totale` | Le total immuable reconstruit par l'intégration : `cycles de bouteilles terminés + cycle actuel`. C'est le meilleur capteur à utiliser pour les statistiques longues / tableaux de bord, car il ne diminue jamais. |

L'intégration interroge Ecobulles toutes les minutes et demande a l'API cloud les
donnees disponibles jusqu'a la minute courante. Cela evite de retarder chaque
mise a jour jusqu'a l'heure pleine suivante, ce qui ferait classer par Home
Assistant l'eau consommee entre `00:00` et `01:00` dans le creneau Energy
Dashboard `01:00`-`02:00`. Si le cloud Ecobulles ne publie lui-meme la valeur
qu'apres la fin de l'heure, Home Assistant enregistrera tout de meme
l'augmentation au moment ou elle devient visible.

Exemple :

```text
La bouteille A atteint 165894 L
La bouteille B est déjà à 7 L avant le prochain rafraîchissement

Consommation d'eau                                      = 7 L
Consommation d'eau avant la bouteille de CO2 actuelle = 165894 L
Consommation d'eau totale                              = 165901 L
```

#### Capteurs CO2

| Capteur | Signification |
| --- | --- |
| `Temps d'injection CO2` | Temps cumulé d'ouverture de l'électrovanne CO2, dérivé de la valeur API `total_gas`. Cette valeur semble être exprimée en millisecondes ; le capteur l'affiche en secondes. |
| `Utilisation estimée de la bouteille CO2` | Estimation expérimentale de l'utilisation de la bouteille, dérivée de la masse de CO2 configurée, du réglage de vis micrométrique, de la plage médiane estimée 85-150 mg/L et de l'impulsion observée/par défaut de 1500 ms/L. |
| `Valeur CO2 brute` | Capteur de diagnostic optionnel, activé par l'interrupteur `Debug CO2 brut`, qui expose la valeur CO2 brute renvoyée par l'API afin d'étudier son comportement dans le temps. |

#### Capteurs de diagnostic

| Capteur | Signification |
| --- | --- |
| `Date d'installation` | Horodatage d'installation reporté par l'appareil. |
| `Dernière réception` | Dernier horodatage auquel l'appareil a transmis des données. |
| `Alertes actives` | Nombre d'alertes Ecobulles actuellement actives. Le détail des alertes est exposé en attributs pour diagnostic. |
| `Activé` | État d'activation reporté par l'appareil. |
| `Verrouillé` | État de verrouillage reporté par l'appareil. |
| `Suspendu` | État de suspension reporté par l'appareil. |

Les noms des entités sont traduits selon la langue backend de Home Assistant au
moment de leur première création. Les entity IDs et unique IDs restent stables ;
changer la langue backend plus tard ne renomme pas automatiquement les entités
déjà créées.

L'API Ecobulles n'expose pas actuellement de champ explicite pour le modèle ou
la gamme. L'intégration déduit donc le modèle depuis le préfixe du numéro de
série lorsque c'est possible : `X...` devient `Ecobulles Expert`, `E...` devient
`Ecobulles Équilibre`, et les préfixes inconnus restent simplement `Ecobulles`.
