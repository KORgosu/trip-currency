import React, { useState, useEffect, useRef } from 'react';
import styled, { keyframes } from 'styled-components';
import * as d3 from 'd3';
import { feature } from 'topojson-client';

const blinkAnimation = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
`;

const goldBlinkAnimation = keyframes`
  0%, 100% {
    fill: #ffd700;
    stroke: #ffd700;
    opacity: 1;
  }
  50% {
    fill: #ffed4e;
    stroke: #ffed4e;
    opacity: 0.7;
  }
`;

const selectedCountryBlinkAnimation = keyframes`
  0%, 100% {
    fill: #ff4444;
    stroke: #ff6666;
    stroke-width: 2px;
  }
  50% {
    fill: #ff6666;
    stroke: #ff8888;
    stroke-width: 3px;
  }
`;

const MapContainer = styled.div`
  width: 100%;
  max-width: 1000px;
  margin: 0 auto;
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
  border: 1px solid #3a3a3a;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3), 0 0 0 1px rgba(255, 215, 0, 0.1);

  @media (max-width: 768px) {
    padding: 1rem;
  }
`;

const MapTitle = styled.h3`
  color: #ffd700;
  text-align: center;
  margin-bottom: 1rem;
  font-size: 1.2rem;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
`;

const SVGContainer = styled.div`
  width: 100%;
  height: 500px;
  border: 3px solid #3a3a3a;
  border-radius: 12px;
  background: #0a0a0a;
  overflow: hidden;
  position: relative;

  svg {
    width: 100%;
    height: 100%;
    cursor: grab;

    &:active {
      cursor: grabbing;
    }
  }
`;



const LoadingMessage = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
  color: #ffd700;
  font-size: 1.1rem;
`;


const WorldMap = ({ selectedCountries = [], onCountrySelect }) => {
  const svgRef = useRef();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [worldData, setWorldData] = useState(null);
  const [currentHighlighted, setCurrentHighlighted] = useState(null);

  // 데이터베이스 69개 국가와 ISO3/영어명 매핑 (ISO3 → 2자리 코드)
  const countryMapping = {
    // 주요 통화
    'USA': { code: 'US', names: ['미국', 'United States', 'United States of America'], currency: 'USD' },
    'JPN': { code: 'JP', names: ['일본', 'Japan'], currency: 'JPY' },
    'GBR': { code: 'GB', names: ['영국', 'United Kingdom', 'UK'], currency: 'GBP' },
    'CHN': { code: 'CN', names: ['중국', 'China'], currency: 'CNY' },
    'AUS': { code: 'AU', names: ['호주', 'Australia'], currency: 'AUD' },
    'CAN': { code: 'CA', names: ['캐나다', 'Canada'], currency: 'CAD' },
    'CHE': { code: 'CH', names: ['스위스', 'Switzerland'], currency: 'CHF' },
    'HKG': { code: 'HK', names: ['홍콩', 'Hong Kong'], currency: 'HKD' },
    'SGP': { code: 'SG', names: ['싱가포르', 'Singapore'], currency: 'SGD' },
    'KOR': { code: 'KR', names: ['한국', 'South Korea', '대한민국'], currency: 'KRW' },

    // 추가 아시아 국가
    'TWN': { code: 'TW', names: ['대만', 'Taiwan'], currency: 'TWD' },
    'MYS': { code: 'MY', names: ['말레이시아', 'Malaysia'], currency: 'MYR' },
    'PHL': { code: 'PH', names: ['필리핀', 'Philippines'], currency: 'PHP' },
    'IDN': { code: 'ID', names: ['인도네시아', 'Indonesia'], currency: 'IDR' },
    'NZL': { code: 'NZ', names: ['뉴질랜드', 'New Zealand'], currency: 'NZD' },
    'ISR': { code: 'IL', names: ['이스라엘', 'Israel'], currency: 'ILS' },
    'ARE': { code: 'AE', names: ['아랍에미리트', 'United Arab Emirates', 'UAE'], currency: 'AED' },
    'QAT': { code: 'QA', names: ['카타르', 'Qatar'], currency: 'QAR' },
    'KWT': { code: 'KW', names: ['쿠웨이트', 'Kuwait'], currency: 'KWD' },
    'BHR': { code: 'BH', names: ['바레인', 'Bahrain'], currency: 'BHD' },
    'OMN': { code: 'OM', names: ['오만', 'Oman'], currency: 'OMR' },
    'JOR': { code: 'JO', names: ['요르단', 'Jordan'], currency: 'JOD' },
    'LBN': { code: 'LB', names: ['레바논', 'Lebanon'], currency: 'LBP' },
    'PAK': { code: 'PK', names: ['파키스탄', 'Pakistan'], currency: 'PKR' },
    'BGD': { code: 'BD', names: ['방글라데시', 'Bangladesh'], currency: 'BDT' },
    'LKA': { code: 'LK', names: ['스리랑카', 'Sri Lanka'], currency: 'LKR' },
    'NPL': { code: 'NP', names: ['네팔', 'Nepal'], currency: 'NPR' },
    'AFG': { code: 'AF', names: ['아프가니스탄', 'Afghanistan'], currency: 'AFN' },
    'KAZ': { code: 'KZ', names: ['카자흐스탄', 'Kazakhstan'], currency: 'KZT' },
    'UZB': { code: 'UZ', names: ['우즈베키스탄', 'Uzbekistan'], currency: 'UZS' },
    'KGZ': { code: 'KG', names: ['키르기스스탄', 'Kyrgyzstan'], currency: 'KGS' },
    'TJK': { code: 'TJ', names: ['타지키스탄', 'Tajikistan'], currency: 'TJS' },
    'TKM': { code: 'TM', names: ['투르크메니스탄', 'Turkmenistan'], currency: 'TMT' },

    // 유럽 국가
    'ISL': { code: 'IS', names: ['아이슬란드', 'Iceland'], currency: 'ISK' },
    'ROU': { code: 'RO', names: ['루마니아', 'Romania'], currency: 'RON' },
    'BGR': { code: 'BG', names: ['불가리아', 'Bulgaria'], currency: 'BGN' },
    'HRV': { code: 'HR', names: ['크로아티아', 'Croatia'], currency: 'HRK' },
    'SRB': { code: 'RS', names: ['세르비아', 'Serbia'], currency: 'RSD' },
    'UKR': { code: 'UA', names: ['우크라이나', 'Ukraine'], currency: 'UAH' },
    'BLR': { code: 'BY', names: ['벨라루스', 'Belarus'], currency: 'BYN' },

    // 아메리카 국가
    'ARG': { code: 'AR', names: ['아르헨티나', 'Argentina'], currency: 'ARS' },
    'CHL': { code: 'CL', names: ['칠레', 'Chile'], currency: 'CLP' },
    'COL': { code: 'CO', names: ['콜롬비아', 'Colombia'], currency: 'COP' },
    'PER': { code: 'PE', names: ['페루', 'Peru'], currency: 'PEN' },
    'URY': { code: 'UY', names: ['우루과이', 'Uruguay'], currency: 'UYU' },
    'BOL': { code: 'BO', names: ['볼리비아', 'Bolivia'], currency: 'BOB' },
    'PRY': { code: 'PY', names: ['파라과이', 'Paraguay'], currency: 'PYG' },
    'VEN': { code: 'VE', names: ['베네수엘라', 'Venezuela'], currency: 'VES' },

    // 아프리카/중동 국가
    'EGY': { code: 'EG', names: ['이집트', 'Egypt'], currency: 'EGP' },
    'MAR': { code: 'MA', names: ['모로코', 'Morocco'], currency: 'MAD' },
    'TUN': { code: 'TN', names: ['튀니지', 'Tunisia'], currency: 'TND' },
    'NGA': { code: 'NG', names: ['나이지리아', 'Nigeria'], currency: 'NGN' },
    'KEN': { code: 'KE', names: ['케냐', 'Kenya'], currency: 'KES' },
    'UGA': { code: 'UG', names: ['우간다', 'Uganda'], currency: 'UGX' },
    'TZA': { code: 'TZ', names: ['탄자니아', 'Tanzania'], currency: 'TZS' },

    // 기타 주요 국가
    'CZE': { code: 'CZ', names: ['체코', 'Czech Republic', 'Czechia'], currency: 'CZK' },
    'DNK': { code: 'DK', names: ['덴마크', 'Denmark'], currency: 'DKK' },
    'HUN': { code: 'HU', names: ['헝가리', 'Hungary'], currency: 'HUF' },
    'NOR': { code: 'NO', names: ['노르웨이', 'Norway'], currency: 'NOK' },
    'SWE': { code: 'SE', names: ['스웨덴', 'Sweden'], currency: 'SEK' },
    'THA': { code: 'TH', names: ['태국', 'Thailand'], currency: 'THB' },
    'VNM': { code: 'VN', names: ['베트남', 'Vietnam'], currency: 'VND' },
    'IND': { code: 'IN', names: ['인도', 'India'], currency: 'INR' },
    'BRA': { code: 'BR', names: ['브라질', 'Brazil'], currency: 'BRL' },
    'RUS': { code: 'RU', names: ['러시아', 'Russia'], currency: 'RUB' },
    'MEX': { code: 'MX', names: ['멕시코', 'Mexico'], currency: 'MXN' },
    'ZAF': { code: 'ZA', names: ['남아프리카 공화국', 'South Africa'], currency: 'ZAR' },
    'TUR': { code: 'TR', names: ['터키', 'Turkey'], currency: 'TRY' }
  };

  // 2자리 코드로 ISO3 찾기 (역방향 매핑)
  const codeToISO3 = {};
  Object.entries(countryMapping).forEach(([iso3, data]) => {
    codeToISO3[data.code] = iso3;
  });

  // world-atlas 숫자 ID 매핑 (일반적인 매핑)
  const worldAtlasIdMapping = {
    '840': 'USA', // 미국
    '392': 'JPN', // 일본
    '826': 'GBR', // 영국
    '156': 'CHN', // 중국
    '036': 'AUS', // 호주
    '124': 'CAN', // 캐나다
    '756': 'CHE', // 스위스
    '344': 'HKG', // 홍콩
    '702': 'SGP', // 싱가포르
    '410': 'KOR', // 한국
    '158': 'TWN', // 대만
    '458': 'MYS', // 말레이시아
    '608': 'PHL', // 필리핀
    '360': 'IDN', // 인도네시아
    '554': 'NZL', // 뉴질랜드
    '376': 'ISR', // 이스라엘
    '784': 'ARE', // 아랍에미리트
    '634': 'QAT', // 카타르
    '414': 'KWT', // 쿠웨이트
    '048': 'BHR', // 바레인
    '512': 'OMN', // 오만
    '400': 'JOR', // 요르단
    '422': 'LBN', // 레바논
    '586': 'PAK', // 파키스탄
    '050': 'BGD', // 방글라데시
    '144': 'LKA', // 스리랑카
    '524': 'NPL', // 네팔
    '004': 'AFG', // 아프가니스탄
    '398': 'KAZ', // 카자흐스탄
    '860': 'UZB', // 우즈베키스탄
    '417': 'KGZ', // 키르기스스탄
    '762': 'TJK', // 타지키스탄
    '795': 'TKM', // 투르크메니스탄
    '352': 'ISL', // 아이슬란드
    '642': 'ROU', // 루마니아
    '100': 'BGR', // 불가리아
    '191': 'HRV', // 크로아티아
    '688': 'SRB', // 세르비아
    '804': 'UKR', // 우크라이나
    '112': 'BLR', // 벨라루스
    '032': 'ARG', // 아르헨티나
    '152': 'CHL', // 칠레
    '170': 'COL', // 콜롬비아
    '604': 'PER', // 페루
    '858': 'URY', // 우루과이
    '068': 'BOL', // 볼리비아
    '600': 'PRY', // 파라과이
    '862': 'VEN', // 베네수엘라
    '818': 'EGY', // 이집트
    '504': 'MAR', // 모로코
    '788': 'TUN', // 튀니지
    '566': 'NGA', // 나이지리아
    '404': 'KEN', // 케냐
    '800': 'UGA', // 우간다
    '834': 'TZA', // 탄자니아
    '203': 'CZE', // 체코
    '208': 'DNK', // 덴마크
    '348': 'HUN', // 헝가리
    '578': 'NOR', // 노르웨이
    '752': 'SWE', // 스웨덴
    '764': 'THA', // 태국
    '704': 'VNM', // 베트남
    '356': 'IND', // 인도
    '076': 'BRA', // 브라질
    '643': 'RUS', // 러시아
    '484': 'MEX', // 멕시코
    '710': 'ZAF', // 남아프리카 공화국
    '792': 'TUR', // 터키
  };

  // ISO3 코드로 국가 코드 찾기
  const findCountryCodeByISO3 = (iso3) => {
    return countryMapping[iso3]?.code;
  };

  // 국가명으로 ISO3 찾기
  const findISO3ByName = (name) => {
    return Object.keys(countryMapping).find(iso3 =>
      countryMapping[iso3].names.some(n =>
        n.toLowerCase().includes(name.toLowerCase()) ||
        name.toLowerCase().includes(n.toLowerCase())
      )
    );
  };

  // 지도 데이터에서 국가 코드로 요소 찾기 (world-atlas ID 사용)
  const findCountryElementByCode = (countryCode, svg) => {
    // 1. ISO3 코드로 world-atlas ID 찾기
    const iso3 = codeToISO3[countryCode];
    if (iso3) {
      // world-atlas ID 매핑에서 찾기
      const worldAtlasId = Object.keys(worldAtlasIdMapping).find(id => 
        worldAtlasIdMapping[id] === iso3
      );
      
      if (worldAtlasId) {
        const element = svg.selectAll('.country').filter(function(d) {
          return d.id === worldAtlasId;
        });
        if (element.size() > 0) {
          return element;
        }
      }
    }

    // 2. 국가명으로 찾기 (정확한 매칭)
    const countryInfo = Object.values(countryMapping).find(info => info.code === countryCode);
    if (countryInfo) {
      const element = svg.selectAll('.country').filter(function(d) {
        const name = d.properties?.NAME || '';
        if (!name) return false; // 이름이 없으면 제외
        
        // 정확한 매칭만 허용 (부분 매칭 제외)
        const found = countryInfo.names.some(n => {
          const nameLower = name.toLowerCase();
          const nLower = n.toLowerCase();
          
          // 정확히 일치하거나, 완전한 단어로 포함되는 경우만
          return nameLower === nLower || 
                 nameLower.includes(' ' + nLower + ' ') ||
                 nameLower.startsWith(nLower + ' ') ||
                 nameLower.endsWith(' ' + nLower);
        });
        
        return found;
      });
      if (element.size() > 0) {
        return element;
      }
    }

    // 3. ISO_A3 속성으로 찾기
    if (iso3) {
      const element = svg.selectAll('.country').filter(function(d) {
        const isoA3 = d.properties?.ISO_A3 || d.properties?.iso_a3;
        return isoA3 === iso3;
      });
      if (element.size() > 0) {
        return element;
      }
    }
    
    // 4. 빈 선택 반환
    return svg.selectAll('.country').filter(() => false);
  };

  // 국가가 클릭 가능한지 확인
  const isCountryClickable = (iso3) => {
    return !!countryMapping[iso3];
  };

  // CDN 실패 시 fallback 데이터 생성
  const createFallbackWorldData = () => {
    console.log('로컬 fallback 세계지도 데이터 생성 중...');

    // 주요 국가들의 간단한 지리 데이터 (대략적인 위치)
    const fallbackCountries = Object.entries(countryMapping).map(([iso3, info]) => ({
      type: "Feature",
      id: iso3,
      properties: {
        NAME: info.names[1] || info.names[0],
        ISO_A3: iso3
      },
      geometry: getSimpleGeometry(iso3, info.code)
    }));

    return {
      type: "Topology",
      objects: {
        countries: {
          type: "GeometryCollection",
          geometries: fallbackCountries.map(f => ({
            type: f.geometry.type,
            coordinates: f.geometry.coordinates,
            properties: f.properties,
            id: f.id
          }))
        }
      }
    };
  };

  // 간단한 국가 지오메트리 생성 (대략적인 위치)
  const getSimpleGeometry = (iso3, code) => {
    // 각 국가별 대략적인 중심점과 크기
    const countryCoords = {
      'USA': [[-125, 49], [-66, 49], [-66, 25], [-125, 25], [-125, 49]],
      'CAN': [[-140, 70], [-60, 70], [-60, 49], [-140, 49], [-140, 70]],
      'MEX': [[-118, 32], [-86, 32], [-86, 14], [-118, 14], [-118, 32]],
      'BRA': [[-74, 5], [-35, 5], [-35, -34], [-74, -34], [-74, 5]],
      'ARG': [[-73, -22], [-54, -22], [-54, -55], [-73, -55], [-73, -22]],
      'GBR': [[-8, 61], [2, 61], [2, 50], [-8, 50], [-8, 61]],
      'FRA': [[-5, 51], [8, 51], [8, 42], [-5, 42], [-5, 51]],
      'DEU': [[6, 55], [15, 55], [15, 47], [6, 47], [6, 55]],
      'ESP': [[-10, 44], [4, 44], [4, 36], [-10, 36], [-10, 44]],
      'ITA': [[6, 47], [19, 47], [19, 36], [6, 36], [6, 47]],
      'RUS': [[20, 82], [180, 82], [180, 42], [20, 42], [20, 82]],
      'CHN': [[73, 54], [135, 54], [135, 18], [73, 18], [73, 54]],
      'JPN': [[129, 46], [146, 46], [146, 30], [129, 30], [129, 46]],
      'KOR': [[124, 39], [131, 39], [131, 33], [124, 33], [124, 39]],
      'IND': [[68, 37], [97, 37], [97, 6], [68, 6], [68, 37]],
      'AUS': [[113, -10], [154, -10], [154, -44], [113, -44], [113, -10]],
      'ZAF': [[16, -22], [33, -22], [33, -35], [16, -35], [16, -22]],
      'TUR': [[26, 42], [45, 42], [45, 36], [26, 36], [26, 42]],
      'THA': [[97, 21], [106, 21], [106, 5], [97, 5], [97, 21]],
      'VNM': [[102, 24], [110, 24], [110, 8], [102, 8], [102, 24]],
      'SGP': [[103.6, 1.5], [104, 1.5], [104, 1.2], [103.6, 1.2], [103.6, 1.5]]
    };

    const coords = countryCoords[iso3];
    if (coords) {
      return {
        type: "Polygon",
        coordinates: [coords]
      };
    }

    // 기본 사각형 (경도, 위도 기준)
    const defaultSize = 5;
    const centerLat = Math.random() * 140 - 70; // -70 to 70
    const centerLon = Math.random() * 320 - 160; // -160 to 160

    return {
      type: "Polygon",
      coordinates: [[
        [centerLon - defaultSize, centerLat + defaultSize],
        [centerLon + defaultSize, centerLat + defaultSize],
        [centerLon + defaultSize, centerLat - defaultSize],
        [centerLon - defaultSize, centerLat - defaultSize],
        [centerLon - defaultSize, centerLat + defaultSize]
      ]]
    };
  };

  useEffect(() => {
    const loadWorldMap = async () => {
      try {
        setIsLoading(true);

        // 여러 CDN 소스로 TopoJSON 세계지도 데이터 로드 시도
        const cdnSources = [
          'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json',
          'https://unpkg.com/world-atlas@2/countries-110m.json',
          'https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson'
        ];

        let world = null;
        let lastError = null;

        for (const url of cdnSources) {
          try {
            if (url.includes('world.geojson')) {
              // GeoJSON 형식인 경우
              world = await d3.json(url);
              // GeoJSON을 TopoJSON 형식으로 변환
              world = {
                type: "Topology",
                objects: {
                  countries: {
                    type: "GeometryCollection",
                    geometries: world.features.map(f => ({
                      type: f.geometry.type,
                      coordinates: f.geometry.coordinates,
                      properties: f.properties,
                      id: f.properties.ISO_A3 || f.properties.ADM0_A3 || f.properties.iso_a3
                    }))
                  }
                }
              };
            } else {
              world = await d3.json(url);
            }
            console.log(`성공적으로 로드: ${url}`);
            break;
          } catch (error) {
            console.warn(`${url} 로드 실패:`, error);
            lastError = error;
            continue;
          }
        }

        if (!world) {
          console.warn('모든 CDN 소스 실패, 로컬 fallback 사용');
          // 로컬 fallback 데이터 사용
          world = createFallbackWorldData();
        }

        const svg = d3.select(svgRef.current);
        svg.selectAll("*").remove();

        const width = 1000;
        const height = 500;

        // Natural Earth 투영법 설정
        const projection = d3.geoNaturalEarth1()
          .scale(150)
          .translate([width / 2, height / 2]);

        const path = d3.geoPath().projection(projection);


        // 국가 데이터 추출
        let countries;
        if (world.type === "FeatureCollection") {
          // 이미 GeoJSON 형식인 경우
          countries = world;
        } else {
          // TopoJSON 형식인 경우
          countries = feature(world, world.objects.countries);
        }
        setWorldData(countries);


        // 국가들 그리기
        svg.selectAll('.country')
          .data(countries.features)
          .enter()
          .append('path')
          .attr('class', d => {
            const iso3 = d.id;
            const isClickable = isCountryClickable(iso3);
            return `country ${isClickable ? 'country-clickable' : 'country-unclickable'}`;
          })
          .attr('d', path)
          .style('fill', d => {
            const iso3 = d.id;
            const countryCode = findCountryCodeByISO3(iso3);
            if (selectedCountries.includes(countryCode)) {
              return '#ffd700';
            }
            return isCountryClickable(iso3) ? '#2a2a2a' : '#1a1a1a';
          })
          .style('stroke', d => {
            const iso3 = d.id;
            const countryCode = findCountryCodeByISO3(iso3);
            if (selectedCountries.includes(countryCode)) {
              return '#ffed4e';
            }
            return isCountryClickable(iso3) ? '#ffd700' : '#666666';
          })
          .style('stroke-width', d => {
            const iso3 = d.id;
            const countryCode = findCountryCodeByISO3(iso3);
            if (selectedCountries.includes(countryCode)) {
              return '2px';
            }
            return isCountryClickable(iso3) ? '1px' : '0.5px';
          })
          .on('click', function(event, d) {
            const iso3 = d.id;
            const countryCode = findCountryCodeByISO3(iso3);
            if (countryCode && onCountrySelect) {
              onCountrySelect(countryCode);
            }
          })
          .on('mouseover', function(event, d) {
            const iso3 = d.id;
            const isClickable = isCountryClickable(iso3);

            // 호버 시 금색 깜빡임 효과 (클릭 가능한 국가만)
            if (isClickable) {
              const element = d3.select(this);

              // 깜빡임 애니메이션 시작
              const blink = () => {
                element
                  .transition()
                  .duration(400)
                  .style('fill', '#ffd700')
                  .style('stroke', '#ffd700')
                  .style('stroke-width', '2px')
                  .transition()
                  .duration(400)
                  .style('fill', '#ffed4e')
                  .style('stroke', '#ffed4e')
                  .on('end', function() {
                    if (element.classed('hovering')) {
                      blink();
                    }
                  });
              };

              element.classed('hovering', true);
              blink();
            }
          })
          .on('mouseout', function(event, d) {
            const iso3 = d.id;
            const countryCode = findCountryCodeByISO3(iso3);
            const isClickable = isCountryClickable(iso3);
            const element = d3.select(this);

            // 호버 상태 제거
            element.classed('hovering', false);

            // 애니메이션 정지하고 원래 스타일로 복원
            element.interrupt();

            if (selectedCountries.includes(countryCode)) {
              // 선택된 국가 스타일
              element
                .style('fill', '#ffd700')
                .style('stroke', '#ffed4e')
                .style('stroke-width', '2px');
            } else if (isClickable) {
              // 클릭 가능한 국가 기본 스타일
              element
                .style('fill', '#2a2a2a')
                .style('stroke', '#ffd700')
                .style('stroke-width', '1px');
            } else {
              // 클릭 불가능한 국가 스타일
              element
                .style('fill', '#1a1a1a')
                .style('stroke', '#666666')
                .style('stroke-width', '0.5px');
            }
          })
          .append('title')
          .text(d => {
            const iso3 = d.id;
            const mapping = countryMapping[iso3];
            return mapping ? `${mapping.names[0]} (${mapping.currency})` : (d.properties.NAME || 'Unknown');
          });


        setIsLoading(false);

      } catch (err) {
        console.error('Error loading world map:', err);
        setError('세계지도를 로드하는 중 오류가 발생했습니다.');
        setIsLoading(false);
      }
    };

    loadWorldMap();
  }, []);

  // 선택된 국가들 업데이트
  useEffect(() => {
    if (!worldData) return;

    const svg = d3.select(svgRef.current);

    svg.selectAll('.country')
      .classed('highlighted', false)
      .style('fill', function(d) {
        const iso3 = d.id;
        const countryCode = findCountryCodeByISO3(iso3);
        if (selectedCountries.includes(countryCode)) {
          return '#ffd700';
        }
        return isCountryClickable(iso3) ? '#2a2a2a' : '#1a1a1a';
      })
      .style('stroke', function(d) {
        const iso3 = d.id;
        const countryCode = findCountryCodeByISO3(iso3);
        if (selectedCountries.includes(countryCode)) {
          return '#ffed4e';
        }
        return isCountryClickable(iso3) ? '#ffd700' : '#666666';
      })
      .style('stroke-width', function(d) {
        const iso3 = d.id;
        const countryCode = findCountryCodeByISO3(iso3);
        if (selectedCountries.includes(countryCode)) {
          return '2px';
        }
        return isCountryClickable(iso3) ? '1px' : '0.5px';
      });

    // 선택된 국가들에 하이라이트 클래스 추가 및 깜빡임 효과
    selectedCountries.forEach(countryCode => {
      // 개선된 방법으로 지도 요소 찾기
      const countryElement = findCountryElementByCode(countryCode, svg);

      if (countryElement.size() > 0) {
        countryElement.classed('highlighted', true);
        
        // 깜빡임 효과 (3번 반복) - 금색
        const blinkSequence = () => {
          countryElement
            .transition()
            .duration(400)
            .style('fill', '#ffed4e')
            .style('stroke', '#ffd700')
            .style('stroke-width', '3px')
            .transition()
            .duration(400)
            .style('fill', '#ffd700')
            .style('stroke', '#ffed4e')
            .style('stroke-width', '2px')
            .transition()
            .duration(400)
            .style('fill', '#ffed4e')
            .style('stroke', '#ffd700')
            .style('stroke-width', '3px')
            .transition()
            .duration(400)
            .style('fill', '#ffd700')
            .style('stroke', '#ffed4e')
            .style('stroke-width', '2px')
            .transition()
            .duration(400)
            .style('fill', '#ffed4e')
            .style('stroke', '#ffd700')
            .style('stroke-width', '3px')
            .transition()
            .duration(400)
            .style('fill', '#ffd700')
            .style('stroke', '#ffed4e')
            .style('stroke-width', '2px')
              .on('end', () => {
                // 깜빡임 완료
              });
        };
        
        // 0.5초 후 깜빡임 시작
        setTimeout(blinkSequence, 500);
      }
    });
  }, [selectedCountries, worldData]);


  if (error) {
    return (
      <MapContainer>
        <MapTitle>🌍 세계지도에서 국가를 선택하세요</MapTitle>
        <LoadingMessage style={{ color: '#ff4444' }}>
          {error}
        </LoadingMessage>
      </MapContainer>
    );
  }

  return (
    <MapContainer>
      <MapTitle>🌍 세계지도에서 나라의 위치를 확인하세요 ({Object.keys(countryMapping).length}개국 지원)</MapTitle>

      {isLoading && (
        <LoadingMessage>
          🌍 실제 세계지도 로딩 중...
        </LoadingMessage>
      )}

      <SVGContainer>
        <svg ref={svgRef} width="100%" height="100%" viewBox="0 0 1000 500" />
      </SVGContainer>

    </MapContainer>
  );
};

export default WorldMap;