import React from 'react';
import styled from 'styled-components';

const RankingItemContainer = styled.div`
  display: flex;
  align-items: center;
  padding: 0.75rem;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.8);
  border: 2px solid #ffd700;
  box-shadow: 0 4px 20px rgba(255, 215, 0, 0.2);
  margin-bottom: 0.5rem;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  
  &:hover {
    box-shadow: 0 8px 30px rgba(255, 215, 0, 0.4);
    transform: translateY(-2px);
    border-color: #ffed4e;
  }
`;

const RankNumber = styled.div`
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.9rem;
  margin-right: 1rem;
  border: 2px solid #ffd700;
  
  ${props => {
    if (props.rank === 1) return 'background: linear-gradient(135deg, #ffd700, #ffed4e); color: #000; box-shadow: 0 0 15px rgba(255, 215, 0, 0.6);';
    if (props.rank === 2) return 'background: linear-gradient(135deg, #c0c0c0, #e8e8e8); color: #000;';
    if (props.rank === 3) return 'background: linear-gradient(135deg, #cd7f32, #daa520); color: #fff;';
    return 'background: rgba(255, 215, 0, 0.1); color: #ffd700;';
  }}
`;

const CountryInfo = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
`;

const CountryName = styled.div`
  font-weight: 600;
  color: #ffd700;
  font-size: 1rem;
  margin-bottom: 0.25rem;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
`;

const CountryCode = styled.div`
  font-size: 0.8rem;
  color: #ffed4e;
  text-transform: uppercase;
  opacity: 0.8;
`;

const SelectionCount = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
`;

const CountRow = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
`;

const CountNumber = styled.div`
  font-size: 1.1rem;
  font-weight: bold;
  color: #ffd700;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
`;

const TotalCountNumber = styled.div`
  font-size: 0.9rem;
  font-weight: bold;
  color: #ffed4e;
  opacity: 0.8;
`;

const CountLabel = styled.div`
  font-size: 0.65rem;
  color: #ffd700;
  margin-top: 0.1rem;
  opacity: 0.7;
`;

const TotalCountLabel = styled.div`
  font-size: 0.6rem;
  color: #ffed4e;
  margin-top: 0.1rem;
  opacity: 0.6;
`;

const TrendingIcon = styled.span`
  margin-left: 0.5rem;
  font-size: 0.8rem;
  filter: drop-shadow(0 0 5px rgba(255, 215, 0, 0.5));
  animation: bounce 2s infinite;
  
  @keyframes bounce {
    0%, 20%, 50%, 80%, 100% {
      transform: translateY(0);
    }
    40% {
      transform: translateY(-3px);
    }
    60% {
      transform: translateY(-2px);
    }
  }
`;

const RankingItem = ({ ranking, rank }) => {
  const getTrendingIcon = () => {
    // 간단한 트렌드 표시 (실제로는 이전 데이터와 비교해야 함)
    const random = Math.random();
    if (random > 0.7) return '📈';
    if (random < 0.3) return '📉';
    return '➡️';
  };

  return (
    <RankingItemContainer>
      <RankNumber rank={rank}>
        {rank}
      </RankNumber>
      
      <CountryInfo>
        <CountryName>
          {ranking.country_name}
          <TrendingIcon>{getTrendingIcon()}</TrendingIcon>
        </CountryName>
        <CountryCode>{ranking.country_code}</CountryCode>
      </CountryInfo>
      
      <SelectionCount>
        <CountRow>
          <CountNumber>{ranking.daily_clicks}</CountNumber>
          <CountLabel>오늘 클릭</CountLabel>
        </CountRow>
        <CountRow>
          <TotalCountNumber>{ranking.total_clicks}</TotalCountNumber>
          <TotalCountLabel>총 클릭</TotalCountLabel>
        </CountRow>
      </SelectionCount>
    </RankingItemContainer>
  );
};

export default RankingItem;
