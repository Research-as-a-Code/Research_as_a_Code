# Scripts Directory

This directory contains various utility scripts for the AI-Q Research Assistant project.

## Cluster Management Scripts

### ⭐ Recommended: New Modular Scripts

Located in `../infrastructure/scripts/`:

- **`sleep-cluster.sh`** - Smart sleep (keeps Milvus/Frontend running)
- **`wake-cluster.sh`** - Quick wake (scales up NIMs and Backend)
- **`monitor-cluster-readiness.sh`** - Wait for full readiness (auto-exits)
- **`test-sleep-wake-cycle.sh`** - End-to-end validation

**Use these for daily development workflow:**
```bash
# End of day
bash infrastructure/scripts/sleep-cluster.sh

# Next morning
bash infrastructure/scripts/wake-cluster.sh
bash infrastructure/scripts/monitor-cluster-readiness.sh
```

**Benefits:**
- ✅ Faster wake times (~17 min vs ~20+ min)
- ✅ Milvus stays warm (no data rehydration)
- ✅ Modular design (reusable monitoring)
- ✅ Battle-tested (17-min validation passed)
- ✅ Better UX (progress updates, auto-exit)
- ✅ 90% cost savings

### 💤 Alternative: Deep Sleep Scripts

Located in this directory:

- **`deep-sleep-cluster.sh`** - Maximum savings (stops EVERYTHING)
- **`deep-wake-cluster.sh`** - Full wake (with built-in monitoring)

**Use these for:**
- Extended downtime (weekends, vacations, 2+ days)
- Maximum cost savings scenarios
- When wake time isn't critical

```bash
# Before vacation
bash scripts/deep-sleep-cluster.sh

# After vacation
bash scripts/deep-wake-cluster.sh
```

**Trade-offs:**
- ✅ 95% cost savings (vs 90%)
- ✅ Monolithic (all-in-one script)
- ❌ Slower wake times (~20+ minutes)
- ❌ Milvus needs rehydration

## RAG Setup Scripts

- **`setup_tariff_rag_enterprise.sh`** - Enterprise RAG deployment with NVIDIA NIMs
- **`setup_tariff_rag_service.sh`** - Lightweight RAG service deployment

These scripts set up the tariff collection with us_tariffs data for the hackathon demo.

## Summary

| Scenario | Recommended Script |
|----------|-------------------|
| **Daily development** | `infrastructure/scripts/sleep-cluster.sh` + `wake-cluster.sh` |
| **Testing cluster lifecycle** | `infrastructure/scripts/test-sleep-wake-cycle.sh` |
| **Extended downtime (2+ days)** | `scripts/deep-sleep-cluster.sh` → `deep-wake-cluster.sh` |
| **Just monitoring** | `infrastructure/scripts/monitor-cluster-readiness.sh` |

---

**💡 Pro Tip**: The standard scripts in `infrastructure/scripts/` are recommended for daily use. They provide 90% cost savings with significantly faster wake times. Use `deep-sleep-cluster.sh` only when you need maximum savings for extended downtime.

