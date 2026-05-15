import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import useCurrencyData from '../../hooks/useCurrencyData';

const CardContainer = styled.div`
  background: #2a2a2a;
  border: 2px solid #ffd700;
  border-radius: 10px;
  padding: 1.5rem;
  box-shadow: 0 2px 10px rgba(255, 215, 0, 0.2);
  transition: transform 0.3s, box-shadow 0.3s;
  
  &:hover {
    transform: translateY(-5px);
    box-shadow: 0 5px 20px rgba(255, 215, 0, 0.3);
  }
`;

const CardHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
`;

const CountryFlag = styled.span`
  font-size: 2rem;
`;

const CountryInfo = styled.div`
  flex: 1;
`;

const CountryName = styled.h3`
  margin: 0;
  color: #ffd700;
  font-size: 1.2rem;
`;

const CountryCode = styled.p`
  margin: 0;
  color: #ffed4e;
  font-size: 0.9rem;
`;

const ChartIcon = styled.button`
  background: none;
  border: 1px solid #ffd700;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 6px;
  color: #ffd700;
  transition: all 0.2s;
  
  &:hover {
    background: #ffd700;
    color: #1a1a1a;
  }
  
  &:active {
    transform: scale(0.95);
  }
`;

const ExchangeRateSection = styled.div`
  margin-bottom: 1rem;
`;

const RateLabel = styled.div`
  font-size: 0.85rem;
  color: #ffed4e;
  margin-bottom: 0.3rem;
`;

const RateValue = styled.div`
  font-size: 1.4rem;
  font-weight: bold;
  color: #ffd700;
  margin-bottom: 0.2rem;
`;

const RateChange = styled.div`
  font-size: 0.8rem;
  color: ${props => props.$positive ? '#ffed4e' : '#ff6666'};
`;

const LoadingIndicator = styled.div`
  text-align: center;
  color: #ffd700;
  font-size: 0.9rem;
  padding: 1rem 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
`;

const LoadingSpinner = styled.div`
  width: 20px;
  height: 20px;
  border: 2px solid #2a2a2a;
  border-top: 2px solid #ffd700;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const ErrorMessage = styled.div`
  text-align: center;
  color: #ff6666;
  font-size: 0.9rem;
  padding: 1rem 0;
`;

const DataInsufficientMessage = styled.div`
  text-align: center;
  color: #ffd700;
  font-size: 0.9rem;
  padding: 1rem 0;
  background-color: #2a2a2a;
  border-radius: 6px;
  border: 1px solid #ffd700;
  margin: 0.5rem 0;
`;

const DataInsufficientIcon = styled.span`
  font-size: 1.2rem;
  margin-right: 0.5rem;
`;

const LastUpdated = styled.div`
  font-size: 0.75rem;
  color: #ffed4e;
  text-align: center;
  padding-top: 1rem;
  border-top: 1px solid #ffd700;
`;

const CountryCard = ({ country, onChartClick }) => {
  const { exchangeRates, loading, error, fetchExchangeRates } = useCurrencyData();
  const [localData, setLocalData] = useState({
    exchangeRate: null,
    lastUpdated: null
  });
  const [dataInsufficient, setDataInsufficient] = useState(false);

  const countryInfo = {
    US: { name: '미국', flag: '🇺🇸', currency: 'USD' },
    JP: { name: '일본', flag: '🇯🇵', currency: 'JPY' },
    GB: { name: '영국', flag: '🇬🇧', currency: 'GBP' },
    CN: { name: '중국', flag: '🇨🇳', currency: 'CNY' },
    CA: { name: '캐나다', flag: '🇨🇦', currency: 'CAD' },
    AU: { name: '호주', flag: '🇦🇺', currency: 'AUD' },
    DE: { name: '독일', flag: '🇩🇪', currency: 'EUR' },
    FR: { name: '프랑스', flag: '🇫🇷', currency: 'EUR' },
    IT: { name: '이탈리아', flag: '🇮🇹', currency: 'EUR' },
    ES: { name: '스페인', flag: '🇪🇸', currency: 'EUR' },
    CH: { name: '스위스', flag: '🇨🇭', currency: 'CHF' },
    SE: { name: '스웨덴', flag: '🇸🇪', currency: 'SEK' },
    NO: { name: '노르웨이', flag: '🇳🇴', currency: 'NOK' },
    DK: { name: '덴마크', flag: '🇩🇰', currency: 'DKK' },
    NZ: { name: '뉴질랜드', flag: '🇳🇿', currency: 'NZD' },
    SG: { name: '싱가포르', flag: '🇸🇬', currency: 'SGD' },
    HK: { name: '홍콩', flag: '🇭🇰', currency: 'HKD' },
    TW: { name: '대만', flag: '🇹🇼', currency: 'TWD' },
    TH: { name: '태국', flag: '🇹🇭', currency: 'THB' },
    MY: { name: '말레이시아', flag: '🇲🇾', currency: 'MYR' },
    ID: { name: '인도네시아', flag: '🇮🇩', currency: 'IDR' },
    PH: { name: '필리핀', flag: '🇵🇭', currency: 'PHP' },
    VN: { name: '베트남', flag: '🇻🇳', currency: 'VND' },
    IN: { name: '인도', flag: '🇮🇳', currency: 'INR' },
    BR: { name: '브라질', flag: '🇧🇷', currency: 'BRL' },
    MX: { name: '멕시코', flag: '🇲🇽', currency: 'MXN' },
    RU: { name: '러시아', flag: '🇷🇺', currency: 'RUB' },
    ZA: { name: '남아프리카', flag: '🇿🇦', currency: 'ZAR' },
    TR: { name: '터키', flag: '🇹🇷', currency: 'TRY' },
    IL: { name: '이스라엘', flag: '🇮🇱', currency: 'ILS' },
    AE: { name: '아랍에미리트', flag: '🇦🇪', currency: 'AED' },
    SA: { name: '사우디아라비아', flag: '🇸🇦', currency: 'SAR' },
    KW: { name: '쿠웨이트', flag: '🇰🇼', currency: 'KWD' },
    QA: { name: '카타르', flag: '🇶🇦', currency: 'QAR' },
    BH: { name: '바레인', flag: '🇧🇭', currency: 'BHD' },
    OM: { name: '오만', flag: '🇴🇲', currency: 'OMR' },
    JO: { name: '요르단', flag: '🇯🇴', currency: 'JOD' },
    EG: { name: '이집트', flag: '🇪🇬', currency: 'EGP' },
    MA: { name: '모로코', flag: '🇲🇦', currency: 'MAD' },
    NG: { name: '나이지리아', flag: '🇳🇬', currency: 'NGN' },
    KE: { name: '케냐', flag: '🇰🇪', currency: 'KES' },
    GH: { name: '가나', flag: '🇬🇭', currency: 'GHS' },
    ET: { name: '에티오피아', flag: '🇪🇹', currency: 'ETB' },
    UG: { name: '우간다', flag: '🇺🇬', currency: 'UGX' },
    TZ: { name: '탄자니아', flag: '🇹🇿', currency: 'TZS' },
    ZW: { name: '짐바브웨', flag: '🇿🇼', currency: 'ZWL' },
    BW: { name: '보츠와나', flag: '🇧🇼', currency: 'BWP' },
    NA: { name: '나미비아', flag: '🇳🇦', currency: 'NAD' },
    SZ: { name: '에스와티니', flag: '🇸🇿', currency: 'SZL' },
    LS: { name: '레소토', flag: '🇱🇸', currency: 'LSL' },
    MZ: { name: '모잠비크', flag: '🇲🇿', currency: 'MZN' },
    MW: { name: '말라위', flag: '🇲🇼', currency: 'MWK' },
    ZM: { name: '잠비아', flag: '🇿🇲', currency: 'ZMW' },
    AO: { name: '앙골라', flag: '🇦🇴', currency: 'AOA' },
    CD: { name: '콩고민주공화국', flag: '🇨🇩', currency: 'CDF' },
    CG: { name: '콩고공화국', flag: '🇨🇬', currency: 'XAF' },
    CM: { name: '카메룬', flag: '🇨🇲', currency: 'XAF' },
    CF: { name: '중앙아프리카공화국', flag: '🇨🇫', currency: 'XAF' },
    TD: { name: '차드', flag: '🇹🇩', currency: 'XAF' },
    GQ: { name: '적도기니', flag: '🇬🇶', currency: 'XAF' },
    GA: { name: '가봉', flag: '🇬🇦', currency: 'XAF' },
    ST: { name: '상투메프린시페', flag: '🇸🇹', currency: 'STN' },
    BJ: { name: '베냉', flag: '🇧🇯', currency: 'XOF' },
    BF: { name: '부르키나파소', flag: '🇧🇫', currency: 'XOF' },
    CI: { name: '코트디부아르', flag: '🇨🇮', currency: 'XOF' },
    GM: { name: '감비아', flag: '🇬🇲', currency: 'GMD' },
    GN: { name: '기니', flag: '🇬🇳', currency: 'GNF' },
    GW: { name: '기니비사우', flag: '🇬🇼', currency: 'XOF' },
    LR: { name: '라이베리아', flag: '🇱🇷', currency: 'LRD' },
    ML: { name: '말리', flag: '🇲🇱', currency: 'XOF' },
    MR: { name: '모리타니', flag: '🇲🇷', currency: 'MRU' },
    NE: { name: '니제르', flag: '🇳🇪', currency: 'XOF' },
    SN: { name: '세네갈', flag: '🇸🇳', currency: 'XOF' },
    SL: { name: '시에라리온', flag: '🇸🇱', currency: 'SLE' },
    TG: { name: '토고', flag: '🇹🇬', currency: 'XOF' },
    CV: { name: '카보베르데', flag: '🇨🇻', currency: 'CVE' },
    DZ: { name: '알제리', flag: '🇩🇿', currency: 'DZD' },
    LY: { name: '리비아', flag: '🇱🇾', currency: 'LYD' },
    SD: { name: '수단', flag: '🇸🇩', currency: 'SDG' },
    SS: { name: '남수단', flag: '🇸🇸', currency: 'SSP' },
    TN: { name: '튀니지', flag: '🇹🇳', currency: 'TND' }
  };

  const info = countryInfo[country] || { name: country, flag: '🏳️', currency: 'USD' };

  useEffect(() => {
    const loadData = async () => {
      try {
        setDataInsufficient(false);
        await fetchExchangeRates(info.currency, 'KRW');
      } catch (err) {
        console.error(`Failed to load exchange rate for ${country}:`, err);
        setDataInsufficient(true);
      }
    };

    loadData();
  }, [country, info.currency, fetchExchangeRates]);

  useEffect(() => {
    if (exchangeRates && exchangeRates.rates) {
      const rate = exchangeRates.rates[info.currency];
      if (rate && rate > 0) {
        setLocalData({
          exchangeRate: rate,
          lastUpdated: new Date().toLocaleTimeString('ko-KR')
        });
        setDataInsufficient(false);
      } else {
        setDataInsufficient(true);
      }
    } else if (exchangeRates && !exchangeRates.rates) {
      setDataInsufficient(true);
    }
  }, [exchangeRates, info.currency]);

  const handleChartClick = () => {
    if (onChartClick) {
      onChartClick(country, info.currency);
    }
  };

  return (
    <CardContainer>
      <CardHeader>
        <CountryFlag>{info.flag}</CountryFlag>
        <CountryInfo>
          <CountryName>{info.name}</CountryName>
          <CountryCode>{info.currency}</CountryCode>
        </CountryInfo>
        <ChartIcon onClick={handleChartClick} title="차트 보기">
          📊
        </ChartIcon>
      </CardHeader>

      <ExchangeRateSection>
        {loading ? (
          <LoadingIndicator>
            <LoadingSpinner />
            환율 로딩 중...
          </LoadingIndicator>
        ) : error ? (
          <ErrorMessage>
            <div style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>⚠️</div>
            환율 정보를 불러올 수 없습니다
          </ErrorMessage>
        ) : dataInsufficient ? (
          <DataInsufficientMessage>
            <DataInsufficientIcon>📉</DataInsufficientIcon>
            데이터 부족!
          </DataInsufficientMessage>
        ) : localData.exchangeRate ? (
          <>
            <RateLabel>KRW 기준</RateLabel>
            <RateValue>
              {localData.exchangeRate 
                ? `₩${Number(localData.exchangeRate).toLocaleString()}`
                : 'N/A'
              }
            </RateValue>
            <RateChange $positive={true}>
              {info.currency}
            </RateChange>
          </>
        ) : (
          <LoadingIndicator>
            <div style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>📊</div>
            데이터 없음
          </LoadingIndicator>
        )}
      </ExchangeRateSection>

      {localData.lastUpdated && (
        <LastUpdated>
          마지막 업데이트: {localData.lastUpdated}
        </LastUpdated>
      )}
    </CardContainer>
  );
};

export default CountryCard;