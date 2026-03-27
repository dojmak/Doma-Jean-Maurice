# Registry — Sous-Agents Claude Code

Registre central de tous les sous-agents du projet. Mis à jour automatiquement par l'`agent-builder`.

---

## Format d'entrée

```
| nom-agent | Déclencheur | Fichier | Modèle | Outils |
```

---

## Agents enregistrés

| Nom | Déclencheur | Fichier | Modèle | Outils |
|---|---|---|---|---|
| agent-builder | Demande de création/conception d'un nouveau sous-agent. Ex : "crée un agent qui...", "ajoute un sous-agent pour...", "conçois un agent capable de..." | `.claude/agents/agent-builder.md` | claude-opus-4-6 | Read, Write, Edit, Glob, Grep, Bash |

---

## Conventions

- **Noms** : kebab-case, minuscules
- **Déclencheur** : 1-2 phrases + exemples de formulations utilisateur
- **Modèle par défaut** : `claude-opus-4-6` (utiliser `claude-sonnet-4-6` pour les agents haute fréquence ou budget contraint)
- **Outils** : liste minimale — jamais `*`

## Historique des modifications

| Date | Action | Agent | Par |
|---|---|---|---|
| 2026-03-27 | Création initiale | agent-builder | agent-builder (bootstrap) |
