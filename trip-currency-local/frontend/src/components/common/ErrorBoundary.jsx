import React from 'react';
import styled from 'styled-components';

const ErrorContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: #ffebee;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  margin: 1rem 0;
`;

const ErrorIcon = styled.div`
  font-size: 3rem;
  margin-bottom: 1rem;
`;

const ErrorTitle = styled.h3`
  color: #c62828;
  margin: 0 0 0.5rem 0;
  font-size: 1.2rem;
`;

const ErrorMessage = styled.p`
  color: #d32f2f;
  margin: 0 0 1rem 0;
  text-align: center;
  line-height: 1.5;
`;

const RetryButton = styled.button`
  background: #c62828;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background-color 0.3s;
  
  &:hover {
    background: #b71c1c;
  }
`;

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
    
    // 에러 로깅 (실제 환경에서는 에러 리포팅 서비스 사용)
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <ErrorContainer>
          <ErrorIcon>⚠️</ErrorIcon>
          <ErrorTitle>문제가 발생했습니다</ErrorTitle>
          <ErrorMessage>
            예상치 못한 오류가 발생했습니다. 페이지를 새로고침하거나 다시 시도해주세요.
          </ErrorMessage>
          <RetryButton onClick={this.handleRetry}>
            다시 시도
          </RetryButton>
        </ErrorContainer>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

