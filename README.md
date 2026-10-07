# Floss & Job

Site personnel, hébergé comme page privée dans Claude. Deux rubriques :

- **Bourse (Floss)** : le point de marché du jour et l'ordre du mois, calculé pour le montant saisi, dans un PEA BoursoBank.
- **Emploi (Job)** : les meilleures offres Java d'une ville, un contact au recrutement, un message LinkedIn et un CV adapté par offre, à télécharger.

Aucune clé API : les analyses tournent sur l'abonnement Claude. La page écrit une demande dans sa base, puis déclenche une tâche Claude qui fait la recherche et range le résultat dans la même base.

## Organisation

| Dossier | Rôle |
|---|---|
| `site/index.html` | La page (publiée comme artefact Claude). Elle calcule l'ordre du mois elle-même : changer le montant ne coûte aucun quota. |
| `prive/` (hors dépôt) | Les consignes des deux tâches Claude et le CV de base. Elles contiennent des données personnelles et restent dans la page privée. |
| `tools/cvgen.py` | Générateur de CV : CV de base en JSON + variantes par offre, sortie en PDF d'une page (XeLaTeX). |
| `data/exemple_*.json` | Jeux d'exemple pour tester l'affichage. |
| `tests/apercu.py` | Rend la page en local avec de fausses données et prend des captures. |

## Base de la page

- `config/main` : identifiants des deux tâches, fourchettes de salaire visées par ville, mots à ne jamais afficher. `config/cv` : le CV déposé.
- `demandes/<id>` : une demande par clic (`type`, `status`, `ville` ou `montant`).
- `floss/<date>` : les données de marché d'un jour. `jobs/<id>` : une recherche d'emploi.

## Économie de quota

- Bourse : une collecte par jour suffit. Le montant se recalcule dans la page.
- Emploi : une recherche par ville tous les trois jours suffit ; les anciennes restent affichées.
- Les tâches ont un nombre d'appels web plafonné et n'écrivent aucun texte hors du résultat.

## Tester

```
python3 tools/cvgen.py cv.json variantes.json sortie/
python3 tests/apercu.py /tmp/captures
```

Les frais BoursoBank sont réglés en tête du script de `site/index.html` (constante `COURTIER`).
