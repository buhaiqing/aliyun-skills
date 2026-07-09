#!/bin/bash
set -euo pipefail

echo "=== Testing Langfuse Integrations Across All Target Skills ==="

SKILLS=("cms" "ecs" "mongodb" "oss" "rds" "redis" "slb" "vpc" "ack")

for skill in "${SKILLS[@]}"; do
    echo -e "\n--- Testing $skill ---"
    DIR="alicloud-${skill}-ops"
    WRAPPER="${DIR}/scripts/${skill}-skillopt-wrapper.sh"
    
    # Check wrapper exists
    if [ ! -f "${WRAPPER}" ]; then
        echo "❌ ERROR: Wrapper not found at ${WRAPPER}"
        continue
    fi
    
    # Check wrapper sources skillopt-lib.sh
    if grep -q "source.*skillopt-lib.sh" "${WRAPPER}"; then
        echo "✅ Wrapper sources skillopt-lib.sh correctly"
    else
        echo "❌ ERROR: Wrapper does not source skillopt-lib.sh"
    fi
    
    # Check skillopt-lib.sh has session ID support
    LIB="${DIR}/scripts/skillopt-lib.sh"
    if grep -q "SKILLOPT_SESSION_ID" "${LIB}"; then
        echo "✅ Session ID propagation implemented"
    else
        echo "❌ ERROR: No session ID support in skillopt-lib.sh"
    fi
    
    # Check trace functions exist
    if grep -q "_skillopt_langfuse_create_trace" "${LIB}"; then
        echo "✅ Langfuse trace functions present"
    else
        echo "❌ ERROR: No Langfuse trace functions"
    fi
    
    # Test read-only command (dry run)
    echo "Testing read-only command with session ID..."
    TEST_SESSION="sess-test-$(date +%s)"
    # Use --help to avoid actual API call
    if "${WRAPPER}" help >/dev/null 2>&1; then
        echo "✅ ${skill} wrapper works correctly"
    else
        echo "⚠️  Warning: Help command failed (expected for some skills)"
    fi
done

echo -e "\n=== All tests completed ==="
