#!/usr/bin/env python3
"""Fix MD040 markdownlint errors: add language tags to untagged fenced code blocks.

Uses a state machine where:
- ```lang at column 0: opens a new block (if outside) or closes current + opens new (if inside)
- ``` at column 0: closes if inside, opens if outside

Only tags ``` that are OPENING (outside → inside transition).
"""

import re
import sys

FILES = [
    'alicloud-bailian-ops/references/knowledge-base-best-practices.md',
    'alicloud-bailian-ops/references/prompt-engineering-guide.md',
    'alicloud-bailian-ops/references/prompt-templates.md',
    'alicloud-bailian-ops/references/troubleshooting.md',
    'alicloud-bailian-ops/references/well-architected-assessment.md',
    'alicloud-billing-ops/references/cli-usage.md',
    'alicloud-billing-ops/references/core-concepts.md',
    'alicloud-billing-ops/references/troubleshooting.md',
    'alicloud-cert-ops/references/integration.md',
    'alicloud-cert-ops/references/troubleshooting.md',
    'alicloud-cert-ops/SKILL.md',
    'alicloud-cms-ops/references/advanced/aiops-prediction.md',
    'alicloud-cms-ops/references/advanced/finops-analysis.md',
    'alicloud-cms-ops/references/aiops-inspection.md',
    'alicloud-cms-ops/references/cli-install-diagnosis.md',
    'alicloud-cms-ops/references/core-concepts.md',
    'alicloud-cms-ops/references/gcl-cms-alarm-guide.md',
    'alicloud-cms-ops/references/gcl-passrate-metrics-guide.md',
    'alicloud-cms-ops/references/integration.md',
    'alicloud-cms-ops/references/knowledge-base.md',
    'alicloud-cms-ops/references/observability.md',
    'alicloud-cms-ops/references/prompt-examples.md',
    'alicloud-cms-ops/references/prompt-templates.md',
    'alicloud-cms-ops/references/skillopt-integration.md',
    'alicloud-cms-ops/references/troubleshooting.md',
    'alicloud-das-ops/references/integration.md',
    'alicloud-das-ops/references/intelligent-inspection.md',
    'alicloud-dns-ops/CONTRIBUTING.md',
    'alicloud-dns-ops/README.md',
    'alicloud-dns-ops/references/core-concepts.md',
    'alicloud-dns-ops/references/integration.md',
    'alicloud-dns-ops/references/prompt-templates.md',
    'alicloud-dts-ops/references/api-sdk-usage.md',
    'alicloud-dts-ops/references/core-concepts.md',
    'alicloud-dts-ops/references/enhanced-self-healing-framework.md',
    'alicloud-eci-ops/references/api-sdk-usage.md',
    'alicloud-eci-ops/references/cli-usage.md',
    'alicloud-eci-ops/references/core-concepts.md',
    'alicloud-eci-ops/references/integration.md',
    'alicloud-eci-ops/references/openapi-verify-checklist.md',
    'alicloud-eci-ops/references/well-architected-assessment.md',
    'alicloud-eci-ops/SKILL.md',
    'alicloud-ecs-ops/references/core-concepts.md',
    'alicloud-ecs-ops/references/host-io-inspection.md',
    'alicloud-ecs-ops/references/llm-diagnosis.md',
    'alicloud-ecs-ops/references/monitoring.md',
    'alicloud-ecs-ops/references/network-troubleshooting-and-tuning.md',
    'alicloud-ecs-ops/references/observability.md',
    'alicloud-ecs-ops/references/prompt-examples.md',
    'alicloud-ecs-ops/SKILL.md',
    'alicloud-eip-ops/references/api-sdk-usage.md',
    'alicloud-eip-ops/references/core-concepts.md',
    'alicloud-eip-ops/references/integration.md',
    'alicloud-elasticsearch-ops/operations/alarm-storm-handling.md',
    'alicloud-elasticsearch-ops/operations/batch-operations.md',
    'alicloud-elasticsearch-ops/references/integration.md',
    'alicloud-elasticsearch-ops/references/knowledge-base.md',
    'alicloud-elasticsearch-ops/references/monitoring.md',
    'alicloud-elasticsearch-ops/references/observability.md',
    'alicloud-elasticsearch-ops/references/prompt-examples.md',
    'alicloud-elasticsearch-ops/references/stability-enhancement.md',
    'alicloud-elasticsearch-ops/references/troubleshooting.md',
    'alicloud-elasticsearch-ops/reports/diagnostic-report-schema.md',
    'alicloud-elasticsearch-ops/reports/optimization-summary.md',
    'alicloud-elasticsearch-ops/reports/round2-assessment.md',
    'alicloud-ess-ops/references/core-concepts.md',
    'alicloud-ess-ops/references/monitoring.md',
    'alicloud-ess-ops/SKILL.md',
    'alicloud-fc-ops/references/core-concepts.md',
    'alicloud-fc-ops/references/gpu-inference.md',
    'alicloud-fc-ops/references/integration.md',
    'alicloud-fc-ops/references/monitoring.md',
    'alicloud-fc-ops/references/observability.md',
    'alicloud-fc-ops/references/prompt-examples.md',
    'alicloud-fc-ops/SKILL.md',
    'alicloud-gcl-runner-ops/references/gcl-execution.md',
    'alicloud-gcl-runner-ops/references/integration.md',
    'alicloud-gcl-runner-ops/scripts/docs/failure-patterns.md',
    'alicloud-gcl-runner-ops/scripts/README-Smart-Alert.md',
    'alicloud-gcl-runner-ops/scripts/README.md',
]


def detect_lang(lines, start):
    """Detect language for a code block starting at line index `start`."""
    end = start
    while end < len(lines) and not lines[end].startswith('```'):
        end += 1
    content = '\n'.join(lines[start:end])

    if re.search(r'[─▶┌┐└┘├┤┬┴┼│]', content):
        return 'text'
    if content.strip().startswith('{') and '}' in content:
        return 'json'
    if re.search(r'^\s*(name:|apiVersion:|kind:|metadata:|spec:|---)', content, re.MULTILINE):
        return 'yaml'
    if re.search(r'^\s*(import |from |def |class |print\(|if __name__|@\w)', content, re.MULTILINE):
        return 'python'
    if re.search(r'^\s*(#{1,6} |\[.+\]\(|> |\||\* |\d+\. |---)', content, re.MULTILINE):
        return 'markdown'
    if re.search(r'^\s*(#!|[$#]|export |alias |source |function |if |for |while |case |echo |exit |return |cd |mkdir |rm |cp |mv |chmod |chown |apt|yum|pip |npm |docker |git |kubectl |aliyun |terraform |helm |ansible |curl |wget |\w+\(\) )', content, re.MULTILINE):
        return 'bash'
    if re.search(r'^\s*(package |func |import |type |var |const |\.\w+\(\))', content, re.MULTILINE):
        return 'go'
    return 'text'


def process_file(fpath):
    """Process a single file, tagging untagged opening fences."""
    with open(fpath, 'r') as f:
        content = f.read()
    lines = content.splitlines()
    modified = False

    inside_fence = False

    for i, line in enumerate(lines):
        if not line.startswith('```'):
            continue
        
        stripped = line.rstrip()
        fence_match = re.match(r'^(```+)(.*?)\s*$', stripped)
        if not fence_match:
            continue
        
        backticks = fence_match.group(1)
        rest = fence_match.group(2).strip()
        
        if backticks != '```':
            continue
        
        if rest:
            # Tagged fence (```lang) at column 0
            # Opens if outside, closes+opens if inside
            inside_fence = True
            continue
        
        # Untagged ``` at column 0
        if inside_fence:
            # Closing fence — leave as-is
            inside_fence = False
        else:
            # Opening fence — tag it
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines):
                lang = detect_lang(lines, j)
                lines[i] = '```' + lang
                modified = True
            inside_fence = True

    if modified:
        with open(fpath, 'w') as f:
            f.write('\n'.join(lines) + ('\n' if content.endswith('\n') else ''))
        return True
    return False


def main():
    modified_count = 0
    error_count = 0
    no_change_count = 0

    for fpath in FILES:
        try:
            if process_file(fpath):
                print(f'MODIFIED: {fpath}')
                modified_count += 1
            else:
                print(f'NO CHANGE: {fpath}')
                no_change_count += 1
        except Exception as e:
            print(f'ERROR: {fpath}: {e}', file=sys.stderr)
            error_count += 1

    print(f'\n--- Summary ---')
    print(f'Processed: {len(FILES)}')
    print(f'Modified:  {modified_count}')
    print(f'No change: {no_change_count}')
    print(f'Errors:    {error_count}')


if __name__ == '__main__':
    main()
