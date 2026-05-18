# Jenkins CI/CD Pipeline

This project includes a declarative Jenkins pipeline in `Jenkinsfile`.

## Jenkins agent prerequisites

- Python 3.10 available as `python3.10`, `python3`, `py -3.10`, or `python`
- Docker installed if `BUILD_DOCKER` or `DEPLOY_LOCAL` is enabled
- Network access to PyPI and Hugging Face for dependency and model downloads

## Pipeline parameters

- `RUN_TRAIN`: runs a short 1 epoch training smoke test. Disabled by default because model downloads and CPU training are slow.
- `BUILD_DOCKER`: builds the Docker image. Enabled by default.
- `DEPLOY_LOCAL`: runs the API container on the Jenkins agent.
- `RUN_ID`: MLflow run ID to serve when `DEPLOY_LOCAL` is enabled.
- `DOCKER_IMAGE`: Docker image name. Default: `hugging-face-classifier`.
- `GITHUB_USERNAME`: username propagated to Ray runtime environment. Default: `jenkins`.

## Recommended first run

Use the defaults first. This installs dependencies, runs import/compile checks, builds the Docker image, and smoke-tests the image.

To deploy the model trained locally, enable `DEPLOY_LOCAL` and set:

```text
RUN_ID=06cb00ce853f41b1af18c78646056727
```

The local deployment exposes the API on:

```text
http://<jenkins-agent-host>:8000/docs
```
