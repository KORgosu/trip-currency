import React from 'react';
import styled from 'styled-components';
import RankingItem from './RankingItem';

const RankingListContainer = styled.div`
  width: 100%;
  position: relative;
  z-index: 1;
`;

const LoadingContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: #ffd700;
  font-size: 1rem;
  background: rgba(0, 0, 0, 0.8);
  border: 2px solid #ffd700;
  border-radius: 8px;
  margin: 1rem 0;
`;

const ErrorContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: #ffd700;
  background: rgba(0, 0, 0, 0.8);
  border: 2px solid #ffd700;
  border-radius: 8px;
  margin: 1rem 0;
`;

const RetryButton = styled.button`
  background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
  color: #000;
  border: 2px solid #ffd700;
  border-radius: 5px;
  padding: 0.5rem 1rem;
  margin-top: 1rem;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.3s ease;
  
  &:hover {
    background: linear-gradient(135deg, #ffed4e 0%, #ffd700 100%);
    box-shadow: 0 0 15px rgba(255, 215, 0, 0.4);
    transform: translateY(-1px);
  }
`;

const EmptyContainer = styled.div`
  text-align: center;
  padding: 3rem;
  color: #ffd700;
  font-size: 1rem;
  background: rgba(0, 0, 0, 0.8);
  border: 2px solid #ffd700;
  border-radius: 8px;
  margin: 1rem 0;
`;

const LastUpdated = styled.div`
  text-align: center;
  font-size: 0.8rem;
  color: #ffd700;
  margin-bottom: 1rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.8);
  border: 2px solid #ffd700;
  border-radius: 5px;
`;

const RefreshButton = styled.button`
  background: none;
  border: 2px solid #ffd700;
  color: #ffd700;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  transition: all 0.3s ease;
  margin-left: 0.5rem;
  
  &:hover {
    background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
    color: #000;
    box-shadow: 0 0 10px rgba(255, 215, 0, 0.4);
    transform: rotate(180deg);
  }
`;

const RankingList = ({ 
  rankings = [], 
  loading = false, 
  error = null, 
  onRefresh = () => {},
  lastUpdated = null 
}) => {
  const formatLastUpdated = (timestamp) => {
    if (!timestamp) return null;
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ko-KR', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  };

  if (loading) {
    return (
      <RankingListContainer>
        <LoadingContainer>
          📊 랭킹 데이터를 불러오는 중...
        </LoadingContainer>
      </RankingListContainer>
    );
  }

  if (error) {
    return (
      <RankingListContainer>
        <ErrorContainer>
          ❌ 랭킹 데이터를 불러올 수 없습니다
          <br />
          <small>{error}</small>
          <RetryButton onClick={onRefresh}>
            🔄 다시 시도
          </RetryButton>
        </ErrorContainer>
      </RankingListContainer>
    );
  }

  if (!rankings || rankings.length === 0) {
    return (
      <RankingListContainer>
        <EmptyContainer>
          📈 아직 랭킹 데이터가 없습니다
          <br />
          <small>국가를 선택하면 랭킹이 업데이트됩니다</small>
        </EmptyContainer>
      </RankingListContainer>
    );
  }

  return (
    <RankingListContainer>
      {lastUpdated && (
        <LastUpdated>
          마지막 업데이트: {formatLastUpdated(lastUpdated)}
          <RefreshButton onClick={onRefresh} title="수동 새로고침">
            🔄
          </RefreshButton>
        </LastUpdated>
      )}
      
      {rankings.map((ranking, index) => (
        <RankingItem 
          key={ranking.country_code} 
          ranking={ranking} 
          rank={ranking.rank || index + 1} 
        />
      ))}
    </RankingListContainer>
  );
};

export default RankingList;
