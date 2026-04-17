# 🚀 QUICK FIX - Grafana Dashboard Import

## ✅ STEP-BY-STEP FIX

### 1️⃣ **Configure Prometheus Data Source**
1. Go to **http://localhost:3000**
2. **Configuration** → **Data Sources** → **Add data source**
3. Select **Prometheus**
4. **URL**: `http://prometheus:9090` (inside Docker network)
5. **Click "Save & test"** - should show green ✅

### 2️⃣ **Import Working Dashboard** 
1. **+ (Plus)** → **Import**
2. **Upload JSON file**: `bootcamp/grafana-dashboard-WORKING.json`
3. **Select Data Source**: Prometheus (from step 1)
4. **Click "Import"**

### 3️⃣ **Set Time Range**
- **Top right**: Change to **"Last 5 minutes"**
- **Refresh**: Set to **5s** for real-time updates

---

## 🎯 **VERIFIED METRICS AVAILABLE:**

✅ **Current data**: 206 evaluation requests  
✅ **Job name**: `eval-py-local` (working)  
✅ **Prometheus**: http://localhost:9090 (accessible)  
✅ **Fresh data**: Just generated 10 new data points  

---

## 🔍 **If still "No data":**

### Quick Debug:
```bash
# Test Grafana → Prometheus connection
curl -s http://localhost:3000/api/datasources/proxy/1/api/v1/query?query=up

# Current metric value  
curl -s "http://localhost:9090/api/v1/query?query=llmqa_eval_requests_total"
```

### Alternative Data Source URL:
If `http://prometheus:9090` doesn't work, try:
- `http://localhost:9090` 
- `http://172.22.0.1:9090`

---

## 📊 **EXPECTED DASHBOARD PANELS:**

1. **🎯 Evaluation Request Rate** - Should show activity from last 5min
2. **📊 Total Evaluations** - Should show **206** (or higher)  
3. **🤖 Agent Loop Performance** - May show 0 if agent not running
4. **🔍 RAG Performance** - Should show latency data
5. **🎯 RAG Search Results** - RAG metrics
6. **🖥️ System Resources** - CPU/Memory usage

---

## 🎉 **SUCCESS = Any panel showing data!**

Even if just panel #2 shows "206" - that means it's working! 
The system is healthy and generating metrics! 🚀

---

Try the import and let me know what happens! 😊