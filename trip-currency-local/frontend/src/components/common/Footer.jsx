import React from 'react';
import styled from 'styled-components';

const FooterText = styled.p`
  margin: 0;
  font-size: 0.9rem;
  color: #ffd700;
  text-align: center;
  padding: 1rem 0;
  background: transparent;
`;

const Footer = () => {
    return (
      <FooterText>
        © 2025 Trip Currency Service. All rights reserved. | Made by Team DK
      </FooterText>
    );
};

export default Footer;
