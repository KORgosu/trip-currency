import { useState, useEffect } from 'react';

const useGeolocation = () => {
  const [location, setLocation] = useState({
    country: '한국',
    loading: false,
    error: null
  });

  // 좌표를 국가명으로 변환하는 함수
  const getCountryFromCoordinates = async (latitude, longitude) => {
    try {
      // Reverse Geocoding API 사용 (예: OpenStreetMap Nominatim)
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&accept-language=ko`
      );
      
      if (!response.ok) {
        throw new Error('위치 정보를 가져올 수 없습니다.');
      }
      
      const data = await response.json();
      
      // 국가명 추출
      const country = data.address?.country || '알 수 없는 위치';
      return country;
    } catch (error) {
      console.error('위치 변환 오류:', error);
      return '위치를 확인할 수 없습니다';
    }
  };

  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      setLocation(prev => ({
        ...prev,
        error: '이 브라우저는 위치 서비스를 지원하지 않습니다.'
      }));
      return;
    }

    setLocation(prev => ({ ...prev, loading: true, error: null }));

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        
        try {
          const country = await getCountryFromCoordinates(latitude, longitude);
          setLocation({
            country,
            loading: false,
            error: null
          });
        } catch (error) {
          setLocation({
            country: '한국',
            loading: false,
            error: error.message
          });
        }
      },
      (error) => {
        let errorMessage = '위치를 가져올 수 없습니다.';
        
        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = '위치 접근이 거부되었습니다.';
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage = '위치 정보를 사용할 수 없습니다.';
            break;
          case error.TIMEOUT:
            errorMessage = '위치 요청이 시간 초과되었습니다.';
            break;
        }
        
        setLocation({
          country: '한국',
          loading: false,
          error: errorMessage
        });
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000 // 5분
      }
    );
  };

  // 컴포넌트 마운트 시 자동으로 위치 가져오기
  useEffect(() => {
    getCurrentLocation();
  }, []);

  return {
    country: location.country,
    loading: location.loading,
    error: location.error,
    refreshLocation: getCurrentLocation
  };
};

export default useGeolocation;
