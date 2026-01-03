# SPL Framework Integration - Implementation Plan & Progress Tracker

**Project:** VoiceAgents-gemini  
**Objective:** Integrate SPL-FRAMEWORK to reduce LLM API costs by 40-95% and improve latency by 10-50x  
**Start Date:** January 3, 2026  
**Status:** 🟡 Planning Phase

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Implementation Phases](#implementation-phases)
3. [Task Checklist](#task-checklist)
4. [Testing & Verification](#testing--verification)
5. [Cache & Storage Management](#cache--storage-management)
6. [Rollback Plan](#rollback-plan)
7. [Progress Log](#progress-log)

---

## 🏗️ Architecture Overview

### Current System (Without SPL)
```
User Utterance → Deepgram STT → Transcript
                                    ↓
                               [ALWAYS]
                                    ↓
                         Groq LLM ($0.01, 300ms) → Response → TTS
```

### New System (With SPL - Hybrid Architecture)
```
User Utterance → Deepgram STT → Transcript
                                    ↓
                            ┌───────────────┐
                            │  SPL SERVICE  │
                            └───────┬───────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
   [Layer 0]                   [Layer 1]                   [Layer 2]
  Validation              Pattern Matching                Groq LLM
   <1ms, $0                                              300ms, $0.01
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
              [Layer 1a]                    [Layer 1b]
          Keyword/Fuzzy                OpenAI Embeddings
           0ms, $0                      50ms, $0.0001
                    │                             │
                    └──────────────┬──────────────┘
                                   ↓
                             Response → TTS
```

### Layer Details

**Layer 0: Validation (Instant Rejection)**
- Length checks (min/max)
- Blocklist filtering
- Rate limiting
- Latency: <1ms, Cost: $0

**Layer 1a: Keyword/Fuzzy Matching (Fast Path)**
- Exact keyword matching ("hours", "location", "hi", "bye")
- Fuzzy string matching using `rapidfuzz`
- Catches 80% of common queries
- Latency: 0ms, Cost: $0

**Layer 1b: Semantic Matching (Fallback)**
- OpenAI embeddings (same as RAG: text-embedding-3-small)
- Cosine similarity against learned patterns
- Handles semantic variations ("When do you close?" ≈ "What are your hours?")
- Latency: 50ms, Cost: $0.0001

**Layer 2: LLM Processing (Last Resort)**
- Groq Llama 3.3-70B for novel queries
- Pattern learning from confident responses
- Latency: 300ms, Cost: $0.01

### Key Design Principles

1. **Multi-Tenancy Preserved**: Each organization has isolated patterns (namespace = organizationId)
2. **Domain Agnostic**: Works for restaurants, pharmacies, hotels, retail, etc.
3. **Non-Breaking**: Existing functionality remains unchanged
4. **Gradual Learning**: Patterns improve over time from confident LLM responses
5. **Hybrid Matching**: Fast keywords first (0ms), embeddings if needed (50ms)
6. **Cost Optimization**: Reuses existing OpenAI embeddings (same as RAG)
7. **Progressive Enhancement**: Layer 1a handles 80%, Layer 1b handles 15%, LLM only 5%

---

## 🎯 Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal:** Set up database schema, install dependencies, create core SPL service

**Duration:** 8-10 days  
**Risk:** Low  
**Dependencies:** None

### Phase 2: Integration (Week 3-4)
**Goal:** Integrate SPL into WebSocket handlers, enable pattern learning

**Duration:** 10-12 days  
**Risk:** Medium (touches core call handling)  
**Dependencies:** Phase 1 complete

### Phase 3: Monitoring (Week 5)
**Goal:** Add metrics, analytics, dashboard for SPL performance

**Duration:** 5-7 days  
**Risk:** Low  
**Dependencies:** Phase 2 complete

### Phase 4: Optimization (Week 6-7)
**Goal:** Domain-specific patterns, performance tuning, A/B testing

**Duration:** 10-14 days  
**Risk:** Low  
**Dependencies:** Phase 3 complete

### Phase 5: Production Hardening (Week 8)
**Goal:** Comprehensive testing, load testing, documentation

**Duration:** 5-7 days  
**Risk:** Low  
**Dependencies:** All phases complete

---

## ✅ Task Checklist

### Phase 1: Foundation

#### 1.1 Dependencies Installation
- [ ] **Task:** Add SPL dependencies to requirements.txt
  - `rapidfuzz>=3.0.0` (fast fuzzy string matching)
  - `openai>=2.14.0` (already installed - reuse for embeddings)
  - `numpy>=1.24.0` (already installed - for cosine similarity)
  - `redis>=5.0.0` (optional - for multi-instance caching)
- [ ] **Task:** Install dependencies
  ```bash
  pip install rapidfuzz
  # openai and numpy already installed
  ```
- [ ] **Verification:** Run `pip list | grep -E "rapidfuzz|openai|numpy"`
- [ ] **Status:** ⬜ Not Started
- [ ] **Assigned To:** 
- [ ] **Notes:** No ML models to download! Using existing OpenAI API for embeddings.

#### 1.2 Convex Schema Updates
- [ ] **Task:** Add `spl_patterns` table to convex/schema.ts
- [ ] **Task:** Create convex/spl_patterns.ts with mutations/queries:
  - `create` - Create new pattern
  - `getByOrganization` - Get all patterns for org
  - `incrementHitCount` - Update usage stats
  - `updateSuccessRate` - Update pattern performance
  - `deactivate` - Disable low-performing pattern
  - `deletePattern` - Hard delete pattern
- [ ] **Task:** Deploy schema to Convex
  ```bash
  npx convex dev  # or npx convex deploy
  ```
- [ ] **Verification:** 
  - Check Convex dashboard for new `spl_patterns` table
  - Run test mutation: `npx convex run spl_patterns:create '{"organizationId":"test", ...}'`
- [ ] **Status:** ⬜ Not Started
- [ ] **Assigned To:**
- [ ] **Notes:**

#### 1.3 SPL Service Implementation
- [ ] **Task:** Create `app/services/spl_service.py`
  - Implement `SPLService` class
  - Implement `SPLDecision` dataclass
  - **Layer 0:** Validation (length, blocklist, rate limiting)
  - **Layer 1a:** Keyword/fuzzy matching (rapidfuzz)
  - **Layer 1b:** Semantic matching (OpenAI embeddings)
  - **Layer 2:** LLM passthrough with pattern learning
- [ ] **Task:** Implement `_keyword_match()` method
  - Exact phrase matching
  - Keyword dictionaries per pattern type
  - Return cached response immediately
- [ ] **Task:** Implement `_semantic_match()` method
  - Generate embedding using OpenAI API
  - Cosine similarity against stored patterns
  - Threshold: 0.75 for match
- [ ] **Task:** Implement singleton factory `get_spl_service()`
- [ ] **Task:** Add OpenAI client initialization (reuse existing)
- [ ] **Verification:**
  - Unit test: `python -c "from app.services.spl_service import get_spl_service; print('✓ Import successful')"`
  - Test keyword matching (should be instant)
  - Test OpenAI embedding generation
- [ ] **Status:** ⬜ Not Started
- [ ] **Assigned To:**
- [ ] **Files Modified:**
  - `app/services/spl_service.py` (NEW)
- [ ] **Notes:** Hybrid approach: fast keywords first, embeddings as fallback

#### 1.4 Bootstrap Script
- [ ] **Task:** Create `scripts/bootstrap_spl_patterns.py`
- [ ] **Task:** Define common patterns with dual representations:
  - **Keywords:** For Layer 1a matching ("hours", "open", "close")
  - **Example Queries:** For Layer 1b embeddings ("What are your hours?")
  - **Cached Responses:** Pre-defined answers or function call specs
- [ ] **Task:** Implement pattern creation with OpenAI embeddings:
  - Generate embedding for first example query
  - Store embedding in Convex (1536-dim array)
  - Store keywords for fast matching
- [ ] **Task:** Pre-define patterns:
  - business_hours (keywords: hours, open, close, time)
  - location (keywords: where, address, directions)
  - greeting (keywords: hi, hello, hey)
  - farewell (keywords: bye, goodbye, thanks)
- [ ] **Verification:**
  - Run: `python scripts/bootstrap_spl_patterns.py test-org`
  - Check Convex dashboard for created patterns
  - Verify embeddings are 1536-dim arrays
  - Verify keywords are stored
- [ ] **Status:** ⬜ Not Started
- [ ] **Assigned To:**
- [ ] **Files Modified:**
  - `scripts/bootstrap_spl_patterns.py` (NEW)
- [ ] **Notes:** Dual representation enables hybrid matching strategy

#### 1.5 Testing - Phase 1
- [ ] **Task:** Create `tests/test_spl_service.py`
- [ ] **Test Cases:**
  - ✅ Layer 0 validation (too short, too long, blocklist)
  - ✅ Layer 1a keyword matching (exact phrases)
  - ✅ Layer 1a fuzzy matching (typos, variations)
  - ✅ Layer 1b semantic matching (OpenAI embeddings)
  - ✅ Pattern learning from LLM responses
  - ✅ Cache operations (get, set, invalidate)
  - ✅ Cost tracking (keyword: $0, embedding: $0.0001, LLM: $0.01)
- [ ] **Task:** Run tests: `pytest tests/test_spl_service.py -v`
- [ ] **Acceptance Criteria:** All tests pass
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

---

### Phase 2: Integration

#### 2.1 WebSocket Handler Integration
- [ ] **Task:** Modify `websocket_server/handlers/audio_handler.py`
- [ ] **Task:** Add SPL import: `from app.services.spl_service import get_spl_service`
- [ ] **Task:** Find ConversationText handler (user role)
- [ ] **Task:** Add SPL processing before LLM call:
  ```python
  # Process through SPL
  spl = get_spl_service(organization_id)
  decision = await spl.process_utterance(transcript, context)
  
  if not decision.should_call_llm:
      # Send cached response via InjectAgentMessage
      await deepgram_ws.send(json.dumps({
          "type": "InjectAgentMessage",
          "message": decision.cached_response
      }))
      return  # Skip LLM!
  ```
- [ ] **Task:** Add pattern learning for assistant responses
- [ ] **Verification:**
  - Manual test: Make call, say "What are your hours?" twice
  - Check logs for "SPL Layer 1" on second utterance
  - Verify LLM not called second time
- [ ] **Status:** ⬜ Not Started
- [ ] **Assigned To:**
- [ ] **Files Modified:**
  - `websocket_server/handlers/audio_handler.py`
- [ ] **Notes:**

#### 2.2 Organization Context Tracking
- [ ] **Task:** Ensure `organization_id` is available in WebSocket handlers
- [ ] **Task:** Pass organization_id to SPL service
- [ ] **Task:** Store last user transcript for pattern learning
- [ ] **Verification:**
  - Check logs for organization_id in SPL decisions
- [ ] **Status:** ⬜ Not Started
- [ ] **Files Modified:**
  - `websocket_server/connection_manager.py` (if needed)
- [ ] **Notes:**

#### 2.3 Pattern Learning Implementation
- [ ] **Task:** Implement pattern key inference (`_infer_pattern_key()`)
- [ ] **Task:** Add confidence scoring logic
- [ ] **Task:** Implement pattern learning on confident responses (>0.90)
- [ ] **Verification:**
  - Manual test: Ask novel question, check if pattern learned
  - Check Convex dashboard for new patterns
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 2.4 Logging & Debugging
- [ ] **Task:** Add structured logging for SPL decisions
  - Log layer (0, 1a, 1b, 2)
  - Log method (validation, keyword_match, semantic_match, llm_required)
  - Log confidence, latency, cost savings
  - Log match type (exact, fuzzy, embedding, none)
- [ ] **Task:** Add debug mode for SPL (env var: `SPL_DEBUG=true`)
- [ ] **Task:** Add performance metrics:
  - Layer 1a hit rate (keyword matches / total)
  - Layer 1b hit rate (embedding matches / total)
  - Average latency per layer
  - Cost per query type
- [ ] **Verification:**
  - Check logs during test calls
  - Verify all SPL decisions are logged with correct layer
  - Verify cost tracking is accurate
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:** Separate Layer 1a and 1b metrics for analysis

#### 2.5 Testing - Phase 2
- [ ] **Task:** End-to-end integration tests
- [ ] **Test Cases:**
  - ✅ First-time query → Layer 2 (LLM)
  - ✅ Repeated query → Layer 1a (keyword hit)
  - ✅ Fuzzy match → Layer 1a ("whats ur hours" matches "what are your hours")
  - ✅ Semantic variation → Layer 1b (embedding match: "When do you close?" ≈ "hours")
  - ✅ Invalid input → Layer 0 (rejection)
  - ✅ Pattern learning after confident response
  - ✅ Cost verification: Layer 1a=$0, Layer 1b=$0.0001, Layer 2=$0.01
- [ ] **Task:** Test with multiple organizations (isolation)
- [ ] **Task:** Load test: 10 concurrent calls
- [ ] **Acceptance Criteria:** 
  - All tests pass
  - No errors in logs
  - Cache hit rate >60% after 10 calls
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

---

### Phase 3: Monitoring

#### 3.1 Metrics Schema
- [ ] **Task:** Update `convex/callMetrics.ts` schema
- [ ] **Task:** Add SPL metrics fields:
  - `splLayer0Count: v.number()` - Validation rejections
  - `splLayer1aCount: v.number()` - Keyword/fuzzy matches
  - `splLayer1bCount: v.number()` - Embedding matches
  - `splLayer2Count: v.number()` - LLM calls (novel queries)
  - `splTotalSavings: v.number()` - Estimated cost saved ($)
  - `splAvgLatency: v.number()` - Average SPL processing time (ms)
  - `splHitRate: v.number()` - Overall cache hit rate (0.0-1.0)
  - `splKeywordHitRate: v.number()` - Layer 1a success rate
  - `splEmbeddingHitRate: v.number()` - Layer 1b success rate
- [ ] **Task:** Deploy schema update
- [ ] **Verification:**
  - Check Convex dashboard for new fields
  - Verify all counters initialize to 0
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:** Granular metrics for hybrid architecture analysis

#### 3.2 Metrics Collection
- [ ] **Task:** Update audio_handler.py to record SPL metrics
- [ ] **Task:** Increment layer counters based on decision.layer and decision.method:
  - Layer 0 → splLayer0Count++
  - Layer 1a (keyword/fuzzy) → splLayer1aCount++
  - Layer 1b (embedding) → splLayer1bCount++
  - Layer 2 → splLayer2Count++
- [ ] **Task:** Calculate cost savings:
  - Layer 0: $0 (validation)
  - Layer 1a: Saved $0.01 (vs LLM)
  - Layer 1b: Saved $0.0099 ($0.01 - $0.0001)
  - Layer 2: $0.01 (LLM cost)
- [ ] **Task:** Track latency per layer:
  - Layer 0: <1ms
  - Layer 1a: 0-2ms
  - Layer 1b: 50-100ms
  - Layer 2: 300ms+
- [ ] **Verification:**
  - Make test calls, check callMetrics table
  - Verify counters increment correctly
  - Verify cost calculations are accurate
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:** Layer 1b cost includes OpenAI embedding API call
  - Make test calls, check callMetrics table
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 3.3 Analytics API
- [ ] **Task:** Create `app/api/v1/spl_analytics.py` (NEW)
- [ ] **Task:** Implement endpoint: `GET /api/v1/analytics/spl-stats/{organization_id}`
- [ ] **Task:** Return aggregated stats:
  - Total requests
  - Layer breakdown (Layer 0, 1a, 1b, 2 counts)
  - LLM calls vs suppressed calls
  - Suppression rate (%)
  - Keyword hit rate (Layer 1a success %)
  - Embedding hit rate (Layer 1b success %)
  - Total savings ($)
  - Cost breakdown by layer
- [ ] **Verification:**
  - Test API: `curl http://localhost:8000/api/v1/analytics/spl-stats/test-org`
  - Verify breakdown shows hybrid architecture performance
- [ ] **Status:** ⬜ Not Started
- [ ] **Files Modified:**
  - `app/api/v1/spl_analytics.py` (NEW)
  - `app/api/v1/__init__.py` (register router)
- [ ] **Notes:** Dashboard should show Layer 1a vs 1b effectiveness

#### 3.4 Pattern Performance Tracking
- [ ] **Task:** Create `app/services/spl_analytics_service.py` (NEW)
- [ ] **Task:** Implement `track_pattern_feedback()` method
- [ ] **Task:** Implement auto-deactivation for low-performing patterns (<60% success)
- [ ] **Verification:**
  - Simulate low-performing pattern, verify deactivation
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 3.5 Testing - Phase 3
- [ ] **Task:** Test metrics collection
- [ ] **Task:** Test analytics API
- [ ] **Task:** Verify pattern deactivation
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

---

### Phase 4: Optimization

#### 4.1 Domain-Specific Patterns
- [ ] **Task:** Update `app/domains/registry.py`
- [ ] **Task:** Add `spl_pattern_templates` to `DomainConfig`
- [ ] **Task:** Define patterns for each domain:
  - HOSPITALITY (restaurant): menu_search, specials, reservations
  - PHARMACY: medication_search, prescription_refill
  - HOTEL: room_availability, booking
  - RETAIL: product_search, inventory_check
- [ ] **Verification:**
  - Bootstrap patterns for each domain
  - Test domain-specific queries
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 4.2 A/B Testing Configuration
- [ ] **Task:** Add SPL config to `config.json` or env vars
- [ ] **Task:** Implement feature flags:
  - `spl.enabled` (bool)
  - `spl.similarity_threshold` (float)
  - `spl.min_confidence_to_learn` (float)
  - `spl.rollout.percentage` (int, 0-100)
  - `spl.rollout.whitelist` (array)
  - `spl.rollout.blacklist` (array)
- [ ] **Task:** Implement rollout logic in SPL service
- [ ] **Verification:**
  - Test with 50% rollout
  - Verify whitelist/blacklist works
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 4.3 Performance Tuning
- [ ] **Task:** Profile Layer 1a keyword matching latency (target: <1ms)
- [ ] **Task:** Profile Layer 1b embedding generation latency (target: <100ms)
- [ ] **Task:** Optimize keyword dictionaries (use hash sets)
- [ ] **Task:** Optimize cache sizes (tune LRU limits)
- [ ] **Task:** Consider caching OpenAI embeddings (avoid regenerating)
- [ ] **Task:** Pre-load common patterns on service startup
- [ ] **Task:** Monitor OpenAI API rate limits for Layer 1b
- [ ] **Verification:**
  - Measure P50, P95, P99 latencies per layer
  - Target: Layer 1a < 1ms, Layer 1b < 100ms (P95)
  - Verify 80%+ queries caught by Layer 1a
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:** Layer 1a should handle majority; optimize for speed

#### 4.4 Testing - Phase 4
- [ ] **Task:** Load testing with 100 concurrent calls
- [ ] **Task:** Test A/B rollout
- [ ] **Task:** Test domain-specific patterns
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

---

### Phase 5: Production Hardening

#### 5.1 Error Handling
- [ ] **Task:** Add try-catch around SPL processing
- [ ] **Task:** Graceful fallback to LLM if SPL fails
- [ ] **Task:** Alert on SPL errors (> 5% error rate)
- [ ] **Verification:**
  - Simulate SPL service failure
  - Verify calls still work (fallback to LLM)
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 5.2 Documentation
- [ ] **Task:** Create `docs/SPL_ARCHITECTURE.md`
- [ ] **Task:** Document API endpoints
- [ ] **Task:** Document configuration options
- [ ] **Task:** Create troubleshooting guide
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 5.3 Deployment Checklist
- [ ] **Task:** Review all code changes
- [ ] **Task:** Run full test suite
- [ ] **Task:** Load testing (1000 calls)
- [ ] **Task:** Backup Convex database
- [ ] **Task:** Prepare rollback plan
- [ ] **Task:** Deploy to staging environment
- [ ] **Task:** Staging validation (24 hours)
- [ ] **Task:** Deploy to production (gradual rollout)
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

#### 5.4 Final Testing
- [ ] **Task:** Production smoke tests
- [ ] **Task:** Monitor error rates (< 0.1%)
- [ ] **Task:** Monitor latency (no degradation)
- [ ] **Task:** Monitor cost savings (> 40% after week 1)
- [ ] **Status:** ⬜ Not Started
- [ ] **Notes:**

---

## 🧪 Testing & Verification

### Testing Strategy

#### Unit Tests
**Location:** `tests/test_spl_service.py`

```bash
# Run unit tests
pytest tests/test_spl_service.py -v

# Run with coverage
pytest tests/test_spl_service.py --cov=app.services.spl_service --cov-report=html
```

**Test Cases:**
1. ✅ Layer 0 validation (short, long, blocklist)
2. ✅ Pattern matching (exact, semantic, threshold)
3. ✅ Pattern learning (confidence, storage)
4. ✅ Cache operations (get, set, invalidate)
5. ✅ Multi-tenancy (organization isolation)

#### Integration Tests
**Location:** `tests/test_spl_integration.py`

```bash
# Run integration tests
pytest tests/test_spl_integration.py -v
```

**Test Cases:**
1. ✅ End-to-end call with SPL (Layer 1 hit)
2. ✅ Novel query → Layer 2 → Pattern learning
3. ✅ Multiple organizations (no cross-contamination)
4. ✅ Concurrent calls (thread safety)
5. ✅ Error handling (SPL failure → LLM fallback)

#### Manual Testing Protocol

**Test Scenario 1: First-Time Query**
```
1. Clean SPL cache (see Cache Management below)
2. Call test number
3. Say: "What are your hours?"
4. Expected: Layer 2 (Groq LLM called)
5. Verify: Check logs for "SPL Layer 2"
6. Verify: Pattern learned (check Convex)
```

**Test Scenario 2: Repeated Query**
```
1. Call test number again
2. Say: "What are your hours?"
3. Expected: Layer 1 (cache hit)
4. Verify: Check logs for "SPL Layer 1"
5. Verify: Response < 50ms
6. Verify: No Groq API call (check API logs)
```

**Test Scenario 3: Semantic Similarity**
```
1. Call test number
2. Say: "When do you close?"
3. Expected: Layer 1 (semantic match to "hours" pattern)
4. Verify: Check logs for similarity score > 0.75
```

**Test Scenario 4: Invalid Input**
```
1. Call test number
2. Say: "a" (single character)
3. Expected: Layer 0 (validation rejection)
4. Verify: Response: "I didn't catch that"
5. Verify: No LLM call, < 1ms latency
```

#### Load Testing

**Tool:** `locust` or `k6`

```python
# tests/load_test_spl.py
from locust import HttpUser, task, between

class VoiceAgentUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def make_call(self):
        # Simulate voice call
        self.client.post("/api/v1/sessions/create-from-number", json={
            "phoneNumber": "+1234567890",
            "callType": "inbound"
        })
```

**Run Load Test:**
```bash
# 100 concurrent users, 1000 total calls
locust -f tests/load_test_spl.py --headless -u 100 -r 10 -t 5m
```

**Acceptance Criteria:**
- ✅ P95 latency < 500ms (overall)
- ✅ P95 SPL Layer 1 latency < 10ms
- ✅ Error rate < 0.1%
- ✅ Cache hit rate > 60% (after 100 calls)

---

## 🧹 Cache & Storage Management

### SPL Cache Cleanup Utilities

#### Script 1: Clear Organization Patterns

**File:** `scripts/clean_spl_cache.py` (NEW)

```python
"""
Clean SPL cache and patterns for testing.
Usage:
  python scripts/clean_spl_cache.py --org test-org  # Clear specific org
  python scripts/clean_spl_cache.py --all           # Clear all orgs
  python scripts/clean_spl_cache.py --dry-run       # Preview only
"""

import asyncio
import argparse
from app.core.convex_client import get_convex_client
from app.services.spl_service import get_spl_service
from app.core.logging import get_logger

logger = get_logger(__name__)


async def clear_organization_patterns(organization_id: str, dry_run: bool = False):
    """Clear all SPL patterns for an organization"""
    convex = get_convex_client()
    
    # Get all patterns
    patterns = await convex.query(
        "spl_patterns:getByOrganization",
        {"organizationId": organization_id}
    )
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Found {len(patterns)} patterns for {organization_id}")
    
    for pattern in patterns:
        print(f"  - {pattern['patternKey']} (hits: {pattern['hitCount']})")
        
        if not dry_run:
            await convex.mutation(
                "spl_patterns:deletePattern",
                {"patternId": pattern['_id']}
            )
    
    if not dry_run:
        # Invalidate cache
        spl = get_spl_service(organization_id)
        await spl.invalidate_cache()
        print(f"✓ Cleared {len(patterns)} patterns and cache for {organization_id}")
    else:
        print(f"[DRY RUN] Would clear {len(patterns)} patterns")


async def clear_all_patterns(dry_run: bool = False):
    """Clear all SPL patterns across all organizations"""
    convex = get_convex_client()
    
    # This would require a Convex query to list all organizations
    # For now, just clear the patterns table
    
    if not dry_run:
        print("⚠️  WARNING: This will clear ALL patterns for ALL organizations!")
        confirm = input("Type 'DELETE ALL' to confirm: ")
        if confirm != "DELETE ALL":
            print("Aborted.")
            return
        
        # Implementation: Convex mutation to clear all patterns
        print("✓ Cleared all patterns")
    else:
        print("[DRY RUN] Would clear all patterns")


async def main():
    parser = argparse.ArgumentParser(description="Clean SPL cache and patterns")
    parser.add_argument("--org", type=str, help="Organization ID to clean")
    parser.add_argument("--all", action="store_true", help="Clear all organizations")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't delete")
    
    args = parser.parse_args()
    
    if args.all:
        await clear_all_patterns(dry_run=args.dry_run)
    elif args.org:
        await clear_organization_patterns(args.org, dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
```

#### Script 2: Reset SPL Statistics

**File:** `scripts/reset_spl_stats.py` (NEW)

```python
"""
Reset SPL statistics (hit counts, success rates) for testing.
Usage:
  python scripts/reset_spl_stats.py --org test-org
"""

import asyncio
import argparse
from app.core.convex_client import get_convex_client


async def reset_statistics(organization_id: str):
    """Reset hit counts and success rates to zero"""
    convex = get_convex_client()
    
    patterns = await convex.query(
        "spl_patterns:getByOrganization",
        {"organizationId": organization_id}
    )
    
    print(f"Resetting statistics for {len(patterns)} patterns...")
    
    for pattern in patterns:
        await convex.mutation(
            "spl_patterns:resetStatistics",
            {
                "patternId": pattern['_id'],
                "hitCount": 0,
                "successRate": 1.0
            }
        )
        print(f"  ✓ Reset {pattern['patternKey']}")
    
    print(f"✓ Reset statistics for {organization_id}")


async def main():
    parser = argparse.ArgumentParser(description="Reset SPL statistics")
    parser.add_argument("--org", type=str, required=True, help="Organization ID")
    
    args = parser.parse_args()
    await reset_statistics(args.org)


if __name__ == "__main__":
    asyncio.run(main())
```

#### Script 3: Inspect SPL Cache

**File:** `scripts/inspect_spl_cache.py` (NEW)

```python
"""
Inspect SPL cache and patterns for debugging.
Usage:
  python scripts/inspect_spl_cache.py --org test-org
  python scripts/inspect_spl_cache.py --org test-org --verbose
"""

import asyncio
import argparse
from app.core.convex_client import get_convex_client
from tabulate import tabulate


async def inspect_patterns(organization_id: str, verbose: bool = False):
    """Display all patterns with statistics"""
    convex = get_convex_client()
    
    patterns = await convex.query(
        "spl_patterns:getByOrganization",
        {"organizationId": organization_id}
    )
    
    if not patterns:
        print(f"No patterns found for {organization_id}")
        return
    
    print(f"\n{'='*80}")
    print(f"SPL Patterns for: {organization_id}")
    print(f"{'='*80}\n")
    
    # Summary table
    table_data = []
    for p in patterns:
        table_data.append([
            p['patternKey'],
            "✅" if p['isActive'] else "❌",
            p['hitCount'],
            f"{p['successRate']:.1%}",
            f"{p['confidence']:.2f}",
            p['responseType']
        ])
    
    headers = ["Pattern Key", "Active", "Hits", "Success", "Confidence", "Type"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Detailed view
    if verbose:
        print(f"\n{'='*80}")
        print("DETAILED VIEW")
        print(f"{'='*80}\n")
        
        for p in patterns:
            print(f"Pattern: {p['patternKey']}")
            print(f"  Active: {p['isActive']}")
            print(f"  Hits: {p['hitCount']}")
            print(f"  Success Rate: {p['successRate']:.1%}")
            print(f"  Confidence: {p['confidence']:.2f}")
            print(f"  Response Type: {p['responseType']}")
            print(f"  Example Queries: {', '.join(p['exampleQueries'][:3])}")
            print(f"  Cached Response: {p['cachedResponse'][:100]}...")
            print()


async def main():
    parser = argparse.ArgumentParser(description="Inspect SPL cache")
    parser.add_argument("--org", type=str, required=True, help="Organization ID")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed view")
    
    args = parser.parse_args()
    await inspect_patterns(args.org, verbose=args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
```

### Cache Cleanup Commands

```bash
# Before each test run:

# 1. Clear patterns for test organization
python scripts/clean_spl_cache.py --org test-org

# 2. Reset statistics (keep patterns, reset counters)
python scripts/reset_spl_stats.py --org test-org

# 3. Inspect current state
python scripts/inspect_spl_cache.py --org test-org

# 4. Bootstrap fresh patterns
python scripts/bootstrap_spl_patterns.py test-org

# 5. Verify patterns loaded
python scripts/inspect_spl_cache.py --org test-org --verbose
```

### Testing Workflow with Clean State

```bash
# Complete clean testing workflow
./scripts/clean_test_spl.sh test-org

# Where clean_test_spl.sh contains:
#!/bin/bash
ORG_ID=$1

echo "🧹 Cleaning SPL state for $ORG_ID..."
python scripts/clean_spl_cache.py --org $ORG_ID

echo "🔄 Resetting statistics..."
python scripts/reset_spl_stats.py --org $ORG_ID

echo "🌱 Bootstrapping fresh patterns..."
python scripts/bootstrap_spl_patterns.py $ORG_ID

echo "🔍 Inspecting final state..."
python scripts/inspect_spl_cache.py --org $ORG_ID

echo "✅ Ready for testing!"
```

---

## 🔄 Rollback Plan

### If Issues Arise

#### Emergency Rollback (Disable SPL)

**Option 1: Feature Flag (Instant)**
```python
# config.json or environment variable
SPL_ENABLED=false

# Or in code:
class SPLService:
    def __init__(self, organization_id: str):
        self.enabled = os.getenv("SPL_ENABLED", "true").lower() == "true"
    
    async def process_utterance(self, transcript: str, context: Dict) -> SPLDecision:
        if not self.enabled:
            # Bypass SPL, go straight to Layer 2
            return SPLDecision(
                should_call_llm=True,
                cached_response=None,
                layer=2,
                method="spl_disabled",
                confidence=0.0
            )
        # ... normal SPL logic
```

**Option 2: Code Rollback**
```bash
# Revert WebSocket handler changes
git diff websocket_server/handlers/audio_handler.py
git checkout HEAD -- websocket_server/handlers/audio_handler.py

# Restart servers
pm2 restart all
```

#### Partial Rollback (Specific Organization)

```python
# Disable SPL for specific organization
await convex.mutation("organizations:update", {
    "organizationId": "problematic-org",
    "config": {"spl_enabled": false}
})
```

#### Full Rollback Checklist

- [ ] Disable SPL feature flag
- [ ] Revert code changes (if needed)
- [ ] Verify calls work normally
- [ ] Monitor error rates (should drop to baseline)
- [ ] Monitor latency (should return to baseline)
- [ ] Post-mortem: Document what went wrong

---

## 📊 Progress Log

### Week 1: Foundation (Jan 3 - Jan 10, 2026)

#### Day 1 (Jan 3, 2026)
- [x] ✅ Created implementation plan (this document)
- [ ] Added dependencies to requirements.txt
- [ ] Status: 🟡 In Progress
- [ ] Notes: Planning phase complete

#### Day 2 (Jan 4, 2026)
- [ ] Task:
- [ ] Status: ⬜ Not Started
- [ ] Notes:

#### Day 3 (Jan 5, 2026)
- [ ] Task:
- [ ] Status: ⬜ Not Started
- [ ] Notes:

---

### Week 2: Foundation Completion (Jan 11 - Jan 17, 2026)

#### Day 8-14
- [ ] Tasks:
- [ ] Status: ⬜ Not Started
- [ ] Notes:

---

### Week 3-4: Integration (Jan 18 - Jan 31, 2026)

#### Progress
- [ ] Tasks:
- [ ] Status: ⬜ Not Started
- [ ] Notes:

---

### Week 5: Monitoring (Feb 1 - Feb 7, 2026)

#### Progress
- [ ] Tasks:
- [ ] Status: ⬜ Not Started
- [ ] Notes:

---

### Week 6-7: Optimization (Feb 8 - Feb 21, 2026)

#### Progress
- [ ] Tasks:
- [ ] Status: ⬜ Not Started
- [ ] Notes:

---

### Week 8: Production Hardening (Feb 22 - Feb 28, 2026)

#### Progress
- [ ] Tasks:
- [ ] Status: ⬜ Not Started
- [ ] Notes:

---

## 📈 Success Metrics

### Target Metrics (End of Week 8)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Cost Reduction** | 85-95% | Compare Groq API costs before/after |
| **Suppression Rate** | 90%+ | (Layer 0 + Layer 1a + Layer 1b) / Total requests |
| **Layer 1a Hit Rate** | 75-85% | Keyword matches / Total requests |
| **Layer 1b Hit Rate** | 10-15% | Embedding matches / Total requests |
| **Layer 1a Latency** | <1ms (P95) | Keyword matching time |
| **Layer 1b Latency** | <100ms (P95) | OpenAI embedding + similarity |
| **Error Rate** | <0.1% | SPL errors / Total requests |
| **Pattern Learning Rate** | 5-10 patterns/day/org | New patterns created |
| **OpenAI Embedding Cost** | <$0.50/day | Layer 1b API usage |

### Performance Breakdown Target (Steady State)

| Layer | % of Requests | Avg Latency | Cost per Request | Status |
|-------|---------------|-------------|------------------|--------|
| **Layer 0** (Validation) | 2-5% | <1ms | $0 | Rejected |
| **Layer 1a** (Keyword) | 75-80% | <1ms | $0 | ✅ Cached |
| **Layer 1b** (Embedding) | 10-15% | 50ms | $0.0001 | ✅ Cached |
| **Layer 2** (LLM) | 5-10% | 300ms | $0.01 | Novel query |

### Weekly Checkpoints

**Week 1:**
- [ ] All dependencies installed
- [ ] Convex schema deployed
- [ ] SPL service implemented
- [ ] Unit tests passing

**Week 2:**
- [ ] WebSocket integration complete
- [ ] Pattern learning working
- [ ] Integration tests passing

**Week 3:**
- [ ] Metrics collection working
- [ ] Analytics API deployed
- [ ] Dashboard accessible

**Week 4:**
- [ ] 40%+ cost reduction observed
- [ ] Domain patterns deployed
- [ ] A/B testing configured

**Week 5:**
- [ ] 70%+ cost reduction observed
- [ ] Load tests passing
- [ ] Production deployment plan finalized

**Week 6:**
- [ ] 85%+ cost reduction observed
- [ ] All tests green
- [ ] Documentation complete
- [ ] **READY FOR PRODUCTION**

---

## 📝 Implementation Notes

### Key Considerations

1. **Multi-Tenancy:** Always scope operations by `organization_id`
2. **Backward Compatibility:** Existing calls must work unchanged
3. **Graceful Degradation:** If SPL fails, fallback to LLM
4. **Hybrid Performance:** Layer 1a should catch 80%+, Layer 1b catches 15%, LLM only 5%
5. **Cost Optimization:** Reuse existing OpenAI infrastructure, minimize new API costs
6. **Testing:** Clean state before each test run

### Common Pitfalls to Avoid

- ❌ Don't hardcode organization IDs
- ❌ Don't skip Layer 1a (keyword) - it's the fastest and cheapest
- ❌ Don't call OpenAI embeddings for simple keyword matches
- ❌ Don't skip error handling (always have fallback)
- ❌ Don't forget to invalidate cache after pattern updates
- ❌ Don't test without cleaning cache first
- ❌ Don't forget to track Layer 1a vs 1b separately in metrics

### Architecture Decision: Why Hybrid?

**Rationale:**
- **80% of queries are simple** → Layer 1a (keywords) handles them instantly at $0
- **15% have variations** → Layer 1b (embeddings) handles semantic similarity at $0.0001
- **5% are novel** → Layer 2 (LLM) handles new queries at $0.01

**Cost Comparison:**
```
Without SPL: 100 queries × $0.01 = $1.00

With Hybrid SPL:
- 80 queries × $0 (Layer 1a keywords) = $0
- 15 queries × $0.0001 (Layer 1b embeddings) = $0.0015
- 5 queries × $0.01 (Layer 2 LLM) = $0.05
Total: $0.0515 (95% savings!)

With Embeddings Only:
- 95 queries × $0.0001 (embeddings) = $0.0095
- 5 queries × $0.01 (LLM) = $0.05
Total: $0.0595 (94% savings, but slower)
```

**Why Not sentence-transformers?**
- Would need to download/load 80MB model (adds complexity)
- Inference time: ~5ms per query
- OpenAI API: Reuses existing infrastructure, no model management
- OpenAI embeddings: Same as RAG (1536-dim), proven quality

### Quick Reference

**Start Servers:**
```bash
# Terminal 1: Convex
npx convex dev

# Terminal 2: FastAPI
python start.py

# Terminal 3: WebSocket
python websocket_server/server.py
```

**Run Tests:**
```bash
# Unit tests
pytest tests/test_spl_service.py -v

# Integration tests
pytest tests/test_spl_integration.py -v

# All tests
pytest -v
```

**Clean SPL State:**
```bash
python scripts/clean_spl_cache.py --org test-org
python scripts/reset_spl_stats.py --org test-org
python scripts/inspect_spl_cache.py --org test-org --verbose
```

---

## 🎯 Next Actions

### Immediate Next Steps (Do This Now)

1. ✅ Review this plan thoroughly
2. ⬜ Confirm approach with team
3. ⬜ Set up development environment
4. ⬜ Start Phase 1, Task 1.1 (Dependencies)

### Daily Standup Questions

1. What did you complete yesterday?
2. What are you working on today?
3. Any blockers?
4. Does testing show expected results?

---

**Last Updated:** January 3, 2026  
**Document Owner:** Development Team  
**Review Schedule:** Update daily during implementation

