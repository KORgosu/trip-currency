import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import styled from 'styled-components';
import Header from './components/common/Header';
import Footer from './components/common/Footer';
import HomePage from './pages/HomePage';
import ComparisonPage from './pages/ComparisonPage';
import './styles/globals.css';

const AppContainer = styled.div`
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 50%, #0f0f0f 100%);
  background-attachment: fixed;
  width: 100vw;
  overflow-x: hidden;
  padding: 0 1rem;
  
  @media (max-width: 768px) {
    padding: 0 0.5rem;
  }
`;

const MainContent = styled.main`
  flex: 1;
  padding: 0;
`;

function App() {
  return (
    <Router>
      <AppContainer>
        <Header />
        <MainContent>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/comparison" element={<ComparisonPage />} />
          </Routes>
        </MainContent>
        <Footer />
      </AppContainer>
    </Router>
  );
}

export default App;
