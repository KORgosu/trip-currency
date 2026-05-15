// API 서비스 레이어
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1/currencies';
const RANKING_API_BASE_URL = import.meta.env.VITE_RANKING_API_BASE_URL || '/api/v1/rankings';
const HISTORY_API_BASE_URL = import.meta.env.VITE_HISTORY_API_BASE_URL || '/api/v1/history';

class ApiService {
  constructor() {
    this.baseURL = API_BASE_URL;
    this.rankingBaseURL = RANKING_API_BASE_URL;
    this.historyBaseURL = HISTORY_API_BASE_URL;
  }

  // 기본 HTTP 요청 메서드
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        'X-Correlation-ID': this.generateCorrelationId(),
      },
    };

    const config = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error?.message || 'API 요청 실패');
      }
      
      return data;
    } catch (error) {
      console.error('API 요청 실패:', error);
      
      // 마이크로서비스가 실행되지 않을 때 Mock 데이터 반환
      if (error.message.includes('Failed to fetch') || error.message.includes('ERR_CONNECTION_REFUSED')) {
        console.warn('마이크로서비스가 실행되지 않음. Mock 데이터를 사용합니다.');
        return this.getMockData(endpoint);
      }
      
      throw error;
    }
  }

  // 랭킹 서비스 전용 요청 메서드
  async rankingRequest(endpoint, options = {}) {
    const url = `${this.rankingBaseURL}${endpoint}`;
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        'X-Correlation-ID': this.generateCorrelationId(),
      },
    };

    const config = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error?.message || '랭킹 API 요청 실패');
      }
      
      return data;
    } catch (error) {
      console.error('랭킹 API 요청 실패:', error);
      
      // 랭킹 서비스가 실행되지 않을 때 Mock 데이터 반환
      if (error.message.includes('Failed to fetch') || error.message.includes('ERR_CONNECTION_REFUSED')) {
        console.warn('랭킹 서비스가 실행되지 않음. Mock 데이터를 사용합니다.');
        return this.getRankingMockData(endpoint);
      }
      
      throw error;
    }
  }

  // History Service 전용 요청 메서드
  async historyRequest(endpoint, options = {}) {
    const url = `${this.historyBaseURL}${endpoint}`;
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        'X-Correlation-ID': this.generateCorrelationId(),
      },
    };

    const config = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error?.message || 'History API 요청 실패');
      }
      
      // 데이터 유효성 및 품질 검사
      if (data.data) {
        if (!this.validateExchangeRateData(data.data)) {
          console.warn('History API에서 받은 데이터가 유효하지 않음:', data.data);
          return {
            success: false,
            error: { message: '데이터 부족' },
            data: null
          };
        }
        
        if (!this.validateExchangeRateQuality(data.data)) {
          console.warn('History API에서 받은 데이터 품질이 낮음:', data.data);
          return {
            success: false,
            error: { message: '데이터 품질 부족' },
            data: null
          };
        }
      }
      
      return data;
    } catch (error) {
      console.error('History API 요청 실패:', error);
      
      // History 서비스가 실행되지 않을 때 Mock 데이터 반환
      if (error.message.includes('Failed to fetch') || error.message.includes('ERR_CONNECTION_REFUSED')) {
        console.warn('History 서비스가 실행되지 않음. Mock 데이터를 사용합니다.');
        return this.getHistoryMockData(endpoint);
      }
      
      throw error;
    }
  }

  // 상관관계 ID 생성
  generateCorrelationId() {
    return Math.random().toString(36).substring(2, 15) + 
           Math.random().toString(36).substring(2, 15);
  }

  // Mock 데이터 반환 (마이크로서비스가 실행되지 않을 때)
  getMockData(endpoint) {
    if (endpoint.includes('/currencies/latest')) {
      return {
        success: true,
        data: {
          base: 'KRW',
          rates: {
            'USD': 1350.50,
            'JPY': 9.25,
            'EUR': 1480.75,
            'GBP': 1720.30,
            'CNY': 190.45
          },
          timestamp: new Date().toISOString(),
          cache_hit: false
        }
      };
    }
    
    
    if (endpoint.includes('/health')) {
      return {
        success: true,
        data: {
          status: 'healthy',
          service: 'currency-service-mock',
          version: '1.0.0-mock'
        }
      };
    }
    
    // 기본 Mock 응답
    return {
      success: true,
      data: { message: 'Mock data - 서비스가 실행되지 않음' }
    };
  }

  // 랭킹 서비스 Mock 데이터 반환
  getRankingMockData(endpoint) {
    if (endpoint.includes('/rankings')) {
      return {
        success: true,
        data: {
          period: 'daily',
          total_selections: 1250,
          last_updated: new Date().toISOString(),
          ranking: [
            { country_code: 'JP', country_name: '일본', selection_count: 245, rank: 1 },
            { country_code: 'US', country_name: '미국', selection_count: 198, rank: 2 },
            { country_code: 'TH', country_name: '태국', selection_count: 156, rank: 3 },
            { country_code: 'VN', country_name: '베트남', selection_count: 134, rank: 4 },
            { country_code: 'SG', country_name: '싱가포르', selection_count: 98, rank: 5 },
            { country_code: 'CN', country_name: '중국', selection_count: 87, rank: 6 },
            { country_code: 'GB', country_name: '영국', selection_count: 76, rank: 7 },
            { country_code: 'AU', country_name: '호주', selection_count: 65, rank: 8 },
            { country_code: 'CA', country_name: '캐나다', selection_count: 54, rank: 9 },
            { country_code: 'DE', country_name: '독일', selection_count: 43, rank: 10 }
          ]
        }
      };
    }
    
    // 기본 랭킹 Mock 응답
    return {
      success: true,
      data: { message: 'Mock ranking data - 랭킹 서비스가 실행되지 않음' }
    };
  }

  // History Service Mock 데이터 반환
  getHistoryMockData(endpoint) {
    if (endpoint.includes('/api/v1/history')) {
      // URL에서 파라미터 추출
      const url = new URL(endpoint, this.historyBaseURL);
      const target = url.searchParams.get('target') || 'USD';
      const period = url.searchParams.get('period') || '1w';
      
      // Mock 환율 이력 데이터 생성
      const mockData = this.generateMockHistoryData(target, period);
      
      return {
        success: true,
        data: mockData
      };
    }
    
    if (endpoint.includes('/api/v1/history/stats')) {
      return {
        success: true,
        data: {
          base: 'KRW',
          target: 'USD',
          period: '6m',
          statistics: {
            average: 1350.25,
            min: 1280.50,
            max: 1420.75,
            volatility: 45.30,
            trend: 'upward',
            data_points: 180
          }
        }
      };
    }
    
    // 기본 History Mock 응답
    return {
      success: true,
      data: { message: 'Mock history data - History 서비스가 실행되지 않음' }
    };
  }

  // 데이터 유효성 검사 함수 (강화된 버전)
  validateExchangeRateData(data) {
    // API 응답 구조에 맞게 수정
    const results = data.results || (data.data && data.data.results);
    
    if (!data || !results || !Array.isArray(results)) {
      return false;
    }
    
    // 유효한 데이터가 있는지 확인
    const validData = results.filter(item => 
      item && 
      typeof item.rate === 'number' && 
      item.rate > 0 && 
      item.date &&
      !isNaN(new Date(item.date).getTime()) &&
      item.rate < 1000000 // 비현실적으로 높은 환율 제외
    );
    
    return validData.length > 0;
  }

  // 환율 데이터 품질 검사
  validateExchangeRateQuality(data) {
    if (!this.validateExchangeRateData(data)) {
      return false;
    }
    
    // API 응답 구조에 맞게 수정
    const results = data.results || (data.data && data.data.results);
    const rates = results.map(item => item.rate).filter(rate => rate > 0);
    
    if (rates.length < 2) {
      return false;
    }
    
    // 이상치 검사 (IQR 방법)
    const sortedRates = [...rates].sort((a, b) => a - b);
    const q1 = sortedRates[Math.floor(sortedRates.length * 0.25)];
    const q3 = sortedRates[Math.floor(sortedRates.length * 0.75)];
    const iqr = q3 - q1;
    const lowerBound = q1 - 1.5 * iqr;
    const upperBound = q3 + 1.5 * iqr;
    
    const outliers = rates.filter(rate => rate < lowerBound || rate > upperBound);
    
    // 이상치가 30% 이상이면 품질이 낮다고 판단
    return outliers.length < rates.length * 0.3;
  }

  // Mock 환율 이력 데이터 생성
  generateMockHistoryData(currency, period) {
    const baseRates = {
      'USD': 1350.0,
      'JPY': 9.2,
      'EUR': 1450.0,
      'GBP': 1650.0,
      'CNY': 185.0
    };
    
    const baseRate = baseRates[currency] || 1000.0;
    
    let results = [];
    let currentRate = baseRate;
    
    if (period === '1d') {
      // 하루 데이터: 5분 단위로 288개 포인트 (24시간 * 12개/시간)
      const now = new Date();
      const startOfDay = new Date(now);
      startOfDay.setHours(0, 0, 0, 0);
      
      for (let i = 0; i < 288; i++) {
        const timePoint = new Date(startOfDay.getTime() + (i * 5 * 60 * 1000));
        
        // 랜덤한 변동 생성 (±0.5% 범위)
        const changePercent = (Math.random() - 0.5) * 1.0; // -0.5% ~ +0.5%
        const change = currentRate * (changePercent / 100);
        currentRate += change;
        
        // 일부 시간대는 데이터가 없도록 설정 (약 20% 확률)
        if (Math.random() > 0.2) {
          results.push({
            date: timePoint.toISOString(),
            rate: Math.round(currentRate * 100) / 100,
            change: Math.round(change * 100) / 100,
            change_percent: Math.round(changePercent * 100) / 100,
            volume: Math.floor(Math.random() * 10) + 1
          });
        }
      }
    } else if (period === 'realtime') {
      // 실시간 데이터: 최근 24시간을 정시 간격으로
      for (let i = 0; i < 24; i++) {
        const date = new Date();
        date.setHours(date.getHours() - (23 - i));
        date.setMinutes(0, 0, 0); // 정시로 설정 (분, 초, 밀리초를 0으로)
        
        // 랜덤 변동 (±1% 범위)
        const changePercent = (Math.random() - 0.5) * 2; // -1% ~ +1%
        const change = currentRate * (changePercent / 100);
        currentRate += change;
        
        results.push({
          date: date.toISOString(),
          rate: Math.round(currentRate * 100) / 100,
          change: Math.round(change * 100) / 100,
          change_percent: Math.round(changePercent * 100) / 100,
          volume: Math.floor(Math.random() * 50) + 10
        });
      }
    } else if (period === '1d') {
      // 1일 데이터: 최근 24시간을 정시 간격으로
      for (let i = 0; i < 24; i++) {
        const date = new Date();
        date.setHours(date.getHours() - (23 - i));
        date.setMinutes(0, 0, 0); // 정시로 설정 (분, 초, 밀리초를 0으로)
        
        // 랜덤 변동 (±2% 범위)
        const changePercent = (Math.random() - 0.5) * 4; // -2% ~ +2%
        const change = currentRate * (changePercent / 100);
        currentRate += change;
        
        results.push({
          date: date.toISOString(),
          rate: Math.round(currentRate * 100) / 100,
          change: Math.round(change * 100) / 100,
          change_percent: Math.round(changePercent * 100) / 100,
          volume: Math.floor(Math.random() * 50) + 10
        });
      }
    } else {
      // 기존 기간들도 지원 (하위 호환성)
      const days = period === '1w' ? 7 : period === '1m' ? 30 : period === '3m' ? 90 : 180;
      
      for (let i = 0; i < days; i++) {
        const date = new Date();
        date.setDate(date.getDate() - (days - i - 1));
        
        // 랜덤 변동 (±2% 범위)
        const changePercent = (Math.random() - 0.5) * 4; // -2% ~ +2%
        const change = currentRate * (changePercent / 100);
        currentRate += change;
        
        results.push({
          date: date.toISOString().split('T')[0],
          rate: Math.round(currentRate * 100) / 100,
          change: Math.round(change * 100) / 100,
          change_percent: Math.round(changePercent * 100) / 100,
          volume: Math.floor(Math.random() * 50) + 10
        });
      }
    }
    
    return {
      base: 'KRW',
      target: currency,
      period: period,
      interval: 'daily',
      data_points: results.length,
      results: results,
      statistics: {
        average: results.length > 0 ? Math.round((results.reduce((sum, item) => sum + item.rate, 0) / results.length) * 100) / 100 : 0,
        min: results.length > 0 ? Math.min(...results.map(item => item.rate)) : 0,
        max: results.length > 0 ? Math.max(...results.map(item => item.rate)) : 0,
        volatility: results.length > 0 ? Math.round(Math.random() * 50 + 20) : 0,
        trend: results.length > 0 ? (results[results.length - 1].rate > results[0].rate ? 'upward' : 'downward') : 'stable',
        data_points: results.length
      }
    };
  }

  // 환율 조회
  async getExchangeRates(symbols = 'USD,JPY,EUR,GBP,CNY,AUD,CAD,CHF,SGD,HKD', base = 'KRW') {
    const symbolsParam = Array.isArray(symbols) ? symbols.join(',') : symbols;
    const response = await this.request(`/latest?symbols=${symbolsParam}&base=${base}`);
    
    // 환율 데이터 유효성 검사
    if (response.success && response.data && response.data.rates) {
      const validRates = {};
      let hasValidData = false;
      
      for (const [currency, rate] of Object.entries(response.data.rates)) {
        if (typeof rate === 'number' && rate > 0) {
          validRates[currency] = rate;
          hasValidData = true;
        }
      }
      
      if (!hasValidData) {
        return {
          success: false,
          error: { message: '데이터 부족' },
          data: null
        };
      }
      
      response.data.rates = validRates;
    }
    
    return response;
  }


  // 통화 정보 조회
  async getCurrencyInfo(currencyCode) {
    return this.request(`/api/v1/currencies/${currencyCode}`);
  }

  // 헬스 체크
  async healthCheck() {
    return this.request('/health');
  }

  // 랭킹 서비스 API 메서드들
  
  // 랭킹 조회
  async getRankings(period = 'daily', limit = 10, offset = 0) {
    return this.rankingRequest(`?limit=${limit}&offset=${offset}`);
  }

  // 나라 클릭 기록
  async recordCountryClick(country) {
    return this.rankingRequest(`/click?country=${encodeURIComponent(country)}`, {
      method: 'POST'
    });
  }

  // 사용자 선택 기록 (기존 호환성 유지)
  async recordSelection(selectionData) {
    return this.rankingRequest('/selections', {
      method: 'POST',
      body: JSON.stringify(selectionData)
    });
  }

  // 국가별 통계 조회
  async getCountryStats(countryCode, period = '7d') {
    return this.rankingRequest(`/stats/${countryCode}?period=${period}`);
  }

  // 랭킹 계산 트리거 (관리자용)
  async triggerRankingCalculation(period) {
    return this.rankingRequest(`/calculate?period=${period}`, {
      method: 'POST'
    });
  }

  // History Service API 메서드들
  
  // 환율 이력 조회
  async getExchangeRateHistory(period, target, base = 'KRW', interval = 'daily') {
    return this.historyRequest(`?period=${period}&target=${target}&base=${base}&interval=${interval}`);
  }

  // 환율 통계 조회
  async getExchangeRateStats(target, period = '6m', base = 'KRW') {
    return this.historyRequest(`/stats?target=${target}&period=${period}&base=${base}`);
  }

  // 환율 비교 분석
  async compareCurrencies(targets, period = '1m', base = 'KRW') {
    const targetsParam = Array.isArray(targets) ? targets.join(',') : targets;
    return this.historyRequest(`/compare?targets=${targetsParam}&period=${period}&base=${base}`);
  }

  // 환율 예측
  async getExchangeRateForecast(currencyCode, days = 7, base = 'KRW') {
    return this.historyRequest(`/forecast/${currencyCode}?days=${days}&base=${base}`);
  }

  // History Service 헬스 체크
  async historyHealthCheck() {
    return this.historyRequest('/health');
  }
}

// 싱글톤 인스턴스 생성
const apiService = new ApiService();

export default apiService;
