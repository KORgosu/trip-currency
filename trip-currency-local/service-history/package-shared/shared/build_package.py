#!/usr/bin/env python3
"""
Trip Currency Shared Package 빌드 스크립트
v1.0.0

이 스크립트는 패키지를 빌드하고 배포하는 데 사용됩니다.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """명령어 실행 및 결과 확인"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} 완료")
        if result.stdout:
            print(f"출력: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} 실패")
        print(f"에러: {e.stderr}")
        return False

def clean_build_dirs():
    """빌드 디렉토리 정리"""
    print("🧹 빌드 디렉토리 정리...")
    dirs_to_clean = ['build', 'dist', '*.egg-info']
    
    for pattern in dirs_to_clean:
        for path in Path('.').glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  삭제됨: {path}")
    
    print("✅ 빌드 디렉토리 정리 완료")

def check_requirements():
    """필수 도구 설치 확인"""
    print("🔍 필수 도구 확인...")
    
    required_tools = ['python', 'pip', 'setuptools', 'wheel', 'twine']
    
    for tool in required_tools:
        try:
            subprocess.run([tool, '--version'], check=True, capture_output=True)
            print(f"  ✅ {tool} 설치됨")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"  ❌ {tool} 설치 필요")
            if tool in ['setuptools', 'wheel', 'twine']:
                print(f"    설치 명령어: pip install {tool}")
            return False
    
    return True

def build_package():
    """패키지 빌드"""
    print("📦 패키지 빌드 시작...")
    
    # 빌드 디렉토리 정리
    clean_build_dirs()
    
    # wheel과 source distribution 빌드
    if not run_command("python -m build", "패키지 빌드"):
        return False
    
    # 빌드 결과 확인
    dist_dir = Path('dist')
    if dist_dir.exists():
        files = list(dist_dir.glob('*'))
        print(f"📁 빌드된 파일들:")
        for file in files:
            print(f"  - {file.name} ({file.stat().st_size / 1024:.1f} KB)")
    
    return True

def check_package():
    """빌드된 패키지 검사"""
    print("🔍 패키지 검사...")
    
    # wheel 파일 검사
    if not run_command("python -m twine check dist/*", "패키지 검사"):
        return False
    
    return True

def install_package_locally():
    """로컬에 패키지 설치 (테스트용)"""
    print("🧪 로컬 패키지 설치 (테스트용)...")
    
    # 기존 패키지 제거
    run_command("pip uninstall trip-currency-shared -y", "기존 패키지 제거")
    
    # 새 패키지 설치
    if not run_command("pip install dist/*.whl", "새 패키지 설치"):
        return False
    
    # 설치 확인
    try:
        import shared
        print(f"✅ 패키지 설치 확인: {shared.__version__}")
        return True
    except ImportError as e:
        print(f"❌ 패키지 설치 실패: {e}")
        return False

def main():
    """메인 함수"""
    print("🚀 Trip Currency Shared Package v1.0.0 빌드 시작")
    print("=" * 60)
    
    # 현재 디렉토리가 package-shared인지 확인
    if not Path('setup.py').exists():
        print("❌ setup.py 파일을 찾을 수 없습니다.")
        print("   package-shared 디렉토리에서 실행해주세요.")
        sys.exit(1)
    
    # 1. 필수 도구 확인
    if not check_requirements():
        print("❌ 필수 도구가 설치되지 않았습니다.")
        sys.exit(1)
    
    # 2. 패키지 빌드
    if not build_package():
        print("❌ 패키지 빌드에 실패했습니다.")
        sys.exit(1)
    
    # 3. 패키지 검사
    if not check_package():
        print("❌ 패키지 검사에 실패했습니다.")
        sys.exit(1)
    
    # 4. 로컬 설치 테스트
    if not install_package_locally():
        print("❌ 로컬 설치 테스트에 실패했습니다.")
        sys.exit(1)
    
    print("=" * 60)
    print("🎉 패키지 빌드 및 테스트 완료!")
    print("📦 빌드된 파일들:")
    
    dist_dir = Path('dist')
    if dist_dir.exists():
        for file in dist_dir.glob('*'):
            print(f"   - {file.name}")
    
    print("\n📋 다음 단계:")
    print("   1. GitHub에 코드 푸시")
    print("   2. Git 태그 생성: git tag v1.0.0")
    print("   3. PyPI에 업로드: python -m twine upload dist/*")
    print("   4. 또는 GitHub Packages 사용")

if __name__ == "__main__":
    main()
