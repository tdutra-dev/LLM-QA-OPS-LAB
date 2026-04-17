# 📊 Grafana Dashboard Setup - LLM-QA-OPS Bootcamp

## 🚀 QUICK IMPORT STEPS

### Step 1: Open Grafana
- Go to **http://localhost:3000**
- Login: `admin` / `admin` (or your credentials)

### Step 2: Import Dashboard
1. Click **"+"** → **"Import"**
2. Upload the JSON file: `/home/tendresse/projects/llm-qa-ops-lab/bootcamp/grafana-dashboard-llm-qa-ops.json`
3. **OR** Copy-paste the JSON content directly

### Step 3: Configure Data Source
1. **Data Source**: Select **"Prometheus"**
2. **URL**: `http://prometheus:9090` (if inside Docker)
   - **OR** `http://localhost:9090` (if local Prometheus)

### Step 4: Set Time Range
- **Time Range**: Last 15 minutes
- **Refresh**: 5 seconds (for real-time updates)

---

## 📈 DASHBOARD PANELS EXPLAINED

### 🎯 **Panel 1: Evaluation Request Rate**
- **Metric**: `rate(llmqa_eval_requests_total[5m])`
- **Shows**: Requests per second by status
- **Expected**: Green line showing ~2-3 req/s from our load tests

### 📊 **Panel 2: Total Evaluations by Status**  
- **Metric**: `llmqa_eval_requests_total`
- **Shows**: Counter totals by incident status
- **Expected**: Numbers like "needs_attention: 226"

### 🔥 **Panel 3: Evaluation Score Distribution**
- **Metric**: `rate(llmqa_eval_score_bucket[5m])`  
- **Shows**: Heatmap of score distributions
- **Expected**: Pattern showing score clusters

### 🔍 **Panel 4: RAG Performance Latency**
- **Metrics**: 
  - `histogram_quantile(0.95, rate(llmqa_rag_retrieval_latency_seconds_bucket[5m]))`
  - `histogram_quantile(0.95, rate(llmqa_rag_embedding_latency_seconds_bucket[5m]))`
- **Shows**: P50/P95 latency for pgvector & OpenAI
- **Expected**: Latency lines ~0.1-1.0 seconds

### 🎯 **Panel 5: RAG Similarity Search Results**
- **Metric**: `histogram_quantile(0.95, rate(llmqa_rag_similar_incidents_found_bucket[5m]))`
- **Shows**: How many similar incidents were found
- **Expected**: Lines showing incident retrieval counts

### 🖥️ **Panel 6: System Resources**
- **Metrics**:
  - `rate(process_cpu_seconds_total[5m]) * 100` (CPU %)
  - `(process_resident_memory_bytes / (1024*1024*1024)) * 100` (Memory %)
- **Shows**: System resource utilization
- **Expected**: CPU ~10-30%, Memory varies

---

## 🔧 TROUBLESHOOTING

### "No data available"
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify metrics endpoint  
curl http://localhost:8011/prometheus-metrics | grep llmqa

# Generate more test data
cd /home/tendresse/projects/llm-qa-ops-lab
for i in {1..5}; do
  curl -X POST http://localhost:8011/evaluate \
    -H "Content-Type: application/json" \
    -d '{"incident":{"id":"test-'$i'","severity":"high"}}' 
  sleep 1
done
```

### "Failed to load dashboard"
1. Check JSON syntax in the dashboard file
2. Ensure Prometheus data source is configured
3. Verify Grafana can reach Prometheus

### Metrics not updating
1. Refresh dashboard (Ctrl+R)
2. Check time range (last 15min)
3. Verify services are running: `docker-compose ps`

---

## 🎯 SUCCESS CRITERIA

✅ **Dashboard imports successfully**  
✅ **All 6 panels show data**  
✅ **Real-time updates (5sec refresh)**  
✅ **Metrics correlate with system activity**  
✅ **Can drill down into specific timeframes**

---

## 💡 NEXT STEPS for BOOTCAMP

With Grafana working, you now have:
- ✅ **Real-time monitoring** of your LLM system
- ✅ **Performance metrics** for RAG pipeline  
- ✅ **Business metrics** for evaluations
- ✅ **System metrics** for health monitoring

**Tomorrow DAY 2: Python Advanced Patterns** will build on this foundation! 🐍

---

## 🔗 QUICK LINKS

- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090  
- **eval-py health**: http://localhost:8011/health
- **Dashboard JSON**: `bootcamp/grafana-dashboard-llm-qa-ops.json`