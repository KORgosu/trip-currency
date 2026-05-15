import { useState, useEffect, useCallback } from 'react';
import apiService from '../services/api';

// 환율 데이터를 관리하는 커스텀 훅
const useCurrencyData = () => {
  const [exchangeRates, setExchangeRates] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 환율 데이터 가져오기
  const fetchExchangeRates = useCallback(async (symbols = 'USD,JPY,EUR,GBP,CNY,AUD,CAD,CHF,SGD,HKD', base = 'KRW') => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.getExchangeRates(symbols, base);
      setExchangeRates(response.data);
      return response.data;
    } catch (err) {
      const errorMessage = err.message || '환율 데이터를 가져오는데 실패했습니다.';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // 전체 데이터 가져오기 (환율만)
  const fetchAllData = useCallback(async (symbols = 'USD,JPY,EUR,GBP,CNY,AUD,CAD,CHF,SGD,HKD', base = 'KRW') => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.getExchangeRates(symbols, base);
      setExchangeRates(response.data);
      
      return {
        exchangeRates: response.data
      };
    } catch (err) {
      const errorMessage = err.message || '데이터를 가져오는데 실패했습니다.';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // 헬스 체크
  const checkHealth = useCallback(async () => {
    try {
      const response = await apiService.healthCheck();
      return response.data;
    } catch (err) {
      console.error('헬스 체크 실패:', err);
      throw err;
    }
  }, []);

  // 데이터 초기화
  const clearData = useCallback(() => {
    setExchangeRates(null);
    setError(null);
  }, []);

  return {
    // 상태
    exchangeRates,
    loading,
    error,
    
    // 액션
    fetchExchangeRates,
    fetchAllData,
    checkHealth,
    clearData
  };
};

export default useCurrencyData;

