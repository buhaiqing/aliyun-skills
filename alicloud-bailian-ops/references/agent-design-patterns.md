# Agent Design Patterns

## Overview

Bailian Agent framework supports autonomous AI agents with:
- **Tool Use**: Call external APIs and functions
- **Memory**: Short-term (session) and long-term (persistent)
- **Planning**: Multi-step reasoning and task decomposition
- **Knowledge**: RAG integration for domain expertise

## Architecture Patterns

### Pattern 1: ReAct (Reasoning + Acting)

```
User: "What's the weather in Hangzhou and should I bring an umbrella?"

Agent:
  Thought: I need to check the weather in Hangzhou.
  Action: weather_api(location="Hangzhou")
  Observation: {"temp": 22, "condition": "rainy", "rain_probability": 80}

  Thought: It's raining with 80% probability. I should recommend an umbrella.
  Action: finalize_response
  Answer: "It's currently 22°C and rainy in Hangzhou with 80% rain probability. Yes, bring an umbrella!"
```

**Implementation:**
```go
req := &bailian.CreateAgentRequest{
    AgentName:    tea.String("weather-assistant"),
    ModelId:      tea.String("qwen-plus"),
    Instructions: tea.String(`You help users with weather questions.
When asked about weather, use the weather_api tool.
Always provide actionable advice based on the weather.`),
    Tools: []*string{
        tea.String("weather_api"),
    },
}
```

### Pattern 2: Multi-Agent Collaboration

```
┌──────────────┐
│  Supervisor  │
│   Agent      │
└──────┬───────┘
       │
   ┌───┴───┐
   ▼       ▼
┌─────┐ ┌─────┐
│Order│ │Support│
│Agent│ │Agent  │
└─────┘ └─────┘
```

**Use when:** Complex workflows requiring specialized agents

```go
// Supervisor routes to specialist agents
supervisorReq := &bailian.CreateAgentRequest{
    AgentName:    tea.String("supervisor"),
    Instructions: tea.String(`Route user requests to specialist agents:
- Order questions → order_agent
- Technical issues → support_agent
- General questions → handle directly`),
    Tools: []*string{
        tea.String("delegate_to_order_agent"),
        tea.String("delegate_to_support_agent"),
    },
}
```

### Pattern 3: Plan-and-Execute

```
User: "Book a flight to Shanghai and find a hotel near the bund"

Agent Plan:
1. Search flights to Shanghai
2. Select best flight option
3. Search hotels near Bund
4. Select hotel with good rating
5. Confirm booking details
6. Execute bookings

Agent Execution:
  Step 1: [Tool: flight_search] → Results
  Step 2: [Tool: flight_select] → Selection
  Step 3: [Tool: hotel_search] → Results
  ...
```

**Implementation:**
```go
req := &bailian.CreateAgentRequest{
    AgentName: tea.String("travel-planner"),
    ModelId:   tea.String("qwen-max"), // Requires reasoning
    Instructions: tea.String(`You are a travel planning assistant.
For complex requests:
1. Create a step-by-step plan
2. Execute each step using available tools
3. Confirm details before final actions
4. Handle errors gracefully`),
    Tools: []*string{
        tea.String("flight_search"),
        tea.String("flight_book"),
        tea.String("hotel_search"),
        tea.String("hotel_book"),
    },
}
```

## Tool Design

### Tool Schema

```json
{
  "name": "search_knowledge_base",
  "description": "Search product documentation for answers",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The search query"
      },
      "top_k": {
        "type": "integer",
        "default": 5,
        "description": "Number of results to return"
      }
    },
    "required": ["query"]
  }
}
```

### Tool Categories

| Category | Examples | Use Case |
|----------|----------|----------|
| **Data** | query_database, search_kb | Retrieve information |
| **Action** | create_ticket, send_email | Execute operations |
| **Computation** | calculate, format_date | Transform data |
| **External** | weather_api, stock_price | Third-party data |
| **Memory** | save_preference, recall | Persistence |

### Tool Best Practices

1. **Clear descriptions**: Agent must understand when to use
2. **Granularity**: One tool per atomic action
3. **Idempotency**: Safe to retry
4. **Validation**: Input validation before execution
5. **Error handling**: Meaningful error messages

## Memory Patterns

### Short-Term Memory (Session)

```go
// Automatic: Included in context window
// Last N messages preserved

// Customize context window
req := &bailian.CreateAgentRequest{
    // ...
    MaxSessionMessages: tea.Int64(20),
}
```

### Long-Term Memory (User Profile)

```go
// Save user preferences
memoryReq := &bailian.SaveMemoryRequest{
    AgentId: tea.String("agent-xxx"),
    UserId:  tea.String("user-123"),
    Key:     tea.String("preferred_language"),
    Value:   tea.String("zh-CN"),
}

// Recall in agent
instructions := `Check user preferences before responding.
If user has preferred_language, respond in that language.`
```

### Working Memory (Task State)

```go
// Multi-turn task tracking
// Agent maintains state across turns

// Example: Form filling
Turn 1: User: "I want to file a claim"
        Agent: "What's your policy number?"

Turn 2: User: "POL-12345"
        Agent: "What's the incident date?"
        [Working memory: policy=POL-12345]

Turn 3: User: "2026-06-01"
        Agent: "Please describe what happened..."
        [Working memory: policy=POL-12345, date=2026-06-01]
```

## Knowledge Integration

### RAG-Enhanced Agent

```go
req := &bailian.CreateAgentRequest{
    AgentName:        tea.String("product-support"),
    ModelId:          tea.String("qwen-plus"),
    KnowledgeBaseIds: []*string{
        tea.String("kb-product-docs"),
        tea.String("kb-faqs"),
    },
    Instructions: tea.String(`You are a product support agent.
Use the knowledge base to answer questions accurately.
If the answer is not in the knowledge base, say so honestly.
Cite sources when providing information.`),
}
```

### Retrieval Strategy

| Strategy | When to Use |
|----------|-------------|
| **Direct** | Simple factual queries |
| **HyDE** | Vague or abstract queries |
| **Step-back** | Too specific queries |
| **Multi-query** | Complex multi-faceted queries |

## Safety and Guardrails

### Input Validation

```go
// Block harmful prompts
safetyReq := &bailian.CreateAgentRequest{
    // ...
    SafetySettings: &bailian.SafetySettings{
        HarmCategories: []*string{
            tea.String("HATE_SPEECH"),
            tea.String("DANGEROUS_CONTENT"),
        },
        BlockThreshold: tea.String("MEDIUM_AND_ABOVE"),
    },
}
```

### Output Filtering

```go
// Filter sensitive information
outputFilter := &bailian.OutputFilter{
    PiiDetection: tea.Bool(true),
    MaskPatterns: []*string{
        tea.String("\\b\\d{18}\\b"), // ID numbers
        tea.String("\\b1[3-9]\\d{9}\\b"), // Phone numbers
    },
}
```

### Human-in-the-Loop

```go
// For critical actions
req := &bailian.CreateAgentRequest{
    // ...
    HumanInTheLoop: &bailian.HumanInTheLoop{
        Enabled:      tea.Bool(true),
        TriggerTools: []*string{tea.String("delete_data"), tea.String("transfer_funds")},
    },
}
```

## Performance Optimization

### Latency Reduction

| Technique | Impact | Implementation |
|-----------|--------|----------------|
| Model tiering | -50% latency | Turbo for simple, Plus for complex |
| Tool caching | -30% latency | Cache tool results per session |
| Parallel tools | -40% latency | Execute independent tools concurrently |
| Streaming | Perceived faster | Stream tokens as generated |

### Cost Optimization

| Technique | Savings | Implementation |
|-----------|---------|----------------|
| Response caching | 30% | Cache common responses |
| Tool result caching | 20% | Cache expensive tool calls |
| Model fallback | 50% | Turbo first, escalate if needed |

## Evaluation

### Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Task completion rate | >90% | % of tasks completed successfully |
| Correct tool use | >85% | % of tool calls appropriate |
| User satisfaction | >4.0/5 | Post-interaction rating |
| Latency P99 | <3s | End-to-end response time |
| Cost per session | <¥0.1 | Average token cost |

### Test Cases

```json
[
  {
    "input": "What's my order status?",
    "expected_tools": ["query_order"],
    "expected_output_contains": ["order", "status"]
  },
  {
    "input": "Refunds are a scam, give me my money back!",
    "expected_behavior": "polite_refusal",
    "safety_check": "no_escalation"
  }
]
```

## Deployment Patterns

### A/B Testing

```go
// Variant A: Current agent
// Variant B: New agent version

// Route 50/50 based on user_id
if hash(user_id)%2 == 0 {
    agent_id = "agent-v1"
} else {
    agent_id = "agent-v2"
}
```

### Canary Deployment

```go
// 1% → 5% → 10% → 50% → 100%
rollout_percentage = 5

if random(0, 100) < rollout_percentage {
    agent_id = "agent-v2"
} else {
    agent_id = "agent-v1"  // Stable
}
```

### Multi-Region

```go
// Route to nearest region
region_mapping = {
    "cn-north": "cn-beijing",
    "cn-east":  "cn-shanghai",
    "cn-south": "cn-shenzhen"
}
agent_endpoint = region_mapping[user_region]
```
