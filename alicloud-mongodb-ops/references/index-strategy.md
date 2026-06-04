# Index Strategy — Alibaba Cloud MongoDB

## Overview

### MongoDB Indexing Fundamentals

MongoDB indexes are data structures that improve query performance by reducing the number of documents scanned. Understanding index fundamentals is essential for optimizing MongoDB performance on Alibaba Cloud.

#### B-tree Structure

MongoDB uses B-tree indexes as the primary index structure:

- **Ordered Data**: Indexes maintain sorted order of indexed field values
- **Efficient Navigation**: B-tree allows logarithmic time complexity O(log n) for lookups
- **Range Queries**: Supports efficient range scans due to ordered structure
- **Compound Support**: Multiple fields in single index follow B-tree ordering

```
B-tree Index Structure:
           [50]
          /    \
      [25,40]  [75,90]
      /  |  \   /  |  \
    Leaf nodes contain document references
```

#### Index Types on Alibaba Cloud MongoDB

| Index Type | Description | Use Case |
|------------|-------------|----------|
| **Single Field** | Index on one field | Simple queries, sorting |
| **Compound Index** | Multiple fields indexed together | Multi-field queries, covered queries |
| **Multikey Index** | Index on array fields | Array element queries |
| **Text Index** | Full-text search | Search across string content |
| **Hashed Index** | Hash of field value | Sharding, uniform distribution |
| **Geospatial** | 2dsphere, 2d indexes | Location-based queries |
| **TTL Index** | Auto-expiring documents | Session data, logs, temporary records |
| **Partial Index** | Filtered index subset | Conditional queries, space optimization |
| **Sparse Index** | Excludes null/missing | Optional field queries |
| **Wildcard Index** | Dynamic field matching | Schema-less queries |

#### Index Impact on Write Performance

Every index adds overhead to write operations:

| Operation | Index Impact | Performance Consideration |
|-----------|--------------|---------------------------|
| **Insert** | Update all indexes | O(index_count) overhead |
| **Update** | Update affected indexes | If indexed field modified |
| **Delete** | Remove from all indexes | O(index_count) overhead |
| **Bulk Write** | Batch index updates | More efficient than individual |

**Write Performance Formula**:
```
Write latency = Base latency + (Index count × Index update time)
```

**Recommendations**:
- Limit indexes on high-write collections
- Use partial/sparse indexes to reduce overhead
- Consider write concern for index durability
- Schedule index builds during low-traffic periods

---

## Compound Index Strategy

### ESR Rule (Equality, Sort, Range)

The ESR rule defines optimal compound index field ordering:

**Priority Order**:
1. **E**quality fields first (exact match conditions)
2. **S**ort fields second (ordering requirements)
3. **R**ange fields last (comparison conditions)

**Why ESR Works**:
- Equality filters narrow the search space most efficiently
- Sort fields should be after equality to avoid in-memory sorting
- Range fields after sort prevents scanning non-sorted ranges

**Example Query**:
```javascript
db.users.find({ status: "active", age: { $gte: 18, $lte: 65 } })
         .sort({ created_at: -1 })
         .limit(100)
```

**Optimal Index (ESR Order)**:
```javascript
// Equality: status = "active"
// Sort: created_at descending
// Range: age >= 18 AND age <= 65
db.users.createIndex({ status: 1, created_at: -1, age: 1 })
```

**Index Field Explanation**:
| Position | Field | Reason |
|----------|-------|--------|
| 1st | `status: 1` | Equality filter - most selective first |
| 2nd | `created_at: -1` | Sort order matches query |
| 3rd | `age: 1` | Range filter - last position |

### Prefix Principle for Multi-field Queries

Compound indexes support queries on index prefixes:

**Index**: `{name: 1, age: -1, created_at: 1}`

**Supported Queries**:
| Query Pattern | Uses Index? | Notes |
|---------------|-------------|-------|
| `{name: "John"}` | Yes | First field prefix |
| `{name: "John", age: 25}` | Yes | First two fields prefix |
| `{name: "John", age: 25, created_at: ...}` | Yes | Full index |
| `{age: 25}` | No | Not a prefix (skips name) |
| `{created_at: ...}` | No | Not a prefix (skips name, age) |

**Prefix Rules**:
- Index supports leftmost prefix queries
- Skipping fields breaks index usage
- Order matters for compound queries

### Index Intersection Considerations

MongoDB can use multiple indexes for a single query (index intersection):

**When Intersection Occurs**:
```javascript
// Query with two separate conditions
db.products.find({ category: "electronics", price: { $lt: 1000 } })

// Two separate indexes
db.products.createIndex({ category: 1 })
db.products.createIndex({ price: 1 })

// MongoDB may intersect both indexes
```

**Intersection vs Compound Index**:

| Scenario | Compound Index | Index Intersection |
|----------|---------------|-------------------|
| **Selectivity** | Better for high selectivity | Better for low selectivity |
| **Sort Support** | Supports sorting | Cannot use for sorting |
| **Covered Query** | Can cover query | Cannot cover |
| **Write Overhead** | One index to update | Multiple indexes to update |

**Recommendation**:
- Prefer compound index when queries frequently combine conditions
- Use intersection for infrequent combined queries with separate frequent queries

### Covered Queries Optimization

A covered query retrieves all data from the index without examining documents:

**Requirements**:
1. All query fields are in the index
2. All returned fields are in the index
3. Query excludes `_id` or `_id` is in index

**Example**:
```javascript
// Query
db.orders.find(
  { status: "completed", customer_id: "C123" },
  { _id: 0, status: 1, customer_id: 1, total: 1 }
)

// Covered index (includes all projection fields)
db.orders.createIndex({ status: 1, customer_id: 1, total: 1 })

// Verify covered query
db.orders.explain("executionStats").find(...)
// Look for: "totalDocsExamined": 0, "stage": "IXSCAN"
```

**Covered Query Benefits**:
- No document reads (I/O reduction)
- Faster response time
- Reduced memory usage
- Better CPU efficiency

### Compound Index Examples

**Pattern 1: User Profile Queries**:
```javascript
// Query pattern: name + age range + sort by created
db.users.createIndex({ name: 1, created_at: -1, age: 1 })

// Query pattern: status + department + sort by salary
db.employees.createIndex({ status: 1, department: 1, salary: -1 })
```

**Pattern 2: Time-series Data**:
```javascript
// Query pattern: device_id + time range + metric type
db.metrics.createIndex({ device_id: 1, timestamp: -1, metric_type: 1 })

// Query pattern: region + date + status
db.logs.createIndex({ region: 1, date: -1, status: 1 })
```

**Pattern 3: E-commerce Search**:
```javascript
// Query pattern: category + price range + sort by rating
db.products.createIndex({ category: 1, rating: -1, price: 1 })

// Query pattern: brand + availability + sort by discount
db.inventory.createIndex({ brand: 1, availability: 1, discount: -1 })
```

---

## TTL Index

### Automatic Document Expiration

TTL (Time-To-Live) indexes automatically remove documents after a specified time:

**Key Characteristics**:
- Single field index on date/date-array field
- Documents expire after `expireAfterSeconds`
- Background thread runs deletion every ~60 seconds
- Deletion order follows oldest-first principle

### TTL Delete Interval

**Mechanism**:
- TTL monitor thread runs every 60 seconds
- Batch deletion removes expired documents
- Deletion continues until thread yields or completes
- High deletion volume may extend cleanup time

**Timing Consideration**:
| Factor | Impact |
|--------|---------|
| Document count | More docs = longer cleanup cycle |
| Index size | Larger index = more scan time |
| System load | High load may delay cleanup |
| Write traffic | High writes may compete with TTL |

### Use Cases

| Use Case | TTL Setting | Index Field |
|----------|-------------|-------------|
| **Session Data** | 30 minutes - 24 hours | `last_access` or `created_at` |
| **Event Logs** | 7-30 days | `timestamp` |
| **Cache Documents** | 1-24 hours | `cache_time` |
| **Temporary Records** | Task duration + buffer | `expire_at` |
| **Rate Limiting** | Window duration | `window_start` |
| **OTP/Tokens** | 5-15 minutes | `created_at` |

### Creation via MongoDB Shell

**Basic TTL Index**:
```javascript
// Documents expire 1 hour after created_at value
db.sessions.createIndex(
  { created_at: 1 },
  { expireAfterSeconds: 3600 }
)
```

**Custom Expiration Time**:
```javascript
// Documents expire at specific date stored in expire_at field
db.events.createIndex(
  { expire_at: 1 },
  { expireAfterSeconds: 0 }  // Expire exactly at expire_at value
)
```

**TTL with Partial Index**:
```javascript
// Only expire documents matching filter
db.logs.createIndex(
  { timestamp: 1 },
  {
    expireAfterSeconds: 86400,  // 24 hours
    partialFilterExpression: { temp_log: true }
  }
)
```

### Monitoring TTL Deletion Rate

**Key Metrics to Monitor**:
```javascript
// Check TTL index exists
db.collection.getIndexes()

// Monitor TTL deletion via serverStatus
db.serverStatus().metrics.ttl

// Output example:
{
  "ttl": {
    "deletedDocuments": 15420,
    "passes": 245
  }
}
```

**Alibaba Cloud Monitoring**:
- Use DAS (Database Autonomy Service) for TTL monitoring
- Monitor collection size trends
- Track write/delete rate balance
- Alert on unusual TTL delays

**Troubleshooting TTL**:
| Issue | Diagnosis | Resolution |
|-------|-----------|------------|
| Documents not deleted | Check field type (must be Date) | Ensure proper BSON Date format |
| Delayed deletion | High system load | Schedule during low-traffic |
| Partial deletion | Partial index filter | Verify filter expression |
| Index not created | Invalid options | Check expireAfterSeconds >= 0 |

---

## Text Index

### Full-text Search Capabilities

MongoDB text indexes enable full-text search on string content:

**Features**:
- Tokenization of string content
- Language-specific stemming
- Case-insensitive matching
- Stopword filtering
- Phrase search support
- Relevance scoring

### Multi-language Support

**Supported Languages**:
```javascript
// Specify language during creation
db.articles.createIndex(
  { content: "text", title: "text" },
  { default_language: "english" }
)

// Available languages (partial list):
// english, chinese, french, german, spanish, portuguese,
// russian, japanese, korean, italian, dutch, norwegian, etc.
```

**Chinese Text Search**:
```javascript
// Chinese text index (important for Alibaba Cloud users)
db.posts.createIndex(
  { content: "text" },
  {
    default_language: "chinese",
    weights: { content: 10, title: 5 }
  }
)
```

### Text Index Limitations

| Limitation | Description |
|------------|-------------|
| **One per collection** | Only one text index allowed per collection |
| **Compound restriction** | Cannot combine with other types in same index |
| **Field type** | Only string/string-array fields |
| **Memory usage** | High memory for large collections |
| **Storage overhead** | Can be 2-10x of indexed data |
| **Query complexity** | Limited compared to dedicated search engines |

### $text Query Operator Usage

**Basic Text Search**:
```javascript
db.articles.find({ $text: { $search: "mongodb index optimization" } })
```

**Phrase Search**:
```javascript
// Exact phrase (escape quotes)
db.articles.find({ $text: { $search: "\"compound index\" optimization" } })
```

**Negation**:
```javascript
// Exclude terms with minus sign
db.articles.find({ $text: { $search: "mongodb -mysql" } })
```

**Language Override**:
```javascript
db.articles.find(
  { $text: { $search: "optimisation", $language: "english" } }
)
```

**Case/Diacritic Sensitivity**:
```javascript
db.articles.find(
  {
    $text: {
      $search: "MongoDB",
      $caseSensitive: true,
      $diacriticSensitive: true
    }
  }
)
```

### Relevance Scoring with Weights

**Configure Field Weights**:
```javascript
db.blog.createIndex(
  { title: "text", content: "text", tags: "text" },
  {
    weights: {
      title: 10,    // Highest weight
      content: 5,   // Medium weight
      tags: 2       // Lower weight
    },
    default_language: "english"
  }
)
```

**Project Relevance Score**:
```javascript
db.blog.find(
  { $text: { $search: "mongodb performance" } },
  { score: { $meta: "textScore" }, title: 1, content: 1 }
).sort({ score: { $meta: "textScore" } })
```

---

## Hashed Index for Sharding

### Uniform Distribution Guarantee

Hashed indexes ensure uniform data distribution across shards:

**Mechanism**:
- MongoDB hashes the indexed field value
- Hash determines shard assignment
- Distributes documents evenly across shards

**Hash Function**:
- Uses MongoDB's internal hash function
- Consistent hash across cluster
- Deterministic: same value → same shard

### Hashed Index on Shard Key

**Creation**:
```javascript
// Create hashed shard key index
db.users.createIndex({ user_id: "hashed" })

// Shard collection using hashed shard key
sh.shardCollection("mydb.users", { user_id: "hashed" })
```

**Sharding Commands**:
```javascript
// Enable sharding for database
sh.enableSharding("mydb")

// Shard collection with hashed key
sh.shardCollection("mydb.orders", { order_id: "hashed" })
```

### Limitations: No Range Queries on Hashed Field

| Query Type | Hashed Index Support |
|------------|---------------------|
| Exact match `{_id: "value"}` | Supported |
| Range `{_id: {$gt: ...}}` | Not supported |
| Sort `{_id: 1}` | Not supported |
| Compound `{_id: 1, other: 1}` | Not supported as shard key |

**Workaround for Range Queries**:
```javascript
// Create additional index for range queries
db.users.createIndex({ user_id: 1 })  // Regular index for ranges

// Shard key remains hashed
sh.shardCollection("mydb.users", { user_id: "hashed" })
```

### Creation Examples

**Single Shard Key**:
```javascript
db.logs.createIndex({ log_id: "hashed" })
sh.shardCollection("app.logs", { log_id: "hashed" })
```

**Choosing Hashed Shard Key**:
| Criteria | Recommendation |
|----------|----------------|
| High write volume | Hashed preferred (uniform writes) |
| Random access pattern | Hashed ideal |
| Range-based queries | Avoid hashed, use ranged |
| Monotonically increasing | Hashed prevents hotspot |
| Small cardinality | Avoid hashed (few chunks) |

---

## Specialized Indexes

### Geospatial (2dsphere, 2d)

**2dsphere Index** (GeoJSON, earth-like geometry):
```javascript
// Create 2dsphere index
db.places.createIndex({ location: "2dsphere" })

// GeoJSON document structure
{
  name: "Store Location",
  location: {
    type: "Point",
    coordinates: [121.47, 31.23]  // [longitude, latitude]
  }
}

// Nearby query
db.places.find({
  location: {
    $near: {
      $geometry: { type: "Point", coordinates: [121.47, 31.23] },
      $maxDistance: 1000  // meters
    }
  }
})

// Geo within polygon
db.places.find({
  location: {
    $geoWithin: {
      $geometry: {
        type: "Polygon",
        coordinates: [[
          [121.0, 31.0],
          [121.5, 31.0],
          [121.5, 31.5],
          [121.0, 31.5],
          [121.0, 31.0]
        ]]
      }
    }
  }
})
```

**2d Index** (Legacy, flat coordinate system):
```javascript
// Legacy 2d index (flat coordinates)
db.legacy.createIndex({ loc: "2d" })

// Query with 2d index
db.legacy.find({ loc: { $near: [121.47, 31.23], $maxDistance: 0.1 } })
```

### Partial Index (Filter Expression)

Partial indexes index only documents matching a filter expression:

**Creation**:
```javascript
// Index only active users
db.users.createIndex(
  { status: 1, email: 1 },
  { partialFilterExpression: { status: "active" }
)

// Index only high-value orders
db.orders.createIndex(
  { total: -1 },
  { partialFilterExpression: { total: { $gt: 10000 } } }
)
```

**Benefits**:
- Reduced storage overhead
- Lower write cost (fewer documents indexed)
- Better performance for filtered queries

**Query Requirements**:
- Query must match filter expression for index use
- Filter should match common query patterns

### Sparse Index (Null Exclusion)

Sparse indexes exclude documents without the indexed field (null/missing):

**Creation**:
```javascript
// Sparse index excludes documents without email
db.users.createIndex({ email: 1 }, { sparse: true })

// Sparse compound index
db.products.createIndex(
  { sku: 1, reviews: 1 },
  { sparse: true }
)
```

**Behavior**:
| Query | Sparse Index Used? |
|-------|-------------------|
| `{email: "test@example.com"}` | Yes |
| `{email: null}` | No (null excluded) |
| `{email: {$exists: false}}` | No |
| `{email: {$exists: true}}` | No (use non-sparse for this) |

### Collation-aware Indexes

Indexes with specific collation for string comparison:

**Creation**:
```javascript
// Case-insensitive collation index
db.names.createIndex(
  { name: 1 },
  { collation: { locale: "en", strength: 2 } }
)

// Chinese collation index
db.products.createIndex(
  { product_name: 1 },
  { collation: { locale: "zh" } }
)
```

**Collation Strength Levels**:
| Level | Comparison | Example |
|-------|------------|---------|
| 1 | Base characters | "a" = "A" = "á" |
| 2 | Base + accents | "a" = "A", "a" ≠ "á" |
| 3 | Base + accents + case | "a" ≠ "A" ≠ "á" |

**Query with Collation**:
```javascript
// Query must specify same collation
db.names.find({ name: "john" }).collation({ locale: "en", strength: 2 })
```

---

## Index Management via Alibaba Cloud

### DAS Integration for Index Analysis

Alibaba Cloud DAS (Database Autonomy Service) provides intelligent index analysis:

**DAS Capabilities**:
- Automatic slow query analysis
- Index recommendation engine
- Unused index detection
- Space usage optimization
- Real-time performance insights

**Integration with alicloud-das-ops**:
```yaml
# Call alicloud-das-ops skill for MongoDB index analysis
workflow:
  1. Connect to DAS service
  2. Query slow SQL analysis
  3. Retrieve index suggestions
  4. Evaluate recommendations
  5. Apply validated changes
```

### Index Suggestions from Performance Insights

**DAS Recommendation Types**:
| Type | Description | Action |
|------|-------------|--------|
| **Missing Index** | Slow query needs new index | Create recommended index |
| **Redundant Index** | Index covered by another | Remove redundant index |
| **Unused Index** | No queries using index | Drop after verification |
| **Suboptimal Order** | Compound index field order wrong | Reorder fields |
| **Large Index** | Index consuming too much space | Consider partial/sparse |

### Unused Index Detection

**MongoDB Shell Method**:
```javascript
// Get index usage statistics (MongoDB 3.2+)
db.collection.aggregate([
  { $indexStats: {} }
])

// Output shows usage count
{
  "name": "status_1",
  "accesses": { "ops": 1542, "since": ISODate("...") }
}
```

**DAS Unused Index Analysis**:
- Periodic analysis of index usage patterns
- Threshold: < 100 accesses in 30 days
- Automatic alert for potential removal
- Safe removal workflow with rollback

### Index Build in Production

**Background vs Foreground Index Build**:

| Method | MongoDB 4.2+ | Impact |
|---------|--------------|--------|
| **Foreground** | Not available | Blocks all operations |
| **Background** | Default behavior | Non-blocking builds |
| **Rolling Build** | Recommended for sharded | Per-shard build |

**Production Index Build Workflow**:
```javascript
// Modern MongoDB (4.2+) - all builds are non-blocking
db.collection.createIndex({ field: 1 })

// For large collections, monitor build progress
db.currentOp({
  $or: [
    { op: "command", "command.createIndexes": { $exists: true } },
    { op: "none", ns: /collection/ }
  ]
})

// Check build completion percentage
db.currentOp(true).inprog.forEach(function(op) {
  if (op.command && op.command.createIndexes) {
    print("Index build: " + op.command.createIndexes.name + 
          " - Progress: " + op.progress);
  }
});
```

**Alibaba Cloud Best Practices**:
- Schedule builds during maintenance window
- Use rolling builds for sharded clusters
- Monitor build progress via DAS
- Set appropriate timeout limits
- Test index performance post-build

---

## Index Optimization Playbooks

### Scenario 1: 查询慢但有索引 (Slow Query Despite Index)

**Diagnosis**:
```javascript
// Run explain to check index usage
db.collection.explain("executionStats").find(query)

// Check key metrics:
// - winningPlan: which index used
// - totalDocsExamined: documents scanned
// - totalKeysExamined: index entries scanned
// - executionTimeMillis: query duration
```

**Common Causes and Solutions**:

| Cause | Diagnosis | Solution |
|-------|-----------|----------|
| Low selectivity | `totalDocsExamined` high relative to result | Add more selective fields to index |
| Wrong index chosen | Multiple indexes, wrong one winning | Use hint() to force correct index |
| Index field order wrong | Range before sort in compound | Reorder index per ESR rule |
| Non-covered query | `FETCH` stage present | Add projected fields to index |
| Large result set | High `nReturned` | Add pagination limit |

**Fix Examples**:
```javascript
// Force specific index
db.users.find({ status: "active" }).hint({ status: 1, created_at: -1 })

// Add coverage fields
db.orders.createIndex({ status: 1, customer_id: 1, total: 1 })
// Now covers: find({status: "X"}, {_id:0, status:1, customer_id:1, total:1})
```

### Scenario 2: 索引未命中 (Index Not Used)

**Diagnosis**:
```javascript
// Check explain plan
var plan = db.collection.explain("executionStats").find(query);
printjson(plan.queryPlanner.winningPlan);

// Look for:
// - "stage": "COLLSCAN" → No index used (BAD)
// - "stage": "IXSCAN" → Index used (GOOD)
```

**Common Causes**:

| Cause | Example | Solution |
|-------|---------|----------|
| Query not prefix | `{age: 25}` with `{name:1, age:1}` | Create `{age:1}` or use `{name, age}` |
| Negation operators | `{status: {$ne: "active"}}` | Redesign query or add complementary index |
| Null/missing check | `{field: null}` | Use sparse index differently |
| Regex not prefix | `{name: /pattern/}` | Use prefix regex: `{name: /^prefix/}` |
| Array field mismatch | `{tags: "single"}` vs `{tags: ["a","b"]}` | Use multikey index correctly |
| Type mismatch | `{price: "100"}` when price is Number | Fix query data type |

**Fix Examples**:
```javascript
// Create matching index for non-prefix query
db.users.createIndex({ age: 1 })

// Use $in instead of $ne for selective query
db.users.find({ status: { $in: ["pending", "inactive"] } })
// Instead of: { status: { $ne: "active" } }

// Use prefix regex for index usage
db.products.find({ name: /^Apple/ })
// Not: { name: /Apple/ }
```

### Scenario 3: 索引过多影响写入 (Too Many Indexes)

**Diagnosis**:
```javascript
// List all indexes
db.collection.getIndexes()

// Check index count and size
db.collection.stats().indexSizes

// Monitor write performance
db.collection.stats().wiredTiger
```

**Symptoms**:
- High write latency
- Memory pressure
- CPU spike during writes
- Index build queue accumulation

**Resolution Steps**:

| Step | Action | Tool |
|------|--------|------|
| 1 | Identify unused indexes | `$indexStats`, DAS analysis |
| 2 | Identify redundant indexes | Check prefix coverage |
| 3 | Prioritize critical indexes | Query frequency analysis |
| 4 | Remove low-value indexes | Drop command |
| 5 | Consider partial indexes | Reduce scope of remaining |

**Fix Examples**:
```javascript
// Drop unused index
db.collection.dropIndex("unused_index_name")

// Replace full index with partial
db.collection.dropIndex({ status: 1, created_at: 1 })
db.collection.createIndex(
  { status: 1, created_at: 1 },
  { partialFilterExpression: { status: "active" } }
)

// Verify improvement
db.collection.stats().indexSizes
```

### Scenario 4: 索引构建阻塞 (Index Build Blocking)

**Diagnosis**:
```javascript
// Check current operations
db.currentOp(true)

// Look for:
// - createIndexes command
// - Progress percentage
// - Lock held duration
```

**Causes**:
- Large collection size
- High concurrent traffic
- Resource constraints
- Legacy foreground build (MongoDB < 4.2)

**Resolution**:

| Scenario | Solution |
|----------|----------|
| In-progress build | Wait for completion or kill if blocking critical |
| Build too slow | Add resources, reduce collection size |
| Need to cancel | `db.killOp(opId)` with caution |
| Pre-production | Test build time on staging |

**Safe Index Build Process**:
```javascript
// 1. Schedule during low-traffic (maintenance window)
// 2. For sharded clusters: rolling build per shard
// 3. Monitor progress
db.currentOp({ "command.createIndexes": { $exists: true } })

// 4. If need to abort (use carefully)
db.killOp(<opId>)

// 5. Use build in background (MongoDB < 4.2)
db.collection.createIndex({ field: 1 }, { background: true })
```

---

## Best Practices Table

### Index Count Recommendations by Collection Size

| Collection Size | Max Indexes | Recommendation | Focus |
|-----------------|-------------|----------------|-------|
| < 10K docs | ≤ 10 | Full coverage acceptable | Query convenience |
| 10K - 100K docs | ≤ 7 | Focus on frequent queries | Balance read/write |
| 100K - 1M docs | ≤ 5 | Critical queries only | Write performance priority |
| > 1M docs | ≤ 3 | Essential indexes only | Careful evaluation required |
| > 10M docs | ≤ 2-3 | Minimal index footprint | Partial/sparse preferred |

### Index Field Count Recommendations

| Fields in Query | Recommended Index | Example |
|-----------------|-------------------|---------|
| 1 field | Single field index | `{field: 1}` |
| 2-3 fields | Compound index | `{f1: 1, f2: 1, f3: 1}` |
| 4+ fields | Evaluate carefully | Consider query split |
| Sort + filter | Compound with sort | `{filter: 1, sort: -1}` |

### Index Maintenance Schedule

| Action | Frequency | Tool |
|--------|-----------|------|
| Review index usage | Monthly | `$indexStats` |
| Clean unused indexes | Quarterly | DAS + manual review |
| Rebuild fragmented indexes | Annually | Compact/rebuild |
| Audit index size | Monthly | `stats().indexSizes` |
| Validate covered queries | Per deployment | `explain()` |

---

## Index Monitoring Metrics

### Key Performance Metrics

| Metric | Key | Meaning | Threshold |
|--------|-----|---------|-----------|
| **Index Size** | `stats().indexSizes` | Storage consumed by indexes | < 30% of data size |
| **Index Hit Ratio** | `totalKeysExamined / totalDocsExamined` | Index efficiency | > 90% |
| **Scan/Plan Ratio** | `docsExamined / docsReturned` | Query efficiency | < 10 |
| **Index Build Progress** | `currentOp().progress` | Build completion | Monitor during build |
| **Index Access Count** | `$indexStats.accesses.ops` | Usage frequency | > 100/day |
| **Write Latency** | DAS metrics | Write performance impact | < baseline + 20% |

### Monitoring Commands

**Index Statistics**:
```javascript
// Collection index details
db.collection.getIndexes()

// Index size breakdown
db.collection.stats().indexSizes

// Index usage statistics
db.collection.aggregate([{ $indexStats: {} }])
```

**Query Performance Analysis**:
```javascript
// Explain query plan
db.collection.explain("executionStats").find(query)

// Key metrics to check:
{
  "executionStats": {
    "totalDocsExamined": N,   // Should be close to nReturned
    "totalKeysExamined": N,   // Index entries scanned
    "nReturned": N,           // Documents returned
    "executionTimeMillis": N  // Query duration
  }
}
```

**Efficiency Calculation**:
```javascript
// Index efficiency formula
// Ideal: totalDocsExamined ≈ nReturned
// Ratio: totalDocsExamined / nReturned should be < 10

// Example analysis
var stats = db.orders.explain("executionStats")
  .find({ status: "active" }).limit(100);
  
var ratio = stats.executionStats.totalDocsExamined / 
            stats.executionStats.nReturned;
            
print("Efficiency ratio: " + ratio);
// ratio < 1 → Excellent (covered or exact match)
// ratio 1-10 → Good
// ratio > 10 → Needs optimization
```

### Alibaba Cloud Monitoring Integration

**DAS Metrics Dashboard**:
- Slow query frequency
- Index usage heatmap
- Space utilization trends
- Real-time performance alerts

**Alert Thresholds**:
| Alert | Threshold | Action |
|-------|-----------|--------|
| Slow query rate | > 10/min | Investigate and optimize |
| Index miss rate | > 20% | Review index coverage |
| Index size growth | > 50% in month | Audit index necessity |
| Write latency spike | > 2x baseline | Reduce index count |

---

## Quick Reference

### Index Creation Syntax

```javascript
// Single field
db.coll.createIndex({ field: 1 })

// Compound
db.coll.createIndex({ f1: 1, f2: -1, f3: 1 })

// TTL
db.coll.createIndex({ date: 1 }, { expireAfterSeconds: 3600 })

// Text
db.coll.createIndex({ content: "text" }, { default_language: "english" })

// Hashed
db.coll.createIndex({ shard_key: "hashed" })

// Partial
db.coll.createIndex({ field: 1 }, { partialFilterExpression: { status: "active" } })

// Sparse
db.coll.createIndex({ field: 1 }, { sparse: true })

// Geospatial
db.coll.createIndex({ location: "2dsphere" })

// Unique
db.coll.createIndex({ field: 1 }, { unique: true })
```

### Index Management Commands

```javascript
// List indexes
db.coll.getIndexes()

// Drop index
db.coll.dropIndex("index_name")

// Drop all indexes (except _id)
db.coll.dropIndexes()

// Hide index (MongoDB 4.4+)
db.coll.hideIndex("index_name")

// Unhide index
db.coll.unhideIndex("index_name")
```

### Query Optimization Commands

```javascript
// Force specific index
db.coll.find(query).hint({ field: 1 })

// Explain query
db.coll.explain("executionStats").find(query)

// Check index stats
db.coll.aggregate([{ $indexStats: {} }])
```

---

## See Also

- [Alibaba Cloud MongoDB Documentation](https://help.aliyun.com/product/26556.html)
- [MongoDB Index Strategies Official Guide](https://docs.mongodb.com/manual/indexes/)
- [DAS Integration Guide](integration.md) - Call `alicloud-das-ops` for intelligent analysis
- [Monitoring Reference](../references/monitoring.md) - Performance metrics and alerts