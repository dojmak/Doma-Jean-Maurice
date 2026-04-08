---
name: reconciliation-fournisseurs
description: >
  Rapprochement GL interne vs relevé fournisseur — SYSCOHADA FCFA CMPC.
  5 passes + TCJ v2.5.2. Typage facture/règlement/avoir. Comptes 401/521.
  Seuil NR 5%. MAX_NM_CANDIDATES=30.
  NON APPLICABLE sans données fournisseurs réelles.
---

# Réconciliation Fournisseurs — v2.5.2

> **RÈGLE DE LECTURE — RESPECTER IMPÉRATIVEMENT**
> - Tâche courante (lancer, vérifier, qualifier suspens) → **lire jusqu'à [STOP-HEAD]**
> - Tâche complexe (déboguer TCJ, modifier typage, générer script) → **lire le fichier entier**
> - Ne jamais charger la section FULL par défaut

---

## RÈGLES ABSOLUES

| # | Règle | Violation |
|---|---|---|
| R1 | DATE en dtype=str — jamais de parse auto | Inversion DD/MM |
| R2 | `controler_totaux()` int64 AVANT tout traitement | Base corrompue |
| R3 | Toutes les lignes — aucun filtre date implicite | Suspens invisibles |
| R4 | Garde Phase 2 AND strict ≤1 FCFA ET ≤20% — micro <10 FCFA absolu seul — cas zéro → False | Faux matchs |
| R5 | DÉBIT négatif Sage = avoir — jamais règlement | Typage erroné |
| R6 | Jamais inventer un compte SYSCOHADA | Écriture fausse |
| R7 | NR >5% → STOP + confirmation avant écritures | Écritures non validées |
| R8 | Planteur CMPC : NOM + MONTANT simultanément — jamais montant seul | Faux paiement |
| R9 | `detecter_convention()` avant tout matching | 0% match sur GL inversé |
| R10 | MAX_NM_CANDIDATES = 30 — non négociable | Timeout volumes élevés |
| R11 | Montants FCFA via `_to_int()` — jamais float64 direct | Arrondi binaire garde ±1 FCFA |

---

## DÉPENDANCES TCJ-CORE v1.0

| Composant | Statut |
|---|---|
| `corriger_date()` 4 cas | ✅ v2.5.2 (convention MM/DD alignée D365) |
| `_to_int()` int64 | ✅ v2.5.1 |
| `resolver_montant()` P1/P2/P3 | ✅ |
| `ecart_montant_ok()` AND strict | ✅ v2.5.2 (garde micro <10 FCFA) |
| `controler_totaux()` int64 | ✅ v2.5.1 |
| `corriger_date_self_healing()` AC-1 | ✅ v2.5.2 |
| `two_sum_hashmap()` AC-3 | ✅ v2.5.2 |
| Stop words + `fuzz_score()` | ✅ v2.5.2 |

Spécificités propres : `detecter_convention()` · `typer_ligne()` · `reconcilier_par_solde()` · règle planteur NOM+MONTANT · comptes 401/4094 · MAX_NM_CANDIDATES=30

---

## ÉTAPES OBLIGATOIRES

```
0A. Lecture dtype=str — colonnes + 3 lignes + dernière ligne
0B. corriger_date() 4 cas sur GL1 et GL2
0C. controler_totaux() int64 — STOP si écart > 1 FCFA (R2)
0D. controler_couverture_temporelle() — STOP si périodes disjointes
0E. detecter_convention() GL1 + GL2 — normaliser montant_abs + type
0F. typer_ligne() : facture / règlement / avoir
0G. Scope — toutes les lignes, pas de filtre
1.  5 passes de lettrage (même type économique uniquement)
    - P1 : Référence exacte + Montant exact + Date exacte → 🟢 Certaine
    - P2 : Référence exacte + Montant exact + Date ±3j → 🟢 Certaine
    - P3 : Montant exact + Date ±5j + Libellé similaire ≥ seuil → 🟢 Haute
    - P4 : Montant exact + Libellé similaire ≥ seuil (sans date) → 🟠 Moyenne
    - P5 : Montant ±1 FCFA + Libellé similaire ≥ seuil → 🟠 Moyenne
    - Bonus : Somme n→1 (max 5) + ecart_montant_ok() → 🟠 Moyenne
2.  TCJ Phase 1 (montant pur N=30)
3.  TCJ Phase 2 (A/B/C/D) — ecart_montant_ok() AND strict
4.  Qualifier suspens (a/b/d/e/f) — seuil 5%
5.  Si couverture asymétrique → reconcilier_par_solde()
6.  Fichier principal + fichier justification écart (si écart ≠ 0)
```

---

## COMMANDE D'EXÉCUTION

```bash
python reconcile_fournisseurs.py \
  --gl1 gl_interne.xlsx --gl2 releve_fournisseur.xlsx \
  --output Rapprochement_Fournisseur_AAAA-MM.xlsx \
  --fournisseur "NOM" \
  [--inverser-sens] [--seuil-similarite 0.3] [--tcj-lookahead 30]
```

---

## CONVENTIONS DE SIGNE

| Système | Facture | Règlement |
|---|---|---|
| D365 GL interne | Montant **négatif** | Positif |
| Sage GL fournisseur | DÉBIT **positif** | CRÉDIT positif |
| Sage extourne / avoir | DÉBIT **négatif** | — |

> Détecter avec `detecter_convention()` → normaliser AVANT matching.

---

## TYPAGE ÉCONOMIQUE — PRIORITÉS

```
R1 : DÉBIT < 0 Sage            → avoir   (PRIORITAIRE)
R2 : type_doc contient 'Avoir' → avoir
R3 : libellé 'AV-' ou 'AVOIR'  → avoir
R4 : DÉBIT > 0 GL fourn.       → facture
R5 : CRÉDIT > 0 GL fourn.      → règlement
R6 : Montant < 0 D365          → facture
R7 : Montant > 0 D365          → règlement
```

---

## CODES ÉCARTS

| Code | Cause | Action |
|---|---|---|
| (a) | Absent autre source | Écriture corrective 401xxx |
| (b) | Présent non identifié | Recherche manuelle |
| (d) | Décalage date hors ±3j | Élargir ou manuel |
| (e) | Annulation / cut-off | Non actionnable |
| (f) | Regroupement partiel | TCJ n→1 |

> Actionnables : a > d > f > b · Code (e) affiché SÉPARÉMENT

---

## RÉSUMÉ RÉPONSE

1. X transactions rapprochées — détail par passe
2. TCJ P1 : N matchs montant pur · P2 : N matchs affinés
3. Suspens actionnables (a/b/d/f) : Y lignes = Y FCFA
4. Suspens non-actionnables (e) : Z lignes — séparés
5. Écart = N FCFA
6. P1 🟢 certains · P2 🟠 à valider · Suspens 🔴 à justifier
7. Lien fichier principal + fichier justification écart

---

## RÈGLE PLANTEUR CMPC

> ⚠️ Toujours croiser **NOM + MONTANT simultanément**.
> Même montant → vérification libellé obligatoire avant validation.

---

<!-- [STOP-HEAD] — TÂCHE COURANTE : NE PAS LIRE AU-DELÀ DE CETTE LIGNE -->

---

# SECTION FULL — Lire uniquement si tâche complexe

---

## ÉTAPE 0 — DÉTAIL COMPLET

### 0B — corriger_date() 4 cas

```python
from datetime import datetime, date
TODAY = date.today()

def corriger_date(raw, journal=None):
    import pandas as pd
    if pd.isna(raw) or str(raw).strip() in ('','nan','NaT','None'): return None
    raw = str(raw).strip()
    if '/' in raw:
        parts = raw.split('/')
        if len(parts)==3:
            try:
                p0,p1,p2 = int(parts[0]),int(parts[1]),int(parts[2])
                if p0>12: return datetime(p2,p1,p0)    # CAS 4 DD/MM/YYYY — non ambigu
                # CAS AMBIGU : p0≤12 ET p1≤12 — convention MM/DD (exports D365 US)
                if p0<=12 and p1<=12 and journal is not None:
                    journal.append(f"[DATE-AMB] '{raw}' — p0={p0}≤12 ET p1={p1}≤12 : interprété MM/DD (US). Vérifier si DD/MM attendu.")
                return datetime(p2,p0,p1)              # CAS 1 MM/DD/YYYY US
            except ValueError: return None
    if '-' in raw or ' ' in raw:
        raw2 = raw.split(' ')[0]
        parts = raw2.split('-')
        if len(parts)==3:
            try:
                y,mm,dd = int(parts[0]),int(parts[1]),int(parts[2])
                d = datetime(y,mm,dd)
                if d.date()>TODAY and mm<=12 and dd<=12: return datetime(y,dd,mm)
                return d
            except ValueError: return None
    return None
```

> **Note** : Convention alignée sur la skill bancaire v2.5.2. Les exports D365 Business Central sont en format US (MM/DD). Le warning `[DATE-AMB]` signale les cas ambigus pour vérification humaine.

### 0C — controler_totaux() int64

```python
def controler_totaux(df, label, col_debit=None, col_credit=None, col_montant=None):
    def _parse(s):
        return (pd.to_numeric(s.str.replace(' ','').str.replace(',','.'), errors='coerce')
                  .fillna(0).round(0).astype('int64'))
    if col_montant:
        m = _parse(df[col_montant])
        solde = int(m.sum())
    elif col_debit and col_credit:
        solde = int(_parse(df[col_debit]).sum()) - int(_parse(df[col_credit]).sum())
    print(f"{label} | Solde net = {solde:,.0f} FCFA")
    return solde
```

### 0D — Couverture temporelle

```python
def controler_couverture_temporelle(df1, df2, col1='date_corr', col2='date_corr'):
    d1min,d1max = df1[col1].dropna().min(), df1[col1].dropna().max()
    d2min,d2max = df2[col2].dropna().min(), df2[col2].dropna().max()
    overlap_s, overlap_e = max(d1min,d2min), min(d1max,d2max)
    if overlap_s > overlap_e:
        raise ValueError("[0D] Périodes disjointes — rapprochement impossible")
    t1 = (overlap_e-overlap_s).days / max((d1max-d1min).days,1)
    t2 = (overlap_e-overlap_s).days / max((d2max-d2min).days,1)
    if abs((d1min-d2min).days)>90 or abs((d1max-d2max).days)>90:
        print("⚠️ [0D] Écart couverture > 3 mois — suspens (e) nombreux attendus")
    if t1<0.80 or t2<0.80:
        print("⚠️ [0D] Chevauchement <80% — matching structurellement limité")
    return overlap_s, overlap_e, t1, t2
```

### 0E — detecter_convention()

```python
def detecter_convention(df, col_debit=None, col_credit=None):
    if col_debit and col_credit:
        deb  = pd.to_numeric(df[col_debit].astype(str).str.replace(' ',''), errors='coerce').fillna(0)
        cred = pd.to_numeric(df[col_credit].astype(str).str.replace(' ',''), errors='coerce').fillna(0)
        n = max(len(df),1)
        is_abs = ((deb<0).sum()==0 and (cred<0).sum()==0)
        is_rep = ((deb>0).sum()/n>=0.10 and (cred>0).sum()/n>=0.10)
        if is_abs and is_rep: return 'inverse'
    return 'standard'
```

### 0F — typer_ligne()

```python
def typer_ligne(row, col_debit=None, col_credit=None, col_montant=None,
                col_type_doc=None, col_libelle=None):
    def _i(v):
        try: return int(round(float(str(v).replace(' ','').replace('\xa0','').replace(',','.'))))
        except: return 0
    deb  = _i(row[col_debit])  if col_debit  else 0
    cred = _i(row[col_credit]) if col_credit else 0
    mt   = _i(row[col_montant]) if col_montant else 0
    tyd  = str(row.get(col_type_doc,'')).upper()
    lib  = str(row.get(col_libelle,'')).upper()
    if col_debit and deb<0: return 'avoir'          # R1 PRIORITAIRE
    if 'AVOIR' in tyd or 'AV-' in lib or 'AVOIR' in lib: return 'avoir'
    if col_debit and col_credit:
        if deb>0: return 'facture'
        if cred>0: return 'reglement'
    if col_montant:
        if mt<0: return 'facture'
        if mt>0: return 'reglement'
    return 'inconnu'
```

---

## COMPOSANTS TCJ-CORE INTÉGRÉS v2.5.2

### `_to_int()` — int64

```python
def _to_int(valeur) -> int:
    import pandas as pd
    if pd.isna(valeur) or str(valeur).strip() in ('', '-', '—'):
        return 0
    s = str(valeur).strip()
    negatif = s.startswith('(') and s.endswith(')')
    s = s.strip('()').replace(' ', '').replace('\xa0', '').replace(',', '.')
    try:
        return -int(round(float(s), 0)) if negatif else int(round(float(s), 0))
    except ValueError:
        return 0
```

### `corriger_date_self_healing()` — AC-1

```python
FORMATS_TENTES = ["%d-%b-%y", "%d-%b-%Y", "%Y.%m.%d", "%d %B %Y", "%d/%m/%Y"]

def corriger_date_self_healing(raw, journal: list):
    r = corriger_date(raw, journal)
    if r: return r
    for fmt in FORMATS_TENTES:
        try:
            d = datetime.strptime(str(raw).strip(), fmt)
            journal.append(f"[AC-1] '{raw}' → {d.date()} via {fmt}")
            return d
        except ValueError: continue
    try:
        from xlrd import xldate_as_datetime
        d = xldate_as_datetime(float(raw), 0)
        journal.append(f"[AC-1] Excel numérique '{raw}' → {d.date()}")
        return d
    except Exception: pass
    journal.append(f"[AC-1] ÉCHEC '{raw}' → suspens (b)")
    return None
```

### Stop words + `fuzz_score()`

```python
import unicodedata

def _strip_accents(s: str) -> str:
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')

STOP_WORDS_CI = {
    "VIR","VIREMENT","CHQ","CHEQUE","REM","REMISE","PRV","PRELEVEMENT",
    "COMM","COMMISSION","FRAIS","ORDRE","DE","DU","AU","ET","LA","LE","LES",
    "FAC","FACTURE","REG","REGLEMENT","PAIEMENT","PAR"
}

def _tok(lib: str) -> set:
    return set(_strip_accents(str(lib)).upper().split()) - STOP_WORDS_CI

def fuzz_score(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    t1, t2 = _tok(a), _tok(b)
    j = len(t1 & t2) / len(t1 | t2) if (t1 and t2) else 0.0
    return max(j, SequenceMatcher(None, _strip_accents(a).upper(), _strip_accents(b).upper()).ratio())
```

### `two_sum_hashmap()` — AC-3

```python
def two_sum_hashmap(montants, ecart: int, journal: list):
    seen = {}
    for idx, val in montants.round(0).astype('int64').items():
        c = ecart - val
        if c in seen:
            journal.append(f"[AC-3] Two-Sum : {seen[c]}({c:,.0f}) + {idx}({val:,.0f}) = {ecart:,.0f}")
            return (seen[c], idx)
        seen[val] = idx
    return None
```

---



### AC-1 — resolver_montant cascade

```python
ALIAS_DEB = ['debit','débit','deb','sortie','charge','montant débit','dbt']
ALIAS_CRD = ['credit','crédit','crd','entree','entrée','produit','montant crédit','crt']
ALIAS_MT  = ['montant','amount','mt','valeur','total','net','montant net','solde']

def resolver_montant_self_heal(df, journal):
    cols = {c.lower().strip():c for c in df.columns}
    col_d = next((cols[a] for a in ALIAS_DEB if a in cols), None)
    col_c = next((cols[a] for a in ALIAS_CRD if a in cols), None)
    if col_d and col_c:
        journal.append(f"[AC-1] P1 : '{col_d}' + '{col_c}'")
        df['__montant__'] = (pd.to_numeric(df[col_c].str.replace(' ',''), errors='coerce').fillna(0)
                           - pd.to_numeric(df[col_d].str.replace(' ',''), errors='coerce').fillna(0))
        return df
    col_m = next((cols[a] for a in ALIAS_MT if a in cols), None)
    if col_m:
        journal.append(f"[AC-1] P2 : '{col_m}'")
        df['__montant__'] = pd.to_numeric(df[col_m].str.replace(' ',''), errors='coerce').fillna(0)
        return df
    raise ValueError(f"[AC-1] ÉCHEC — colonnes : {list(df.columns)}")
```

### AC-2 — Ligne total

```python
def exclure_ligne_total(df, col_montant, journal):
    if df.empty: return df
    derniere = df.iloc[-1]
    for col in df.columns:
        if any(m in str(derniere[col]).lower() for m in ['total','sous-total','cumul','sum']):
            journal.append(f"[AC-2] Total détecté col '{col}' — exclue")
            return df.iloc[:-1].copy()
    try:
        vals = pd.to_numeric(df[col_montant].str.replace(' ',''), errors='coerce').fillna(0)
        if abs(vals.iloc[:-1].sum() - vals.iloc[-1]) <= 1:
            journal.append("[AC-2] Total numérique détecté — exclue")
            return df.iloc[:-1].copy()
    except: pass
    return df
```

### AC-3 — NR >5%

```
1. Si alerte 0D → signaler NR structurel (e) vs NR actionnable
2. TCJ Phase 1 + Phase 2
3. NR ≤ 5% → continuer | NR > 5% → STOP avec décomposition codes
```

### AC-4 — Tri suspens actionnables

```python
def prioriser_suspens(df_suspens, ecart_global, journal):
    PRIO = {'a':1,'d':2,'f':3,'b':4}
    act  = df_suspens[df_suspens['code_ecart']!='e'].copy()
    nact = df_suspens[df_suspens['code_ecart']=='e'].copy()
    act['_d'] = abs(act['__montant__'].abs() - abs(ecart_global))
    act['_p'] = act['code_ecart'].map(PRIO).fillna(9)
    tries = act.sort_values(['_d','_p'])
    journal.append(f"[AC-4] Top 5 actionnables :")
    for _,r in tries.head(5).iterrows():
        journal.append(f"  {r.get('__date__','')} | {str(r.get('__libelle__',''))[:40]} | {r['__montant__']:,.0f} | ({r['code_ecart']})")
    journal.append(f"[AC-4] Non-actionnables (e) : {len(nact)} lignes — pas d'écriture corrective")
    return tries
```

---

## ecart_montant_ok — Garde Phase 2

```python
MAX_ECART_ABSOLU_P2  = 1
MAX_ECART_RELATIF_P2 = 0.20

def ecart_montant_ok(m1: int, m2: int) -> bool:
    if m1==0 or m2==0: return False
    if (m1>0)!=(m2>0): return False
    ecart_abs = abs(m1-m2)
    if abs(m1) < 10 or abs(m2) < 10: return ecart_abs <= 1  # garde micro-montants
    return ecart_abs<=MAX_ECART_ABSOLU_P2 and (ecart_abs/max(abs(m1),abs(m2)))<=MAX_ECART_RELATIF_P2
```

Utilisation :
```python
crit_A = (ecart_date<=3) and (score_lib>=SEUIL) and ecart_montant_ok(m1,m2)
crit_B = (ecart_date<=5) and (score_lib>=SEUIL*0.8) and ecart_montant_ok(m1,m2)
crit_C = (score_lib>=SEUIL) and ecart_montant_ok(m1,m2)
```

---

## TCJ v2.5 — DÉTAIL ALGO

### Phase 1

```
Tri croissant GL1 + GL2 par montant_abs.
|GL1[i] - GL2[j]| ≤ 1 FCFA → MATCH
  Run doublons → scoring ref+lib+date
FAUX → look-ahead bilatéral N=30
  Aucun match → suspens (avancer le plus petit)
```

### Phase 2

```
A : date ±3j + lib ≥ seuil + ecart_montant_ok()
B : date ±5j + lib ≥ seuil×0.8 + ecart_montant_ok()
C : lib ≥ seuil + ecart_montant_ok()
D : n→m (MAX_NM_CANDIDATES=30) + ecart_montant_ok()
```

### Score composite

| Composante | Poids |
|---|---|
| Référence | 1.2 |
| Libellé | 1.0 |
| Date | 0.8 |
| Total normalisé | /3.0 |

### JUSTIFICATION_MATCH — Format canonique

```
[PASSE] CRITÈRE1=valeur | CRITÈRE2=valeur | score=X.XX
Ex : [TCJ-P1] MONTANT=1 900 548 | look-ahead=5 | score=0.61
     SUSPENS — aucune contrepartie après Phase 1+2
```

---

## STRUCTURE EXCEL

### Fichier principal

| Onglet | Contenu |
|---|---|
| Récapitulatif | Soldes, écart, stats, journal AC |
| Suspens GL Interne | GL1 sans correspondance (jaune) |
| Suspens Relevé Fournisseur | GL2 sans correspondance (orange) |
| Transactions Rapprochées | Paires + JUSTIFICATION_MATCH |
| Analyse TCJ Amélioré v2.5 | TOUJOURS — codes couleur + JUSTIFICATION_MATCH |
| Détail Écarts côte à côte | Actionnables en haut · (e) en bas |

### Fichier justification écart — si écart ≠ 0

`[Fournisseur]_Detail_Ecart_[Montant]_FCFA_[AAAAMM].xlsx`

| Onglet | Couleur |
|---|---|
| Synthèse Écart | — |
| Écart GL1 — Détail (a/b/d/f) | Jaune #FFEB9C |
| Écart GL2 — Détail (a/b) | Orange #FCE4D6 |
| GL1 hors-période (e) — Info | Vert #E2EFDA |

Vérification : `Écart global = Suspens GL1 actionnables + Suspens GL2 actionnables`

---

## RÉCONCILIATION PAR SOLDE — Option v2.5

Déclenchement : couverture asymétrique détectée en 0D.

```python
def reconcilier_par_solde(df1, df2, col_date1='date_corr', col_date2='date_corr',
                           col_mont1='__montant__', col_mont2='__montant__', frequence='M'):
    def _sec(df, col):
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            return df[col].apply(corriger_date)
        return df[col]
    df1w = df1.copy(); df1w[col_date1] = _sec(df1w, col_date1)
    df1w['per'] = pd.to_datetime(df1w[col_date1]).dt.to_period(frequence)
    s1 = df1w.groupby('per')[col_mont1].sum().cumsum().reset_index().rename(columns={col_mont1:'s_gl1'})
    mask_ran = df2.get('JRNL',pd.Series(dtype=str)).str.upper().str.strip()=='RAN'
    ran = df2.loc[mask_ran,col_mont2].sum() if mask_ran.any() else None
    df2w = df2[~mask_ran].copy(); df2w[col_date2] = _sec(df2w, col_date2)
    df2w['per'] = pd.to_datetime(df2w[col_date2]).dt.to_period(frequence)
    s2 = df2w.groupby('per')[col_mont2].sum().cumsum().reset_index().rename(columns={col_mont2:'s_gl2'})
    df_s = pd.merge(s1,s2,on='per',how='outer').sort_values('per')
    df_s['ecart'] = df_s['s_gl1'] - df_s['s_gl2']
    return df_s, ran
```

---

---

## TABLEAU DES VERSIONS

| Fonctionnalité | v2.5.1 | v2.5.2 |
|---|---|---|
| `_to_int()` int64 | ✅ | inchangé |
| `controler_totaux()` int64 | ✅ | inchangé |
| `corriger_date()` — convention MM/DD D365 + warning DATE-AMB | ❌ (DD/MM CI) | **✅** |
| `corriger_date_self_healing()` formats exotiques | ⚠️ DIV-003 | **✅** |
| `two_sum_hashmap()` AC-3 O(n) | ⚠️ DIV-002 | **✅** |
| Stop words + `fuzz_score()` normalisation accents | ❌ | **✅** |
| `ecart_montant_ok()` garde micro <10 FCFA | ❌ | **✅** |
| 5 passes détaillées avec critères | ❌ | **✅** |
| `_to_int()` code source dans FULL | ❌ | **✅** |

---

## DIV OUVERTES

Aucune DIV ouverte en v2.5.2.

> P1 restants (non bloquants) : code (g) collision, `controler_totaux()` → journal, vue alignée côte-à-côte.
> Traiter lors d'une prochaine révision si besoin opérationnel identifié.
