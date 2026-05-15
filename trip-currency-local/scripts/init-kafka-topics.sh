#!/bin/bash

# Kafka 토픽 초기화 스크립트
# 새로운 데이터 수신 이벤트 기반 아키텍처를 위한 토픽 생성

echo "🚀 Kafka 토픽 초기화 시작..."

# Kafka 컨테이너가 준비될 때까지 대기
echo "⏳ Kafka 컨테이너 준비 대기 중..."
sleep 30

# Kafka 토픽 생성 함수
create_topic() {
    local topic_name=$1
    local partitions=${2:-3}
    local replication_factor=${3:-1}
    
    echo "📝 토픽 생성: $topic_name (파티션: $partitions, 복제: $replication_factor)"
    
    docker exec currency-kafka kafka-topics.sh \
        --create \
        --topic "$topic_name" \
        --partitions "$partitions" \
        --replication-factor "$replication_factor" \
        --bootstrap-server localhost:9092 \
        --if-not-exists
    
    if [ $? -eq 0 ]; then
        echo "✅ 토픽 '$topic_name' 생성 완료"
    else
        echo "❌ 토픽 '$topic_name' 생성 실패"
    fi
}

# 기존 토픽들 (호환성을 위해 유지)
echo "📋 기존 토픽 생성..."
create_topic "exchange_rate_updates" 3 1
# ranking_updates 토픽 제거 - service-ranking은 독립적이므로 불필요

# 새로운 이벤트 기반 토픽들
echo "📋 새로운 이벤트 토픽 생성..."

# 1. 새로운 데이터 수신 이벤트
create_topic "new_data_received" 3 1

# 2. 환율 데이터 업데이트 이벤트
create_topic "exchange_rate_updated" 3 1

# 3. 데이터 처리 완료 이벤트
create_topic "data_processing_completed" 3 1

# 4. 캐시 무효화 이벤트
create_topic "cache_invalidation" 3 1

# 5. 사용자 활동 이벤트 (향후 확장용)
create_topic "user_activity" 3 1

# 6. 시스템 알림 이벤트 (향후 확장용)
create_topic "system_notifications" 3 1

echo "🔍 생성된 토픽 목록 확인..."
docker exec currency-kafka kafka-topics.sh \
    --list \
    --bootstrap-server localhost:9092

echo "📊 토픽 상세 정보 확인..."
for topic in "new_data_received" "exchange_rate_updated" "data_processing_completed" "cache_invalidation"; do
    echo "--- $topic ---"
    docker exec currency-kafka kafka-topics.sh \
        --describe \
        --topic "$topic" \
        --bootstrap-server localhost:9092
done

echo "✅ Kafka 토픽 초기화 완료!"
echo ""
echo "📚 생성된 토픽 설명:"
echo "  - new_data_received: 외부 API에서 새로운 데이터를 받았을 때 발행"
echo "  - exchange_rate_updated: 환율 데이터가 업데이트되었을 때 발행"
echo "  - data_processing_completed: 데이터 처리 작업이 완료되었을 때 발행"
echo "  - cache_invalidation: 캐시 무효화가 필요할 때 발행"
echo "  - user_activity: 사용자 활동 관련 이벤트 (향후 확장)"
echo "  - system_notifications: 시스템 알림 이벤트 (향후 확장)"
echo ""
echo "🎯 이벤트 흐름:"
echo "  1. Data Ingestor → new_data_received 발행"
echo "  2. Data Ingestor → exchange_rate_updated 발행 (각 통화별)"
echo "  3. Data Ingestor → data_processing_completed 발행"
echo "  4. Data Ingestor → cache_invalidation 발행"
echo "  5. Currency Service, History Service → 이벤트 구독 및 처리"
echo "  6. Ranking Service → 독립적 (Kafka 구독 불필요)"
