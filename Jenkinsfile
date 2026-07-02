pipeline {
  agent any

  environment {
    NAMESPACE = "retail-microservices-dev"
  }

  stages {

    stage('Initialize') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          echo "Creating namespace..."
          sh '''
            kubectl get ns ${NAMESPACE} --kubeconfig=$KUBECONFIG >/dev/null 2>&1 \
              || kubectl create ns ${NAMESPACE} --kubeconfig=$KUBECONFIG
          '''
        }
      }
    }

    stage('Deploy Secrets + Config') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/secrets.yaml   --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/configmap.yaml --kubeconfig=$KUBECONFIG"
        }
      }
    }

    stage('Deploy Data Layer') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          echo "Applying databases, Redis, Kafka..."
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/db-customer-db.yaml     --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/db-payment-db.yaml      --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/db-product-db.yaml      --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/db-order-db.yaml        --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/db-notification-db.yaml --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/redis.yaml             --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/kafka.yaml             --kubeconfig=$KUBECONFIG"

          echo "Waiting for data layer to be ready..."
          sh "kubectl rollout status deployment/customer-db     -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG || true"
          sh "kubectl rollout status deployment/payment-db      -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG || true"
          sh "kubectl rollout status deployment/product-db      -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG || true"
          sh "kubectl rollout status deployment/order-db        -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG || true"
          sh "kubectl rollout status deployment/notification-db -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG || true"
          sh "kubectl rollout status deployment/retail-ms-redis -n ${NAMESPACE} --timeout=60s  --kubeconfig=$KUBECONFIG || true"
          sh "kubectl rollout status deployment/retail-ms-kafka -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG || true"
        }
      }
    }

    // Startup order matters: config-server must be healthy before anything else
    // pulls its configuration, and discovery must be up before services register.
    stage('Deploy config-server') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-config-server.yaml --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/config-server -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG"
        }
      }
    }

    stage('Deploy discovery') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-discovery.yaml --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/discovery -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG"
        }
      }
    }

    stage('Deploy business services') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-customer-service.yaml     --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-payment-service.yaml      --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-product-service.yaml      --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-order-service.yaml        --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-notification-service.yaml --kubeconfig=$KUBECONFIG"
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-copilot-service.yaml      --kubeconfig=$KUBECONFIG"

          echo "Waiting for business services rollout..."
          sh "kubectl rollout status deployment/customer-service     -n ${NAMESPACE} --timeout=180s --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/payment-service      -n ${NAMESPACE} --timeout=180s --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/product-service      -n ${NAMESPACE} --timeout=180s --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/order-service        -n ${NAMESPACE} --timeout=180s --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/notification-service -n ${NAMESPACE} --timeout=180s --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/copilot-service      -n ${NAMESPACE} --timeout=180s --kubeconfig=$KUBECONFIG"
        }
      }
    }

    // Last: api-gateway routes by Eureka service name, so every business service
    // must already be registered before it's useful.
    stage('Deploy api-gateway') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          sh "kubectl apply -n ${NAMESPACE} -f k8s/dev/svc-api-gateway.yaml --kubeconfig=$KUBECONFIG"
          sh "kubectl rollout status deployment/api-gateway -n ${NAMESPACE} --timeout=120s --kubeconfig=$KUBECONFIG"
        }
      }
    }

    stage('Verify') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
          sh "kubectl get pods -n ${NAMESPACE} --kubeconfig=$KUBECONFIG"
          sh "kubectl get svc  -n ${NAMESPACE} --kubeconfig=$KUBECONFIG"
        }
      }
    }
  }

  post {
    failure {
      withCredentials([file(credentialsId: 'kubeconfig-retail', variable: 'KUBECONFIG')]) {
        echo "Pipeline failed — rolling back all business services and the gateway..."
        sh "kubectl rollout undo deployment/api-gateway          -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/customer-service     -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/payment-service      -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/product-service      -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/order-service        -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/notification-service -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/copilot-service      -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/discovery            -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl rollout undo deployment/config-server        -n ${NAMESPACE} --kubeconfig=$KUBECONFIG || true"
        sh "kubectl get pods -n ${NAMESPACE} --kubeconfig=$KUBECONFIG"
        echo "Rollback complete."
      }
    }
    success {
      echo "Deployment successful — ${NAMESPACE} is live."
    }
  }
}
