import { useState, useEffect, useCallback } from 'react';
import apiService from '../services/api';

const useRankingData = () => {
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchRankings = useCallback(async (period = 'daily', limit = 10, offset = 0) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiService.getRankings(period, limit, offset);
      
      if (response.success) {
        setRankings(response.data.rankings || []);
        setLastUpdated(new Date().toISOString());
      }
    } catch (err) {
      console.error('랭킹 데이터 로드 실패:', err);
      setError(err.message || '랭킹 데이터를 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  const recordSelection = useCallback(async (countryCode) => {
    try {
      await apiService.recordCountryClick(countryCode);
      
      // 선택 기록 후 랭킹 새로고침
      fetchRankings('daily', 10, 0);
    } catch (err) {
      console.warn('선택 기록 실패:', err);
      // 선택 기록 실패는 사용자에게 노출하지 않음 (비치명적)
    }
  }, [fetchRankings]);

  // 1분마다 자동 새로고침
  useEffect(() => {
    const interval = setInterval(() => {
      fetchRankings('daily', 10, 0);
    }, 60000); // 1분 = 60,000ms

    return () => clearInterval(interval);
  }, [fetchRankings]);

  return {
    rankings,
    loading,
    error,
    lastUpdated,
    fetchRankings,
    recordSelection
  };
};

export default useRankingData;
