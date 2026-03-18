---
name: reconciliation-fournisseurs
description: Rapprochement inter-comptes fournisseurs SYSCOHADA Revise 2017. Use when the user wants to reconcile two supplier ledgers (GL interne vs releve fournisseur), identify matched and unmatched transactions, and produce a structured Excel report. Implements 5-pass matching + TCJ Ameliore (Tri Croissant Juxtapose) for residual suspens.
---

# Rapprochement Fournisseurs — TCJ Ameliore — SYSCOHADA Revise 2017

Compare deux grands livres fournisseurs (GL interne vs releve fournisseur),
identifie les transactions rapprochees et les suspens, et produit un fichier
Excel structure avec un onglet TCJ Ameliore pour les ecarts residuels.

## Regles OHADA / Zone FCFA

- Devise : FCFA (XOF/XAF) — montants entiers
- Tolerance d'arrondi : +/-1 FCFA (regle OHADA art. 59)
- Plan comptable : SYSCOHADA Revise 2017
- Comptes cles : 401 Fournisseurs, 521 Banque, 631 Frais bancaires

## Fichiers d'entree attendus

- **GL1** : Grand livre interne (.xlsx ou .pdf) — export SAGE, CEGID, etc.
- **GL2** : Releve fournisseur (.xlsx ou .pdf) — document fournisseur

Si les fichiers ne sont pas fournis, demander a l'utilisateur de les charger.

## Workflow

Faire une todo list de toutes les etapes ci-dessous et les traiter une par une.

### 1. Verifier la presence des fichiers

Verifier que les deux fichiers GL1 et GL2 sont disponibles dans le repertoire
de travail. Si absents, demander a l'utilisateur de les fournir avant de
continuer.

```python
import pandas as pd
df1 = pd.read_excel('gl_interne.xlsx')
df2 = pd.read_excel('releve_fournisseur.xlsx')
print(df1.columns.tolist(), df1.head(3))
print(df2.columns.tolist(), df2.head(3))
```

Le script detecte automatiquement les colonnes Date, Reference, Libelle,
Debit/Credit (ou Montant signe). Si Debit/Credit sont dans deux colonnes
separees, ils sont fusionnes automatiquement (Credit+, Debit-).

### 2. Lancer le rapprochement

```bash
python reconcile_fournisseurs.py \
    --gl1   gl_interne.xlsx \
    --gl2   releve_fournisseur.xlsx \
    --output Rapprochement_Fournisseur_AAAA-MM.xlsx \
    --fournisseur "NOM DU FOURNISSEUR" \
    [--inverser-sens] \
    [--seuil-similarite 0.3] \
    [--tcj-lookahead 4] \
    [--devise FCFA] \
    [--gl1-label "GL Interne"] \
    [--gl2-label "Releve Fournisseur"]
```

**Parametres cles :**

| Parametre | Defaut | Description |
|-----------|--------|-------------|
| `--fournisseur` | FOURNISSEUR | Nom affiche dans le recap Excel |
| `--inverser-sens` | off | Inverser debit/credit de GL2 (convention inverse) |
| `--seuil-similarite` | 0.3 | Seuil Jaccard + SequenceMatcher (0.0-1.0) |
| `--tcj-lookahead` | 4 | Nb max d'ecritures dans un groupe TCJ (2-5) |
| `--gl1-label` | GL Interne | Etiquette GL1 dans l'Excel |
| `--gl2-label` | Releve Fournisseur | Etiquette GL2 dans l'Excel |

### 3. Protocole de lettrage multi-passes

| Passe | Criteres | Confiance |
|-------|----------|-----------|
| 1 | Reference + Montant + Date exacte | Parfaite |
| 2 | Reference + Montant + Date +/-3j | Tres haute |
| 3 | Montant + Date +/-5j + Libelle similaire | Haute |
| 4 | Montant exact + Reference partielle (sans date) | Bonne |
| 5 | Montant +/-1 FCFA + Libelle similaire | Acceptable |
| TCJ | Regroupements additifs n:1 et 1:n sur les suspens | Suggestion |

Chaque ecriture ne peut etre rapprochee qu'une seule fois.

**Score de similarite des libelles** : max(Jaccard sur tokens-cles, SequenceMatcher).
Seuil 30% par defaut (suffisant car les libelles GL et fournisseur different souvent).

### 4. TCJ Ameliore — Suspens residuels

Apres les 5 passes, le TCJ Ameliore (Tri Croissant Juxtapose) analyse les
ecritures non rapprochees en cherchant des combinaisons additives :
- **1 GL1 -> n GL2** : une ecriture GL1 = somme de n ecritures GL2
- **n GL1 -> 1 GL2** : n ecritures GL1 = une ecriture GL2

Les suggestions sont affichees dans l'onglet **"TCJ Ameliore"** de l'Excel.
Ce ne sont que des propositions — l'utilisateur doit les valider manuellement.

### 5. Verifier le fichier produit

Ouvrir le fichier Excel et verifier que l'onglet **Recapitulatif** affiche :
- L'ecart de solde en **vert** (= 0 ou <= 1 FCFA) : soldes equilibres
- L'ecart de solde en **rouge** : ecart a investiguer (verifier compte 401)

**Onglets du fichier Excel :**

| Onglet | Contenu |
|--------|---------|
| Recapitulatif | Soldes, taux de rapprochement, detail par passe, suggestions TCJ |
| Ecarts GL Interne | Ecritures GL1 sans correspondance dans GL2 (orange) |
| Ecarts Releve Fournisseur | Ecritures GL2 sans correspondance dans GL1 (rouge) |
| Transactions Rapprochees | Toutes les paires rapprochees, colorees par passe |
| TCJ Ameliore | Suggestions de regroupements additifs sur les suspens |
| Detail Ecarts (cote a cote) | GL1 suspens et GL2 suspens juxtaposes pour analyse visuelle |

### 6. Analyser les ecarts

Pour chaque suspens identifie, determiner la cause :
- **Ecriture en transit** : ecriture comptabilisee mais non encore recue par le fournisseur (ou vice versa) — cut-off art. 59 OHADA
- **Ecriture manquante** : oubli de comptabilisation
- **Erreur de montant** : ecart superieur a 1 FCFA
- **Doublon** : ecriture enregistree deux fois
- **Regroupement** : plusieurs ecritures d'un cote = une ecriture de l'autre (voir onglet TCJ)

### 7. Cas particuliers

**Sens inverse (--inverser-sens)** : certains fournisseurs presentent leur
releve en sens inverse (debit GL = credit fournisseur). Utiliser ce flag
si les montants correspondent mais les sens sont opposes.

**Fichiers PDF** : le script supporte les PDF via `pdfplumber`.
Installer avec : `pip install pdfplumber`

**Ecritures de compensation** : les avoirs fournisseurs peuvent apparaitre
avec un montant negatif. S'assurer que la colonne Montant est signee, ou
utiliser les colonnes Debit/Credit separees.

## Conclusion

A la fin du rapprochement, fournir un resume avec :

- Taux de rapprochement (nb ecritures rapprochees / total GL1)
- Ecart de solde GL1 - GL2 (OK si <= 1 FCFA)
- Nombre de suspens GL1 et GL2 avec montants
- Nombre de suggestions TCJ a valider manuellement
- Actions recommandees pour les ecarts residuels (relance fournisseur,
  recherche de piece manquante, correction d'ecriture comptable)
- Comptes SYSCOHADA concernes : 401 Fournisseurs, 521 Banque
