# Jenkins CI/CD Pipeline

This project includes a declarative Jenkins pipeline in `Jenkinsfile`.

## Jenkins agent prerequisites

- Python 3.10 available as `python3.10`, `py -3.10`, or `python`. On Linux agents without Python 3.10, the pipeline installs `uv` with `curl` and creates a Python 3.10 virtual environment.
- `curl` installed on Linux agents when Python 3.10 is not already available
- Docker installed if `BUILD_DOCKER` or `DEPLOY_LOCAL` is enabled. The pipeline detects Docker and skips Docker stages when it is not available.
- Network access to PyPI and Hugging Face for dependency and model downloads

## Pipeline parameters

- `RUN_TRAIN`: runs a short 1 epoch training smoke test. Disabled by default because model downloads and CPU training are slow.
- `BUILD_DOCKER`: builds the Docker image when Docker is available. Disabled by default to keep the first Jenkins build fast.
- `DEPLOY_LOCAL`: runs the API container on the Jenkins agent when Docker is available.
- `RUN_ID`: MLflow run ID to serve when `DEPLOY_LOCAL` is enabled.
- `DOCKER_IMAGE`: Docker image name. Default: `hugging-face-classifier`.
- `GITHUB_USERNAME`: username propagated to Ray runtime environment. Default: `jenkins`.

## Recommended first run

Use the defaults first. This installs the smaller CI dependency set from `requirements-ci.txt`, runs import/compile checks, and runs smoke tests.

Enable `BUILD_DOCKER` only after the Python checks pass and Docker is available on the Jenkins agent.

To deploy the model trained locally, enable `DEPLOY_LOCAL` and set:

```text
RUN_ID=06cb00ce853f41b1af18c78646056727
```

The local deployment exposes the API on:

```text
http://<jenkins-agent-host>:8000/docs
```
