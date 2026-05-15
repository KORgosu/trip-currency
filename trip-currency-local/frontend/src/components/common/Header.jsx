import React from 'react';
import styled from 'styled-components';
import { Link } from 'react-router-dom';

const HeaderContainer = styled.header`
  background: rgba(26, 26, 26, 0.3);
  border-bottom: 2px solid #ffd700;
  color: #f8f9fa;
  padding: 1.6rem 2rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3), 0 0 0 1px rgba(255, 215, 0, 0.1);
  max-width: 2448px;
  margin: 0 auto;
  border-radius: 0 0 12px 12px;
  position: relative;
  z-index: 10;
  backdrop-filter: blur(10px);
  
  @media (max-width: 2448px) {
    margin: 0 1.5rem;
  }
  
  @media (max-width: 1024px) {
    margin: 0 1rem;
  }
  
  @media (max-width: 768px) {
    margin: 0 0.5rem;
    padding: 1.2rem 1rem;
  }
  
  @media (max-width: 480px) {
    padding: 0.8rem 0.75rem;
  }
`;

const HeaderContent = styled.div`
  max-width: 2448px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 2rem;
`;

const Logo = styled(Link)`
  font-size: 2.7rem;
  font-weight: bold;
  color: #ffd700;
  text-decoration: none;
  transition: all 0.3s ease;
  padding: 0.75rem 0;
  flex: 7.09;
  width: 425%;
  min-width: 851px;

  &:hover {
    color: #ffed4e;
    text-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
  }

  @media (max-width: 768px) {
    font-size: 2.25rem;
    min-width: 709px;
    width: 425%;
  }

  @media (max-width: 480px) {
    font-size: 1.95rem;
    min-width: 567px;
    width: 425%;
  }
`;

const Nav = styled.nav`
  display: flex;
  gap: 2rem;
  
  @media (max-width: 768px) {
    gap: 1rem;
  }
  
  @media (max-width: 480px) {
    gap: 0.5rem;
  }
`;

const NavLink = styled(Link)`
  color: #f8f9fa;
  text-decoration: none;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  transition: all 0.3s ease;
  border: 1px solid transparent;
  font-size: 1.1rem;
  font-weight: 500;
  
  &:hover {
    background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
    color: #0a0a0a;
    border-color: #ffd700;
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
  }
  
  &.active {
    background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
    color: #0a0a0a;
    border-color: #ffd700;
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
  }
  
  @media (max-width: 768px) {
    padding: 0.6rem 1.2rem;
    font-size: 1rem;
  }
  
  @media (max-width: 480px) {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
  }
`;

const Header = () => {
  return (
    <HeaderContainer>
      <HeaderContent>
        <Logo to="/">
          🌍 Trip Currency
        </Logo>
        <Nav>
          <NavLink to="/">홈</NavLink>
        </Nav>
      </HeaderContent>
    </HeaderContainer>
  );
};

export default Header;
