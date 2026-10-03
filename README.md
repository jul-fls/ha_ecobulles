# ha_ecobulles

Home Assistant custom integration for an [Ecobulles](https://ecobulles.com) installation, using the [Ecobulles customer portal](https://portail.ecobulles.com/login).

[![CI](https://github.com/jul-fls/ha_ecobulles/actions/workflows/ci.yml/badge.svg)](https://github.com/jul-fls/ha_ecobulles/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jul-fls/ha_ecobulles/branch/master/graph/badge.svg)](https://codecov.io/gh/jul-fls/ha_ecobulles)

[English](#english) · [Français](#français)

## English

### Install

[![Open your Home Assistant instance and open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jul-fls&repository=ha_ecobulles&category=integration)

[![Open your Home Assistant instance and start setting up a new integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ecobulles)

1. Add the repository to HACS with the first button above.
2. Download the integration in HACS and restart Home Assistant.
3. Use the second button to start the Ecobulles setup flow.

### Configuration parameters

During setup, enter the same email/password you use for the new Ecobulles customer portal, the CO2 mass in the
bottle, and the micrometric screw setting. Advanced settings expose the CO2
pressure, estimated dose range, reference valve pulse, and polling interval.
They also let you select whether raw bottle-contact value `0` or `1` means
"empty" for your installation; compare the entity's `raw_contact_value`
attribute with the Ecobulles display before choosing it.
The raw CO2 debug sensor can be enabled later from the integration options.
One Home Assistant integration entry represents the Ecobulles account. Every
box linked to that account becomes a separate Home Assistant device with its
own name and its own water, CO2, alert, and bottle-empty entities. The entry
uses the account holder's name from the portal. Reload the integration after
linking another box to the same account to discover it. The raw CO2 debug
switch is account-wide and affects the raw sensor on every box.

### Data updates and availability

Ecobulles is a cloud polling integration. By default, Home Assistant refreshes
data every `120` seconds. Required usage/device requests are fetched through
Home Assistant's async web session; if the cloud is temporarily unreachable,
entities become unavailable until the next successful coordinator refresh.

The integration also opts into Home Assistant DHCP tracking for already
registered devices. The Ecobulles box does not advertise a distinctive DHCP
hostname, so the integration deliberately avoids broad Microchip MAC-prefix
auto-discovery to prevent false positives.

### Removal

Remove the integration from **Settings → Devices & services → Ecobulles**. If
installed through HACS, also remove the repository from HACS and restart Home
Assistant. Long-term statistics already stored by Home Assistant are not deleted
automatically by removing the integration.

### Supported devices and limitations

This integration targets Ecobulles cloud-connected CO2 water treatment devices,
tested with Ecobulles Expert. The API does not currently expose a formal model
field, LAN discovery, or official CO2 mass counters. CO2 bottle usage is
therefore estimated from public Ecobulles dose guidance and observed valve-open
time, not measured directly. The portal does not expose a confirmed bottle
replacement event, so the integration cannot automatically distinguish a new
bottle from a technical counter reset. Observed installations disagree on
whether raw bottle-contact value `0` or `1` means empty. The integration therefore leaves
the bottle-empty entity unavailable until its installation-specific empty value
is selected in advanced options; the raw value remains visible as an attribute.

### Use cases and examples

- Use `Ecobulles Total Water Usage` for long-term water statistics because it
  stays monotonic across technical counter resets.
- Create an automation when `Ecobulles Active Alerts` is above `0`.
- Track `Ecobulles Estimated CO2 Bottle Usage` to anticipate bottle replacement.

Example automation:

```yaml
alias: Ecobulles active alert notification
triggers:
  - trigger: numeric_state
    entity_id: sensor.ecobulles_active_alerts
    above: 0
actions:
  - action: notify.notify
    data:
      message: "Ecobulles reports an active alert."
```

### Troubleshooting

- If all entities are unavailable, check that your credentials work at
  [portail.ecobulles.com](https://portail.ecobulles.com/login).
- If authentication fails, reconfigure or reload the integration from Home
  Assistant.
- If a raw water or injection-time counter decreases after a power cut, the
  integration preserves the previous segment in persistent storage and keeps
  the reconstructed total monotonic.

### Diagnostics

Home Assistant diagnostics are available from the integration device page. The
diagnostic payload redacts credentials, device identifiers, and active alert
details before export.

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
water and CO2 accounting logic that keeps usage monotonic across technical
counter resets.

### Raw CO2 diagnostics

If you want to study the API's undocumented CO2 value over time, enable the
`Ecobulles Raw CO2 Debug` switch in Home Assistant. When enabled, the integration
adds a diagnostic sensor named `Ecobulles Raw CO2 Value` so you can compare its
hourly / daily evolution against device restarts and water usage.

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
The pytest job enforces a minimum integration coverage gate and uploads
`coverage.json` as a workflow artifact. Coverage is also uploaded to Codecov so
the README badge shows the current percentage dynamically.

### Python library

The Ecobulles cloud client lives in
[`jul-fls/pyecobulles`](https://github.com/jul-fls/pyecobulles) as the
`pyecobulles` async Python package. This keeps Home Assistant-specific code
focused on config entries, coordinators, devices, and entities, while the API
transport is reusable and publishable on PyPI for a future Home Assistant Core
contribution.

### Sensors

#### Water sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles Water Usage` | The cumulative water counter currently reported by the Ecobulles API. It normally represents water usage since installation. |
| `Ecobulles Water Usage Before Current Counter Segment` | The sum of earlier API counter segments preserved after observed technical resets. It is normally `0 L` and does not represent water used with previous CO2 bottles. |
| `Ecobulles Water Usage Total` | A monotonic total reconstructed by the integration. If the device counter drops after a restart or another technical reset, the previous segment is preserved and the new readings are added to it. |

The integration polls Ecobulles every 120 seconds by default and asks the cloud API for data up
to the current minute. This avoids delaying each update until the next closed
hour, which would make Home Assistant assign water used between `00:00` and
`01:00` to the `01:00`-`02:00` Energy dashboard bucket. If the Ecobulles cloud
itself only publishes a value after the hour has closed, Home Assistant will
still record the increase when it first becomes visible.

The API does not currently expose a confirmed bottle-replacement event or a
documented per-bottle water counter. A decrease is therefore treated only as a
technical counter reset; the integration does not claim that it proves a CO2
bottle was replaced.

#### CO2 sensors

| Sensor | Meaning |
| --- | --- |
| `Ecobulles CO2 Injection Time` | Cumulative CO2 electrovalve open time, derived from the API `total_gas` value. The API value appears to be milliseconds; the sensor displays seconds. |
| `Ecobulles Estimated CO2 Bottle Usage` | Experimental estimate of bottle usage, derived from the configured bottle CO2 mass, micrometric screw setting, the inferred 85-150 mg/L middle dose range, and the observed/default 1500 ms/L pulse. |
| `Ecobulles CO2 Bottle Empty` | Device contact from the portal's latest reading. Its raw polarity differs between observed installations, so the sensor stays unavailable until the matching empty-contact value (`0` or `1`) is configured in advanced options. |
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

### Paramètres de configuration

À l'installation, renseignez les mêmes identifiants que sur le [nouveau portail Ecobulles](https://portail.ecobulles.com/login), la masse de CO2
dans la bouteille et le réglage de la vis micrométrique. Les options avancées
exposent la pression CO2, la plage de dose estimée, l'impulsion de référence et
l'intervalle de rafraîchissement. Elles permettent aussi d'indiquer si la valeur
brute `0` ou `1` signifie « bouteille vide » sur votre installation : comparez
d'abord l'attribut `raw_contact_value` avec l'écran du boîtier. Le capteur CO2
brut peut être activé ensuite depuis les options de l'intégration.
Une seule configuration Home Assistant représente le compte Ecobulles. Chaque
boîtier associé à ce compte devient un appareil Home Assistant distinct, avec
son propre nom et ses propres capteurs d'eau, de CO2, d'alertes et de bouteille
vide. L'entrée porte le nom du titulaire du compte indiqué par le portail. Rechargez
l'intégration après avoir associé un nouveau boîtier au compte. L'interrupteur
de diagnostic CO2 brut est commun au compte et affecte tous les boîtiers.

### Mise à jour des données et disponibilité

Ecobulles est une intégration cloud polling. Par défaut, Home Assistant
rafraîchit les données toutes les `120` secondes. Les requêtes nécessaires sont
effectuées via la session web asynchrone de Home Assistant ; si le cloud est
temporairement inaccessible, les entités deviennent indisponibles jusqu'au
prochain rafraîchissement réussi.

L'intégration active aussi le suivi DHCP Home Assistant pour les appareils déjà
enregistrés. Le boîtier Ecobulles n'annonce pas de hostname DHCP distinctif ;
l'intégration évite donc volontairement l'auto-découverte large par préfixe MAC
Microchip afin d'éviter les faux positifs.

### Suppression

Supprimez l'intégration depuis **Paramètres → Appareils et services →
Ecobulles**. Si elle a été installée via HACS, supprimez aussi le dépôt dans HACS
puis redémarrez Home Assistant. Les statistiques longues déjà enregistrées par
Home Assistant ne sont pas supprimées automatiquement.

### Appareils supportés et limites connues

L'intégration cible les appareils Ecobulles connectés au cloud, testée avec un
Ecobulles Expert. L'API n'expose actuellement pas de champ modèle officiel, pas
de découverte LAN, ni de compteur officiel de masse CO2. L'utilisation de
bouteille CO2 est donc estimée à partir des indications publiques Ecobulles et
du temps d'ouverture observé de l'électrovanne, pas mesurée directement. Le
portail n'expose pas d'événement confirmé de remplacement de bouteille :
l'intégration ne peut donc pas distinguer automatiquement une nouvelle bouteille
d'une remise à zéro technique du compteur.
La polarité de l'entrée « bouteille vide » diffère entre des installations
observées : une valeur brute `0` n'a donc pas une signification universelle.
Le capteur reste indisponible tant que la valeur correspondant à « vide » (`0`
ou `1`) n'a pas été choisie dans les options avancées après comparaison avec
l'écran du boîtier.
Si le portail renvoie `total_gas = 0` alors que la bouteille est signalée vide,
l'estimation est indisponible plutôt qu'affichée à tort à `0 %`.

### Cas d'usage et exemples

- Utilisez `Consommation d'eau totale` pour les statistiques longues, car elle
  reste monotone malgré les remises à zéro techniques du compteur.
- Créez une automatisation lorsque `Alertes actives` passe au-dessus de `0`.
- Suivez `Utilisation estimée de la bouteille CO2` pour anticiper le
  remplacement de bouteille.

Exemple d'automatisation :

```yaml
alias: Notification alerte Ecobulles active
triggers:
  - trigger: numeric_state
    entity_id: sensor.ecobulles_active_alerts
    above: 0
actions:
  - action: notify.notify
    data:
      message: "Ecobulles signale une alerte active."
```

### Dépannage

- Si toutes les entités sont indisponibles, vérifiez que vos identifiants
  fonctionnent sur [portail.ecobulles.com](https://portail.ecobulles.com/login).
- Si l'authentification échoue, reconfigurez ou rechargez l'intégration depuis
  Home Assistant.
- Si le compteur brut d'eau ou de temps d'injection diminue après une coupure
  de courant, l'intégration conserve automatiquement le segment précédent dans
  son stockage persistant afin de reconstruire un total monotone.

### Diagnostics

Les diagnostics Home Assistant sont disponibles depuis la page appareil de
l'intégration. Le fichier exporté masque les identifiants, les identifiants
appareil et le détail des alertes actives.

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

Cette commande compile l'intégration et vérifie la logique qui conserve les
compteurs d'eau et de temps d'injection monotones malgré leurs remises à zéro
techniques.

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
son évolution horaire / journalière avec les redémarrages du boîtier et la
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
Le job pytest impose un seuil minimum de couverture de l'intégration et téléverse
`coverage.json` en artefact de workflow. La couverture est aussi envoyée à
Codecov afin que le badge du README affiche dynamiquement le pourcentage actuel.

### Librairie Python

Le client cloud Ecobulles vit dans
[`jul-fls/ecobulles_api`](https://github.com/jul-fls/ecobulles_api) sous forme
du package Python asynchrone `pyecobulles`. L'intégration Home Assistant reste
ainsi centrée sur les config entries, coordinators, appareils et entités, tandis
que le transport API est réutilisable et publiable sur PyPI pour une future
contribution à Home Assistant Core.

### Capteurs

#### Capteurs d'eau

| Capteur | Signification |
| --- | --- |
| `Consommation d'eau` | Le compteur d'eau cumulatif actuellement reporté par l'API Ecobulles. Il représente normalement la consommation depuis l'installation. |
| `Consommation d'eau avant le segment de compteur actuel` | La somme des anciens segments du compteur API conservés après des remises à zéro techniques observées. Elle vaut normalement `0 L` et ne représente pas l'eau utilisée avec les bouteilles de CO2 précédentes. |
| `Consommation d'eau totale` | Un total monotone reconstruit par l'intégration. Si le compteur du boîtier diminue après un redémarrage ou une autre remise à zéro technique, le segment précédent est conservé et les nouvelles valeurs lui sont ajoutées. |

L'intégration interroge Ecobulles toutes les 120 secondes par défaut et demande a l'API cloud les
donnees disponibles jusqu'a la minute courante. Cela evite de retarder chaque
mise a jour jusqu'a l'heure pleine suivante, ce qui ferait classer par Home
Assistant l'eau consommee entre `00:00` et `01:00` dans le creneau Energy
Dashboard `01:00`-`02:00`. Si le cloud Ecobulles ne publie lui-meme la valeur
qu'apres la fin de l'heure, Home Assistant enregistrera tout de meme
l'augmentation au moment ou elle devient visible.

L'API n'expose actuellement ni événement de remplacement de bouteille confirmé,
ni compteur d'eau par bouteille documenté. Une diminution est donc uniquement
traitée comme une remise à zéro technique ; l'intégration n'affirme pas qu'elle
prouve le remplacement d'une bouteille de CO2.

#### Capteurs CO2

| Capteur | Signification |
| --- | --- |
| `Temps d'injection CO2` | Temps cumulé d'ouverture de l'électrovanne CO2, dérivé de la valeur API `total_gas`. Cette valeur semble être exprimée en millisecondes ; le capteur l'affiche en secondes. |
| `Utilisation estimée de la bouteille CO2` | Estimation expérimentale de l'utilisation de la bouteille, dérivée de la masse de CO2 configurée, du réglage de vis micrométrique, de la plage médiane estimée 85-150 mg/L et de l'impulsion observée/par défaut de 1500 ms/L. |
| `Bouteille de CO2 vide` | Contact du boîtier lu sur le portail. Sa polarité brute varie entre les installations observées : le capteur reste indisponible tant que la valeur signifiant « vide » (`0` ou `1`) n'est pas configurée dans les options avancées. |
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

