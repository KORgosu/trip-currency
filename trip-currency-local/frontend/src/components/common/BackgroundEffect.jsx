import React from 'react';
import styled, { keyframes } from 'styled-components';

// 유기적인 빛줄기 애니메이션
const flowingLight = keyframes`
  0% {
    transform: translateY(-100%) translateX(-50%) scaleY(0.3) rotate(0deg);
    opacity: 0;
  }
  15% {
    opacity: 0.9;
    transform: translateY(-70%) translateX(-45%) scaleY(0.8) rotate(2deg);
  }
  30% {
    transform: translateY(-40%) translateX(-55%) scaleY(1.2) rotate(-1deg);
  }
  50% {
    transform: translateY(0%) translateX(-50%) scaleY(1) rotate(1deg);
  }
  70% {
    transform: translateY(40%) translateX(-45%) scaleY(0.9) rotate(-2deg);
  }
  85% {
    opacity: 0.9;
    transform: translateY(70%) translateX(-55%) scaleY(0.6) rotate(1deg);
  }
  100% {
    transform: translateY(100vh) translateX(-50%) scaleY(0.2) rotate(0deg);
    opacity: 0;
  }
`;

// 파티클 퍼지는 애니메이션 (다양한 방향)
const particleFloat = keyframes`
  0% {
    transform: translateY(100vh) translateX(0) scale(0.3) rotate(0deg);
    opacity: 0;
  }
  15% {
    opacity: 0.8;
    transform: translateY(85vh) translateX(15px) scale(0.6) rotate(30deg);
  }
  30% {
    transform: translateY(70vh) translateX(-25px) scale(0.9) rotate(60deg);
  }
  50% {
    transform: translateY(50vh) translateX(40px) scale(1.1) rotate(120deg);
  }
  70% {
    transform: translateY(30vh) translateX(-30px) scale(1.3) rotate(200deg);
  }
  85% {
    opacity: 0.8;
    transform: translateY(15vh) translateX(20px) scale(1.1) rotate(280deg);
  }
  100% {
    transform: translateY(0vh) translateX(0) scale(0.8) rotate(360deg);
    opacity: 0;
  }
`;

// 파티클 퍼지는 애니메이션 (반대 방향)
const particleFloatReverse = keyframes`
  0% {
    transform: translateY(100vh) translateX(0) scale(0.4) rotate(0deg);
    opacity: 0;
  }
  20% {
    opacity: 0.7;
    transform: translateY(80vh) translateX(-20px) scale(0.7) rotate(-45deg);
  }
  40% {
    transform: translateY(60vh) translateX(35px) scale(1) rotate(-90deg);
  }
  60% {
    transform: translateY(40vh) translateX(-40px) scale(1.2) rotate(-150deg);
  }
  80% {
    transform: translateY(20vh) translateX(25px) scale(1.4) rotate(-220deg);
  }
  95% {
    opacity: 0.7;
    transform: translateY(5vh) translateX(-15px) scale(1.2) rotate(-300deg);
  }
  100% {
    transform: translateY(-5vh) translateX(0) scale(0.9) rotate(-360deg);
    opacity: 0;
  }
`;

// 파티클 퍼지는 애니메이션 (대각선)
const particleFloatDiagonal = keyframes`
  0% {
    transform: translateY(100vh) translateX(0) scale(0.2) rotate(0deg);
    opacity: 0;
  }
  25% {
    opacity: 0.9;
    transform: translateY(75vh) translateX(50px) scale(0.8) rotate(90deg);
  }
  50% {
    transform: translateY(50vh) translateX(-60px) scale(1.3) rotate(180deg);
  }
  75% {
    transform: translateY(25vh) translateX(70px) scale(1.5) rotate(270deg);
  }
  100% {
    transform: translateY(0vh) translateX(0) scale(1) rotate(360deg);
    opacity: 0;
  }
`;

// 메인 컨테이너
const BackgroundContainer = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: -30;
  pointer-events: none;
  overflow: hidden;
  background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 50%, #0f0f0f 100%);
`;


// 파티클 (작은 빛 점들)
const Particle = styled.div`
  position: absolute;
  top: 0;
  left: ${props => props.$left}%;
  width: 7px;
  height: 7px;
  background: radial-gradient(circle, rgba(255, 215, 0, 1) 0%, transparent 70%);
  border-radius: 50%;
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.9);
  animation: ${particleFloat} ${props => props.$duration}s ease-in-out infinite;
  animation-delay: ${props => props.$delay}s;
`;

// 파티클 (반대 방향)
const ParticleReverse = styled.div`
  position: absolute;
  top: 0;
  left: ${props => props.$left}%;
  width: 7px;
  height: 7px;
  background: radial-gradient(circle, rgba(255, 215, 0, 0.8) 0%, transparent 70%);
  border-radius: 50%;
  box-shadow: 0 0 18px rgba(255, 215, 0, 0.7);
  animation: ${particleFloatReverse} ${props => props.$duration}s ease-in-out infinite;
  animation-delay: ${props => props.$delay}s;
`;

// 파티클 (대각선)
const ParticleDiagonal = styled.div`
  position: absolute;
  top: 0;
  left: ${props => props.$left}%;
  width: 7px;
  height: 7px;
  background: radial-gradient(circle, rgba(255, 215, 0, 1) 0%, transparent 60%);
  border-radius: 50%;
  box-shadow: 0 0 25px rgba(255, 215, 0, 1);
  animation: ${particleFloatDiagonal} ${props => props.$duration}s ease-in-out infinite;
  animation-delay: ${props => props.$delay}s;
`;

// 작은 파티클
const SmallParticle = styled.div`
  position: absolute;
  top: 0;
  left: ${props => props.$left}%;
  width: 7px;
  height: 7px;
  background: radial-gradient(circle, rgba(255, 215, 0, 0.6) 0%, transparent 80%);
  border-radius: 50%;
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.6);
  animation: ${particleFloat} ${props => props.$duration}s ease-in-out infinite;
  animation-delay: ${props => props.$delay}s;
`;


const BackgroundEffect = () => {
  return (
    <BackgroundContainer>
      {/* 메인 파티클들 (정방향) - 30개 */}
      <Particle $left={2} $duration={25} $delay={0} />
      <Particle $left={5} $duration={30} $delay={3} />
      <Particle $left={8} $duration={28} $delay={6} />
      <Particle $left={12} $duration={32} $delay={1} />
      <Particle $left={15} $duration={26} $delay={8} />
      <Particle $left={18} $duration={29} $delay={4} />
      <Particle $left={22} $duration={27} $delay={11} />
      <Particle $left={25} $duration={31} $delay={2} />
      <Particle $left={28} $duration={24} $delay={9} />
      <Particle $left={32} $duration={33} $delay={5} />
      <Particle $left={35} $duration={25} $delay={12} />
      <Particle $left={38} $duration={30} $delay={7} />
      <Particle $left={42} $duration={28} $delay={14} />
      <Particle $left={45} $duration={32} $delay={3} />
      <Particle $left={48} $duration={26} $delay={10} />
      <Particle $left={52} $duration={29} $delay={6} />
      <Particle $left={55} $duration={27} $delay={13} />
      <Particle $left={58} $duration={31} $delay={1} />
      <Particle $left={62} $duration={24} $delay={8} />
      <Particle $left={65} $duration={33} $delay={4} />
      <Particle $left={68} $duration={25} $delay={11} />
      <Particle $left={72} $duration={30} $delay={7} />
      <Particle $left={75} $duration={28} $delay={14} />
      <Particle $left={78} $duration={32} $delay={2} />
      <Particle $left={82} $duration={26} $delay={9} />
      <Particle $left={85} $duration={29} $delay={5} />
      <Particle $left={88} $duration={27} $delay={12} />
      <Particle $left={92} $duration={31} $delay={3} />
      <Particle $left={95} $duration={24} $delay={10} />
      <Particle $left={98} $duration={33} $delay={6} />
      
      {/* 반대 방향 파티클들 - 30개 */}
      <ParticleReverse $left={1} $duration={22} $delay={1} />
      <ParticleReverse $left={4} $duration={27} $delay={4} />
      <ParticleReverse $left={7} $duration={25} $delay={7} />
      <ParticleReverse $left={11} $duration={29} $delay={2} />
      <ParticleReverse $left={14} $duration={26} $delay={9} />
      <ParticleReverse $left={17} $duration={31} $delay={5} />
      <ParticleReverse $left={21} $duration={24} $delay={12} />
      <ParticleReverse $left={24} $duration={28} $delay={8} />
      <ParticleReverse $left={27} $duration={32} $delay={3} />
      <ParticleReverse $left={31} $duration={25} $delay={10} />
      <ParticleReverse $left={34} $duration={30} $delay={6} />
      <ParticleReverse $left={37} $duration={27} $delay={13} />
      <ParticleReverse $left={41} $duration={29} $delay={1} />
      <ParticleReverse $left={44} $duration={26} $delay={8} />
      <ParticleReverse $left={47} $duration={31} $delay={4} />
      <ParticleReverse $left={51} $duration={24} $delay={11} />
      <ParticleReverse $left={54} $duration={28} $delay={7} />
      <ParticleReverse $left={57} $duration={32} $delay={2} />
      <ParticleReverse $left={61} $duration={25} $delay={9} />
      <ParticleReverse $left={64} $duration={30} $delay={5} />
      <ParticleReverse $left={67} $duration={27} $delay={12} />
      <ParticleReverse $left={71} $duration={29} $delay={3} />
      <ParticleReverse $left={74} $duration={26} $delay={10} />
      <ParticleReverse $left={77} $duration={31} $delay={6} />
      <ParticleReverse $left={81} $duration={24} $delay={13} />
      <ParticleReverse $left={84} $duration={28} $delay={8} />
      <ParticleReverse $left={87} $duration={32} $delay={1} />
      <ParticleReverse $left={91} $duration={25} $delay={9} />
      <ParticleReverse $left={94} $duration={30} $delay={4} />
      <ParticleReverse $left={97} $duration={27} $delay={11} />
      
      {/* 대각선 파티클들 - 30개 */}
      <ParticleDiagonal $left={3} $duration={35} $delay={2} />
      <ParticleDiagonal $left={6} $duration={28} $delay={5} />
      <ParticleDiagonal $left={9} $duration={32} $delay={8} />
      <ParticleDiagonal $left={13} $duration={26} $delay={3} />
      <ParticleDiagonal $left={16} $duration={30} $delay={10} />
      <ParticleDiagonal $left={19} $duration={27} $delay={6} />
      <ParticleDiagonal $left={23} $duration={29} $delay={13} />
      <ParticleDiagonal $left={26} $duration={25} $delay={1} />
      <ParticleDiagonal $left={29} $duration={33} $delay={8} />
      <ParticleDiagonal $left={33} $duration={24} $delay={4} />
      <ParticleDiagonal $left={36} $duration={31} $delay={11} />
      <ParticleDiagonal $left={39} $duration={28} $delay={7} />
      <ParticleDiagonal $left={43} $duration={30} $delay={14} />
      <ParticleDiagonal $left={46} $duration={26} $delay={2} />
      <ParticleDiagonal $left={49} $duration={32} $delay={9} />
      <ParticleDiagonal $left={53} $duration={25} $delay={5} />
      <ParticleDiagonal $left={56} $duration={29} $delay={12} />
      <ParticleDiagonal $left={59} $duration={27} $delay={8} />
      <ParticleDiagonal $left={63} $duration={31} $delay={3} />
      <ParticleDiagonal $left={66} $duration={24} $delay={10} />
      <ParticleDiagonal $left={69} $duration={30} $delay={6} />
      <ParticleDiagonal $left={73} $duration={28} $delay={13} />
      <ParticleDiagonal $left={76} $duration={32} $delay={1} />
      <ParticleDiagonal $left={79} $duration={25} $delay={8} />
      <ParticleDiagonal $left={83} $duration={29} $delay={4} />
      <ParticleDiagonal $left={86} $duration={27} $delay={11} />
      <ParticleDiagonal $left={89} $duration={31} $delay={7} />
      <ParticleDiagonal $left={93} $duration={24} $delay={14} />
      <ParticleDiagonal $left={96} $duration={30} $delay={2} />
      <ParticleDiagonal $left={99} $duration={28} $delay={9} />
      
      {/* 작은 파티클들 - 50개 */}
      <SmallParticle $left={0.5} $duration={20} $delay={0} />
      <SmallParticle $left={1.5} $duration={23} $delay={2} />
      <SmallParticle $left={2.5} $duration={21} $delay={4} />
      <SmallParticle $left={3.5} $duration={25} $delay={6} />
      <SmallParticle $left={4.5} $duration={19} $delay={8} />
      <SmallParticle $left={5.5} $duration={24} $delay={10} />
      <SmallParticle $left={6.5} $duration={22} $delay={12} />
      <SmallParticle $left={7.5} $duration={26} $delay={14} />
      <SmallParticle $left={8.5} $duration={20} $delay={16} />
      <SmallParticle $left={9.5} $duration={23} $delay={18} />
      <SmallParticle $left={10.5} $duration={21} $delay={1} />
      <SmallParticle $left={11.5} $duration={25} $delay={3} />
      <SmallParticle $left={12.5} $duration={19} $delay={5} />
      <SmallParticle $left={13.5} $duration={24} $delay={7} />
      <SmallParticle $left={14.5} $duration={22} $delay={9} />
      <SmallParticle $left={15.5} $duration={26} $delay={11} />
      <SmallParticle $left={16.5} $duration={20} $delay={13} />
      <SmallParticle $left={17.5} $duration={23} $delay={15} />
      <SmallParticle $left={18.5} $duration={21} $delay={17} />
      <SmallParticle $left={19.5} $duration={25} $delay={19} />
      <SmallParticle $left={20.5} $duration={19} $delay={2} />
      <SmallParticle $left={21.5} $duration={24} $delay={4} />
      <SmallParticle $left={22.5} $duration={22} $delay={6} />
      <SmallParticle $left={23.5} $duration={26} $delay={8} />
      <SmallParticle $left={24.5} $duration={20} $delay={10} />
      <SmallParticle $left={25.5} $duration={23} $delay={12} />
      <SmallParticle $left={26.5} $duration={21} $delay={14} />
      <SmallParticle $left={27.5} $duration={25} $delay={16} />
      <SmallParticle $left={28.5} $duration={19} $delay={18} />
      <SmallParticle $left={29.5} $duration={24} $delay={1} />
      <SmallParticle $left={30.5} $duration={22} $delay={3} />
      <SmallParticle $left={31.5} $duration={26} $delay={5} />
      <SmallParticle $left={32.5} $duration={20} $delay={7} />
      <SmallParticle $left={33.5} $duration={23} $delay={9} />
      <SmallParticle $left={34.5} $duration={21} $delay={11} />
      <SmallParticle $left={35.5} $duration={25} $delay={13} />
      <SmallParticle $left={36.5} $duration={19} $delay={15} />
      <SmallParticle $left={37.5} $duration={24} $delay={17} />
      <SmallParticle $left={38.5} $duration={22} $delay={19} />
      <SmallParticle $left={39.5} $duration={26} $delay={2} />
      <SmallParticle $left={40.5} $duration={20} $delay={4} />
      <SmallParticle $left={41.5} $duration={23} $delay={6} />
      <SmallParticle $left={42.5} $duration={21} $delay={8} />
      <SmallParticle $left={43.5} $duration={25} $delay={10} />
      <SmallParticle $left={44.5} $duration={19} $delay={12} />
      <SmallParticle $left={45.5} $duration={24} $delay={14} />
      <SmallParticle $left={46.5} $duration={22} $delay={16} />
      <SmallParticle $left={47.5} $duration={26} $delay={18} />
      <SmallParticle $left={48.5} $duration={20} $delay={1} />
      <SmallParticle $left={49.5} $duration={23} $delay={3} />
    </BackgroundContainer>
  );
};

export default BackgroundEffect;
