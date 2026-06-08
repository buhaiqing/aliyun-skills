# Prompt Engineering Guide

## Overview

Bailian Prompt Management enables:
- **Template versioning**: Track prompt changes over time
- **A/B testing**: Compare prompt performance
- **Variable substitution**: Dynamic content injection
- **Optimization**: Iterative improvement based on metrics

## Template Structure

### Basic Template

```yaml
name: customer-greeting
description: Greet customers professionally
version: "1.0.0"
model: qwen-turbo
content: |
  You are {{agent_name}}, a helpful customer service representative.
  
  Greet the customer in {{language}} and ask how you can help today.
  
  Customer name: {{customer_name}}
  Customer tier: {{customer_tier}}

variables:
  - agent_name
  - language
  - customer_name
  - customer_tier
```

### System + User Pattern

```yaml
name: code-reviewer
description: Review code for bugs and improvements
model: qwen-coder
system_content: |
  You are an expert code reviewer with 20 years of experience.
  Review code for:
  1. Bugs and logic errors
  2. Security vulnerabilities
  3. Performance issues
  4. Best practice violations
  
  Be thorough but constructive. Provide specific line references.

user_template: |
  Review this {{language}} code:
  
  ```{{language}}
  {{code}}
  ```
  
  Focus areas: {{focus_areas}}

variables:
  - language
  - code
  - focus_areas
```

### Few-Shot Template

```yaml
name: sentiment-classifier
description: Classify customer feedback sentiment
model: qwen-turbo
content: |
  Classify the sentiment of customer feedback as POSITIVE, NEGATIVE, or NEUTRAL.
  
  Examples:
  
  Feedback: "The product exceeded my expectations!"
  Sentiment: POSITIVE
  
  Feedback: "Shipping was delayed by a week."
  Sentiment: NEGATIVE
  
  Feedback: "It's a standard product, nothing special."
  Sentiment: NEUTRAL
  
  Now classify:
  Feedback: {{feedback}}
  Sentiment:

variables:
  - feedback
```

## Variable Types

| Type | Example | Use Case |
|------|---------|----------|
| **String** | `{{name}}` | Names, descriptions |
| **Number** | `{{count}}` | Quantities, IDs |
| **List** | `{{#items}}{{name}}, {{/items}}` | Arrays |
| **Boolean** | `{{#is_premium}}Priority{{/is_premium}}` | Conditionals |
| **JSON** | `{{data\|json}}` | Structured data |

### Conditional Blocks

```yaml
content: |
  Hello {{customer_name}},
  
  {{#is_vip}}
  As a VIP customer, you have access to priority support.
  {{/is_vip}}
  
  {{^is_vip}}
  Upgrade to VIP for priority support.
  {{/is_vip}}
  
  How can I help you today?
```

### List Iteration

```yaml
content: |
  Your order contains:
  {{#items}}
  - {{name}} (x{{quantity}}): ¥{{price}}
  {{/items}}
  
  Total: ¥{{total}}
```

## Prompt Patterns

### Pattern 1: Chain-of-Thought

```yaml
name: math-solver
model: qwen-plus
content: |
  Solve this math problem step by step.
  
  Problem: {{problem}}
  
  Let's work through this:
  1. First, identify what we're solving for
  2. List the given information
  3. Apply the appropriate formula
  4. Show each calculation step
  5. Verify the answer
  
  Solution:
```

### Pattern 2: Structured Output

```yaml
name: data-extractor
model: qwen-turbo
content: |
  Extract information from the text into JSON format.
  
  Text: {{text}}
  
  Extract these fields:
  - name (string)
  - date (ISO 8601 format)
  - amount (number)
  - category (one of: food, transport, utilities, other)
  
  Return ONLY valid JSON, no markdown:
  {
    "name": "...",
    "date": "...",
    "amount": ...,
    "category": "..."
  }
```

### Pattern 3: Role-Based

```yaml
name: legal-advisor
model: qwen-max
content: |
  You are a {{legal_specialty}} attorney with expertise in {{jurisdiction}} law.
  
  Client question: {{question}}
  
  Context:
  - Client type: {{client_type}}
  - Urgency: {{urgency_level}}
  - Previous actions: {{previous_actions}}
  
  Provide advice considering:
  1. Relevant statutes and regulations
  2. Precedent cases
  3. Risk assessment
  4. Recommended next steps
  
  Disclaimer: This is general information, not legal advice.
```

### Pattern 4: Multi-Lingual

```yaml
name: translator
model: qwen-plus
content: |
  Translate the following text from {{source_language}} to {{target_language}}.
  
  Consider:
  - Maintain formal/informal tone: {{tone}}
  - Preserve technical terms: {{preserve_terms}}
  - Adapt cultural references appropriately
  
  Text to translate:
  {{text}}
  
  Translation:
```

## Versioning

### Semantic Versioning

| Version | Change Type | Example |
|---------|-------------|---------|
| 1.0.0 | Initial release | New template |
| 1.1.0 | Enhancement | Added variable, improved output |
| 1.1.1 | Bug fix | Fixed typo, clarified instruction |
| 2.0.0 | Breaking | Removed variable, changed structure |

### Changelog Format

```markdown
## [1.2.0] - 2026-06-08
### Added
- New {{tone}} variable for formal/casual control
- Examples for edge cases

### Changed
- Improved clarity in instructions
- Updated model to qwen-plus for better reasoning

### Fixed
- Resolved ambiguity in output format
```

## A/B Testing

### Setup

```bash
# Create variant A (control)
aliyun bailian CreatePromptTemplate --body '{
  "TemplateName": "greeting-v1",
  "Content": "Hello! How can I help?",
  ...
}'

# Create variant B (treatment)
aliyun bailian CreatePromptTemplate --body '{
  "TemplateName": "greeting-v2",
  "Content": "Welcome! What brings you here today?",
  ...
}'
```

### Metrics

| Metric | Description | Success Criteria |
|--------|-------------|------------------|
| Response quality | Human rating 1-5 | B > A by 0.5+ points |
| Task completion | % successful tasks | B ≥ A |
| Token efficiency | Tokens per response | B ≤ A |
| Latency | Response time | B ≤ A + 10% |

### Analysis

```python
# Statistical significance check
from scipy import stats

control = [4.2, 4.0, 4.5, ...]      # v1 ratings
treatment = [4.6, 4.8, 4.4, ...]    # v2 ratings

t_stat, p_value = stats.ttest_ind(treatment, control)
if p_value < 0.05 and mean(treatment) > mean(control):
    print("v2 significantly better — promote to production")
```

## Optimization Techniques

### 1. Instruction Clarity

```yaml
# Before (vague)
content: "Write a summary of {{text}}"

# After (specific)
content: |
  Summarize the following text in 2-3 sentences.
  
  Requirements:
  - Capture main points only
  - Use simple language
  - Maximum 100 words
  
  Text: {{text}}
  
  Summary:
```

### 2. Example Quality

```yaml
# Before (generic)
examples: |
  Input: "I love this!"
  Output: "POSITIVE"

# After (diverse, specific)
examples: |
  Input: "The product exceeded my expectations, especially the battery life!"
  Output: "POSITIVE"
  
  Input: "It took 3 weeks to arrive and was damaged."
  Output: "NEGATIVE"
  
  Input: "It's a standard USB cable, works as expected."
  Output: "NEUTRAL"
```

### 3. Output Formatting

```yaml
# JSON mode
response_format:
  type: json_object
  schema:
    type: object
    properties:
      sentiment:
        type: string
        enum: [POSITIVE, NEGATIVE, NEUTRAL]
      confidence:
        type: number
        minimum: 0
        maximum: 1
      keywords:
        type: array
        items:
          type: string
    required: [sentiment, confidence]
```

## CLI Commands

```bash
# Create template
aliyun bailian CreatePromptTemplate --body '{
  "TemplateName": "my-template",
  "Content": "Hello {{name}}!",
  "Variables": ["name"],
  "ModelId": "qwen-turbo"
}'

# List templates
aliyun bailian ListPromptTemplates

# Get template
aliyun bailian GetPromptTemplate --PromptTemplateId "pt-xxx"

# Update template (creates new version)
aliyun bailian UpdatePromptTemplate --body '{
  "PromptTemplateId": "pt-xxx",
  "Content": "Hi {{name}}!",
  "Version": "1.1.0"
}'

# Delete template
aliyun bailian DeletePromptTemplate --PromptTemplateId "pt-xxx"

# Use template in completion
aliyun bailian CreateChatCompletion --body '{
  "model": "qwen-turbo",
  "prompt_template_id": "pt-xxx",
  "variables": {
    "name": "Alice"
  }
}'
```

## Best Practices

1. **Start simple**: Begin with minimal instructions, add complexity as needed
2. **Be specific**: Clear instructions beat clever prompts
3. **Use examples**: Few-shot examples improve reliability
4. **Test edge cases**: Include unusual inputs in testing
5. **Version everything**: Track changes and performance
6. **Monitor metrics**: Token usage, latency, quality ratings
7. **Iterate**: Prompt engineering is iterative refinement
