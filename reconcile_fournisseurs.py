#!/usr/bin/env python3
"""
reconcile_fournisseurs.py
--------------------------
Rapprochement inter-comptes fournisseurs -- SYSCOHADA Revise 2017
Implemente la methodologie TCJ ameliore (Tableau de Comparaison des Journaux
ameliore) pour le rapprochement multi-passes des comptes fournisseurs.
Compare deux grand livres fournisseurs (GL1 vs GL2) et produit un Excel structure.

Methodologie TCJ ameliore :
  - Passe 1 : Ref + Montant + Date exacte       (confiance : Parfaite)
  - Passe 2 : Ref + Montant + Date +/-3j        (confiance : Tres haute)
  - Passe 3 : Montant + Date +/-5j + Libelle    (confiance : Haute)
  - Passe 4 : Montant + Reference partielle     (confiance : Bonne)
  - Passe 5 : Montant +/-1 + Libelle similaire  (confiance : Acceptable)

Usage:
    python reconcile_fournisseurs.py \
        --gl1 gl_interne.xlsx \
        --gl2 releve_fournisseur.xlsx \
        --output Rapprochement_Fournisseur.xlsx \
        [--fournisseur "NOM"] \
        [--inverser-sens] \
        [--seuil-similarite 0.3] \
        [--devise FCFA] \
        [--gl1-label "GL Interne"] \
        [--gl2-label "Releve Fournisseur"]
"""
import argparse
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
# --- Couleurs -----------------------------------------------------------------
CLR_HEADER_FILL = "1F3864"  # bleu marine
CLR_HEADER_FONT = "FFFFFF"  # blanc
CLR_ECART_GL1   = "FFD966"  # orange    -- absent dans GL2
CLR_ECART_GL2   = "FF9999"  # rouge     -- absent dans GL1
CLR_MATCH       = "C6EFCE"  # vert      -- rapprochees
CLR_MATCH_FONT  = "276221"  # vert fonce
CLR_ALT_ROW     = "F2F2F2"  # gris clair
PASSE_COLORS = {1: "70AD47", 2: "A9D18E", 3: "FFD966", 4: "F4B942", 5: "FF7F50"}
# --- Aliases colonnes ---------------------------------------------------------
DATE_ALIASES   = ["date", "dat", "dt", "date_op", "date_operation", "date_ecriture",
                  "date_piece", "dateop", "date_compta"]
REF_ALIASES    = ["reference", "ref", "n_piece", "num_piece", "piece", "no_piece",
                  "numero", "nopièce", "n_facture", "facture", "num_fact", "numfact",
                  "invoice", "ref_piece", "n_facture", "num_fact"]
LIB_ALIASES    = ["libelle", "libellé", "designation", "description", "motif",
                  "label", "intitule", "detail", "observation"]
DEBIT_ALIASES  = ["debit", "débit", "deb", "dbt", "montant_debit", "sortie",
                  "decaissement", "credit_gl"]
CREDIT_ALIASES = ["credit", "crédit", "cred", "crt", "montant_credit", "entree",
                  "encaissement", "debit_gl"]
MONTANT_ALIASES = ["montant", "amount", "valeur", "somme", "montant_ht", "total"]
SOLDE_ALIASES  = ["solde", "balance", "cumul", "running_balance"]
MOTS_GENERIQUES = {
    "VIREMENT", "PAIEMENT", "FACTURE", "FAC", "REGLEMENT", "REG", "AVOIR",
    "ACOMPTE", "SOLDE", "REPORT", "DE", "DU", "LA", "LE", "LES", "ET", "EN",
    "AU", "AUX", "PAR", "POUR", "SUR", "DANS", "AVEC", "A", "D", "L",
}
# --- Utilitaires --------------------------------------------------------------
def _norm_col(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", s.lower().strip())
def detect_column(df: pd.DataFrame, aliases: list) -> str:
    normed = {_norm_col(c): c for c in df.columns}
    for alias in aliases:
        key = _norm_col(alias)
        if key in normed:
            return normed[key]
    return None
def _clean_amount(s) -> float:
    if pd.isna(s):
        return 0.0
    s2 = str(s).replace("\xa0", "").replace(" ", "").replace(",", ".").replace("FCFA", "")
    try:
        return float(s2)
    except ValueError:
        return 0.0
def extract_columns(df: pd.DataFrame, label: str) -> pd.DataFrame:
    col_date  = detect_column(df, DATE_ALIASES)
    col_ref   = detect_column(df, REF_ALIASES)
    col_lib   = detect_column(df, LIB_ALIASES)
    col_deb   = detect_column(df, DEBIT_ALIASES)
    col_cred  = detect_column(df, CREDIT_ALIASES)
    col_mont  = detect_column(df, MONTANT_ALIASES)
    col_solde = detect_column(df, SOLDE_ALIASES)
    print(f"\n[{label}] Colonnes detectees :")
    print(f"  Date:{col_date}  Ref:{col_ref}  Lib:{col_lib}")
    print(f"  Debit:{col_deb}  Credit:{col_cred}  Montant:{col_mont}  Solde:{col_solde}")
    result = pd.DataFrame(index=df.index)
    result["date"]      = pd.to_datetime(df[col_date], dayfirst=True, errors="coerce") if col_date else pd.NaT
    result["reference"] = df[col_ref].astype(str).str.strip() if col_ref else ""
    result["libelle"]   = df[col_lib].astype(str).str.strip() if col_lib else ""
    if col_deb and col_cred:
        result["debit"]          = df[col_deb].apply(_clean_amount)
        result["credit"]         = df[col_cred].apply(_clean_amount)
        result["montant_signe"]  = result["credit"] - result["debit"]
    elif col_mont:
        result["montant_signe"]  = df[col_mont].apply(_clean_amount)
        result["debit"]  = result["montant_signe"].apply(lambda x: abs(x) if x < 0 else 0.0)
        result["credit"] = result["montant_signe"].apply(lambda x: x if x >= 0 else 0.0)
    else:
        result["debit"] = result["credit"] = result["montant_signe"] = 0.0
    result["solde"] = df[col_solde].apply(_clean_amount) if col_solde else 0.0
    result = result[result["montant_signe"].abs() > 0].copy()
    result["_matched"] = False
    result["_passe"]   = 0
    print(f"  => {len(result)} lignes significatives")
    return result.reset_index(drop=True)
def load_file(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Fichier introuvable : {path}")
    ext = p.suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(path, dtype=str)
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
                    headers = [str(c).strip() if c else f"col_{i}" for i, c in enumerate(table[0])]
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
    return r1c == r2c or r1c in r2c or r2c in r1c or (len(r1c) >= 4 and r1c[:4] == r2c[:4])
def _dates_proches(d1, d2, jours: int) -> bool:
    if pd.isna(d1) or pd.isna(d2):
        return False
    return abs((d1 - d2).days) <= jours
def _montants_ok(m1: float, m2: float, tol: float = 1.0) -> bool:
    return abs(abs(m1) - abs(m2)) <= tol
# --- Moteur de rapprochement --------------------------------------------------
def rapprocher(df1: pd.DataFrame, df2: pd.DataFrame, seuil: float):
    matches = []
    def try_match(i1, i2, passe):
        if df1.at[i1, "_matched"] or df2.at[i2, "_matched"]:
            return False
        df1.at[i1, "_matched"] = True
        df1.at[i1, "_passe"]   = passe
        df2.at[i2, "_matched"] = True
        df2.at[i2, "_passe"]   = passe
        matches.append({
            "passe":       passe,
            "date_gl1":    df1.at[i1, "date"],
            "ref_gl1":     df1.at[i1, "reference"],
            "libelle_gl1": df1.at[i1, "libelle"],
            "debit_gl1":   df1.at[i1, "debit"],
            "credit_gl1":  df1.at[i1, "credit"],
            "date_gl2":    df2.at[i2, "date"],
            "ref_gl2":     df2.at[i2, "reference"],
            "libelle_gl2": df2.at[i2, "libelle"],
            "debit_gl2":   df2.at[i2, "debit"],
            "credit_gl2":  df2.at[i2, "credit"],
        })
        return True
    idx1 = list(df1.index)
    idx2 = list(df2.index)
    print("\n[PASSE 1] Reference + Montant + Date exacte ...")
    for i1 in idx1:
        for i2 in idx2:
            if (not df1.at[i1, "_matched"] and not df2.at[i2, "_matched"]
                    and _montants_ok(df1.at[i1, "montant_signe"], df2.at[i2, "montant_signe"])
                    and _refs_communes(df1.at[i1, "reference"], df2.at[i2, "reference"])
                    and _dates_proches(df1.at[i1, "date"], df2.at[i2, "date"], 0)):
                try_match(i1, i2, 1)
    print("[PASSE 2] Reference + Montant + Date +/-3j ...")
    for i1 in idx1:
        for i2 in idx2:
            if (not df1.at[i1, "_matched"] and not df2.at[i2, "_matched"]
                    and _montants_ok(df1.at[i1, "montant_signe"], df2.at[i2, "montant_signe"])
                    and _refs_communes(df1.at[i1, "reference"], df2.at[i2, "reference"])
                    and _dates_proches(df1.at[i1, "date"], df2.at[i2, "date"], 3)):
                try_match(i1, i2, 2)
    print("[PASSE 3] Montant + Date +/-5j + Libelle similaire ...")
    for i1 in idx1:
        for i2 in idx2:
            if (not df1.at[i1, "_matched"] and not df2.at[i2, "_matched"]
                    and _montants_ok(df1.at[i1, "montant_signe"], df2.at[i2, "montant_signe"])
                    and _dates_proches(df1.at[i1, "date"], df2.at[i2, "date"], 5)
                    and similarite(df1.at[i1, "libelle"], df2.at[i2, "libelle"]) >= seuil):
                try_match(i1, i2, 3)
    print("[PASSE 4] Montant + Reference partielle (sans date) ...")
    for i1 in idx1:
        for i2 in idx2:
            if (not df1.at[i1, "_matched"] and not df2.at[i2, "_matched"]
                    and _montants_ok(df1.at[i1, "montant_signe"], df2.at[i2, "montant_signe"])
                    and _refs_communes(df1.at[i1, "reference"], df2.at[i2, "reference"])):
                try_match(i1, i2, 4)
    print("[PASSE 5] Montant +/-1 FCFA + Libelle similaire ...")
    for i1 in idx1:
        for i2 in idx2:
            if (not df1.at[i1, "_matched"] and not df2.at[i2, "_matched"]
                    and _montants_ok(df1.at[i1, "montant_signe"], df2.at[i2, "montant_signe"], 1.0)
                    and similarite(df1.at[i1, "libelle"], df2.at[i2, "libelle"]) >= seuil):
                try_match(i1, i2, 5)
    df_m  = pd.DataFrame(matches)
    df_e1 = df1[~df1["_matched"]].copy()
    df_e2 = df2[~df2["_matched"]].copy()
    return df_m, df_e1, df_e2
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
def fmt_date(d):
    if pd.notna(d):
        try:
            return pd.Timestamp(d).strftime("%d/%m/%Y")
        except Exception:
            return str(d)
    return ""
# --- Onglets Excel ------------------------------------------------------------
def sheet_ecarts(ws, df, fill_color, devise):
    write_headers(ws, ["Date", "Reference", "Libelle", "Debit", "Credit", "Solde"])
    ws.freeze_panes = "A2"
    for i, (_, row) in enumerate(df.iterrows(), 2):
        write_row(ws, i, [
            fmt_date(row["date"]),
            row["reference"] if row["reference"] != "nan" else "",
            row["libelle"],
            row["debit"] or None,
            row["credit"] or None,
            row["solde"] or None,
        ], fill_color=fill_color, money_cols=[4, 5, 6], devise=devise)
    auto_width(ws)
def sheet_rapprochees(ws, df, devise):
    if df.empty:
        ws["A1"] = "Aucune transaction rapprochee."
        return
    headers = ["Passe", "Confiance",
               "Date GL1", "Ref GL1", "Libelle GL1", "Debit GL1", "Credit GL1",
               "Date GL2", "Ref GL2", "Libelle GL2", "Debit GL2", "Credit GL2"]
    write_headers(ws, headers)
    ws.freeze_panes = "A2"
    conf = {1: "Parfaite", 2: "Tres haute", 3: "Haute", 4: "Bonne", 5: "Acceptable"}
    for i, (_, row) in enumerate(df.iterrows(), 2):
        passe = int(row.get("passe", 0))
        write_row(ws, i, [
            f"Passe {passe}", conf.get(passe, "?"),
            fmt_date(row.get("date_gl1")), row.get("ref_gl1", ""), row.get("libelle_gl1", ""),
            row.get("debit_gl1"), row.get("credit_gl1"),
            fmt_date(row.get("date_gl2")), row.get("ref_gl2", ""), row.get("libelle_gl2", ""),
            row.get("debit_gl2"), row.get("credit_gl2"),
        ], fill_color=PASSE_COLORS.get(passe, CLR_MATCH), money_cols=[6, 7, 11, 12], devise=devise)
    auto_width(ws)
def sheet_recapitulatif(ws, df1, df2, df_m, df_e1, df_e2,
                         fournisseur, devise, lbl1, lbl2):
    ws.merge_cells("A1:D1")
    t = ws["A1"]
    t.value     = f"RAPPROCHEMENT FOURNISSEUR -- {fournisseur.upper()}"
    t.font      = _font(bold=True, color=CLR_HEADER_FONT, size=14)
    t.fill      = _fill(CLR_HEADER_FILL)
    t.alignment = _center()
    ws.row_dimensions[1].height = 30
    ws["A2"] = f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].font = _font(size=9, color="666666")
    ws["A3"] = "Methodologie : TCJ ameliore (Tableau de Comparaison des Journaux)"
    ws["A3"].font = _font(size=9, color="666666", bold=True)
    def kv(r, k, v, vc="000000"):
        ws.cell(row=r, column=1, value=k).font = _font(bold=True)
        c = ws.cell(row=r, column=2, value=v)
        c.font = _font(color=vc)
    solde1 = df1["montant_signe"].sum()
    solde2 = df2["montant_signe"].sum()
    ecart  = solde1 - solde2
    ws["A4"] = "SOLDES"
    ws["A4"].font = _font(bold=True, color=CLR_HEADER_FILL)
    kv(5, f"Solde {lbl1}", round(solde1, 0))
    kv(6, f"Solde {lbl2}", round(solde2, 0))
    ecart_ok = abs(ecart) <= 1
    kv(7, "Ecart de solde (GL1 - GL2)", round(ecart, 0), "276221" if ecart_ok else "C00000")
    for r in [5, 6, 7]:
        ws.cell(row=r, column=2).number_format = _money(devise)
    ws.cell(row=7, column=2).fill = _fill("C6EFCE" if ecart_ok else "FFCCCC")
    ws["A9"] = "RAPPROCHEMENT"
    ws["A9"].font = _font(bold=True, color=CLR_HEADER_FILL)
    total = len(df1)
    n_m   = len(df_m)
    kv(10, "Transactions GL1 (total)",    total)
    kv(11, "Transactions rapprochees",    n_m)
    kv(12, "Taux de rapprochement",       f"{round(n_m/total*100,1) if total else 0} %")
    kv(13, f"Ecarts GL1 (absent dans {lbl2})", len(df_e1))
    kv(14, f"Ecarts GL2 (absent dans {lbl1})", len(df_e2))
    ws["A16"] = "DETAIL PAR PASSE"
    ws["A16"].font = _font(bold=True, color=CLR_HEADER_FILL)
    passe_labels = {
        1: "Passe 1 -- Ref + Montant + Date exacte",
        2: "Passe 2 -- Ref + Montant + Date +/-3j",
        3: "Passe 3 -- Montant + Date +/-5j + Libelle",
        4: "Passe 4 -- Montant + Ref partielle",
        5: "Passe 5 -- Montant +/-1 FCFA + Libelle",
    }
    r = 17
    if not df_m.empty:
        for passe, label in passe_labels.items():
            cnt = len(df_m[df_m["passe"] == passe])
            if cnt > 0:
                kv(r, label, cnt)
                r += 1
    ws["A" + str(r+1)] = "MONTANT DES ECARTS"
    ws["A" + str(r+1)].font = _font(bold=True, color=CLR_HEADER_FILL)
    kv(r+2, f"Montant ecarts {lbl1}", round(df_e1["montant_signe"].sum(), 0))
    kv(r+3, f"Montant ecarts {lbl2}", round(df_e2["montant_signe"].sum(), 0))
    for rr in [r+2, r+3]:
        ws.cell(row=rr, column=2).number_format = _money(devise)
    ws.column_dimensions["A"].width = 45
    ws.column_dimensions["B"].width = 20
def sheet_detail(ws, df_e1, df_e2, lbl1, lbl2, devise):
    headers = [
        f"Date {lbl1}", f"Ref {lbl1}", f"Libelle {lbl1}", f"Debit {lbl1}", f"Credit {lbl1}",
        "",
        f"Date {lbl2}", f"Ref {lbl2}", f"Libelle {lbl2}", f"Debit {lbl2}", f"Credit {lbl2}",
    ]
    write_headers(ws, headers)
    ws.freeze_panes = "A2"
    r1 = df_e1.reset_index(drop=True)
    r2 = df_e2.reset_index(drop=True)
    for i in range(max(len(r1), len(r2))):
        row = []
        if i < len(r1):
            rr = r1.iloc[i]
            row.extend([fmt_date(rr["date"]),
                        rr["reference"] if rr["reference"] != "nan" else "",
                        rr["libelle"], rr["debit"] or None, rr["credit"] or None])
        else:
            row.extend(["", "", "", None, None])
        row.append("")
        if i < len(r2):
            rr = r2.iloc[i]
            row.extend([fmt_date(rr["date"]),
                        rr["reference"] if rr["reference"] != "nan" else "",
                        rr["libelle"], rr["debit"] or None, rr["credit"] or None])
        else:
            row.extend(["", "", "", None, None])
        ridx = i + 2
        for col, val in enumerate(row, 1):
            c = ws.cell(row=ridx, column=col, value=val)
            c.border    = _border()
            c.alignment = Alignment(vertical="center")
            c.font      = _font()
            if col <= 5 and i < len(r1):
                c.fill = _fill(CLR_ECART_GL1)
            elif col >= 7 and i < len(r2):
                c.fill = _fill(CLR_ECART_GL2)
            if col in [4, 5, 9, 10] and isinstance(val, (int, float)):
                c.number_format = _money(devise)
    auto_width(ws)
# --- Main ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gl1",   required=True)
    parser.add_argument("--gl2",   required=True)
    parser.add_argument("--output",  default="Rapprochement_Fournisseur.xlsx")
    parser.add_argument("--fournisseur", default="FOURNISSEUR")
    parser.add_argument("--inverser-sens", action="store_true")
    parser.add_argument("--seuil-similarite", type=float, default=0.3)
    parser.add_argument("--devise", default="FCFA")
    parser.add_argument("--gl1-label", default="GL Interne")
    parser.add_argument("--gl2-label", default="Releve Fournisseur")
    args = parser.parse_args()
    print("=" * 60)
    print("  RAPPROCHEMENT INTER-COMPTES FOURNISSEURS")
    print(f"  Fournisseur : {args.fournisseur}")
    print("=" * 60)
    print("\n[1/4] Chargement des fichiers...")
    raw1 = load_file(args.gl1)
    raw2 = load_file(args.gl2)
    print("\n[2/4] Extraction des colonnes...")
    df1 = extract_columns(raw1, args.gl1_label)
    df2 = extract_columns(raw2, args.gl2_label)
    if args.inverser_sens:
        print("\n  Inversion de sens appliquee a GL2")
        df2["montant_signe"] = -df2["montant_signe"]
        df2["debit"],  df2["credit"] = df2["credit"].copy(), df2["debit"].copy()
    print("\n[3/4] Rapprochement multi-passes...")
    df_m, df_e1, df_e2 = rapprocher(df1, df2, args.seuil_similarite)
    n_m, n_t = len(df_m), len(df1)
    print(f"\n  => {n_m}/{n_t} rapprochees | {len(df_e1)} ecarts GL1 | {len(df_e2)} ecarts GL2")
    print(f"\n[4/4] Generation Excel : {args.output}")
    wb = Workbook()
    ws_recap = wb.active
    ws_recap.title = "Recapitulatif"
    sheet_recapitulatif(ws_recap, df1, df2, df_m, df_e1, df_e2,
                        args.fournisseur, args.devise, args.gl1_label, args.gl2_label)
    ws_e1 = wb.create_sheet("Ecarts GL Interne")
    sheet_ecarts(ws_e1, df_e1, CLR_ECART_GL1, args.devise)
    ws_e2 = wb.create_sheet("Ecarts Releve Fournisseur")
    sheet_ecarts(ws_e2, df_e2, CLR_ECART_GL2, args.devise)
    ws_m = wb.create_sheet("Transactions Rapprochees")
    sheet_rapprochees(ws_m, df_m, args.devise)
    ws_d = wb.create_sheet("Detail Ecarts (cote a cote)")
    sheet_detail(ws_d, df_e1, df_e2, args.gl1_label, args.gl2_label, args.devise)
    wb.save(args.output)
    solde1 = df1["montant_signe"].sum()
    solde2 = df2["montant_signe"].sum()
    ecart  = round(solde1 - solde2, 0)
    print("\n" + "=" * 60)
    print("  RESUME")
    print("=" * 60)
    print(f"  Rapprochees : {n_m}/{n_t}  |  Taux : {round(n_m/n_t*100,1) if n_t else 0}%")
    print(f"  Ecarts GL1  : {len(df_e1)}  |  Ecarts GL2 : {len(df_e2)}")
    print(f"  Ecart solde : {ecart:,.0f} {args.devise}")
    if abs(ecart) <= 1:
        print("  OK : Soldes equilibres")
    else:
        print(f"  ATTENTION : Ecart residuel a investiguer")
    print(f"  Fichier : {args.output}")
    print("=" * 60)
if __name__ == "__main__":
    main()
