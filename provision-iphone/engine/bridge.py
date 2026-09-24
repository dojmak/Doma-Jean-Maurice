# -*- coding: utf-8 -*-
"""
bridge.py — passerelle entre la web app iPhone et provision_engine.py (exécuté tel quel dans Pyodide).

Aucun calcul ici : le moteur reste la seule voie de calcul (SKILL.md, séquence étape 3).
La passerelle ne fait que :
  - preview() : relire les entrées via pe.load_input pour l'étape « Confirmer les entrées » (I3) ;
  - run()     : lancer pe.main() avec les mêmes arguments que la ligne de commande, capturer la
                sortie console, les arrêts bloquants (sys.exit / assert) et le fichier produit.
Les deux renvoient du JSON (chaîne) pour éviter les conversions d'objets Python → JS.
"""
import contextlib, io, json, sys, traceback, types
from pathlib import Path

import provision_engine as pe


def _args(retours_sheet=None, cnps_sheet=None):
    return types.SimpleNamespace(retours_sheet=retours_sheet or None, cnps_sheet=cnps_sheet or None)


def _cache_sizes(wbv):
    """Nombre de salariés présents en cache dans les onglets C et R (même lecture que pe.crosscheck).
    0 = cross-check [L-6] non effectué pour cet onglet (le moteur l'ignore silencieusement)."""
    out = {}
    for sheet in ("C", "R"):
        n = set()
        if sheet in wbv.sheetnames:
            ws = wbv[sheet]
            for r in range(7, ws.max_row + 1):
                nom = ws.cell(row=r, column=1).value
                v = ws.cell(row=r, column=12).value
                if isinstance(nom, str) and nom.strip() and isinstance(v, (int, float)):
                    n.add(nom.strip())
        out[sheet] = len(n)
    return out


def preview(path, retours_sheet=None, cnps_sheet=None):
    try:
        data = pe.load_input(path, _args(retours_sheet, cnps_sheet))
    except SystemExit as e:
        return json.dumps({"ok": False, "error": str(e.code)})
    except Exception:
        return json.dumps({"ok": False, "error": traceback.format_exc(limit=3)})
    n_entree = sum(1 for _, m in data["controles"] if m.startswith("Date d'entrée introuvable"))
    return json.dumps({
        "ok": True,
        "arrete": data["arrete"].strftime("%d/%m/%Y"),
        "effectif": len(data["emp"]),
        "taux_at": data["taux_at"],
        "retours": data["retours"],
        "cnps": data["cnps"],
        "onglets": data["wbv"].sheetnames,
        "controles": [[n, m] for n, m in data["controles"]],
        "n_entree_absente": n_entree,
        "cache": _cache_sizes(data["wbv"]),
    }, ensure_ascii=False)


def run(path, outdir, prev_conges=0.0, prev_chsoc=0.0, prev_retraite=0.0, tolerance=1.0,
        retours_sheet=None, cnps_sheet=None):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    for old in Path(outdir).glob("PROVISION_RC_*.xlsx"):
        old.unlink()
    argv = ["provision_engine.py", path, "--out", outdir,
            "--prev-conges", repr(float(prev_conges)),
            "--prev-chsoc-conges", repr(float(prev_chsoc)),
            "--prev-retraite", repr(float(prev_retraite)),
            "--tolerance", repr(float(tolerance))]
    if retours_sheet:
        argv += ["--retours-sheet", retours_sheet]
    if cnps_sheet:
        argv += ["--cnps-sheet", cnps_sheet]
    buf = io.StringIO()
    status, message = "ok", ""
    saved = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf):
            pe.main()
    except SystemExit as e:
        status, message = "stop", str(e.code)
    except AssertionError as e:
        status, message = "stop", f"Assertion bloquante : {e}"
    except Exception:
        status, message = "error", traceback.format_exc(limit=5)
    finally:
        sys.argv = saved
    files = sorted(str(p) for p in Path(outdir).glob("PROVISION_RC_*.xlsx"))
    return json.dumps({"status": status, "message": message, "stdout": buf.getvalue(),
                       "fichier": files[0] if (files and status == "ok") else None},
                      ensure_ascii=False)
