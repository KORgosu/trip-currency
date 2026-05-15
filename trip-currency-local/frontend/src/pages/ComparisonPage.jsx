import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import ExchangeRateChart from '../components/country/ExchangeRateChart';
import CountryCard from '../components/country/CountryCard';
import BackgroundEffect from '../components/common/BackgroundEffect';
import useCurrencyData from '../hooks/useCurrencyData';
import apiService from '../services/api';

const ComparisonContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
  background: transparent;
  min-height: 100vh;
  color: #ffd700;
  position: relative;
  z-index: 1;
`;

const PageTitle = styled.h1`
  color: #ffd700;
  margin-bottom: 2rem;
  text-align: center;
`;

const ChartSection = styled.section`
  background: #2a2a2a;
  padding: 2rem;
  border-radius: 10px;
  border: 2px solid #ffd700;
  box-shadow: 0 2px 10px rgba(255, 215, 0, 0.2);
  margin-bottom: 2rem;
  min-height: 500px;
  position: relative;
`;

const SectionTitle = styled.h2`
  color: #ffd700;
  margin-bottom: 1.5rem;
`;

const CountriesGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
`;

const BackButton = styled.button`
  background-color: #2a2a2a;
  color: #ffd700;
  border: 2px solid #ffd700;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  cursor: pointer;
  margin-bottom: 2rem;
  transition: all 0.3s;
  
  &:hover {
    background-color: #ffd700;
    color: #1a1a1a;
  }
`;

const NoCountriesMessage = styled.div`
  text-align: center;
  padding: 3rem;
  color: #ffd700;
  font-size: 1.1rem;
`;

const RefreshButton = styled.button`
  background-color: #2a2a2a;
  color: #ffd700;
  border: 2px solid #ffd700;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  cursor: pointer;
  margin-left: 1rem;
  transition: all 0.3s;
  
  &:hover {
    background-color: #ffd700;
    color: #1a1a1a;
  }
  
  &:disabled {
    background-color: #666666;
    color: #999999;
    border-color: #666666;
    cursor: not-allowed;
  }
`;

const HeaderActions = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
`;

const TimeRangeSelector = styled.div`
  display: flex;
  gap: 0.5rem;
  position: absolute;
  top: calc(1rem + 5px);
  right: 1rem;
  z-index: 10;
`;

const TimeButton = styled.button`
  padding: 0.4rem 0.8rem;
  border: 1px solid #ffd700;
  background: #2a2a2a;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.3s;
  color: #ffd700;
  font-size: 0.9rem;
  box-shadow: 0 2px 4px rgba(255, 215, 0, 0.2);
  
  &:hover {
    background-color: #ffd700;
    color: #1a1a1a;
    box-shadow: 0 2px 8px rgba(255, 215, 0, 0.3);
  }
  
  &.active {
    background-color: #ffd700;
    color: #1a1a1a;
    border-color: #ffd700;
    box-shadow: 0 2px 8px rgba(255, 215, 0, 0.4);
  }
`;

const ComparisonPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [selectedCountries, setSelectedCountries] = useState([]);
  const [timeRange, setTimeRange] = useState('realtime');
  const [selectedChartCountry, setSelectedChartCountry] = useState(null);
  const { fetchAllData, loading } = useCurrencyData();

  const timeRanges = [
    { value: 'realtime', label: '실시간' }
  ];

  // 국가 코드를 통화 코드로 변환하는 함수 (확장된 매핑)
  const getCurrencyCode = (countryCode) => {
    const countryToCurrency = {
      // 주요 국가들
      'US': 'USD', 'JP': 'JPY', 'GB': 'GBP', 'CN': 'CNY', 'KR': 'KRW',
      'DE': 'EUR', 'FR': 'EUR', 'IT': 'EUR', 'ES': 'EUR', 'NL': 'EUR',
      'BE': 'EUR', 'AT': 'EUR', 'FI': 'EUR', 'IE': 'EUR', 'PT': 'EUR',
      'GR': 'EUR', 'LU': 'EUR', 'MT': 'EUR', 'CY': 'EUR', 'SK': 'EUR',
      'SI': 'EUR', 'EE': 'EUR', 'LV': 'EUR', 'LT': 'EUR',
      
      // 아시아-태평양
      'AU': 'AUD', 'NZ': 'NZD', 'SG': 'SGD', 'HK': 'HKD', 'TW': 'TWD',
      'TH': 'THB', 'MY': 'MYR', 'ID': 'IDR', 'PH': 'PHP', 'VN': 'VND',
      'IN': 'INR', 'PK': 'PKR', 'BD': 'BDT', 'LK': 'LKR', 'NP': 'NPR',
      'MM': 'MMK', 'KH': 'KHR', 'LA': 'LAK', 'BN': 'BND', 'FJ': 'FJD',
      'PG': 'PGK', 'SB': 'SBD', 'VU': 'VUV', 'WS': 'WST', 'TO': 'TOP',
      'KI': 'AUD', 'TV': 'AUD', 'NR': 'AUD', 'PW': 'USD', 'FM': 'USD',
      'MH': 'USD',
      
      // 아메리카
      'CA': 'CAD', 'MX': 'MXN', 'BR': 'BRL', 'AR': 'ARS', 'CL': 'CLP',
      'CO': 'COP', 'PE': 'PEN', 'VE': 'VES', 'UY': 'UYU', 'PY': 'PYG',
      'BO': 'BOB', 'EC': 'USD', 'GY': 'GYD', 'SR': 'SRD', 'TT': 'TTD',
      'JM': 'JMD', 'BB': 'BBD', 'BZ': 'BZD', 'GT': 'GTQ', 'HN': 'HNL',
      'SV': 'USD', 'NI': 'NIO', 'CR': 'CRC', 'PA': 'PAB', 'CU': 'CUP',
      'DO': 'DOP', 'HT': 'HTG', 'PR': 'USD', 'VI': 'USD', 'AG': 'XCD',
      'DM': 'XCD', 'GD': 'XCD', 'KN': 'XCD', 'LC': 'XCD', 'VC': 'XCD',
      
      // 유럽 (EUR 외)
      'CH': 'CHF', 'SE': 'SEK', 'NO': 'NOK', 'DK': 'DKK', 'IS': 'ISK',
      'PL': 'PLN', 'CZ': 'CZK', 'HU': 'HUF', 'RO': 'RON', 'BG': 'BGN',
      'HR': 'HRK', 'RS': 'RSD', 'BA': 'BAM', 'ME': 'EUR', 'MK': 'MKD',
      'AL': 'ALL', 'XK': 'EUR', 'MD': 'MDL', 'UA': 'UAH', 'BY': 'BYN',
      'RU': 'RUB', 'KZ': 'KZT', 'KG': 'KGS', 'TJ': 'TJS', 'TM': 'TMT',
      'UZ': 'UZS', 'GE': 'GEL', 'AM': 'AMD', 'AZ': 'AZN', 'TR': 'TRY',
      
      // 중동 및 아프리카
      'SA': 'SAR', 'AE': 'AED', 'KW': 'KWD', 'QA': 'QAR', 'BH': 'BHD',
      'OM': 'OMR', 'JO': 'JOD', 'LB': 'LBP', 'SY': 'SYP', 'IQ': 'IQD',
      'IR': 'IRR', 'IL': 'ILS', 'PS': 'ILS', 'EG': 'EGP', 'LY': 'LYD',
      'TN': 'TND', 'DZ': 'DZD', 'MA': 'MAD', 'SD': 'SDG', 'SS': 'SSP',
      'ET': 'ETB', 'ER': 'ERN', 'DJ': 'DJF', 'SO': 'SOS', 'KE': 'KES',
      'UG': 'UGX', 'TZ': 'TZS', 'RW': 'RWF', 'BI': 'BIF', 'MW': 'MWK',
      'ZM': 'ZMW', 'ZW': 'ZWL', 'BW': 'BWP', 'NA': 'NAD', 'SZ': 'SZL',
      'LS': 'LSL', 'MZ': 'MZN', 'MG': 'MGA', 'MU': 'MUR', 'SC': 'SCR',
      'KM': 'KMF', 'YT': 'EUR', 'RE': 'EUR', 'ZA': 'ZAR', 'AO': 'AOA',
      'CD': 'CDF', 'CG': 'XAF', 'CM': 'XAF', 'CF': 'XAF', 'TD': 'XAF',
      'GQ': 'XAF', 'GA': 'XAF', 'ST': 'STN', 'BJ': 'XOF', 'BF': 'XOF',
      'CI': 'XOF', 'GM': 'GMD', 'GN': 'GNF', 'GW': 'XOF', 'LR': 'LRD',
      'ML': 'XOF', 'MR': 'MRU', 'NE': 'XOF', 'SN': 'XOF', 'SL': 'SLE',
      'TG': 'XOF', 'CV': 'CVE', 'GH': 'GHS', 'NG': 'NGN'
    };
    return countryToCurrency[countryCode] || 'USD';
  };

  // 차트 클릭 핸들러
  const handleChartClick = (countryCode) => {
    setSelectedChartCountry(countryCode);
  };

  useEffect(() => {
    const countriesParam = searchParams.get('countries');
    if (countriesParam) {
      const countries = countriesParam.split(',').filter(country => country.trim());
      setSelectedCountries(countries);
    } else {
      // URL 파라미터가 없으면 기본 국가들로 설정
      setSelectedCountries(['US', 'JP', 'GB', 'CN']);
    }
  }, [searchParams]);

  // 랭킹 기능 제거됨 - 더 이상 선택된 국가들의 점수를 증가시키지 않음

  const handleBackToHome = () => {
    navigate('/');
  };

  const handleRefreshData = async () => {
    try {
      await fetchAllData();
    } catch (error) {
      console.error('데이터 새로고침 실패:', error);
    }
  };

  return (
    <ComparisonContainer>
      <BackgroundEffect />
      <HeaderActions>
        <BackButton onClick={handleBackToHome}>
          ← 홈으로 돌아가기
        </BackButton>
        
        <RefreshButton onClick={handleRefreshData} disabled={loading}>
          {loading ? '새로고침 중...' : '🔄 데이터 새로고침'}
        </RefreshButton>
      </HeaderActions>
      
      <PageTitle>
        {selectedCountries.length > 0 
          ? `선택된 ${selectedCountries.length}개국 실시간 환율 및 물가 지수 비교`
          : '국가별 실시간 환율 및 물가 지수 비교'
        }
      </PageTitle>
      
      <ChartSection>
        <SectionTitle>
          {selectedChartCountry ? `${selectedChartCountry} 환율 차트` : '환율 차트'}
        </SectionTitle>
        
        <TimeRangeSelector>
          <TimeButton className="active">
            📊 하루 차트 (5분 단위)
          </TimeButton>
        </TimeRangeSelector>
        
        <ExchangeRateChart 
          currencyCode={getCurrencyCode(selectedChartCountry || selectedCountries[0]) || 'USD'} 
          timeRange={timeRange} 
        />
      </ChartSection>

      {selectedCountries.length > 0 ? (
        <CountriesGrid>
          {selectedCountries.map(countryCode => (
            <CountryCard 
              key={countryCode} 
              country={countryCode} 
              onChartClick={handleChartClick}
            />
          ))}
        </CountriesGrid>
      ) : (
        <NoCountriesMessage>
          비교할 국가가 선택되지 않았습니다.
          <br />
          홈페이지에서 국가를 선택한 후 다시 시도해주세요.
        </NoCountriesMessage>
      )}
    </ComparisonContainer>
  );
};

export default ComparisonPage;
