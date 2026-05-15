import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import useRankingData from '../../hooks/useRankingData';

const SelectorContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
`;

const SearchContainer = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
`;

const SearchInput = styled.input`
  flex: 1;
  padding: 1rem;
  border: 2px solid #3a3a3a;
  border-radius: 8px;
  font-size: 1rem;
  background-color: #1a1a1a;
  color: #f8f9fa;
  transition: all 0.3s ease;
  
  &::placeholder {
    color: #a0a0a0;
  }
  
  &:focus {
    outline: none;
    border-color: #ffd700;
    box-shadow: 0 0 0 3px rgba(255, 215, 0, 0.1);
  }
  
  @media (max-width: 480px) {
    padding: 0.75rem;
    font-size: 0.9rem;
  }
`;

const SearchButton = styled.button`
  background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
  color: #0a0a0a;
  border: none;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
  outline: none;
  
  &:hover {
    background: linear-gradient(135deg, #ffed4e 0%, #ffd700 100%);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(255, 215, 0, 0.4);
  }
  
  &:focus {
    outline: none;
  }
  
  &:active {
    outline: none;
  }
  
  &:disabled {
    background: linear-gradient(135deg, #3a3a3a 0%, #4a4a4a 100%);
    color: #a0a0a0;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  
  @media (max-width: 480px) {
    width: 45px;
    height: 45px;
  }
`;

const SelectedCountries = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: flex-start;
  width: 100%;
`;

const CountryTag = styled.div`
  display: flex;
  align-items: center;
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
  border: 2px solid #ffd700;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  font-size: 1.1rem;
  color: #ffd700;
  box-shadow: 0 2px 10px rgba(255, 215, 0, 0.2);
  transition: all 0.3s ease;
  
  &:hover {
    border-color: #ffed4e;
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
    transform: translateY(-2px);
  }
`;

const RemoveButton = styled.button`
  background: none;
  border: none;
  color: #a0a0a0;
  cursor: pointer;
  margin-left: 0.5rem;
  font-size: 1.2rem;
  transition: all 0.3s ease;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  outline: none;
  box-shadow: none;
  
  &:hover {
    color: #ff6b6b;
    background: rgba(255, 107, 107, 0.1);
    transform: scale(1.1);
  }
  
  &:focus {
    outline: none;
    box-shadow: none;
  }
  
  &:active {
    outline: none;
    box-shadow: none;
  }
`;

const DropdownContainer = styled.div`
  position: relative;
  width: 100%;
`;

const CountryList = styled.div`
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
  border: 1px solid #3a3a3a;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3), 0 0 0 1px rgba(255, 215, 0, 0.1);
  max-height: 300px;
  overflow-y: auto;
  z-index: 1000;
  margin-top: 4px;
`;

const CountryItem = styled.button`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border: none;
  background: ${props => {
    if (props.$isClicked) return 'linear-gradient(135deg, #2a4a2a 0%, #3a5a3a 100%)';
    if (props.$isActive) return 'linear-gradient(135deg, #2a2a4a 0%, #3a3a5a 100%)';
    return 'transparent';
  }};
  cursor: pointer;
  text-align: left;
  transition: all 0.3s ease;
  width: 100%;
  border-bottom: 1px solid #3a3a3a;
  color: ${props => props.$isClicked ? '#4ade80' : '#f8f9fa'};
  
  &:hover {
    background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
    color: #0a0a0a;
    transform: translateX(5px);
  }
  
  &:last-child {
    border-bottom: none;
  }
  
  &.highlighted {
    background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
    color: #0a0a0a;
  }
`;

const CountryFlag = styled.span`
  font-size: 1.2rem;
`;

const CountrySelector = ({ selectedCountries: externalSelectedCountries = [], onCountriesChange }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCountries, setSelectedCountries] = useState(externalSelectedCountries.length > 0 ? externalSelectedCountries : ['US', 'JP', 'GB']);
  const [showList, setShowList] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [clickedItem, setClickedItem] = useState(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const navigate = useNavigate();
  const { recordSelection } = useRankingData();

  // 데이터베이스의 69개 국가 데이터 (init-db.sql 기반)
  const countries = [
    // 주요 통화
    { code: 'US', name: '미국', flag: '🇺🇸', nameEn: 'United States', currency: 'USD' },
    { code: 'JP', name: '일본', flag: '🇯🇵', nameEn: 'Japan', currency: 'JPY' },
    { code: 'GB', name: '영국', flag: '🇬🇧', nameEn: 'United Kingdom', currency: 'GBP' },
    { code: 'CN', name: '중국', flag: '🇨🇳', nameEn: 'China', currency: 'CNY' },
    { code: 'AU', name: '호주', flag: '🇦🇺', nameEn: 'Australia', currency: 'AUD' },
    { code: 'CA', name: '캐나다', flag: '🇨🇦', nameEn: 'Canada', currency: 'CAD' },
    { code: 'CH', name: '스위스', flag: '🇨🇭', nameEn: 'Switzerland', currency: 'CHF' },
    { code: 'HK', name: '홍콩', flag: '🇭🇰', nameEn: 'Hong Kong', currency: 'HKD' },
    { code: 'SG', name: '싱가포르', flag: '🇸🇬', nameEn: 'Singapore', currency: 'SGD' },
    { code: 'KR', name: '한국', flag: '🇰🇷', nameEn: 'South Korea', currency: 'KRW' },

    // 추가 아시아 통화
    { code: 'TW', name: '대만', flag: '🇹🇼', nameEn: 'Taiwan', currency: 'TWD' },
    { code: 'MY', name: '말레이시아', flag: '🇲🇾', nameEn: 'Malaysia', currency: 'MYR' },
    { code: 'PH', name: '필리핀', flag: '🇵🇭', nameEn: 'Philippines', currency: 'PHP' },
    { code: 'ID', name: '인도네시아', flag: '🇮🇩', nameEn: 'Indonesia', currency: 'IDR' },
    { code: 'NZ', name: '뉴질랜드', flag: '🇳🇿', nameEn: 'New Zealand', currency: 'NZD' },
    { code: 'IL', name: '이스라엘', flag: '🇮🇱', nameEn: 'Israel', currency: 'ILS' },
    { code: 'AE', name: '아랍에미리트', flag: '🇦🇪', nameEn: 'United Arab Emirates', currency: 'AED' },
    { code: 'QA', name: '카타르', flag: '🇶🇦', nameEn: 'Qatar', currency: 'QAR' },
    { code: 'KW', name: '쿠웨이트', flag: '🇰🇼', nameEn: 'Kuwait', currency: 'KWD' },
    { code: 'BH', name: '바레인', flag: '🇧🇭', nameEn: 'Bahrain', currency: 'BHD' },
    { code: 'OM', name: '오만', flag: '🇴🇲', nameEn: 'Oman', currency: 'OMR' },
    { code: 'JO', name: '요르단', flag: '🇯🇴', nameEn: 'Jordan', currency: 'JOD' },
    { code: 'LB', name: '레바논', flag: '🇱🇧', nameEn: 'Lebanon', currency: 'LBP' },
    { code: 'PK', name: '파키스탄', flag: '🇵🇰', nameEn: 'Pakistan', currency: 'PKR' },
    { code: 'BD', name: '방글라데시', flag: '🇧🇩', nameEn: 'Bangladesh', currency: 'BDT' },
    { code: 'LK', name: '스리랑카', flag: '🇱🇰', nameEn: 'Sri Lanka', currency: 'LKR' },
    { code: 'NP', name: '네팔', flag: '🇳🇵', nameEn: 'Nepal', currency: 'NPR' },
    { code: 'AF', name: '아프가니스탄', flag: '🇦🇫', nameEn: 'Afghanistan', currency: 'AFN' },
    { code: 'KZ', name: '카자흐스탄', flag: '🇰🇿', nameEn: 'Kazakhstan', currency: 'KZT' },
    { code: 'UZ', name: '우즈베키스탄', flag: '🇺🇿', nameEn: 'Uzbekistan', currency: 'UZS' },
    { code: 'KG', name: '키르기스스탄', flag: '🇰🇬', nameEn: 'Kyrgyzstan', currency: 'KGS' },
    { code: 'TJ', name: '타지키스탄', flag: '🇹🇯', nameEn: 'Tajikistan', currency: 'TJS' },
    { code: 'TM', name: '투르크메니스탄', flag: '🇹🇲', nameEn: 'Turkmenistan', currency: 'TMT' },

    // 추가 유럽 통화
    { code: 'IS', name: '아이슬란드', flag: '🇮🇸', nameEn: 'Iceland', currency: 'ISK' },
    { code: 'RO', name: '루마니아', flag: '🇷🇴', nameEn: 'Romania', currency: 'RON' },
    { code: 'BG', name: '불가리아', flag: '🇧🇬', nameEn: 'Bulgaria', currency: 'BGN' },
    { code: 'HR', name: '크로아티아', flag: '🇭🇷', nameEn: 'Croatia', currency: 'HRK' },
    { code: 'RS', name: '세르비아', flag: '🇷🇸', nameEn: 'Serbia', currency: 'RSD' },
    { code: 'UA', name: '우크라이나', flag: '🇺🇦', nameEn: 'Ukraine', currency: 'UAH' },
    { code: 'BY', name: '벨라루스', flag: '🇧🇾', nameEn: 'Belarus', currency: 'BYN' },

    // 추가 아메리카 통화
    { code: 'AR', name: '아르헨티나', flag: '🇦🇷', nameEn: 'Argentina', currency: 'ARS' },
    { code: 'CL', name: '칠레', flag: '🇨🇱', nameEn: 'Chile', currency: 'CLP' },
    { code: 'CO', name: '콜롬비아', flag: '🇨🇴', nameEn: 'Colombia', currency: 'COP' },
    { code: 'PE', name: '페루', flag: '🇵🇪', nameEn: 'Peru', currency: 'PEN' },
    { code: 'UY', name: '우루과이', flag: '🇺🇾', nameEn: 'Uruguay', currency: 'UYU' },
    { code: 'BO', name: '볼리비아', flag: '🇧🇴', nameEn: 'Bolivia', currency: 'BOB' },
    { code: 'PY', name: '파라과이', flag: '🇵🇾', nameEn: 'Paraguay', currency: 'PYG' },
    { code: 'VE', name: '베네수엘라', flag: '🇻🇪', nameEn: 'Venezuela', currency: 'VES' },

    // 추가 아프리카/중동 통화
    { code: 'EG', name: '이집트', flag: '🇪🇬', nameEn: 'Egypt', currency: 'EGP' },
    { code: 'MA', name: '모로코', flag: '🇲🇦', nameEn: 'Morocco', currency: 'MAD' },
    { code: 'TN', name: '튀니지', flag: '🇹🇳', nameEn: 'Tunisia', currency: 'TND' },
    { code: 'NG', name: '나이지리아', flag: '🇳🇬', nameEn: 'Nigeria', currency: 'NGN' },
    { code: 'KE', name: '케냐', flag: '🇰🇪', nameEn: 'Kenya', currency: 'KES' },
    { code: 'UG', name: '우간다', flag: '🇺🇬', nameEn: 'Uganda', currency: 'UGX' },
    { code: 'TZ', name: '탄자니아', flag: '🇹🇿', nameEn: 'Tanzania', currency: 'TZS' },

    // 기타 주요 통화
    { code: 'CZ', name: '체코', flag: '🇨🇿', nameEn: 'Czech Republic', currency: 'CZK' },
    { code: 'DK', name: '덴마크', flag: '🇩🇰', nameEn: 'Denmark', currency: 'DKK' },
    { code: 'HU', name: '헝가리', flag: '🇭🇺', nameEn: 'Hungary', currency: 'HUF' },
    { code: 'NO', name: '노르웨이', flag: '🇳🇴', nameEn: 'Norway', currency: 'NOK' },
    { code: 'SE', name: '스웨덴', flag: '🇸🇪', nameEn: 'Sweden', currency: 'SEK' },
    { code: 'TH', name: '태국', flag: '🇹🇭', nameEn: 'Thailand', currency: 'THB' },
    { code: 'VN', name: '베트남', flag: '🇻🇳', nameEn: 'Vietnam', currency: 'VND' },
    { code: 'IN', name: '인도', flag: '🇮🇳', nameEn: 'India', currency: 'INR' },
    { code: 'BR', name: '브라질', flag: '🇧🇷', nameEn: 'Brazil', currency: 'BRL' },
    { code: 'RU', name: '러시아', flag: '🇷🇺', nameEn: 'Russia', currency: 'RUB' },
    { code: 'MX', name: '멕시코', flag: '🇲🇽', nameEn: 'Mexico', currency: 'MXN' },
    { code: 'ZA', name: '남아프리카 공화국', flag: '🇿🇦', nameEn: 'South Africa', currency: 'ZAR' },
    { code: 'TR', name: '터키', flag: '🇹🇷', nameEn: 'Turkey', currency: 'TRY' }
  ];

  // 디바운싱 효과
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // 개선된 필터링 (한국어, 영어, 코드 모두 검색 가능 + 이미 선택된 국가 제외)
  const filteredCountries = countries.filter(country => {
    // 이미 선택된 국가는 제외
    if (selectedCountries.includes(country.code)) {
      return false;
    }
    
    const searchLower = debouncedSearchTerm.toLowerCase();
    return (
      country.name.toLowerCase().includes(searchLower) ||
      country.nameEn.toLowerCase().includes(searchLower) ||
      country.code.toLowerCase().includes(searchLower)
    );
  }).sort((a, b) => {
    // 검색어와 정확히 일치하는 것을 우선순위로 정렬
    const searchLower = debouncedSearchTerm.toLowerCase();
    const aExactMatch = a.name.toLowerCase() === searchLower || a.nameEn.toLowerCase() === searchLower;
    const bExactMatch = b.name.toLowerCase() === searchLower || b.nameEn.toLowerCase() === searchLower;
    
    if (aExactMatch && !bExactMatch) return -1;
    if (!aExactMatch && bExactMatch) return 1;
    
    // 그 다음으로 시작하는 것을 우선순위로
    const aStartsWith = a.name.toLowerCase().startsWith(searchLower) || a.nameEn.toLowerCase().startsWith(searchLower);
    const bStartsWith = b.name.toLowerCase().startsWith(searchLower) || b.nameEn.toLowerCase().startsWith(searchLower);
    
    if (aStartsWith && !bStartsWith) return -1;
    if (!aStartsWith && bStartsWith) return 1;
    
    return a.name.localeCompare(b.name);
  });

  const handleCountrySelect = async (country) => {
    if (!selectedCountries.includes(country.code)) {
      // 클릭 애니메이션 효과 시작
      setClickedItem(country.code);
      
      // 0.5초 후 애니메이션 효과 제거
      setTimeout(() => {
        setClickedItem(null);
      }, 500);
      
      const newSelectedCountries = [...selectedCountries, country.code];
      setSelectedCountries(newSelectedCountries);
      
      // 외부 컴포넌트에 변경사항 전달
      if (onCountriesChange) {
        onCountriesChange(newSelectedCountries);
      }
      
      // 랭킹 서비스에 사용자 선택 기록
      try {
        await recordSelection(country.code);
        console.log(`국가 선택 기록 완료: ${country.name} (${country.code})`);
      } catch (error) {
        console.error('국가 선택 기록 실패:', error);
        // 기록 실패는 사용자 경험에 영향을 주지 않음
      }
    }
    setSearchTerm('');
    setShowList(false);
    setHighlightedIndex(-1);
    inputRef.current?.focus();
  };

  const handleCountryRemove = (countryCode) => {
    const newSelectedCountries = selectedCountries.filter(code => code !== countryCode);
    setSelectedCountries(newSelectedCountries);
    
    // 외부 컴포넌트에 변경사항 전달
    if (onCountriesChange) {
      onCountriesChange(newSelectedCountries);
    }
  };

  const getCountryInfo = (code) => {
    return countries.find(country => country.code === code);
  };

  // 검색 실행 함수
  const handleSearch = () => {
    if (selectedCountries.length === 0) {
      alert('비교할 국가를 최소 1개 이상 선택해주세요.');
      return;
    }
    
    // 선택된 국가들을 URL 파라미터로 전달
    const countriesParam = selectedCountries.join(',');
    navigate(`/comparison?countries=${countriesParam}`);
  };

  // 키보드 네비게이션 핸들러
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !showList) {
      // 드롭다운이 열려있지 않을 때 Enter키를 누르면 검색 실행
      e.preventDefault();
      handleSearch();
      return;
    }

    if (!showList || filteredCountries.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(prev => 
          prev < filteredCountries.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(prev => 
          prev > 0 ? prev - 1 : filteredCountries.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < filteredCountries.length) {
          handleCountrySelect(filteredCountries[highlightedIndex]);
        }
        break;
      case 'Escape':
        setShowList(false);
        setHighlightedIndex(-1);
        inputRef.current?.blur();
        break;
    }
  };

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (listRef.current && !listRef.current.contains(event.target) && 
          inputRef.current && !inputRef.current.contains(event.target)) {
        setShowList(false);
        setHighlightedIndex(-1);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <SelectorContainer>
      <SearchContainer>
        <DropdownContainer>
        <SearchInput
            ref={inputRef}
          type="text"
            placeholder="국가를 검색하세요 (한국어/영어/코드)"
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setShowList(true);
              setHighlightedIndex(-1);
          }}
          onFocus={() => setShowList(true)}
            onKeyDown={handleKeyDown}
          />
          
          {showList && debouncedSearchTerm && (
            <CountryList ref={listRef}>
              {filteredCountries.length > 0 ? (
                filteredCountries.map((country, index) => (
                  <CountryItem
                    key={country.code}
                    $isActive={index === highlightedIndex}
                    $isClicked={clickedItem === country.code}
                    className={index === highlightedIndex ? 'highlighted' : ''}
                    onClick={() => handleCountrySelect(country)}
                  >
                    <CountryFlag>{country.flag}</CountryFlag>
                    <div>
                      <div>{country.name}</div>
                      <div style={{ fontSize: '0.8rem', color: '#666' }}>
                        {country.nameEn}
                      </div>
                    </div>
                  </CountryItem>
                ))
              ) : (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666' }}>
                  검색 결과가 없습니다
                </div>
              )}
            </CountryList>
          )}
        </DropdownContainer>
        
        <SearchButton onClick={handleSearch} title="선택된 국가들 비교하기">
          🔍
        </SearchButton>
      </SearchContainer>

      <SelectedCountries>
        {selectedCountries.map(countryCode => {
          const country = getCountryInfo(countryCode);
          return (
            <CountryTag key={countryCode}>
              <CountryFlag>{country?.flag}</CountryFlag>
              <span>{country?.name}</span>
              <RemoveButton onClick={() => handleCountryRemove(countryCode)}>
                ×
              </RemoveButton>
            </CountryTag>
          );
        })}
      </SelectedCountries>
    </SelectorContainer>
  );
};

export default CountrySelector;
