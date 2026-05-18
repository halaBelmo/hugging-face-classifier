# hugging-face-classifier

## CI/CD

Le pipeline GitHub Actions est dans `.github/workflows/ci-cd.yml`.

Il s'execute sur les branches `dev` et `main`:

- installation des dependances Python;
- compilation des modules `madewithml`;
- execution des tests avec `pytest`;
- build de l'image Docker;
- publication de l'image vers GitHub Container Registry sur les `push`.

Pour lancer les tests localement:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest tests
```

Pour construire l'image Docker localement:

```powershell
docker build -t mlops-app:local .
```

Pour executer le conteneur:

```powershell
docker run --rm -p 8000:8000 -e RUN_ID=247e3bfe9a7a4bb596f4f81961044f34 mlops-app:local
```

## Jenkins

Un pipeline Jenkins est disponible dans `Jenkinsfile`.

Pre-requis sur la machine Jenkins:

- Git;
- Python 3.10;
- Docker;
- acces au depot GitHub.

Etapes pour l'utiliser:

1. Ouvrir Jenkins.
2. Creer un nouveau job de type `Pipeline`.
3. Dans `Pipeline`, choisir `Pipeline script from SCM`.
4. SCM: `Git`.
5. Repository URL: URL de ton depot GitHub.
6. Branch: `*/dev` ou `*/main`.
7. Script Path: `Jenkinsfile`.
8. Sauvegarder puis cliquer sur `Build Now`.

Le pipeline Jenkins fait:

- checkout du code;
- creation d'un environnement virtuel Python;
- installation de `requirements.txt`;
- compilation de `madewithml`;
- execution de `pytest`;
- build de l'image Docker `mlops-app`.
