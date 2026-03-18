#!/usr/bin/env python3
"""
rapprochement_bancaire.py
--------------------------
Rapprochement bancaire -- SYSCOHADA Revise 2017
Compare un releve bancaire (RB) et un journal/grand livre comptable (GL),
identifie les transactions rapprochees et non rapprochees, et produit un
fichier Excel structure.

Algorithmes implementes :
  1. Protocole de lettrage multi-passes (5 passes + bonus)
       Passe 1 : Ref + Montant + Date exacte         (Parfaite)
       Passe 2 : Ref + Montant + Date +/-3j           (Tres haute)
       Passe 3 : Montant + Date +/-5j + Libelle       (Haute)
       Passe 4 : Montant exact + Libelle (sans date)  (Bonne)
       Passe 5 : Montant +/-1 FCFA + Libelle          (Acceptable)
       Bonus   : Somme n->1 (max 5 entrees)           (Regroupement)
  2. TCJ Ameliore (Tri Croissant Juxtapose) -- suspens residuels

Regles OHADA / Zone FCFA :
  - Devise : FCFA (XOF/XAF) -- montants entiers
  - Tolerance d'arrondi : +/-1 FCFA
  - Comptes cles SYSCOHADA : 521 Banque, 531 Caisse, 411 Clients,
                              401 Fournisseurs, 631 Frais bancaires

Usage:
    python rapprochement_bancaire.py \
        --banque  releve_bancaire.xlsx \
        --compta  journal_comptable.xlsx \
        --output  Rapprochement_Bancaire_AAAA-MM.xlsx \
        [--seuil-similarite 0.3] \
        [--tcj-lookahead 4] \
        [--col-montant-banque "Montant"] \
        [--no-memory] \
        [--devise FCFA] \
        [--mois "2024-01"]
"""
import argparse
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# --- Couleurs -----------------------------------------------------------------
CLR_HEADER_FILL  = "1F3864"   # bleu marine
CLR_HEADER_FONT  = "FFFFFF"   # blanc
CLR_ECART_RB     = "FFD966"   # orange  -- absent dans GL
CLR_ECART_GL     = "FF9999"   # rouge   -- absent dans RB
CLR_MATCH        = "C6EFCE"   # vert    -- rapprochees
CLR_MATCH_FONT   = "276221"   # vert fonce
CLR_ALT_ROW      = "F2F2F2"   # gris clair
CLR_BONUS        = "BDD7EE"   # bleu clair -- regroupement bonus
CLR_TCJ          = "E2EFDA"   # vert pale  -- TCJ
CLR_WARN         = "FFCCCC"   # rouge pale -- ecart non nul

PASSE_COLORS = {
    1: "70AD47",   # vert vif
    2: "A9D18E",   # vert moyen
    3: "FFD966",   # jaune
    4: "F4B942",   # orange clair
    5: "FF7F50",   # corail
    6: "BDD7EE",   # bleu clair (bonus regroupement)
}

# --- Aliases colonnes ---------------------------------------------------------
DATE_ALIASES   = ["date", "dat", "dt", "date_op", "date_operation", "date_valeur",
                  "date_ecriture", "date_piece", "dateop", "date_compta", "value_date",
                  "transaction_date"]
REF_ALIASES    = ["reference", "ref", "n_piece", "num_piece", "piece", "no_piece",
                  "numero", "n_facture", "facture", "num_fact", "invoice",
                  "ref_piece", "transaction_id", "id", "cheque", "virement"]
LIB_ALIASES    = ["libelle", "libelle", "designation", "description", "motif",
                  "label", "intitule", "detail", "observation", "wording",
                  "narrative", "details"]
DEBIT_ALIASES  = ["debit", "debit", "deb", "dbt", "montant_debit", "sortie",
                  "decaissement", "withdrawal", "debit_amount", "amount_debit"]
CREDIT_ALIASES = ["credit", "credit", "cred", "crt", "montant_credit", "entree",
                  "encaissement", "deposit", "credit_amount", "amount_credit"]
MONTANT_ALIASES = ["montant", "amount", "valeur", "somme", "montant_ht", "total",
                   "net_amount", "transaction_amount"]
SOLDE_ALIASES  = ["solde", "balance", "cumul", "running_balance", "solde_cumule"]
COMPTE_ALIASES = ["compte", "account", "n_compte", "num_compte", "compte_gl",
                  "code_compte", "gl_account"]
JOURNAL_ALIASES = ["journal", "code_journal", "journal_code", "jnl"]

MOTS_GENERIQUES = {
    "VIREMENT", "PAIEMENT", "FACTURE", "FAC", "REGLEMENT", "REG", "AVOIR",
    "ACOMPTE", "SOLDE", "REPORT", "DE", "DU", "LA", "LE", "LES", "ET", "EN",
    "AU", "AUX", "PAR", "POUR", "SUR", "DANS", "AVEC", "A", "D", "L",
    "BANQUE", "CREDIT", "DEBIT", "FRAIS", "COMMISSION", "VIR", "CHQ",
    "CHEQUE", "PRELEVEMENT", "CB", "TPE",
}

# --- Utilitaires --------------------------------------------------------------
def _norm_col(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", s.lower().strip())

def detect_column(df: pd.DataFrame, aliases: list, override: str = None) -> str:
    if override:
        if override in df.columns:
            return override
        normed = {_norm_col(c): c for c in df.columns}
        key = _norm_col(override)
        if key in normed:
            return normed[key]
    normed = {_norm_col(c): c for c in df.columns}
    for alias in aliases:
        key = _norm_col(alias)
        if key in normed:
            return normed[key]
    return None

def _clean_amount(s) -> float:
    if pd.isna(s):
        return 0.0
    s2 = (str(s)
          .replace("\xa0", "").replace("\u202f", "").replace(" ", "")
          .replace(",", ".").replace("FCFA", "").replace("XOF", "").replace("XAF", ""))
    try:
        return float(s2)
    except ValueError:
        return 0.0

def extract_columns(df: pd.DataFrame, label: str,
                    col_montant_override: str = None) -> pd.DataFrame:
    col_date   = detect_column(df, DATE_ALIASES)
    col_ref    = detect_column(df, REF_ALIASES)
    col_lib    = detect_column(df, LIB_ALIASES)
    col_deb    = detect_column(df, DEBIT_ALIASES)
    col_cred   = detect_column(df, CREDIT_ALIASES)
    col_mont   = detect_column(df, MONTANT_ALIASES, override=col_montant_override)
    col_solde  = detect_column(df, SOLDE_ALIASES)
    col_compte = detect_column(df, COMPTE_ALIASES)
    col_jnl    = detect_column(df, JOURNAL_ALIASES)

    print(f"\n[{label}] Colonnes detectees :")
    print(f"  Date:{col_date}  Ref:{col_ref}  Lib:{col_lib}")
    print(f"  Debit:{col_deb}  Credit:{col_cred}  Montant:{col_mont}  Solde:{col_solde}")
    print(f"  Compte:{col_compte}  Journal:{col_jnl}")

    result = pd.DataFrame(index=df.index)
    result["date"] = (pd.to_datetime(df[col_date], dayfirst=True, errors="coerce")
                      if col_date else pd.NaT)
    result["reference"] = df[col_ref].astype(str).str.strip() if col_ref else ""
    result["libelle"]   = df[col_lib].astype(str).str.strip() if col_lib else ""
    result["compte"]    = df[col_compte].astype(str).str.strip() if col_compte else ""
    result["journal"]   = df[col_jnl].astype(str).str.strip() if col_jnl else ""

    if col_deb and col_cred:
        result["debit"]         = df[col_deb].apply(_clean_amount)
        result["credit"]        = df[col_cred].apply(_clean_amount)
        result["montant_signe"] = result["credit"] - result["debit"]
    elif col_mont:
        result["montant_signe"] = df[col_mont].apply(_clean_amount)
        result["debit"]  = result["montant_signe"].apply(lambda x: abs(x) if x < 0 else 0.0)
        result["credit"] = result["montant_signe"].apply(lambda x: x if x >= 0 else 0.0)
    else:
        result["debit"] = result["credit"] = result["montant_signe"] = 0.0

    result["solde"] = df[col_solde].apply(_clean_amount) if col_solde else 0.0
    result = result[result["montant_signe"].abs() > 0].copy()
    result["_matched"] = False
    result["_passe"]   = 0
    result["_group"]   = ""   # identifiant de groupe pour le bonus

    print(f"  => {len(result)} lignes significatives")
    return result.reset_index(drop=True)

def load_file(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Fichier introuvable : {path}")
    ext = p.suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(path, dtype=str)
    elif ext == ".csv":
        for sep in [";", ",", "\t", "|"]:
            try:
                df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8-sig")
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
        sys.exit(f"Impossible de parser le CSV : {path}")
    elif ext == ".pdf":
        return _load_pdf(path)
    else:
        sys.exit(f"Format non supporte : {ext}")

def _load_pdf(path: str) -> pd.DataFrame:
    try:
        import pdfplumber
    except ImportError:
        sys.exit("pdfplumber non installe. Lancer : pip install pdfplumber")
    rows, headers = [], None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                if not table:
                    continue
                if headers is None:
                    headers = [str(c).strip() if c else f"col_{i}"
                               for i, c in enumerate(table[0])]
                    data = table[1:]
                else:
                    data = table
                for row in data:
                    rows.append([str(c).strip() if c else "" for c in row])
    if not rows:
        sys.exit(f"Impossible d'extraire des donnees du PDF : {path}")
    return pd.DataFrame(rows, columns=headers[:len(rows[0])])

# --- Algorithme de similarite -------------------------------------------------
def _tokens_cles(s: str) -> set:
    tokens = set(re.findall(r"[A-Z0-9]+", s.upper()))
    return tokens - MOTS_GENERIQUES

def similarite(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta, tb = _tokens_cles(a), _tokens_cles(b)
    if ta and tb:
        inter = ta & tb
        jaccard = len(inter) / len(ta | tb)
    else:
        jaccard = 0.0
    seq = SequenceMatcher(None, a.upper(), b.upper()).ratio()
    return max(jaccard, seq)

def _refs_communes(r1: str, r2: str) -> bool:
    if not r1 or not r2 or r1 in ("nan", "") or r2 in ("nan", ""):
        return False
    r1c = re.sub(r"[^A-Z0-9]", "", r1.upper())
    r2c = re.sub(r"[^A-Z0-9]", "", r2.upper())
    if not r1c or not r2c:
        return False
    return (r1c == r2c
            or r1c in r2c
            or r2c in r1c
            or (len(r1c) >= 4 and r1c[:4] == r2c[:4]))

def _dates_proches(d1, d2, jours: int) -> bool:
    if pd.isna(d1) or pd.isna(d2):
        return False
    return abs((d1 - d2).days) <= jours

def _montants_ok(m1: float, m2: float, tol: float = 1.0) -> bool:
    return abs(abs(m1) - abs(m2)) <= tol

# --- TCJ Ameliore (Tri Croissant Juxtapose) ------------------------------------
def tcj_ameliore(df_rb: pd.DataFrame, df_gl: pd.DataFrame,
                 lookahead: int = 4) -> list:
    """
    TCJ Ameliore : tri les suspens residuels par montant croissant et tente
    de trouver des combinaisons additives d'ecritures qui s'equilibrent.
    Retourne une liste de suggestions de rapprochement.
    """
    rb_unmatched = df_rb[~df_rb["_matched"]].copy().sort_values("montant_signe")
    gl_unmatched = df_gl[~df_gl["_matched"]].copy().sort_values("montant_signe")

    suggestions = []

    # Cas 1 : 1 ecriture RB = n ecritures GL (n <= lookahead)
    for i_rb, row_rb in rb_unmatched.iterrows():
        m_rb = abs(row_rb["montant_signe"])
        candidates = gl_unmatched[
            (~gl_unmatched["_matched"])
            & (gl_unmatched["montant_signe"].apply(lambda x: abs(x)) <= m_rb + 1)
        ]
        for n in range(2, min(lookahead + 1, len(candidates) + 1)):
            for combo in combinations(candidates.index, n):
                total = sum(abs(gl_unmatched.at[j, "montant_signe"]) for j in combo)
                if abs(total - m_rb) <= 1.0:
                    suggestions.append({
                        "type":    f"1 RB -> {n} GL",
                        "rb_idx":  [i_rb],
                        "gl_idx":  list(combo),
                        "montant": m_rb,
                        "ecart":   round(total - m_rb, 0),
                    })
                    break  # une seule combinaison par ligne RB
            else:
                continue
            break

    # Cas 2 : n ecritures RB = 1 ecriture GL (n <= lookahead)
    for i_gl, row_gl in gl_unmatched.iterrows():
        m_gl = abs(row_gl["montant_signe"])
        candidates = rb_unmatched[
            (~rb_unmatched["_matched"])
            & (rb_unmatched["montant_signe"].apply(lambda x: abs(x)) <= m_gl + 1)
        ]
        for n in range(2, min(lookahead + 1, len(candidates) + 1)):
            for combo in combinations(candidates.index, n):
                total = sum(abs(rb_unmatched.at[j, "montant_signe"]) for j in combo)
                if abs(total - m_gl) <= 1.0:
                    suggestions.append({
                        "type":    f"{n} RB -> 1 GL",
                        "rb_idx":  list(combo),
                        "gl_idx":  [i_gl],
                        "montant": m_gl,
                        "ecart":   round(total - m_gl, 0),
                    })
                    break
            else:
                continue
            break

    return suggestions

# --- Moteur de rapprochement multi-passes ------------------------------------
def rapprocher(df_rb: pd.DataFrame, df_gl: pd.DataFrame,
               seuil: float, tcj_lookahead: int):
    matches  = []
    group_id = [0]

    def try_match(i_rb, i_gl, passe, rb_indices=None, gl_indices=None):
        """Appariement simple (1:1) ou groupe (n:1 ou 1:n)."""
        rb_list = rb_indices if rb_indices else [i_rb]
        gl_list = gl_indices if gl_indices else [i_gl]
        if any(df_rb.at[i, "_matched"] for i in rb_list):
            return False
        if any(df_gl.at[i, "_matched"] for i in gl_list):
            return False
        group_id[0] += 1
        gid = f"G{group_id[0]:04d}"
        for i in rb_list:
            df_rb.at[i, "_matched"] = True
            df_rb.at[i, "_passe"]   = passe
            df_rb.at[i, "_group"]   = gid
        for i in gl_list:
            df_gl.at[i, "_matched"] = True
            df_gl.at[i, "_passe"]   = passe
            df_gl.at[i, "_group"]   = gid
        # Pour l'affichage, on produit autant de lignes que max(rb, gl)
        for k in range(max(len(rb_list), len(gl_list))):
            i_rb_k = rb_list[k] if k < len(rb_list) else None
            i_gl_k = gl_list[k] if k < len(gl_list) else None
            matches.append({
                "passe":      passe,
                "groupe":     gid,
                "date_rb":    df_rb.at[i_rb_k, "date"]      if i_rb_k is not None else pd.NaT,
                "ref_rb":     df_rb.at[i_rb_k, "reference"] if i_rb_k is not None else "",
                "libelle_rb": df_rb.at[i_rb_k, "libelle"]   if i_rb_k is not None else "",
                "debit_rb":   df_rb.at[i_rb_k, "debit"]     if i_rb_k is not None else None,
                "credit_rb":  df_rb.at[i_rb_k, "credit"]    if i_rb_k is not None else None,
                "date_gl":    df_gl.at[i_gl_k, "date"]      if i_gl_k is not None else pd.NaT,
                "ref_gl":     df_gl.at[i_gl_k, "reference"] if i_gl_k is not None else "",
                "libelle_gl": df_gl.at[i_gl_k, "libelle"]   if i_gl_k is not None else "",
                "debit_gl":   df_gl.at[i_gl_k, "debit"]     if i_gl_k is not None else None,
                "credit_gl":  df_gl.at[i_gl_k, "credit"]    if i_gl_k is not None else None,
                "compte_gl":  df_gl.at[i_gl_k, "compte"]    if i_gl_k is not None else "",
            })
        return True

    idx_rb = list(df_rb.index)
    idx_gl = list(df_gl.index)

    print("\n[PASSE 1] Reference + Montant + Date exacte ...")
    for i in idx_rb:
        for j in idx_gl:
            if (not df_rb.at[i, "_matched"] and not df_gl.at[j, "_matched"]
                    and _montants_ok(df_rb.at[i, "montant_signe"], df_gl.at[j, "montant_signe"])
                    and _refs_communes(df_rb.at[i, "reference"], df_gl.at[j, "reference"])
                    and _dates_proches(df_rb.at[i, "date"], df_gl.at[j, "date"], 0)):
                try_match(i, j, 1)

    print("[PASSE 2] Reference + Montant + Date +/-3j ...")
    for i in idx_rb:
        for j in idx_gl:
            if (not df_rb.at[i, "_matched"] and not df_gl.at[j, "_matched"]
                    and _montants_ok(df_rb.at[i, "montant_signe"], df_gl.at[j, "montant_signe"])
                    and _refs_communes(df_rb.at[i, "reference"], df_gl.at[j, "reference"])
                    and _dates_proches(df_rb.at[i, "date"], df_gl.at[j, "date"], 3)):
                try_match(i, j, 2)

    print("[PASSE 3] Montant + Date +/-5j + Libelle similaire ...")
    for i in idx_rb:
        for j in idx_gl:
            if (not df_rb.at[i, "_matched"] and not df_gl.at[j, "_matched"]
                    and _montants_ok(df_rb.at[i, "montant_signe"], df_gl.at[j, "montant_signe"])
                    and _dates_proches(df_rb.at[i, "date"], df_gl.at[j, "date"], 5)
                    and similarite(df_rb.at[i, "libelle"], df_gl.at[j, "libelle"]) >= seuil):
                try_match(i, j, 3)

    print("[PASSE 4] Montant exact + Libelle similaire (sans date) ...")
    for i in idx_rb:
        for j in idx_gl:
            if (not df_rb.at[i, "_matched"] and not df_gl.at[j, "_matched"]
                    and _montants_ok(df_rb.at[i, "montant_signe"], df_gl.at[j, "montant_signe"], 0)
                    and similarite(df_rb.at[i, "libelle"], df_gl.at[j, "libelle"]) >= seuil):
                try_match(i, j, 4)

    print("[PASSE 5] Montant +/-1 FCFA + Libelle similaire ...")
    for i in idx_rb:
        for j in idx_gl:
            if (not df_rb.at[i, "_matched"] and not df_gl.at[j, "_matched"]
                    and _montants_ok(df_rb.at[i, "montant_signe"], df_gl.at[j, "montant_signe"], 1.0)
                    and similarite(df_rb.at[i, "libelle"], df_gl.at[j, "libelle"]) >= seuil):
                try_match(i, j, 5)

    print("[BONUS] Regroupement somme n->1 (max 5 entrees) ...")
    # Cherche les cas ou n ecritures d'un cote = 1 ecriture de l'autre
    for i in idx_rb:
        if df_rb.at[i, "_matched"]:
            continue
        m_rb = abs(df_rb.at[i, "montant_signe"])
        cands = [j for j in idx_gl if not df_gl.at[j, "_matched"]
                 and abs(df_gl.at[j, "montant_signe"]) <= m_rb + 1]
        for n in range(2, min(6, len(cands) + 1)):
            matched = False
            for combo in combinations(cands, n):
                total = sum(abs(df_gl.at[j, "montant_signe"]) for j in combo)
                if abs(total - m_rb) <= 1.0:
                    try_match(None, None, 6, rb_indices=[i], gl_indices=list(combo))
                    matched = True
                    break
            if matched:
                break

    for j in idx_gl:
        if df_gl.at[j, "_matched"]:
            continue
        m_gl = abs(df_gl.at[j, "montant_signe"])
        cands = [i for i in idx_rb if not df_rb.at[i, "_matched"]
                 and abs(df_rb.at[i, "montant_signe"]) <= m_gl + 1]
        for n in range(2, min(6, len(cands) + 1)):
            matched = False
            for combo in combinations(cands, n):
                total = sum(abs(df_rb.at[i, "montant_signe"]) for i in combo)
                if abs(total - m_gl) <= 1.0:
                    try_match(None, None, 6, rb_indices=list(combo), gl_indices=[j])
                    matched = True
                    break
            if matched:
                break

    df_m  = pd.DataFrame(matches)
    df_e_rb = df_rb[~df_rb["_matched"]].copy()
    df_e_gl = df_gl[~df_gl["_matched"]].copy()

    # TCJ Ameliore sur les suspens residuels
    print("[TCJ AMELIORE] Analyse des suspens residuels ...")
    tcj_suggestions = tcj_ameliore(df_rb, df_gl, lookahead=tcj_lookahead)
    print(f"  => {len(tcj_suggestions)} suggestion(s) TCJ")

    return df_m, df_e_rb, df_e_gl, tcj_suggestions

# --- Mise en forme Excel ------------------------------------------------------
def _fill(color: str) -> PatternFill:
    return PatternFill("solid", fgColor=color)

def _font(bold=False, color="000000", size=10) -> Font:
    return Font(name="Arial", bold=bold, color=color, size=size)

def _border() -> Border:
    s = Side(style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def _center() -> Alignment:
    return Alignment(horizontal="center", vertical="center")

def _money(devise: str) -> str:
    return f'#,##0 "{devise}";[Red]-#,##0 "{devise}"'

def fmt_date(d):
    if pd.notna(d):
        try:
            return pd.Timestamp(d).strftime("%d/%m/%Y")
        except Exception:
            return str(d)
    return ""

def write_headers(ws, headers, fill_color=CLR_HEADER_FILL):
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font      = _font(bold=True, color=CLR_HEADER_FONT)
        c.fill      = _fill(fill_color)
        c.alignment = _center()
        c.border    = _border()
    ws.row_dimensions[1].height = 20

def write_row(ws, row_idx, values, fill_color=None, font_color="000000",
              money_cols=None, devise="FCFA"):
    fc = _fill(fill_color) if fill_color else (
        _fill(CLR_ALT_ROW) if row_idx % 2 == 0 else None
    )
    money_cols = money_cols or []
    for col, val in enumerate(values, 1):
        c = ws.cell(row=row_idx, column=col, value=val)
        if fc:
            c.fill = fc
        c.font      = _font(color=font_color)
        c.border    = _border()
        c.alignment = Alignment(vertical="center")
        if col in money_cols and isinstance(val, (int, float)):
            c.number_format = _money(devise)

def auto_width(ws):
    for col in ws.columns:
        max_len = 0
        ltr = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[ltr].width = min(max_len + 4, 50)

# --- Onglets Excel ------------------------------------------------------------
def sheet_recapitulatif(ws, df_rb, df_gl, df_m, df_e_rb, df_e_gl,
                         mois, devise, tcj_suggestions):
    ws.merge_cells("A1:D1")
    t = ws["A1"]
    t.value     = f"RAPPROCHEMENT BANCAIRE -- {mois.upper()}"
    t.font      = _font(bold=True, color=CLR_HEADER_FONT, size=14)
    t.fill      = _fill(CLR_HEADER_FILL)
    t.alignment = _center()
    ws.row_dimensions[1].height = 30

    ws["A2"] = f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].font = _font(size=9, color="666666")
    ws["A3"] = "Methodologie : Protocole de lettrage multi-passes + TCJ Ameliore (SYSCOHADA Revise 2017)"
    ws["A3"].font = _font(size=9, color="666666", bold=True)

    def kv(r, k, v, vc="000000"):
        ws.cell(row=r, column=1, value=k).font = _font(bold=True)
        c = ws.cell(row=r, column=2, value=v)
        c.font = _font(color=vc)

    solde_rb = df_rb["montant_signe"].sum()
    solde_gl = df_gl["montant_signe"].sum()
    ecart    = solde_rb - solde_gl
    ecart_ok = abs(ecart) <= 1

    ws["A5"] = "SOLDES"
    ws["A5"].font = _font(bold=True, color=CLR_HEADER_FILL)
    kv(6, "Solde Releve Bancaire",     round(solde_rb, 0))
    kv(7, "Solde Grand Livre (521)",   round(solde_gl, 0))
    kv(8, "Ecart (RB - GL)",           round(ecart, 0), "276221" if ecart_ok else "C00000")
    for r in [6, 7, 8]:
        ws.cell(row=r, column=2).number_format = _money(devise)
    ws.cell(row=8, column=2).fill = _fill("C6EFCE" if ecart_ok else CLR_WARN)

    ws["A10"] = "RAPPROCHEMENT"
    ws["A10"].font = _font(bold=True, color=CLR_HEADER_FILL)
    total = len(df_rb)
    n_m   = len(df_m["groupe"].unique()) if not df_m.empty and "groupe" in df_m.columns else 0
    # nombre de lignes RB rapprochees
    n_rb_matched = df_rb["_matched"].sum()
    kv(11, "Lignes Releve Bancaire (total)",  total)
    kv(12, "Lignes rapprochees (RB)",         int(n_rb_matched))
    kv(13, "Taux de rapprochement",
       f"{round(n_rb_matched/total*100, 1) if total else 0} %")
    kv(14, "Suspens RB (absent dans GL)",     len(df_e_rb))
    kv(15, "Suspens GL (absent dans RB)",     len(df_e_gl))
    kv(16, "Suggestions TCJ Ameliore",        len(tcj_suggestions))

    ws["A18"] = "DETAIL PAR PASSE"
    ws["A18"].font = _font(bold=True, color=CLR_HEADER_FILL)
    passe_labels = {
        1: "Passe 1 -- Ref + Montant + Date exacte",
        2: "Passe 2 -- Ref + Montant + Date +/-3j",
        3: "Passe 3 -- Montant + Date +/-5j + Libelle",
        4: "Passe 4 -- Montant exact + Libelle (sans date)",
        5: "Passe 5 -- Montant +/-1 FCFA + Libelle",
        6: "Bonus  -- Regroupement somme n->1",
    }
    r = 19
    if not df_m.empty and "passe" in df_m.columns:
        for passe, label in passe_labels.items():
            cnt = len(df_m[df_m["passe"] == passe]["groupe"].unique()) \
                  if "groupe" in df_m.columns else len(df_m[df_m["passe"] == passe])
            if cnt > 0:
                kv(r, label, cnt)
                r += 1

    ws[f"A{r+1}"] = "MONTANT DES SUSPENS"
    ws[f"A{r+1}"].font = _font(bold=True, color=CLR_HEADER_FILL)
    kv(r+2, "Montant suspens RB", round(df_e_rb["montant_signe"].sum(), 0))
    kv(r+3, "Montant suspens GL", round(df_e_gl["montant_signe"].sum(), 0))
    for rr in [r+2, r+3]:
        ws.cell(row=rr, column=2).number_format = _money(devise)

    ws["A" + str(r+5)] = "COMPTES SYSCOHADA (Revise 2017)"
    ws["A" + str(r+5)].font = _font(bold=True, color=CLR_HEADER_FILL)
    syscohada_ref = [
        ("521", "Banque -- compte courant"),
        ("531", "Caisse"),
        ("411", "Clients"),
        ("401", "Fournisseurs"),
        ("631", "Services bancaires (frais, commissions)"),
    ]
    for k, (code, lib) in enumerate(syscohada_ref):
        ws.cell(row=r+6+k, column=1, value=code).font = _font(bold=True, color="1F3864")
        ws.cell(row=r+6+k, column=2, value=lib).font  = _font()

    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 22

def sheet_rapprochees(ws, df_m, devise):
    if df_m.empty:
        ws["A1"] = "Aucune transaction rapprochee."
        return
    headers = [
        "Passe", "Confiance", "Groupe",
        "Date RB", "Ref RB", "Libelle RB", "Debit RB", "Credit RB",
        "Date GL", "Ref GL", "Libelle GL", "Debit GL", "Credit GL", "Compte GL",
    ]
    write_headers(ws, headers)
    ws.freeze_panes = "A2"
    conf = {1: "Parfaite", 2: "Tres haute", 3: "Haute",
            4: "Bonne", 5: "Acceptable", 6: "Regroupement"}
    for i, (_, row) in enumerate(df_m.iterrows(), 2):
        passe = int(row.get("passe", 0))
        write_row(ws, i, [
            f"Passe {passe}", conf.get(passe, "?"), row.get("groupe", ""),
            fmt_date(row.get("date_rb")), row.get("ref_rb", ""), row.get("libelle_rb", ""),
            row.get("debit_rb"), row.get("credit_rb"),
            fmt_date(row.get("date_gl")), row.get("ref_gl", ""), row.get("libelle_gl", ""),
            row.get("debit_gl"), row.get("credit_gl"), row.get("compte_gl", ""),
        ], fill_color=PASSE_COLORS.get(passe, CLR_MATCH),
           money_cols=[7, 8, 12, 13], devise=devise)
    auto_width(ws)

def sheet_suspens(ws, df, fill_color, label, devise):
    write_headers(ws, ["Date", "Reference", "Libelle", "Debit", "Credit",
                        "Solde", "Compte", "Journal"])
    ws.freeze_panes = "A2"
    for i, (_, row) in enumerate(df.iterrows(), 2):
        write_row(ws, i, [
            fmt_date(row["date"]),
            row["reference"] if row["reference"] != "nan" else "",
            row["libelle"],
            row["debit"]  or None,
            row["credit"] or None,
            row["solde"]  or None,
            row.get("compte", "") if row.get("compte", "") != "nan" else "",
            row.get("journal", "") if row.get("journal", "") != "nan" else "",
        ], fill_color=fill_color, money_cols=[4, 5, 6], devise=devise)
    auto_width(ws)

def sheet_tcj(ws, df_rb, df_gl, suggestions, devise):
    ws["A1"] = "TCJ AMELIORE -- Tri Croissant Juxtapose -- Suggestions de rapprochement"
    ws["A1"].font = _font(bold=True, color=CLR_HEADER_FONT, size=12)
    ws["A1"].fill = _fill(CLR_HEADER_FILL)
    ws.row_dimensions[1].height = 22

    if not suggestions:
        ws["A2"] = "Aucune suggestion de rapprochement TCJ identifiee."
        ws["A2"].font = _font(color="666666")
        return

    write_headers(ws, ["Type", "Montant RB", "Montant GL", "Ecart",
                        "Libelles RB", "Libelles GL"], fill_color="2E75B6")
    ws.freeze_panes = "A3"

    for i, s in enumerate(suggestions, 3):
        rb_libs = " | ".join(
            str(df_rb.at[j, "libelle"])
            for j in s["rb_idx"] if j in df_rb.index
        )
        gl_libs = " | ".join(
            str(df_gl.at[j, "libelle"])
            for j in s["gl_idx"] if j in df_gl.index
        )
        rb_total = sum(abs(df_rb.at[j, "montant_signe"])
                       for j in s["rb_idx"] if j in df_rb.index)
        gl_total = sum(abs(df_gl.at[j, "montant_signe"])
                       for j in s["gl_idx"] if j in df_gl.index)
        write_row(ws, i, [
            s["type"],
            round(rb_total, 0) or None,
            round(gl_total, 0) or None,
            s["ecart"] or None,
            rb_libs,
            gl_libs,
        ], fill_color=CLR_TCJ, money_cols=[2, 3, 4], devise=devise)
    auto_width(ws)

def sheet_detail_suspens(ws, df_e_rb, df_e_gl, devise):
    """Affichage cote-a-cote des suspens RB et GL."""
    headers = [
        "Date RB", "Ref RB", "Libelle RB", "Debit RB", "Credit RB",
        "",
        "Date GL", "Ref GL", "Libelle GL", "Debit GL", "Credit GL", "Compte GL",
    ]
    write_headers(ws, headers)
    ws.freeze_panes = "A2"

    r1 = df_e_rb.reset_index(drop=True)
    r2 = df_e_gl.reset_index(drop=True)
    for idx in range(max(len(r1), len(r2))):
        row = []
        if idx < len(r1):
            rr = r1.iloc[idx]
            row.extend([fmt_date(rr["date"]),
                        rr["reference"] if rr["reference"] != "nan" else "",
                        rr["libelle"],
                        rr["debit"]  or None,
                        rr["credit"] or None])
        else:
            row.extend(["", "", "", None, None])
        row.append("")
        if idx < len(r2):
            rr = r2.iloc[idx]
            row.extend([fmt_date(rr["date"]),
                        rr["reference"] if rr["reference"] != "nan" else "",
                        rr["libelle"],
                        rr["debit"]  or None,
                        rr["credit"] or None,
                        rr.get("compte", "") if rr.get("compte", "") != "nan" else ""])
        else:
            row.extend(["", "", "", None, None, ""])

        ridx = idx + 2
        for col, val in enumerate(row, 1):
            c = ws.cell(row=ridx, column=col, value=val)
            c.border    = _border()
            c.alignment = Alignment(vertical="center")
            c.font      = _font()
            if col <= 5 and idx < len(r1):
                c.fill = _fill(CLR_ECART_RB)
            elif col >= 7 and idx < len(r2):
                c.fill = _fill(CLR_ECART_GL)
            if col in [4, 5, 10, 11] and isinstance(val, (int, float)):
                c.number_format = _money(devise)
    auto_width(ws)

# --- Main ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Rapprochement bancaire SYSCOHADA Revise 2017"
    )
    parser.add_argument("--banque",  required=True, help="Releve bancaire (.xlsx/.csv/.pdf)")
    parser.add_argument("--compta",  required=True, help="Journal / Grand livre (.xlsx/.csv)")
    parser.add_argument("--output",  default="Rapprochement_Bancaire.xlsx")
    parser.add_argument("--mois",    default=datetime.now().strftime("%Y-%m"))
    parser.add_argument("--seuil-similarite", type=float, default=0.3)
    parser.add_argument("--tcj-lookahead",    type=int,   default=4)
    parser.add_argument("--col-montant-banque", default=None,
                        help="Nom de la colonne montant dans le releve bancaire")
    parser.add_argument("--no-memory", action="store_true",
                        help="Ne pas conserver le fichier de rapprochement precedent")
    parser.add_argument("--devise", default="FCFA")
    args = parser.parse_args()

    print("=" * 60)
    print("  RAPPROCHEMENT BANCAIRE -- SYSCOHADA Revise 2017")
    print(f"  Mois : {args.mois}")
    print(f"  Protocole : lettrage multi-passes + TCJ Ameliore")
    print("=" * 60)

    print("\n[1/4] Chargement des fichiers...")
    raw_rb = load_file(args.banque)
    raw_gl = load_file(args.compta)

    print("\n[2/4] Extraction des colonnes...")
    df_rb = extract_columns(raw_rb, "Releve Bancaire",
                            col_montant_override=args.col_montant_banque)
    df_gl = extract_columns(raw_gl, "Grand Livre")

    print("\n[3/4] Rapprochement multi-passes + TCJ Ameliore...")
    df_m, df_e_rb, df_e_gl, tcj_sugg = rapprocher(
        df_rb, df_gl, args.seuil_similarite, args.tcj_lookahead
    )

    n_rb_matched = df_rb["_matched"].sum()
    n_t          = len(df_rb)
    print(f"\n  => {n_rb_matched}/{n_t} lignes RB rapprochees")
    print(f"     {len(df_e_rb)} suspens RB | {len(df_e_gl)} suspens GL")
    print(f"     {len(tcj_sugg)} suggestion(s) TCJ")

    print(f"\n[4/4] Generation Excel : {args.output}")
    wb = Workbook()

    ws_recap = wb.active
    ws_recap.title = "Recapitulatif"
    sheet_recapitulatif(ws_recap, df_rb, df_gl, df_m, df_e_rb, df_e_gl,
                        args.mois, args.devise, tcj_sugg)

    ws_m = wb.create_sheet("Transactions Rapprochees")
    sheet_rapprochees(ws_m, df_m, args.devise)

    ws_e_rb = wb.create_sheet("Suspens Releve Bancaire")
    sheet_suspens(ws_e_rb, df_e_rb, CLR_ECART_RB, "Releve Bancaire", args.devise)

    ws_e_gl = wb.create_sheet("Suspens Grand Livre")
    sheet_suspens(ws_e_gl, df_e_gl, CLR_ECART_GL, "Grand Livre", args.devise)

    ws_tcj = wb.create_sheet("TCJ Ameliore")
    sheet_tcj(ws_tcj, df_rb, df_gl, tcj_sugg, args.devise)

    ws_d = wb.create_sheet("Detail Suspens (cote a cote)")
    sheet_detail_suspens(ws_d, df_e_rb, df_e_gl, args.devise)

    wb.save(args.output)

    solde_rb = df_rb["montant_signe"].sum()
    solde_gl = df_gl["montant_signe"].sum()
    ecart    = round(solde_rb - solde_gl, 0)

    print("\n" + "=" * 60)
    print("  RESUME")
    print("=" * 60)
    print(f"  Rapprochees  : {n_rb_matched}/{n_t}  |  Taux : "
          f"{round(n_rb_matched/n_t*100, 1) if n_t else 0}%")
    print(f"  Suspens RB   : {len(df_e_rb)}  |  Suspens GL : {len(df_e_gl)}")
    print(f"  Suggestions TCJ : {len(tcj_sugg)}")
    print(f"  Ecart solde  : {ecart:,.0f} {args.devise}")
    if abs(ecart) <= 1:
        print("  OK : Soldes equilibres (regle OHADA +/-1 FCFA)")
    else:
        print("  ATTENTION : Ecart residuel a investiguer")
        print(f"  Comptes a verifier : 521 Banque, 631 Frais bancaires")
    print(f"  Fichier      : {args.output}")
    print("=" * 60)

if __name__ == "__main__":
    main()
