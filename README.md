# Hermes Agent Cloud

Le VRAI Hermes Agent déployé sur Render avec interface web 24/7.

## Fonctionnalités

- ✅ Interface web desktop (accessible partout)
- ✅ Mémoire persistante (sauvegardée sur disque)
- ✅ Support OpenAI, OpenRouter, Ollama Cloud
- ✅ Historique des conversations
- ✅ Déployé 24/7 sur Render (gratuit)

## Déploiement

1. Pousser sur GitHub
2. Créer un nouveau Blueprint sur Render
3. Configurer les variables d'environnement

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| HERMES_PASSWORD | Mot de passe pour l'interface web |
| OPENAI_API_KEY | Clé API OpenAI / OpenRouter / Ollama Cloud |
| OPENAI_BASE_URL | URL de base (https://ollama.com/v1 pour Ollama Cloud) |
| HERMES_MODEL | Modèle à utiliser (glm-5.1, gpt-4o-mini, etc.) |

## Utilisation

1. Ouvrir l'URL Render
2. Entrer le mot de passe
3. Discuter avec Hermes!

## Notes

- Le plan gratuit Render a 750 heures/mois
- L'instance "sleep" après 15 min d'inactivité
- Le premier réveil prend 10-30 secondes