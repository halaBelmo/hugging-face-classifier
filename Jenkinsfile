pipeline {
    agent any

    environment {
        PYTHON_VERSION = '3.10'
        VENV_DIR = '.venv-jenkins'
        IMAGE_NAME = 'mlops-app'
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        GITHUB_USERNAME = 'ci'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set up Python') {
            steps {
                sh '''
                    python3 --version
                    python3 -m venv ${VENV_DIR}
                    . ${VENV_DIR}/bin/activate
                    python -m pip install --upgrade pip
                    python -m pip install -r requirements.txt
                '''
            }
        }

        stage('Validate') {
            steps {
                sh '''
                    . ${VENV_DIR}/bin/activate
                    python -m compileall madewithml
                    python -m pytest tests
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
                    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:latest
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
