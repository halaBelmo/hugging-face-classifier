pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    parameters {
        booleanParam(name: 'RUN_TRAIN', defaultValue: false, description: 'Run a short training job during CI.')
        booleanParam(name: 'BUILD_DOCKER', defaultValue: true, description: 'Build the Docker image.')
        booleanParam(name: 'DEPLOY_LOCAL', defaultValue: false, description: 'Run the API container on this Jenkins agent.')
        string(name: 'RUN_ID', defaultValue: '', description: 'MLflow run_id to serve when DEPLOY_LOCAL is enabled.')
        string(name: 'DOCKER_IMAGE', defaultValue: 'hugging-face-classifier', description: 'Docker image name.')
        string(name: 'GITHUB_USERNAME', defaultValue: 'jenkins', description: 'Username propagated to Ray runtime_env.')
    }

    environment {
        GITHUB_USERNAME = "${params.GITHUB_USERNAME}"
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        PYTHONUNBUFFERED = '1'
        DOCKER_BUILDKIT = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Create Python Environment') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -eux
                            rm -rf .venv
                            if command -v python3.10 >/dev/null 2>&1; then
                                python3.10 -m venv .venv
                            else
                                export UV_PYTHON_INSTALL_DIR="$WORKSPACE/.uv-python"
                                if command -v curl >/dev/null 2>&1; then
                                    curl -LsSf https://astral.sh/uv/install.sh | sh
                                elif command -v python3 >/dev/null 2>&1; then
                                    python3 - <<'PY'
import urllib.request

url = "https://astral.sh/uv/install.sh"
with urllib.request.urlopen(url, timeout=60) as response:
    script = response.read()
with open("install-uv.sh", "wb") as fp:
    fp.write(script)
PY
                                    sh install-uv.sh
                                else
                                    echo "python3.10 is missing, and neither curl nor python3 is available to install uv."
                                    exit 1
                                fi
                                export PATH="$HOME/.local/bin:$PATH"
                                uv venv --python 3.10 --seed .venv
                            fi
                            . .venv/bin/activate
                            python --version
                            python -m pip install --upgrade "pip<27" "setuptools==68.2.2" wheel
                        '''
                    } else {
                        bat '''
                            if exist .venv rmdir /s /q .venv
                            py -3.10 -m venv .venv || python -m venv .venv
                            call .venv\\Scripts\\activate.bat
                            python --version
                            python -m pip install --upgrade "pip<27" "setuptools==68.2.2" wheel
                        '''
                    }
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -eux
                            . .venv/bin/activate
                            python -m pip install -r requirements.txt
                            python -m pip install --force-reinstall "setuptools==68.2.2" "click==8.1.7"
                        '''
                    } else {
                        bat '''
                            call .venv\\Scripts\\activate.bat
                            python -m pip install -r requirements.txt
                            python -m pip install --force-reinstall "setuptools==68.2.2" "click==8.1.7"
                        '''
                    }
                }
            }
        }

        stage('Quality Checks') {
            steps {
                script {
                    def smoke = '''
                        python -m compileall madewithml
                        python -c "import ray, mlflow, pandas, sklearn, torch, transformers; print('ray', ray.__version__); print('mlflow', mlflow.__version__); print('pandas', pandas.__version__); print('sklearn', sklearn.__version__); print('torch', torch.__version__); print('transformers', transformers.__version__)"
                    '''
                    if (isUnix()) {
                        sh """
                            set -eux
                            . .venv/bin/activate
                            ${smoke}
                        """
                    } else {
                        bat """
                            call .venv\\Scripts\\activate.bat
                            ${smoke}
                        """
                    }
                }
            }
        }

        stage('Tests') {
            when {
                expression { fileExists('tests') }
            }
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -eux
                            . .venv/bin/activate
                            python -m pytest
                        '''
                    } else {
                        bat '''
                            call .venv\\Scripts\\activate.bat
                            python -m pytest
                        '''
                    }
                }
            }
        }

        stage('Detect Docker') {
            steps {
                script {
                    if (isUnix()) {
                        def status = sh(returnStatus: true, script: 'command -v docker >/dev/null 2>&1 && docker version >/dev/null 2>&1')
                        env.HAS_DOCKER = status == 0 ? 'true' : 'false'
                    } else {
                        def status = bat(returnStatus: true, script: 'docker version >NUL 2>NUL')
                        env.HAS_DOCKER = status == 0 ? 'true' : 'false'
                    }
                    echo "Docker available: ${env.HAS_DOCKER}"
                }
            }
        }

        stage('Short Train Smoke') {
            when {
                expression { return params.RUN_TRAIN }
            }
            steps {
                script {
                    def trainCommand = 'python -m madewithml.train --num-epochs=1 --num-samples=20 --batch-size=4 --results-fp=results-ci.json'
                    if (isUnix()) {
                        sh """
                            set -eux
                            . .venv/bin/activate
                            export HF_HOME="\$WORKSPACE/.hf_cache"
                            export TRANSFORMERS_CACHE="\$WORKSPACE/.hf_cache/transformers"
                            ${trainCommand}
                        """
                    } else {
                        bat """
                            call .venv\\Scripts\\activate.bat
                            set HF_HOME=%WORKSPACE%\\.hf_cache
                            set TRANSFORMERS_CACHE=%WORKSPACE%\\.hf_cache\\transformers
                            ${trainCommand}
                        """
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'results-ci.json,efs/**/result.json', allowEmptyArchive: true
                }
            }
        }

        stage('Docker Build') {
            when {
                expression { return params.BUILD_DOCKER && env.HAS_DOCKER == 'true' }
            }
            steps {
                script {
                    def imageTag = "${params.DOCKER_IMAGE}:${env.BUILD_NUMBER}"
                    def latestTag = "${params.DOCKER_IMAGE}:latest"
                    if (isUnix()) {
                        sh "docker build -t ${imageTag} -t ${latestTag} ."
                    } else {
                        bat "docker build -t ${imageTag} -t ${latestTag} ."
                    }
                    env.BUILT_IMAGE = imageTag
                }
            }
        }

        stage('Docker Smoke') {
            when {
                expression { return params.BUILD_DOCKER && env.HAS_DOCKER == 'true' }
            }
            steps {
                script {
                    def imageTag = env.BUILT_IMAGE ?: "${params.DOCKER_IMAGE}:${env.BUILD_NUMBER}"
                    def smokeCommand = "docker run --rm ${imageTag} python -c \"import madewithml.config; print('image smoke ok')\""
                    if (isUnix()) {
                        sh smokeCommand
                    } else {
                        bat smokeCommand
                    }
                }
            }
        }

        stage('Deploy Local') {
            when {
                allOf {
                    expression { return params.DEPLOY_LOCAL }
                    expression { return params.RUN_ID?.trim() }
                    expression { return env.HAS_DOCKER == 'true' }
                }
            }
            steps {
                script {
                    def imageTag = env.BUILT_IMAGE ?: "${params.DOCKER_IMAGE}:latest"
                    if (isUnix()) {
                        sh """
                            docker rm -f hugging-face-classifier-api || true
                            docker run -d --name hugging-face-classifier-api \
                                -p 8000:8000 \
                                -e GITHUB_USERNAME="${env.GITHUB_USERNAME}" \
                                -e HF_HOME=/app/.hf_cache \
                                -e TRANSFORMERS_CACHE=/app/.hf_cache/transformers \
                                -v "\$WORKSPACE/efs:/app/efs" \
                                ${imageTag} \
                                python -m madewithml.serve --run_id ${params.RUN_ID} --host 0.0.0.0 --port 8000
                        """
                    } else {
                        bat """
                            docker rm -f hugging-face-classifier-api 2>NUL
                            docker run -d --name hugging-face-classifier-api -p 8000:8000 -e GITHUB_USERNAME=%GITHUB_USERNAME% -e HF_HOME=/app/.hf_cache -e TRANSFORMERS_CACHE=/app/.hf_cache/transformers -v "%WORKSPACE%\\efs:/app/efs" ${imageTag} python -m madewithml.serve --run_id ${params.RUN_ID} --host 0.0.0.0 --port 8000
                        """
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'logs/*.log,results*.json', allowEmptyArchive: true
        }
    }
}
