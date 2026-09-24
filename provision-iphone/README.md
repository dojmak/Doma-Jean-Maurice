# Provisions CP & IFC — web app iPhone

Version exécutable sur iPhone de la skill `provision-retraite-conges` (moteur `provision_engine.py` v1.2.0).

Le moteur Python d'origine tourne **tel quel** dans Safari via Pyodide (Python compilé en WebAssembly).
Aucun calcul n'a été réécrit. Le classeur est lu et calculé sur l'appareil : aucune donnée de paie
n'est envoyée à un serveur.

## Contenu

| Chemin | Rôle |
|---|---|
| `index.html` | Interface : choix du classeur → confirmation des entrées (I3) → soldes GL → calcul → partage du `.xlsx` |
| `engine/provision_engine.py` | Copie à l'identique du moteur de la skill (SHA-256 `0da26040…be30c`, vérifié au démarrage : divergence = calcul bloqué) |
| `engine/bridge.py` | Passerelle : relecture des entrées pour l'étape de confirmation, lancement de `main()` avec les arguments CLI, capture des arrêts bloquants |
| `vendor/pyodide/` | Pyodide 0.27.7, hébergé localement (aucun CDN) |
| `vendor/wheels/` | openpyxl 3.1.5 + et_xmlfile 2.0.0 |
| `sw.js`, `manifest.webmanifest`, `icons/` | Mode hors-ligne et icône d'écran d'accueil |
| `tests/` | Classeur synthétique + test de bout en bout en émulation iPhone |

## Installation sur l'iPhone

1. Héberger le dossier `provision-iphone/` en **HTTPS** (GitHub Pages, ou tout hébergement statique).
   Le HTTPS est nécessaire pour la vérification d'empreinte du moteur et pour le mode hors-ligne.
2. Ouvrir l'URL dans **Safari** → bouton Partager → **« Sur l'écran d'accueil »**.
3. Le premier lancement télécharge environ 14 Mo, une seule fois. Les lancements suivants fonctionnent hors-ligne.

## Utilisation

1. Choisir le classeur `Provision_Retraite_Congé_exo_MM AA.xlsm` (depuis Fichiers, Drive, OneDrive…).
2. Vérifier la date d'arrêté, l'effectif, le taux AT et les onglets détectés, puis cocher la confirmation.
3. Saisir les soldes GL avant OD (4281x, 4382x, 196100). Avec 0, l'OD constate la dotation pleine.
4. Calculer, puis **Partager / Enregistrer dans Fichiers** le fichier `PROVISION_RC_AAAA-MM.xlsx`.

Les garde-fous du moteur restent actifs : arrêt anti-cache-vide, assertion D=C sur l'OD, cross-check [L-6].
L'app affiche aussi deux alertes : cache C/R vide (le cross-check « OK » ne compare alors rien) et
effectif supérieur à 50 avec cross-check OK.

**Limites :**
- le validateur GM-1 n'est pas embarqué, donc tout livrable reste **[NON VALIDÉ GM-1]** jusqu'à son passage au validateur dans Cowork ;
- l'app ne recalcule pas un classeur dont le cache de formules est vide (pas de LibreOffice sur iPhone) : il faut d'abord l'ouvrir et l'enregistrer dans Excel.

## Mise à jour du moteur

Quand la skill évolue :

1. Recopier `scripts/provision_engine.py` dans `engine/`.
2. Mettre à jour `ENGINE_SHA256` dans `index.html` (`sha256sum engine/provision_engine.py`).
3. Incrémenter `CACHE` dans `sw.js`.
4. Relancer le test.

## Test

```bash
pip install openpyxl
python tests/make_sample.py /tmp/sample.xlsx
python engine/provision_engine.py /tmp/sample.xlsx --out /tmp/native --prev-retraite 500000
python -m http.server 8765 &            # depuis provision-iphone/
NODE_PATH=$(npm root -g) node tests/e2e.mjs http://localhost:8765/index.html /tmp/sample.xlsx /tmp
```
