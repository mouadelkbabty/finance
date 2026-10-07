#!/usr/bin/env python3
"""Générateur de CV adaptés, une page, à partir d'un CV de base en JSON.

Usage : python3 cvgen.py cv.json variantes.json dossier_sortie

Le CV de base n'est jamais réécrit : une variante change seulement le titre,
le profil, l'ordre des puces et l'ordre des compétences. Le script refuse
toute variante qui retire une puce, en ajoute une, ou contient un mot interdit
(liste facultative "mots_interdits" dans cv.json).

cv.json
  nom, contact (texte), liens [{t,u}],
  experiences [{titre, dates, puces[]}], projets [{titre, lien{t,u}?, puces[]}],
  formation [{titre, dates}], competences [{label, items[]}], langues (texte)
  Dans les textes : **gras** et *italique* sont convertis.

variantes.json : liste de
  {fichier, titre, profil,
   puces: {"0": [ordre des puces de l'expérience 0], ...}   (optionnel)
   competences: [ordre des catégories]                      (optionnel)
   items: {"0": [ordre des éléments de la catégorie 0]}     (optionnel)}
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SPECIAUX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
            "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
SYMBOLES = {"→": r"$\rightarrow$", "⇒": r"$\Rightarrow$", "=>": r"$\Rightarrow$", "->": r"$\rightarrow$",
            "|": r"$\vert$", "≥": r"$\geq$", "≤": r"$\leq$"}


def tex(texte):
    """Échappe le texte pour LaTeX et convertit **gras** / *italique*."""
    texte = str(texte)
    for brut, code in (("=>", "⇒"), ("->", "→")):
        texte = texte.replace(brut, code)
    sortie = "".join(SPECIAUX.get(c, c) for c in texte)
    for brut, code in SYMBOLES.items():
        if len(brut) == 1:
            sortie = sortie.replace(brut, code)
    sortie = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", sortie)
    sortie = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\textit{\1}", sortie)
    return sortie


def verifier_interdits(objet, ou, interdits):
    brut = json.dumps({k: v for k, v in objet.items() if k != "mots_interdits"} if isinstance(objet, dict) else objet, ensure_ascii=False).lower()
    for mot in interdits:
        if mot in brut:
            raise SystemExit(f"ERREUR : mot interdit « {mot} » dans {ou}")


def permutation(ordre, n, ou):
    if ordre is None:
        return list(range(n))
    ordre = [int(i) for i in ordre]
    if sorted(ordre) != list(range(n)):
        raise SystemExit(f"ERREUR : {ou} doit reprendre chaque indice de 0 à {n - 1} une seule fois, reçu {ordre}")
    return ordre


def lien(l):
    return r"\href{%s}{%s}" % (l["u"].replace("%", r"\%").replace("#", r"\#"), tex(l["t"]))


def document(cv, var, reglage):
    taille, marge, saut = reglage
    p = [r"\documentclass[%s,a4paper]{article}" % taille,
         r"\usepackage{fontspec}",
         r"\usepackage[top=%scm,bottom=%scm,left=1.4cm,right=1.4cm]{geometry}" % (marge, marge),
         r"\usepackage{titlesec}", r"\usepackage{enumitem}", r"\usepackage[hidelinks]{hyperref}", r"\usepackage{xcolor}",
         r"\pagestyle{empty}", r"\definecolor{darkblue}{RGB}{0,50,100}", r"\setlength{\parindent}{0pt}",
         r"\titleformat{\section}{\large\bfseries\color{darkblue}}{}{0em}{}[\titlerule]",
         r"\titlespacing*{\section}{0pt}{%spt}{3pt}" % saut,
         r"\setlist[itemize]{leftmargin=1.1em, noitemsep, topsep=2pt}",
         r"\begin{document}", r"\begin{center}",
         r"{\Huge \textbf{%s}}" % tex(cv["nom"]), "", r"\vspace{5pt}",
         r"\textbf{%s}" % tex(var["titre"]), "", r"\vspace{5pt}", tex(cv["contact"])]
    if cv.get("liens"):
        p += ["", r"\vspace{3pt}", r" $\vert$ ".join(lien(l) for l in cv["liens"])]
    p += [r"\end{center}", "", r"\section{Profil}", tex(var["profil"]), ""]

    p.append(r"\section{Expériences professionnelles}")
    for i, exp in enumerate(cv["experiences"]):
        ordre = permutation((var.get("puces") or {}).get(str(i)), len(exp["puces"]), f"puces[{i}] de {var['fichier']}")
        if i:
            p.append(r"\vspace{4pt}")
        p.append(r"\textbf{%s} \hfill %s" % (tex(exp["titre"]), tex(exp.get("dates", ""))))
        p.append(r"\begin{itemize}")
        p += [r"\item " + tex(exp["puces"][k]) for k in ordre]
        p.append(r"\end{itemize}")
        p.append("")

    if cv.get("projets"):
        p.append(r"\section{Projets}")
        for i, pr in enumerate(cv["projets"]):
            if i:
                p.append(r"\vspace{4pt}")
            droite = lien(pr["lien"]) if pr.get("lien") else ""
            p.append(r"\textbf{%s} \hfill %s" % (tex(pr["titre"]), droite))
            if pr.get("puces"):
                p.append(r"\begin{itemize}")
                p += [r"\item " + tex(x) for x in pr["puces"]]
                p.append(r"\end{itemize}")
            p.append("")

    if cv.get("formation"):
        p.append(r"\section{Formation}")
        for i, f in enumerate(cv["formation"]):
            if i:
                p += ["", r"\vspace{2pt}"]
            p.append(r"\textbf{%s} \hfill %s" % (tex(f["titre"]), tex(f.get("dates", ""))))
        p.append("")

    comp = cv.get("competences") or []
    if comp:
        p.append(r"\section{Compétences techniques}")
        cats = permutation(var.get("competences"), len(comp), f"competences de {var['fichier']}")
        lignes = []
        for c in cats:
            items = comp[c]["items"]
            ordre = permutation((var.get("items") or {}).get(str(c)), len(items), f"items[{c}] de {var['fichier']}")
            lignes.append(r"\textbf{%s :} %s" % (tex(comp[c]["label"]), ", ".join(tex(items[k]) for k in ordre)))
        p.append("\n\n".join(lignes))
        p.append("")

    if cv.get("langues"):
        p += [r"\section{Langues}", tex(cv["langues"]).replace(r" $\vert$ ", r" \quad$\vert$\quad "), ""]
    p.append(r"\end{document}")
    return "\n".join(p)


REGLAGES = [("10pt", "1.3", "6"), ("10pt", "1.1", "4"), ("10pt", "0.9", "3"), ("9pt", "1.0", "3"), ("9pt", "0.8", "2")]


def pages(pdf):
    r = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
    for ligne in r.stdout.splitlines():
        if ligne.startswith("Pages:"):
            return int(ligne.split()[1])
    return -1


def generer(cv, var, sortie):
    nom = re.sub(r"[^A-Za-z0-9_.-]+", "_", var["fichier"]).strip("_") or "CV"
    with tempfile.TemporaryDirectory() as tmp:
        for reglage in REGLAGES:
            src = os.path.join(tmp, nom + ".tex")
            with open(src, "w", encoding="utf-8") as f:
                f.write(document(cv, var, reglage))
            r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", nom + ".tex"],
                               cwd=tmp, capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit(f"ERREUR LaTeX pour {nom} :\n{r.stdout[-1200:]}")
            n = pages(os.path.join(tmp, nom + ".pdf"))
            if n == 1:
                cible = os.path.join(sortie, nom + ".pdf")
                shutil.copy(os.path.join(tmp, nom + ".pdf"), cible)
                return {"fichier": nom + ".pdf", "chemin": cible, "pages": 1, "reglage": "/".join(reglage)}
    raise SystemExit(f"ERREUR : {nom} ne tient pas sur une page, même en réduisant la mise en page")


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    cv = json.load(open(sys.argv[1], encoding="utf-8"))
    variantes = json.load(open(sys.argv[2], encoding="utf-8"))
    sortie = sys.argv[3]
    os.makedirs(sortie, exist_ok=True)
    interdits = [str(m).lower() for m in cv.get("mots_interdits", []) if str(m).strip()]
    verifier_interdits(cv, "le CV de base", interdits)
    resultats = []
    for var in variantes:
        verifier_interdits(var, f"la variante {var.get('fichier')}", interdits)
        resultats.append(generer(cv, var, sortie))
    print(json.dumps(resultats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
