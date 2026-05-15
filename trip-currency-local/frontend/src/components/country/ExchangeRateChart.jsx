import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import apiService from '../../services/api';

// Chart.js 등록
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const ChartContainer = styled.div`
  width: 100%;
  min-height: 400px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  background-color: #2a2a2a;
  border-radius: 8px;
  position: relative;
`;

const ChartTitle = styled.h3`
  color: #ffd700;
  margin-bottom: 1rem;
  text-align: center;
  position: relative;
`;

const RealtimeIndicator = styled.span`
  display: inline-block;
  width: 8px;
  height: 8px;
  background-color: #28a745;
  border-radius: 50%;
  margin-left: 8px;
  animation: pulse 2s infinite;
  
  @keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
  }
`;


const ChartWrapper = styled.div`
  width: 100%;
  height: 250px;
  position: relative;
  margin-bottom: 1rem;
`;

const LoadingContainer = styled.div`
  width: 100%;
  height: 250px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: #f8f9fa;
  border-radius: 8px;
  color: #666;
  font-size: 1rem;
`;

const LoadingSpinner = styled.div`
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const LoadingMessage = styled.div`
  font-size: 0.9rem;
  color: #666;
  text-align: center;
  line-height: 1.4;
`;

const ErrorContainer = styled.div`
  width: 100%;
  height: 250px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #ffe6e6;
  border-radius: 8px;
  color: #d63031;
  font-size: 1rem;
`;

const DataInsufficientContainer = styled.div`
  width: 100%;
  height: 250px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: #fff3cd;
  border-radius: 8px;
  color: #856404;
  font-size: 1rem;
  border: 2px dashed #ffc107;
`;

const DataInsufficientIcon = styled.div`
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.7;
`;

const DataInsufficientMessage = styled.div`
  font-size: 1.2rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
`;

const DataInsufficientSubMessage = styled.div`
  font-size: 0.9rem;
  opacity: 0.8;
  text-align: center;
  line-height: 1.4;
`;

const StatsContainer = styled.div`
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
  margin-top: 0.5rem;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 8px;
  position: relative;
  z-index: 1;
`;

const StatItem = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  padding: 0.75rem;
  background-color: white;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
`;

const StatLabel = styled.div`
  font-size: 0.8rem;
  color: #666;
  font-weight: 500;
  margin-bottom: 0.25rem;
  text-align: center;
`;

const StatValue = styled.div`
  font-size: 1rem;
  font-weight: bold;
  color: #2c3e50;
  text-align: center;
`;

const ExchangeRateChart = ({ currencyCode = 'USD', timeRange = 'realtime' }) => {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [dataInsufficient, setDataInsufficient] = useState(false);

  useEffect(() => {
    fetchChartData();
  }, [timeRange, currencyCode]);

  // 하루 데이터의 경우 5분마다 자동 새로고침 (data-ingestor와 동기화)
  useEffect(() => {
    let interval;
    
    // 데이터가 부족한 경우 더 자주 새로고침 (1분마다)
    if (dataInsufficient) {
      interval = setInterval(() => {
        fetchChartData();
      }, 60000); // 1분마다 새로고침
    } else {
      interval = setInterval(() => {
        fetchChartData();
      }, 300000); // 5분마다 새로고침
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [currencyCode, dataInsufficient]);

  const validateChartData = (data) => {
    // API 응답 구조에 맞게 수정 - data는 이미 response.data
    const results = data.results;
    
    if (!data || !results || !Array.isArray(results)) {
      console.log('데이터 구조 검증 실패:', { data, results });
      return false;
    }
    
    // 유효한 데이터 포인트 검사
    const validData = results.filter(item => 
      item && 
      typeof item.rate === 'number' && 
      item.rate > 0 && 
      item.date &&
      !isNaN(new Date(item.date).getTime())
    );
    
    console.log('유효한 데이터 개수:', validData.length, '전체 데이터 개수:', results.length);
    return validData.length > 0;
  };

  const fetchChartData = async () => {
    setLoading(true);
    setError(null);
    setDataInsufficient(false);
    
    try {
      const response = await apiService.getExchangeRateHistory(
        '1d', // 하루 데이터 요청
        currencyCode, 
        'KRW', 
        'hourly' // 5분 단위 데이터를 위해 hourly로 요청
      );
      
      if (response.success) {
        const data = response.data;
        
        // 디버깅을 위한 로그 추가
        console.log('API 응답 데이터:', data);
        console.log('데이터 포인트 수:', data.data_points);
        console.log('결과 배열:', data.results);
        
        // 데이터 유효성 검사 강화
        if (!validateChartData(data)) {
          console.log('데이터 검증 실패');
          setDataInsufficient(true);
          setLoading(false);
          return;
        }
        
        // API 응답 구조에 맞게 수정
        const results = data.results || (data.data && data.data.results);
        
        // 실제 데이터가 있는 시간 범위를 찾아서 차트 생성
        if (results.length === 0) {
          setDataInsufficient(true);
          setLoading(false);
          return;
        }
        
        // 데이터를 시간순으로 정렬
        const sortedResults = results.sort((a, b) => new Date(a.date) - new Date(b.date));
        
        // 첫 번째 데이터와 마지막 데이터의 시간을 기준으로 차트 생성
        const firstDataTime = new Date(sortedResults[0].date);
        const lastDataTime = new Date(sortedResults[sortedResults.length - 1].date);
        
        // 데이터 간격 계산 (분 단위)
        const timeDiffMinutes = (lastDataTime.getTime() - firstDataTime.getTime()) / (1000 * 60);
        const intervalMinutes = Math.max(5, Math.floor(timeDiffMinutes / (results.length - 1))); // 최소 5분 간격
        
        const chartLabels = [];
        const chartData = [];
        const chartPoints = [];
        
        // 실제 데이터를 기반으로 차트 포인트 생성
        sortedResults.forEach((item, index) => {
          const itemTime = new Date(item.date);
          const timeLabel = itemTime.toLocaleTimeString('ko-KR', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false
          });
          
          chartLabels.push(timeLabel);
          chartData.push(item.rate);
          chartPoints.push({
            x: index,
            y: item.rate,
            showPoint: true
          });
        });
        
        // 유효한 데이터가 충분하지 않은 경우 (최소 1개 데이터 필요)
        const validRates = chartData.filter(rate => rate !== null && rate > 0);
        if (validRates.length < 1) { // 최소 1개 데이터 필요
          setDataInsufficient(true);
          setLoading(false);
          return;
        }
        
        // 데이터 품질 검사 (이상치 제거)
        const sortedRates = [...validRates].sort((a, b) => a - b);
        const q1 = sortedRates[Math.floor(sortedRates.length * 0.25)];
        const q3 = sortedRates[Math.floor(sortedRates.length * 0.75)];
        const iqr = q3 - q1;
        const lowerBound = q1 - 1.5 * iqr;
        const upperBound = q3 + 1.5 * iqr;
        
        // 이상치가 너무 많은 경우 데이터 부족으로 처리
        const outliers = validRates.filter(rate => rate < lowerBound || rate > upperBound);
        if (outliers.length > validRates.length * 0.3) { // 30% 이상이 이상치인 경우
          setDataInsufficient(true);
          setLoading(false);
          return;
        }
        
        setChartData({
          labels: chartLabels,
          datasets: [{
            label: `${currencyCode}/KRW`,
            data: chartData,
            borderColor: '#ffd700',
            backgroundColor: 'rgba(255, 215, 0, 0.1)',
            borderWidth: 2,
            pointBackgroundColor: '#ffd700',
            pointBorderColor: '#ffd700',
            pointRadius: chartPoints.map(point => point.showPoint ? 3 : 0),
            pointHoverRadius: chartPoints.map(point => point.showPoint ? 5 : 0),
            tension: 0.4,
            fill: true,
            spanGaps: false // null 값이 있는 부분은 선을 연결하지 않음
          }]
        });
        
        // 통계 데이터 설정 (실제 데이터만으로 계산)
        if (validRates.length > 0) {
          const avg = validRates.reduce((sum, rate) => sum + rate, 0) / validRates.length;
          const min = Math.min(...validRates);
          const max = Math.max(...validRates);
          const volatility = Math.sqrt(validRates.reduce((sum, rate) => sum + Math.pow(rate - avg, 2), 0) / validRates.length);
          
          setStatistics({
            average: avg,
            min: min,
            max: max,
            volatility: volatility,
            trend: validRates[validRates.length - 1] > validRates[0] ? 'upward' : 
                   validRates[validRates.length - 1] < validRates[0] ? 'downward' : 'stable',
            data_points: validRates.length
          });
        }
      } else {
        setDataInsufficient(true);
      }
    } catch (error) {
      console.error('차트 데이터 로드 실패:', error);
      setError('차트 데이터를 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: '#2a2a2a',
        titleColor: '#ffd700',
        bodyColor: '#ffd700',
        borderColor: '#ffd700',
        borderWidth: 1,
        callbacks: {
          label: function(context) {
            return `${currencyCode}/KRW: ${context.parsed.y.toLocaleString()}원`;
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        grid: {
          color: '#ffd700',
          opacity: 0.3
        },
        ticks: {
          color: '#ffd700'
        },
        title: {
          display: true,
          text: timeRange === 'realtime' || timeRange === '1d' ? '시간' : '날짜',
          color: '#ffd700'
        }
      },
      y: {
        display: true,
        grid: {
          color: '#ffd700',
          opacity: 0.3
        },
        ticks: {
          color: '#ffd700',
          callback: function(value) {
            return value.toLocaleString() + '원';
          }
        },
        title: {
          display: true,
          text: '환율 (원)',
          color: '#ffd700'
        },
        beginAtZero: false
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    }
  };

  const getChartTitle = () => {
    return `${currencyCode}/KRW 하루 환율 차트 (5분 단위)`;
  };

  return (
    <ChartContainer>
      <ChartTitle>
        {getChartTitle()}
        <RealtimeIndicator />
      </ChartTitle>

      <ChartWrapper>
        {loading ? (
          <LoadingContainer>
            <LoadingSpinner />
            <LoadingMessage>
              📊 {currencyCode} 차트 데이터를 불러오는 중...<br />
              <span style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                잠시만 기다려주세요
              </span>
            </LoadingMessage>
          </LoadingContainer>
        ) : error ? (
          <ErrorContainer>
            <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>❌</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>
              오류가 발생했습니다
            </div>
            <div style={{ fontSize: '0.9rem', opacity: 0.8 }}>
              {error}
            </div>
          </ErrorContainer>
        ) : dataInsufficient ? (
          <DataInsufficientContainer>
            <DataInsufficientIcon>📉</DataInsufficientIcon>
            <DataInsufficientMessage>데이터 부족!</DataInsufficientMessage>
            <DataInsufficientSubMessage>
              {currencyCode} 통화의 충분한 환율 데이터가 없습니다.<br />
              잠시 후 다시 시도해주세요.
            </DataInsufficientSubMessage>
          </DataInsufficientContainer>
        ) : chartData ? (
          <Line data={chartData} options={chartOptions} />
        ) : (
          <LoadingContainer>
            <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>📊</div>
            <LoadingMessage>
              차트 데이터가 없습니다.<br />
              <span style={{ fontSize: '0.8rem', opacity: 0.7 }}>
                데이터를 불러오는 중이거나 서비스에 문제가 있을 수 있습니다
              </span>
            </LoadingMessage>
          </LoadingContainer>
        )}
      </ChartWrapper>

      {statistics && (
        <StatsContainer>
          <StatItem>
            <StatLabel>평균</StatLabel>
            <StatValue>{statistics.average.toLocaleString()}원</StatValue>
          </StatItem>
          <StatItem>
            <StatLabel>최고</StatLabel>
            <StatValue>{statistics.max.toLocaleString()}원</StatValue>
          </StatItem>
          <StatItem>
            <StatLabel>최저</StatLabel>
            <StatValue>{statistics.min.toLocaleString()}원</StatValue>
          </StatItem>
          <StatItem>
            <StatLabel>변동성</StatLabel>
            <StatValue>{statistics.volatility.toFixed(2)}</StatValue>
          </StatItem>
          <StatItem>
            <StatLabel>트렌드</StatLabel>
            <StatValue>
              {statistics.trend === 'upward' ? '📈 상승' : 
               statistics.trend === 'downward' ? '📉 하락' : '➡️ 보합'}
            </StatValue>
          </StatItem>
        </StatsContainer>
      )}
    </ChartContainer>
  );
};

export default ExchangeRateChart;
