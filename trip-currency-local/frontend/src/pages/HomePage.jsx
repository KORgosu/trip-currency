import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import CountrySelector from '../components/country/CountrySelector';
import RankingList from '../components/ranking/RankingList';
import WorldMap from '../components/map/WorldMap';
import BackgroundEffect from '../components/common/BackgroundEffect';
import useGeolocation from '../hooks/useGeolocation';
import useRankingData from '../hooks/useRankingData';

const HomeContainer = styled.div`
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: transparent;
  position: relative;
  z-index: 1;
  
  @media (max-width: 768px) {
    padding: 0;
  }
`;

const ContentWrapper = styled.div`
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 3rem;
  padding: 2rem 3rem 0 3rem;
  
  @media (max-width: 1024px) {
    padding: 1.5rem 2rem 0 2rem;
  }
  
  @media (max-width: 768px) {
    padding: 1rem 1.5rem 0 1.5rem;
    gap: 2.5rem;
  }
  
  @media (max-width: 480px) {
    padding: 0.5rem 1rem 0 1rem;
    gap: 2rem;
  }
`;

const HeaderSection = styled.section`
  text-align: center;
  padding: 3rem 2rem;
  background: rgba(26, 26, 26, 0.8);
  border: 2px solid #ffd700;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(255, 215, 0, 0.2);
  width: 100%;
  backdrop-filter: blur(10px);
`;

const MainTitle = styled.h1`
  font-size: 2rem;
  font-weight: bold;
  color: #ffd700;
  margin-bottom: 0.5rem;
  text-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
  
  @media (max-width: 768px) {
    font-size: 1.5rem;
  }
  
  @media (max-width: 480px) {
    font-size: 1.2rem;
  }
`;

const CurrentLocation = styled.p`
  font-size: 1.1rem;
  color: #a0a0a0;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
`;

const LocationIcon = styled.span`
  font-size: 1rem;
`;

const RefreshButton = styled.button`
  background: none;
  border: none;
  color: #a0a0a0;
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  transition: all 0.3s ease;
  
  &:hover {
    background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
    color: #0a0a0a;
    transform: rotate(180deg);
  }
`;

const SearchSection = styled.section`
  padding: 2rem;
  background: rgba(26, 26, 26, 0.8);
  border: 2px solid #ffd700;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(255, 215, 0, 0.2);
  width: 100%;
  backdrop-filter: blur(10px);
  
  @media (max-width: 768px) {
    padding: 1.5rem;
  }
`;

const RankingSection = styled.section`
  background: rgba(0, 0, 0, 0.9);
  border: 3px solid #ffd700;
  border-radius: 12px;
  box-shadow: 0 8px 40px rgba(255, 215, 0, 0.4);
  padding: 2rem;
  width: 100%;
  backdrop-filter: blur(15px);
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(45deg, transparent 30%, rgba(255, 215, 0, 0.05) 50%, transparent 70%);
    pointer-events: none;
  }
  
  @media (max-width: 768px) {
    padding: 1.5rem;
  }
`;

const RankingHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  position: relative;
  z-index: 1;
`;

const RankingIcon = styled.span`
  font-size: 1.2rem;
  animation: pulse 2s infinite;
  
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.1); }
    100% { transform: scale(1); }
  }
`;

const RankingTitle = styled.h2`
  font-size: 1.1rem;
  font-weight: bold;
  color: #ffd700;
  margin: 0;
  text-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
  position: relative;
`;


const MainContentSection = styled.section`
  display: flex;
  flex-direction: column;
  gap: 2rem;
  width: 100%;
  min-height: auto;
`;

const ContentColumn = styled.div`
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2rem;
`;

const HomePage = () => {
  const { country, loading, error, refreshLocation } = useGeolocation();
  const { rankings, loading: rankingLoading, error: rankingError, fetchRankings, lastUpdated } = useRankingData();
  const [selectedCountries, setSelectedCountries] = useState([]);

  // 컴포넌트 마운트 시 랭킹 데이터 로드
  useEffect(() => {
    fetchRankings('daily', 10, 0);
  }, [fetchRankings]);

  // 지도에서 국가 선택 시 처리
  const handleMapCountrySelect = (countryCode) => {
    setSelectedCountries(prev => {
      if (prev.includes(countryCode)) {
        return prev.filter(code => code !== countryCode);
      } else {
        return [...prev, countryCode];
      }
    });
  };

  // CountrySelector에서 국가 변경 시 처리
  const handleCountriesChange = (newCountries) => {
    setSelectedCountries(newCountries);
  };

  return (
    <HomeContainer>
      <BackgroundEffect />
      <ContentWrapper>
        <HeaderSection>
          <MainTitle>여행하고 싶은 국가를 입력해주세요</MainTitle>
          <CurrentLocation>
            <LocationIcon>📍</LocationIcon>
            현재 위치 : {loading ? '위치 확인 중...' : country}
            <RefreshButton onClick={refreshLocation} title="위치 새로고침">
              🔄
            </RefreshButton>
          </CurrentLocation>
        </HeaderSection>

        <MainContentSection>
          <ContentColumn>
            <SearchSection>
              <WorldMap 
                selectedCountries={selectedCountries}
                onCountrySelect={handleMapCountrySelect}
              />
            </SearchSection>
            
            <SearchSection>
              <CountrySelector 
                selectedCountries={selectedCountries}
                onCountriesChange={handleCountriesChange}
              />
            </SearchSection>
            
            <RankingSection>
              <RankingHeader>
                <RankingIcon>⚡</RankingIcon>
                <RankingTitle>실시간 인기 여행지 랭킹</RankingTitle>
              </RankingHeader>
              <RankingList 
                rankings={rankings} 
                loading={rankingLoading} 
                error={rankingError}
                onRefresh={() => fetchRankings('daily', 10, 0)}
                lastUpdated={lastUpdated}
              />
            </RankingSection>
          </ContentColumn>
        </MainContentSection>
      </ContentWrapper>
    </HomeContainer>
  );
};

export default HomePage;