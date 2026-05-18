pipeline {
    agent any

    environment {
        VENV_DIR = '.venv-jenkins'
        IMAGE_NAME = 'mlops-app'
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        GITHUB_USERNAME = 'ci'
    }

    stages {
        stage('Checkout') {
            steps {
                git branch: 'dev',
                    url: 'https://github.com/halaBelmo/hugging-face-classifier.git'
            }
        }

        stage('Set up Python') {
            steps {
                bat '''
                    py -3.10 --version
                    py -3.10 -m venv %VENV_DIR%
                    call %VENV_DIR%\\Scripts\\activate.bat
                    python -m pip install --upgrade pip
                    findstr /V /I "anyscale==" requirements.txt > requirements-ci.txt
                    python -m pip install -r requirements-ci.txt
                '''
            }
        }

        stage('Validate') {
            steps {
                bat '''
                    call %VENV_DIR%\\Scripts\\activate.bat
                    python -m compileall madewithml
                    python -c "from madewithml.predict import decode, format_prob; assert decode([0], {0: 'ok'}) == ['ok']; assert format_prob([0.9], {0: 'ok'}) == {'ok': 0.9}"
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                writeFile file: 'Dockerfile.ci', text: '''FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-ci.txt .
RUN pip install --no-cache-dir -r requirements-ci.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "madewithml.serve", "--host", "0.0.0.0", "--run_id", "247e3bfe9a7a4bb596f4f81961044f34"]
'''
                bat '''
                    docker build -f Dockerfile.ci -t %IMAGE_NAME%:%IMAGE_TAG% .
                    docker tag %IMAGE_NAME%:%IMAGE_TAG% %IMAGE_NAME%:latest
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'results.json', allowEmptyArchive: true
        }
        success {
            echo 'Pipeline Jenkins termine avec succes.'
        }
        failure {
            echo 'Pipeline Jenkins echoue. Verifiez les logs du stage en erreur.'
        }
    }
}
