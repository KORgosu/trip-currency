import React from 'react';
import styled from 'styled-components';

const ExchangeRateContainer = styled.div`
  background: #2a2a2a;
  border: 2px solid #ffd700;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(255, 215, 0, 0.2);
  padding: 2rem;
  width: 100%;
  
  @media (max-width: 768px) {
    padding: 1.5rem;
  }
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
`;

const HeaderIcon = styled.span`
  font-size: 1.2rem;
`;

const HeaderTitle = styled.h2`
  font-size: 1.1rem;
  font-weight: bold;
  color: #ffd700;
  margin: 0;
`;

const RateGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

const RateCard = styled.div`
  background: #1a1a1a;
  border: 1px solid #ffd700;
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.3s ease;
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(255, 215, 0, 0.3);
    border-color: #ffed4e;
  }
`;

const CurrencyInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
`;

const CurrencyFlag = styled.span`
  font-size: 1.2rem;
`;

const CurrencyCode = styled.span`
  font-weight: bold;
  color: #ffd700;
  font-size: 0.9rem;
`;

const CurrencyName = styled.span`
  color: #ffed4e;
  font-size: 0.8rem;
`;

const ExchangeRate = styled.div`
  font-size: 1.1rem;
  font-weight: 600;
  color: #ffd700;
`;

const CacheInfo = styled.div`
  font-size: 0.7rem;
  color: #ffed4e;
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
`;

const LoadingContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: #666;
`;

const Spinner = styled.div`
  border: 3px solid #f3f3f3;
  border-top: 3px solid #667eea;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  animation: spin 1s linear infinite;
  margin-right: 1rem;
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const ErrorContainer = styled.div`
  background: #ffebee;
  color: #c62828;
  padding: 1rem;
  border-radius: 8px;
  border-left: 4px solid #c62828;
  text-align: center;
`;

const RefreshButton = styled.button`
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font-size: 0.8rem;
  margin-top: 1rem;
  transition: background-color 0.3s;
  
  &:hover {
    background: #5a6fd8;
  }
`;

// 국가 정보 매핑
const countryMap = {
  'USD': { name: '미국', flag: '🇺🇸', code: 'US' },
  'JPY': { name: '일본', flag: '🇯🇵', code: 'JP' },
  'EUR': { name: '유럽', flag: '🇪🇺', code: 'EU' },
  'GBP': { name: '영국', flag: '🇬🇧', code: 'GB' },
  'CNY': { name: '중국', flag: '🇨🇳', code: 'CN' }
};

const ExchangeRateDisplay = ({ 
  exchangeRates, 
  loading, 
  error, 
  onRefresh 
}) => {
  if (loading) {
    return (
      <ExchangeRateContainer>
        <Header>
          <HeaderIcon>💱</HeaderIcon>
          <HeaderTitle>실시간 환율 정보</HeaderTitle>
        </Header>
        <LoadingContainer>
          <Spinner />
          환율 데이터를 불러오는 중...
        </LoadingContainer>
      </ExchangeRateContainer>
    );
  }

  if (error) {
    return (
      <ExchangeRateContainer>
        <Header>
          <HeaderIcon>💱</HeaderIcon>
          <HeaderTitle>실시간 환율 정보</HeaderTitle>
        </Header>
        <ErrorContainer>
          <div>{error}</div>
          {onRefresh && (
            <RefreshButton onClick={onRefresh}>
              다시 시도
            </RefreshButton>
          )}
        </ErrorContainer>
      </ExchangeRateContainer>
    );
  }

  if (!exchangeRates || !exchangeRates.rates) {
    return (
      <ExchangeRateContainer>
        <Header>
          <HeaderIcon>💱</HeaderIcon>
          <HeaderTitle>실시간 환율 정보</HeaderTitle>
        </Header>
        <div style={{ textAlign: 'center', color: '#666', padding: '2rem' }}>
          환율 데이터가 없습니다.
          {onRefresh && (
            <RefreshButton onClick={onRefresh} style={{ marginTop: '1rem' }}>
              데이터 불러오기
            </RefreshButton>
          )}
        </div>
      </ExchangeRateContainer>
    );
  }

  return (
    <ExchangeRateContainer>
      <Header>
        <HeaderIcon>💱</HeaderIcon>
        <HeaderTitle>실시간 환율 정보</HeaderTitle>
      </Header>
      
      <RateGrid>
        {Object.entries(exchangeRates.rates).map(([currency, rate]) => {
          const country = countryMap[currency] || { 
            name: currency, 
            flag: '🌍', 
            code: currency 
          };
          
          return (
            <RateCard key={currency}>
              <CurrencyInfo>
                <CurrencyFlag>{country.flag}</CurrencyFlag>
                <div>
                  <CurrencyCode>{currency}</CurrencyCode>
                  <div>
                    <CurrencyName>{country.name}</CurrencyName>
                  </div>
                </div>
              </CurrencyInfo>
              <ExchangeRate>
                {rate.toLocaleString()}원
              </ExchangeRate>
              {exchangeRates.cache_hit !== undefined && (
                <CacheInfo>
                  {exchangeRates.cache_hit ? '✅ 캐시 적중' : '🔄 실시간'}
                </CacheInfo>
              )}
            </RateCard>
          );
        })}
      </RateGrid>
      
      {exchangeRates.timestamp && (
        <div style={{ 
          textAlign: 'center', 
          color: '#ffed4e', 
          fontSize: '0.8rem', 
          marginTop: '1rem',
          padding: '0.5rem',
          background: '#1a1a1a',
          border: '1px solid #ffd700',
          borderRadius: '4px'
        }}>
          마지막 업데이트: {new Date(exchangeRates.timestamp).toLocaleString('ko-KR')}
        </div>
      )}
    </ExchangeRateContainer>
  );
};

export default ExchangeRateDisplay;

