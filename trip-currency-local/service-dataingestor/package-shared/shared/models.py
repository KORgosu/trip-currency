"""
Data Models
Pydantic 모델 정의
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class CurrencyCode(str, Enum):
    """통화 코드"""
    # 주요 통화
    USD = "USD"
    JPY = "JPY"
    EUR = "EUR"
    CNY = "CNY"
    GBP = "GBP"
    AUD = "AUD"
    CAD = "CAD"
    CHF = "CHF"
    SGD = "SGD"
    HKD = "HKD"
    THB = "THB"
    VND = "VND"
    INR = "INR"
    BRL = "BRL"
    RUB = "RUB"
    MXN = "MXN"
    ZAR = "ZAR"
    TRY = "TRY"
    PLN = "PLN"
    CZK = "CZK"
    HUF = "HUF"
    NOK = "NOK"
    SEK = "SEK"
    DKK = "DKK"
    KRW = "KRW"
    # 추가 아시아 통화
    TWD = "TWD"
    MYR = "MYR"
    PHP = "PHP"
    IDR = "IDR"
    NZD = "NZD"
    ILS = "ILS"
    AED = "AED"
    QAR = "QAR"
    KWD = "KWD"
    BHD = "BHD"
    OMR = "OMR"
    JOD = "JOD"
    LBP = "LBP"
    PKR = "PKR"
    BDT = "BDT"
    LKR = "LKR"
    NPR = "NPR"
    AFN = "AFN"
    KZT = "KZT"
    UZS = "UZS"
    KGS = "KGS"
    TJS = "TJS"
    TMT = "TMT"
    # 추가 유럽 통화
    ISK = "ISK"
    RON = "RON"
    BGN = "BGN"
    HRK = "HRK"
    RSD = "RSD"
    UAH = "UAH"
    BYN = "BYN"
    # 추가 아메리카 통화
    ARS = "ARS"
    CLP = "CLP"
    COP = "COP"
    PEN = "PEN"
    UYU = "UYU"
    BOB = "BOB"
    PYG = "PYG"
    VES = "VES"
    # 추가 아프리카/중동 통화
    EGP = "EGP"
    MAD = "MAD"
    TND = "TND"
    NGN = "NGN"
    KES = "KES"
    UGX = "UGX"
    TZS = "TZS"


class CountryCode(str, Enum):
    """국가 코드"""
    # 주요 국가
    US = "US"
    JP = "JP"
    EU = "EU"
    CN = "CN"
    GB = "GB"
    AU = "AU"
    CA = "CA"
    CH = "CH"
    SG = "SG"
    HK = "HK"
    TH = "TH"
    VN = "VN"
    IN = "IN"
    BR = "BR"
    RU = "RU"
    MX = "MX"
    ZA = "ZA"
    TR = "TR"
    PL = "PL"
    CZ = "CZ"
    HU = "HU"
    NO = "NO"
    SE = "SE"
    DK = "DK"
    KR = "KR"
    # 추가 아시아 국가
    TW = "TW"
    MY = "MY"
    PH = "PH"
    ID = "ID"
    NZ = "NZ"
    IL = "IL"
    AE = "AE"
    QA = "QA"
    KW = "KW"
    BH = "BH"
    OM = "OM"
    JO = "JO"
    LB = "LB"
    PK = "PK"
    BD = "BD"
    LK = "LK"
    NP = "NP"
    AF = "AF"
    KZ = "KZ"
    UZ = "UZ"
    KG = "KG"
    TJ = "TJ"
    TM = "TM"
    # 추가 유럽 국가
    IS = "IS"
    RO = "RO"
    BG = "BG"
    HR = "HR"
    RS = "RS"
    UA = "UA"
    BY = "BY"
    # 추가 아메리카 국가
    AR = "AR"
    CL = "CL"
    CO = "CO"
    PE = "PE"
    UY = "UY"
    BO = "BO"
    PY = "PY"
    VE = "VE"
    # 추가 아프리카/중동 국가
    EG = "EG"
    MA = "MA"
    TN = "TN"
    NG = "NG"
    KE = "KE"
    UG = "UG"
    TZ = "TZ"


class ExchangeRate(BaseModel):
    """환율 정보"""
    currency_code: CurrencyCode
    currency_name: str
    deal_base_rate: Decimal
    tts: Optional[Decimal] = None
    ttb: Optional[Decimal] = None
    source: str
    recorded_at: datetime
    updated_at: datetime


class CurrencyInfo(BaseModel):
    """통화 정보"""
    code: CurrencyCode
    name: str
    rate: Decimal
    change: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None


class LatestRatesResponse(BaseModel):
    """최신 환율 응답"""
    data: List[CurrencyInfo]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True


class UserSelection(BaseModel):
    """사용자 선택"""
    user_id: str
    country_code: CountryCode
    session_id: Optional[str] = None
    referrer: Optional[str] = None


class SelectionRecord(BaseModel):
    """선택 기록"""
    record_id: str = Field(..., description="기록 ID")
    user_id: str = Field(..., description="사용자 ID")
    country_code: str = Field(..., description="국가 코드")
    country_name: Optional[str] = Field(None, description="국가명")
    timestamp: datetime = Field(..., description="선택 시간")
    session_id: Optional[str] = Field(None, description="세션 ID")
    ip_address: Optional[str] = Field(None, description="IP 주소")
    user_agent: Optional[str] = Field(None, description="User Agent")
    referrer: Optional[str] = Field(None, description="리퍼러")


class RankingItem(BaseModel):
    """랭킹 항목"""
    country: str
    clicks: int
    rank: int


class RankingResponse(BaseModel):
    """랭킹 응답"""
    data: Dict[str, Any]
    success: bool = True


class HistoryDataPoint(BaseModel):
    """히스토리 데이터 포인트"""
    timestamp: datetime
    rate: Decimal
    change: Optional[Decimal] = None


class HistoryStatistics(BaseModel):
    """히스토리 통계"""
    min_rate: Decimal
    max_rate: Decimal
    avg_rate: Decimal
    volatility: Decimal


class HistoryResponse(BaseModel):
    """히스토리 응답"""
    currency_code: CurrencyCode
    data_points: List[HistoryDataPoint]
    statistics: HistoryStatistics
    success: bool = True




class CountryStats(BaseModel):
    """국가 통계"""
    country: str
    clicks: int
    rank: int
    change: Optional[int] = None


class RankingPeriod(str, Enum):
    """랭킹 기간"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class HistoryPeriod(str, Enum):
    """히스토리 기간"""
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    SIX_MONTHS = "6m"


class SuccessResponse(BaseModel):
    """성공 응답"""
    data: Any
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CollectionResult(BaseModel):
    """데이터 수집 결과"""
    source: str
    success: bool
    raw_data: Optional[List[Any]] = None
    error_message: Optional[str] = None
    collection_time: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0


class RawExchangeRateData(BaseModel):
    """원시 환율 데이터"""
    currency_code: str
    rate: float
    timestamp: datetime
    source: str = "exchangerate_api"
    metadata: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """에러 응답"""
    error: Dict[str, Any]
    success: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "v1"
