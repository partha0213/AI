#!/bin/bash

echo "📊 Setting up monitoring and logging..."

# Create monitoring directories
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/datasources
mkdir -p monitoring/prometheus/rules
mkdir -p logs/nginx

# Copy Grafana datasource configuration
cat > monitoring/grafana/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

# Copy sample dashboard
cat > monitoring/grafana/dashboards/api-dashboard.json << EOF
{
  "dashboard": {
    "title": "AI Intern Platform API Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      }
    ]
  }
}
EOF

echo "✅ Monitoring setup completed"
echo "📁 Configuring Nginx logging..."