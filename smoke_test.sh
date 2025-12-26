#!/bin/bash
# Smoke test script for AI Model Security Scanner
# This script verifies basic functionality of the application

set -e

BASE_URL="${BASE_URL:-http://localhost:8080}"
TIMEOUT=120  # Max seconds to wait for job completion

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if container is running
check_health() {
    log_info "Checking application health..."
    
    for i in {1..30}; do
        if curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
            log_info "Application is healthy!"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    log_error "Application health check failed"
    return 1
}

# Create a test pickle file
create_test_file() {
    log_info "Creating test pickle file..."
    
    python3 -c "
import pickle
data = {'test': 'data', 'numbers': [1, 2, 3]}
with open('/tmp/test_model.pkl', 'wb') as f:
    pickle.dump(data, f)
print('Test file created: /tmp/test_model.pkl')
" 2>/dev/null || {
        log_warn "Python not available, creating empty test file"
        echo "test" > /tmp/test_model.pkl
    }
}

# Test job creation
test_create_job() {
    log_info "Testing job creation..."
    
    RESPONSE=$(curl -s -X POST "${BASE_URL}/api/jobs" \
        -F "file=@/tmp/test_model.pkl" \
        -F "enable_picklescan=true" \
        -F "strict_policy=false")
    
    JOB_ID=$(echo "$RESPONSE" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
    
    if [ -z "$JOB_ID" ]; then
        log_error "Failed to create job: $RESPONSE"
        return 1
    fi
    
    log_info "Job created: $JOB_ID"
    echo "$JOB_ID"
}

# Wait for job completion
wait_for_job() {
    local job_id=$1
    log_info "Waiting for job to complete..."
    
    local start_time=$(date +%s)
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -gt $TIMEOUT ]; then
            log_error "Job timed out after ${TIMEOUT}s"
            return 1
        fi
        
        RESPONSE=$(curl -s "${BASE_URL}/api/jobs/${job_id}")
        STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        
        case $STATUS in
            succeeded|failed)
                log_info "Job completed with status: $STATUS"
                return 0
                ;;
            queued|running)
                echo -n "."
                sleep 2
                ;;
            *)
                log_error "Unknown status: $STATUS"
                return 1
                ;;
        esac
    done
}

# Test artifacts download
test_artifacts() {
    local job_id=$1
    log_info "Testing artifacts..."
    
    # List artifacts
    ARTIFACTS=$(curl -s "${BASE_URL}/api/jobs/${job_id}/artifacts")
    log_info "Artifacts: $ARTIFACTS"
    
    # Download summary
    curl -sf "${BASE_URL}/api/jobs/${job_id}/download/summary.json" -o /tmp/summary.json
    
    if [ -f /tmp/summary.json ]; then
        log_info "Summary downloaded successfully"
        cat /tmp/summary.json | head -20
    else
        log_error "Failed to download summary"
        return 1
    fi
}

# Test web UI
test_web_ui() {
    log_info "Testing web UI..."
    
    # Check main page
    if curl -sf "${BASE_URL}/" > /dev/null; then
        log_info "Main page OK"
    else
        log_error "Main page failed"
        return 1
    fi
    
    # Check jobs page
    if curl -sf "${BASE_URL}/jobs" > /dev/null; then
        log_info "Jobs page OK"
    else
        log_error "Jobs page failed"
        return 1
    fi
}

# Cleanup
cleanup() {
    rm -f /tmp/test_model.pkl /tmp/summary.json
}

# Main
main() {
    log_info "========================================="
    log_info "AI Model Security Scanner - Smoke Test"
    log_info "========================================="
    
    trap cleanup EXIT
    
    check_health || exit 1
    test_web_ui || exit 1
    create_test_file
    
    JOB_ID=$(test_create_job) || exit 1
    wait_for_job "$JOB_ID" || exit 1
    test_artifacts "$JOB_ID" || exit 1
    
    echo ""
    log_info "========================================="
    log_info "All smoke tests passed! ✓"
    log_info "========================================="
}

main "$@"
